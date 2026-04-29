from __future__ import annotations

from enum import Enum
from typing import Any, Annotated, Literal
from pydantic import BaseModel, Field, model_validator, field_validator

from .field_formats import FORMAT_REGISTRY
from .environment import Environment


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


BASE_TYPE_MAP: dict[FieldType, Any] = {
    FieldType.STRING: str,
    FieldType.INTEGER: int,
    FieldType.NUMBER: float,
    FieldType.BOOLEAN: bool,
    FieldType.ARRAY: list,
    FieldType.OBJECT: dict,
}


class FieldSpec(BaseModel):
    name: str
    type: FieldType
    format: str | None = None

    default: Any | None = None
    description: str | None = None
    enum: list[str] | None = None
    placeholder: str | None = None
    sensitive: bool = False               # encrypt at rest, mask on read
    write_only: bool = False              # never returned in responses or logs
    special_storage: Literal["ephemeral", "session", "cache", "immutable_after_create", "env_only", "oauth"] | None = None

    @model_validator(mode="after")
    def validate_field_spec(self):
        if self.enum and self.type is not FieldType.STRING:
            raise ValueError("enum is only supported for string fields")

        if self.format:
            if self.format == "secret":
                self.sensitive = True
            elif self.format not in FORMAT_REGISTRY:
                raise ValueError(f"Unknown field format: {self.format}. Supported formats: {list(FORMAT_REGISTRY.keys())}")

        return self


class RunFeatures(BaseModel):
    supports_retry: bool = True
    supports_cancel: bool = True
    supports_schedule: bool = False
    supports_heartbeat: bool = False
    max_runtime_seconds: int = 300


class GovernancePolicy(BaseModel):
    risk_floor: int = 0
    approval_threshold: int = 60
    approval_required_in: list[Environment] = Field(default_factory=lambda: [Environment.PROD])
    blocked_in: list[Environment] = Field(default_factory=list)


class CapabilityRequirement(BaseModel):
    """What this job type needs from its connector to execute."""

    connector_types: list[str] = Field(default_factory=list)
    """Connector type names this contract is compatible with (e.g. 'sql-mcp')."""
    required_tools: list[str] = Field(default_factory=list)
    """MCP tool names that must be available on the connector."""
    required_scopes: list[str] = Field(default_factory=list)
    """OAuth-style scopes the connector must grant (e.g. 'repo:write')."""


class ArtifactSpec(BaseModel):
    """Describes the file/document a job of this type produces.

    Presence of this field on a contract marks it as an artifact job. Absence means a runtime (side-effect-only) job."""

    output_format: str
    """File extension or format identifier ('xlsx', 'pptx', 'md', 'csv', 'sql')."""
    versioned: bool = True
    """Whether each run produces a new version (vs. overwriting)."""
    storage: Literal["github", "s3", "local"] = "github"
    path_template: str
    """Where to write the artifact. May use {date}, {job_name}, {run_id} placeholders."""


class InputSchema(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    fields: dict[str, "FieldSpec"] = Field(
        default_factory=dict,
        description=(
            "Full field definitions keyed by field name. When populated, the UI can "
            "render a dynamic form without knowing the job type ahead of time. "
            "required/optional lists are the source of truth for validation; this "
            "dict adds type, format, and display metadata on top."
        ),
    )


JobTypeSource = Annotated[Literal["system", "admin", "user"], Field(default="system")]

JobKind = Literal["runtime", "artifact"]


class JobTypeContract(BaseModel):
    # ── Identity ──────────────────────────────────────────────────────────────
    type: str
    version: str = "1.0"
    display_name: str | None = None
    description: str | None = None
    kind: JobKind = "runtime"
    supported_actions: list[str] = Field(default_factory=lambda: ["activate", "pause", "archive"])
    # ── Schema ────────────────────────────────────────────────────────────────
    deterministic: bool = False
    config: InputSchema = Field(default_factory=InputSchema)  # job-level config (set once, reused across runs)
    params: InputSchema = Field(default_factory=InputSchema)  # run-time parameters
    # ── Execution Wiring ──────────────────────────────────────────────────────
    executor: str = "mcp"
    """Registry key into the executor registry (e.g. 'mcp', 'agent')."""
    requires: CapabilityRequirement = Field(default_factory=CapabilityRequirement)
    features: RunFeatures = Field(default_factory=RunFeatures)
    # ── Provenance ────────────────────────────────────────────────────────────
    policy: GovernancePolicy = Field(default_factory=GovernancePolicy)
    source: JobTypeSource
    created_by: str | None = None  # User ID for non-system contracts
    domain: str | None = None  # Visibility scope. None = global, otherwise restricted to that domain

    def form_schema(self) -> dict:
        """Return a UI-renderable form schema derived from config.fields + params.fields.

        This is what MCP App integrations will call to render a dynamic job creation form.
        """
        config_fields = [f.model_dump() for f in self.config.fields.values()]
        params_fields = [f.model_dump() for f in self.params.fields.values()]
        return {
            "type": self.type,
            "display_name": self.display_name,
            "config_fields": config_fields,
            "params_fields": params_fields,
            "required_config": self.config.required,
            "optional_config": self.config.optional,
            "required_params": self.params.required,
            "optional_params": self.params.optional,
        }
