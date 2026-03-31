from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.policy import PolicyCheckResult as PolicyCheckResultModel
from app.models.policy import PolicyEvaluation
from app.models.resource import Resource
from app.schemas.policy import PolicyCheckResult, PolicyDecision, PolicyEvaluationOut


POLICY_VERSION = "v0.1"


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _severity_from_result(result: str) -> str:
    return {"PASS": "low", "WARN": "medium", "FAIL": "high"}.get(result, "low")


def _build_check(
    evaluation_id: str,
    check_name: str,
    category: str,
    result: str,
    reason: str,
    weight: int,
    threshold: str | None = None,
    actual_value: str | None = None,
) -> dict:
    return {
        "id": new_id("pcr"),
        "evaluation_id": evaluation_id,
        "check_name": check_name,
        "category": category,
        "result": result,
        "reason": reason,
        "severity": _severity_from_result(result),
        "weight": weight,
        "threshold": threshold,
        "actual_value": actual_value,
    }


def evaluate_run_request(db: Session, user, run: dict) -> PolicyDecision:
    resource = db.get(Resource, run["resource_id"])
    if not resource:
        return PolicyDecision(
            status="blocked",
            risk_score=100,
            risk_level="high",
            reasons=["Resource not found for policy evaluation"],
            requires_approval=True,
            evaluation_id=None,
        )

    evaluation_id = new_id("peval")
    checks: list[dict] = []

    env = run["target_environment"]
    env_result = "PASS"
    env_reason = "Dev environment"
    env_weight = 5
    if env == "semi-prod":
        env_result = "WARN"
        env_reason = "Semi-prod environment requires heightened attention"
        env_weight = 20
    elif env == "prod":
        env_result = "WARN"
        env_reason = "Prod environment requires stricter controls"
        env_weight = 35
    checks.append(
        _build_check(
            evaluation_id,
            "Environment",
            "environment",
            env_result,
            env_reason,
            env_weight,
            threshold="dev<semi-prod<prod",
            actual_value=env,
        )
    )

    sensitivity = resource.data_sensitivity or "low"
    sens_result = "PASS"
    sens_reason = "Low sensitivity data"
    sens_weight = 5
    if sensitivity == "medium":
        sens_result = "WARN"
        sens_reason = "Medium sensitivity data"
        sens_weight = 15
    elif sensitivity == "high":
        sens_result = "FAIL"
        sens_reason = "High sensitivity data requires approval"
        sens_weight = 35
    checks.append(
        _build_check(
            evaluation_id,
            "Data Sensitivity",
            "security",
            sens_result,
            sens_reason,
            sens_weight,
            threshold="low/medium/high",
            actual_value=sensitivity,
        )
    )

    connector = resource.connector or ""
    egress_result = "PASS"
    egress_reason = "No high-risk external egress connector detected"
    egress_weight = 5
    if connector in {"powerbi", "tableau"}:
        egress_result = "WARN"
        egress_reason = "BI connector may call external services"
        egress_weight = 12
    if connector in {"airflow"} and env == "prod":
        egress_result = "FAIL"
        egress_reason = "Airflow in prod flagged for external side effects"
        egress_weight = 20
    checks.append(
        _build_check(
            evaluation_id,
            "External Egress",
            "security",
            egress_result,
            egress_reason,
            egress_weight,
            threshold="restricted connectors in prod",
            actual_value=connector,
        )
    )

    has_schedule = "schedule" in (resource.config or {})
    checks.append(
        _build_check(
            evaluation_id,
            "Schedule Change",
            "operational",
            "WARN" if has_schedule else "PASS",
            "Schedule present; review cadence impact" if has_schedule else "No schedule impact detected",
            10 if has_schedule else 2,
            threshold="no unexpected cadence changes",
            actual_value="configured" if has_schedule else "none",
        )
    )

    risk_score = max(0, min(sum(c["weight"] for c in checks), 100))
    risk_level = _risk_level(risk_score)

    has_fail = any(c["result"] == "FAIL" for c in checks)
    requires_approval = has_fail or risk_score >= 60
    overall_status = "blocked" if has_fail else ("pending_approval" if requires_approval else "approved")
    reasons = [c["reason"] for c in checks if c["result"] in {"WARN", "FAIL"}]

    evaluation = PolicyEvaluation(
        evaluation_id=evaluation_id,
        run_id=run["id"],
        policy_version=POLICY_VERSION,
        overall_status=overall_status,
        risk_score=risk_score,
        risk_level=risk_level,
        requires_approval=requires_approval,
        evaluated_at=now_iso(),
    )
    db.add(evaluation)
    db.add_all([PolicyCheckResultModel(**check) for check in checks])
    db.commit()

    return PolicyDecision(
        status=overall_status,
        risk_score=risk_score,
        risk_level=risk_level,
        reasons=reasons,
        requires_approval=requires_approval,
        evaluation_id=evaluation_id,
    )


def get_policy_checks_for_run(db: Session, user, run_id: str):
    evaluation = (
        db.query(PolicyEvaluation)
        .filter(PolicyEvaluation.run_id == run_id)
        .order_by(PolicyEvaluation.evaluated_at.desc())
        .first()
    )
    if not evaluation:
        return None

    checks = (
        db.query(PolicyCheckResultModel)
        .filter(PolicyCheckResultModel.evaluation_id == evaluation.evaluation_id)
        .all()
    )
    return PolicyEvaluationOut(
        evaluation_id=evaluation.evaluation_id,
        run_id=evaluation.run_id,
        policy_version=evaluation.policy_version,
        overall_status=evaluation.overall_status,
        risk_score=evaluation.risk_score,
        risk_level=evaluation.risk_level,
        requires_approval=evaluation.requires_approval,
        evaluated_at=evaluation.evaluated_at,
        checks=[
            PolicyCheckResult(
                id=item.id,
                evaluation_id=item.evaluation_id,
                check_name=item.check_name,
                category=item.category,
                result=item.result,
                reason=item.reason,
                severity=item.severity,
                weight=item.weight,
                threshold=item.threshold,
                actual_value=item.actual_value,
            )
            for item in checks
        ],
    )
