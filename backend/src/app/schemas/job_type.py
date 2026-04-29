from __future__ import annotations

"""API-facing serialization of JobTypeContract."""

from typing import Any
from pydantic import BaseModel

from control_center.specs.job_type import JobTypeContract


class FieldSpecOut(BaseModel):
    name: str
    type: str
    format: str | None = None
    default: Any | None = None
    description: str | None = None
    enum: list[str] | None = None
    placeholder: str | None = None
    sensitive: bool = False
    write_only: bool = False
    special_storage: str | None = None


class InputSchemaOut(BaseModel):
    required: list[str]
    optional: list[str]
    fields: dict[str, FieldSpecOut]


class RunFeaturesOut(BaseModel):
    supports_retry: bool
    supports_cancel: bool
    supports_schedule: bool
    supports_heartbeat: bool
    max_runtime_seconds: int


class GovernancePolicyOut(BaseModel):
    risk_floor: int
    approval_threshold: int
    approval_required_in: list[str]
    blocked_in: list[str]


class CapabilityRequirementOut(BaseModel):
    connector_types: list[str]
    required_tools: list[str]
    required_scopes: list[str]


class JobTypeContractOut(BaseModel):
    type: str
    version: str
    display_name: str | None
    description: str | None
    kind: str
    supported_actions: list[str]
    executor: str
    requires: CapabilityRequirementOut
    features: RunFeaturesOut
    policy: GovernancePolicyOut
    config: InputSchemaOut
    params: InputSchemaOut
    source: str

    @classmethod
    def from_contract(cls, contract: JobTypeContract) -> "JobTypeContractOut":
        return cls.model_validate(contract.model_dump())
