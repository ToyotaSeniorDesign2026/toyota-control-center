from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyCheckResult(BaseModel):
    id: str
    evaluation_id: str
    check_name: str
    category: str
    result: str
    reason: str
    severity: str
    weight: int = Field(ge=0, le=100)
    threshold: str | None = None
    actual_value: str | None = None


class PolicyDecision(BaseModel):
    status: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    reasons: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    evaluation_id: str | None = None


class PolicyEvaluationOut(BaseModel):
    evaluation_id: str
    run_id: str
    policy_version: str
    overall_status: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: str
    requires_approval: bool
    evaluated_at: str
    checks: list[PolicyCheckResult] = Field(default_factory=list)
