from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "RiskCheck",
    "RiskAssessment",
    "RiskEngine",
    "derive_risk_inputs",
]


@dataclass
class RiskCheck:
    check_name: str
    category: str
    result: str          # "PASS" | "WARN" | "FAIL"
    reason: str
    weight: int
    threshold: str | None = None
    actual_value: str | None = None


@dataclass
class RiskAssessment:
    checks: list[RiskCheck]
    risk_score: int
    risk_level: str      # "low" | "medium" | "high"
    requires_approval: bool
    overall_status: str  # "approved" | "pending_approval" | "blocked"


def _risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def derive_risk_inputs(
    *,
    data_sensitivity: str,
    connector: str,
    target_environment: str,
    tool_name: str | None = None,
) -> list[str]:
    """Compute risk input tags for a job run. Used to populate JobSpec.risk_score_input."""
    risk_inputs: list[str] = []

    sensitivity = (data_sensitivity or "").strip().lower()
    if sensitivity:
        risk_inputs.append(sensitivity)
        if sensitivity in {"high", "medium"}:
            risk_inputs.append("pii")

    connector_lower = (connector or "").strip().lower()
    if connector_lower in {"fetch", "airflow", "powerbi", "tableau"}:
        risk_inputs.append("external_egress")

    env = (target_environment or "").strip().lower()
    if env == "semi-prod":
        risk_inputs.append("semi_prod")
    elif env == "prod":
        risk_inputs.append("prod")

    if tool_name:
        risk_inputs.append(f"tool:{tool_name}")

    return sorted(set(risk_inputs))


class RiskEngine:
    """Evaluate run-level risk and return structured check results.

    This is the single authoritative risk scorer. app/services/policy_service
    calls this and persists the results; it does not reimplement the scoring.
    """

    @staticmethod
    def evaluate(
        *,
        data_sensitivity: str,
        connector: str,
        target_environment: str,
        has_schedule: bool = False,
    ) -> RiskAssessment:
        checks: list[RiskCheck] = []
        env = (target_environment or "dev").strip().lower()

        # Environment risk
        if env == "prod":
            env_result, env_reason, env_weight = "WARN", "Prod environment requires stricter controls", 35
        elif env == "semi-prod":
            env_result, env_reason, env_weight = "WARN", "Semi-prod environment requires heightened attention", 20
        else:
            env_result, env_reason, env_weight = "PASS", "Dev environment", 5
        checks.append(RiskCheck(
            check_name="Environment",
            category="environment",
            result=env_result,
            reason=env_reason,
            weight=env_weight,
            threshold="dev<semi-prod<prod",
            actual_value=env,
        ))

        # Data sensitivity risk
        sensitivity = (data_sensitivity or "low").strip().lower()
        if sensitivity == "high":
            sens_result, sens_reason, sens_weight = "FAIL", "High sensitivity data requires approval", 35
        elif sensitivity == "medium":
            sens_result, sens_reason, sens_weight = "WARN", "Medium sensitivity data", 15
        else:
            sens_result, sens_reason, sens_weight = "PASS", "Low sensitivity data", 5
        checks.append(RiskCheck(
            check_name="Data Sensitivity",
            category="security",
            result=sens_result,
            reason=sens_reason,
            weight=sens_weight,
            threshold="low/medium/high",
            actual_value=sensitivity,
        ))

        # External egress risk
        connector_lower = (connector or "").strip().lower()
        if connector_lower == "airflow" and env == "prod":
            egress_result = "FAIL"
            egress_reason = "Airflow in prod flagged for external side effects"
            egress_weight = 20
        elif connector_lower in {"powerbi", "tableau"}:
            egress_result = "WARN"
            egress_reason = "BI connector may call external services"
            egress_weight = 12
        else:
            egress_result = "PASS"
            egress_reason = "No high-risk external egress connector detected"
            egress_weight = 5
        checks.append(RiskCheck(
            check_name="External Egress",
            category="security",
            result=egress_result,
            reason=egress_reason,
            weight=egress_weight,
            threshold="restricted connectors in prod",
            actual_value=connector_lower or "none",
        ))

        # Schedule risk
        checks.append(RiskCheck(
            check_name="Schedule Change",
            category="operational",
            result="WARN" if has_schedule else "PASS",
            reason="Schedule present; review cadence impact" if has_schedule else "No schedule impact detected",
            weight=10 if has_schedule else 2,
            threshold="no unexpected cadence changes",
            actual_value="configured" if has_schedule else "none",
        ))

        risk_score = max(0, min(sum(c.weight for c in checks), 100))
        risk_level = _risk_level(risk_score)
        has_fail = any(c.result == "FAIL" for c in checks)
        requires_approval = has_fail or risk_score >= 60
        overall_status = "blocked" if has_fail else ("pending_approval" if requires_approval else "approved")

        return RiskAssessment(
            checks=checks,
            risk_score=risk_score,
            risk_level=risk_level,
            requires_approval=requires_approval,
            overall_status=overall_status,
        )
