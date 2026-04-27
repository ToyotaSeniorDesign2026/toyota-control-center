from typing import Tuple
from control_center.core.specs import JobSpec


class RiskEngine:
    """
    Calculates risk based on environment, data sensitivity, egress, and scheduling.
    Enforces guardrails to prevent high-risk configurations from being deployed to production without approval.
    """

    @staticmethod
    def get_risk_assessment(spec: JobSpec) -> Tuple[float, str | None]:
        score = 0.0
        warning = None

        # Environment Risk
        if spec.environment == "Environment.PROD":
            score += 0.5
        elif spec.environment == "Environment.SEMI_PROD":
            score += 0.3

        # Data Sensitivity Risk
        if "pii" in spec.risk_score_input:
            score += 0.4

        # Egress Risk
        if "external_egress" in spec.risk_score_input:
            score += 0.3  # Outbound traffic to external services/websites is a significant risk factor

        # Schedule/Concurrency Risk
        if spec.schedule and "high_frequency" in spec.risk_score_input:
            score += 0.1

        # Final risk score capped at 1.0 (100%)
        final_score = min(score, 1.0)

        # Policy Guardrail: If risk score exceeds threshold, require approval and revert to DEV environment
        if final_score >= 0.7 and spec.environment != "Environment.DEV":
            warning = "HIGH RISK: Required approval for this configuration. Reverting to DEV for safety."

        return final_score, warning
