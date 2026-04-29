from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import new_id, now_iso
from app.models.job import Job
from app.models.policy import PolicyCheckResult as PolicyCheckResultModel
from app.models.policy import PolicyEvaluation
from app.schemas.policy import PolicyCheckResult, PolicyDecision, PolicyEvaluationOut
from control_center.policy.risk_engine import RiskEngine

POLICY_VERSION = "v0.1"


def evaluate_run_request(db: Session, user, run: dict) -> PolicyDecision:
    """Evaluate policy for a run request.

    Risk scoring is delegated to control_center.policy.risk_engine.RiskEngine.
    This function is responsible only for DB persistence and returning the decision.
    """
    resource = db.get(Job, run["job_id"])
    if not resource:
        return PolicyDecision(
            status="blocked",
            risk_score=100,
            risk_level="high",
            reasons=["Job not found for policy evaluation"],
            requires_approval=True,
            evaluation_id=None,
        )

    assessment = RiskEngine.evaluate(
        data_sensitivity=resource.data_sensitivity or "low",
        connector=resource.connector or "",
        target_environment=run["target_environment"],
        has_schedule="schedule" in (resource.config or {}),
    )

    evaluation_id = new_id("peval")

    evaluation = PolicyEvaluation(
        evaluation_id=evaluation_id,
        run_id=run["id"],
        policy_version=POLICY_VERSION,
        overall_status=assessment.overall_status,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        requires_approval=assessment.requires_approval,
        evaluated_at=now_iso(),
    )
    db.add(evaluation)

    db.add_all([
        PolicyCheckResultModel(
            id=new_id("pcr"),
            evaluation_id=evaluation_id,
            check_name=check.check_name,
            category=check.category,
            result=check.result,
            reason=check.reason,
            severity={"PASS": "low", "WARN": "medium", "FAIL": "high"}.get(check.result, "low"),
            weight=check.weight,
            threshold=check.threshold,
            actual_value=check.actual_value,
        )
        for check in assessment.checks
    ])
    db.commit()

    reasons = [c.reason for c in assessment.checks if c.result in {"WARN", "FAIL"}]
    return PolicyDecision(
        status=assessment.overall_status,
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        reasons=reasons,
        requires_approval=assessment.requires_approval,
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
