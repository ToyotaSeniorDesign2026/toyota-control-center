from __future__ import annotations

"""Pydantic schemas describing job-type contracts exposed by /job-types."""

from pydantic import BaseModel, Field


class ConfigSchemaOut(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class RunCapabilitiesOut(BaseModel):
    supports_retry: bool = True
    supports_cancel: bool = True
    supports_schedule: bool = False
    supports_heartbeat: bool = False


class ApprovalDefaultsOut(BaseModel):
    required_above_risk_score: int = 60
    always_required_environments: list[str] = Field(default_factory=list)


class JobTypeContractOut(BaseModel):
    type: str
    kind: str
    required_config_schema: ConfigSchemaOut
    supported_job_actions: list[str] = Field(default_factory=list)
    run_capabilities: RunCapabilitiesOut
    approval_defaults: ApprovalDefaultsOut
