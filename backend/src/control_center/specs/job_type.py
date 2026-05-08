from __future__ import annotations

from enum import Enum, StrEnum
from typing import Any, Annotated, Literal
from pydantic import BaseModel, Field, model_validator, field_validator
from fnmatch import fnmatch

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


class AccessPolicyMode(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class AccessPolicy(BaseModel):
    mode: AccessPolicyMode = AccessPolicyMode.BLOCK
    items: list[str] = Field(default_factory=list)
    extensions: dict[str, Any] = Field(default_factory=dict)

    def allows(self, name: str) -> bool:
        matched = any(fnmatch(name, item) for item in self.items)
        if self.mode == AccessPolicyMode.ALLOW:
            return matched
        if self.mode == AccessPolicyMode.BLOCK:
            return not matched
        raise ValueError(f"Unknown access policy mode: {self.mode}")


class EnvironmentPolicy(BaseModel):
    approval_required_in: list[Environment] = Field(default_factory=lambda: ["prod"])
    blocked_in: list[Environment] = Field(default_factory=list)


class RiskPolicy(BaseModel):
    floor: int = 0
    approval_threshold: int = 60
    config: dict[str, Any] = Field(default_factory=dict)


class GovernancePolicy(BaseModel):
    """Defines governance rules for a job type, including risk assessment, environment restrictions, and access controls."""
    risk: RiskPolicy = Field(default_factory=RiskPolicy)
    environment: EnvironmentPolicy = Field(default_factory=EnvironmentPolicy)
    scopes: dict[str, AccessPolicy] = Field(default_factory=dict)
    extensions: dict[str, Any] = Field(default_factory=dict)


class InteractionSurfaceType(StrEnum):
    """
    Categories of external systems a job may interact with at execution time.

    Each value is the *kind* of dependency. Specific instances (server names,
    URLs, hostnames) live on ExecutionRequirement.names.
    """
    # --- Tool-Protocol Surfaces ---
    MCP_SERVER = "mcp_server"  # An MCP server exposing tools, prompts, and resources.

    # --- Direct API Surfaces ---
    HTTP_API = "http_api"  # Generic HTTP/HTTPS REST or RPC endpoint reached via plain HTTP client.
    AIRFLOW_API = "airflow_api"  # Airflow REST API for DAG triggering and run polling.

    # --- Data-Store Surfaces ---
    SQL_DATABASE = "sql_database"  # Direct SQL connection (Snowflake, Postgres, etc.) outside an MCP wrapper.
    OBJECT_STORAGE = "object_storage"  # S3, GCS, Azure Blob, etc.
    GIT_REPOSITORY = "git_repository"  # A Git repo, accessed via host API (GitHub, GitLab) or SSH/HTTPS clone.
    FILE_SYSTEM = "file_system"  # Local filesystem path scope (sandbox dir, mounted volume).

    # --- Local-Execution Surfaces ---
    PYTHON_RUNTIME = "python_runtime"  # Local Python interpreter; Used for PYTHON_FILE and PYTHON_BUILTIN executors.
    SHELL_PROCESS = "shell_process"  # Local shell — `bash`, `npx`, etc. Used by CLI-driven executors."""

    # --- None ---
    NONE = "none"  # """Job has no external surface requirements. Fully self-contained execution."""


class ExecutionRequirement(BaseModel):
    """
    External interaction surfaces this job type may need to execute.

    Example:
        ExecutionRequirement(
            surface_type=InteractionSurfaceType.MCP_SERVER,
            names=["github-mcp", "slack-mcp"],
            required_tools=["github.create_issue", "slack.send_message"],
            required_scopes=["repo:write", "chat:write"]
        )
    """
    surface_type: InteractionSurfaceType = Field(description="Kind of interaction surface required by the job")
    names: list[str] = Field(default_factory=list, description="Specific surfaces, server names, IDs, or patterns this job can connect to.")
    required_tools: list[str] = Field(default_factory=list, description="Tool names that must be available from this surface, if applicable.")
    required_scopes: list[str] = Field(default_factory=list, description="OAuth-style scopes or permissions required for this surface, if applicable.")
    extensions: dict[str, Any] = Field(default_factory=dict)


ArtifactBackend = Literal["github", "s3", "local", "gcs", "blob", "snowflake", "memory"]


class VersioningPolicy(BaseModel):
    strategy: Literal["overwrite", "append_version", "snapshot", "partition"] = "append_version"
    version_format: Literal["semver", "timestamp", "run_id", "sequence"] = "timestamp"
    keep_last: int | None = None


class ArtifactSpec(BaseModel):
    """
    Describes the file/document a job of this type produces. May use {field} placeholders filled at runtime.

    Presence of this field on a contract marks it as an artifact job. Absence means a runtime (side-effect-only) job.

    Example:
        ArtifactSpec(
            format="md",
            backend="github",
            address={
                "repo": "{config.target_repo}",
                "branch": "main",
                "path_template": "AGENTS.md",
            },
            versioning=VersioningPolicy(strategy="overwrite"),
        )
    """
    format: str
    media_type: str | None = None
    backend: ArtifactBackend
    address: dict[str, str] = Field(default_factory=dict)
    versioning: VersioningPolicy = Field(default_factory=VersioningPolicy)
    retention_days: int | None = None
    extensions: dict[str, Any] = Field(default_factory=dict)


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


SupportedActions = Literal[
    "activate", "pause",  # Lifecycle Actions Pair
    "archive", "unarchive",  # Job Storage Pair
    "publish", "unpublish",  # Artifact Storage Pair
    "promote", "demote",  # Environment Governance Pair
    "deploy", "undeploy",  # Execution Availability Pair
    "*"  # Wildcard for "all supported actions"
]
DEFAULT_ACTIONS: list[SupportedActions] = ["activate", "pause", "archive"]


JobTypeSource = Literal["system", "admin", "user"]


class ExecutorType(StrEnum):
    """
    Categories of executor implementations that run jobs.

    Each value maps to exactly one Executor class in the EXECUTOR_REGISTRY
    (one-to-one). The companion `executor` field on JobTypeContract carries
    the per-instance payload (tool name, agent profile, script path, DAG ID, etc.)
    interpreted by the resolved executor.
    """
    # --- Tool-Protocol Executors ---
    MCP_TOOL = "mcp_tool"  # Single deterministic call to one named MCP tool with fixed args. Used for: deterministic SQL queries, direct API calls, file ops.
    MCP_AGENT = "mcp_agent"  # LLM-driven tool-calling loop over one or more MCP servers. Used for: agentic research, multi-step workflows, anything with a prompt.

    # --- Direct API Executors ---
    HTTP_REQUEST = "http_request"  # Generic HTTP/HTTPS call against a configured endpoint (GET/POST/PUT/etc.). Used for: webhooks, internal services, anything reachable by plain HTTP.
    AIRFLOW_TRIGGER = "airflow_trigger"  # Trigger an Airflow DAG via Airflow REST API and poll the resulting dag_run for completion.

    # --- Data-Store Executors ---
    SQL_QUERY = "sql_query"  # Direct SQL execution against a SQL_DATABASE surface. Used for: native Snowflake/Postgres jobs that don't go through sql-mcp.
    SQL_TO_ARTIFACT = "sql_to_artifact"  # Run SQL, materialize the result as a file (CSV/Parquet/Excel) and write it via an ArtifactSpec. Bridges SQL execution with artifact storage.
    GIT_COMMIT = "git_commit"  # Write a file (or set of files) to a GIT_REPOSITORY surface and commit. Used for: SQL-to-GitHub flows, generated docs, AGENTS.md jobs.

    # --- Local-Execution Executors ---
    PYTHON_BUILTIN = "python_builtin"  # Run a Python module shipped in the repo (e.g. scripts/runtime/*.py). Code-reviewed, deterministic, no sandbox.
    PYTHON_FILE = "python_file"  # Run a user-uploaded Python script. Sandboxed, governed, source='user'. Looked up via UserJobScript table at execution time.
    AIRFLOW_PYTHON = "airflow_python"  # Run a Python file as an Airflow DAG/PythonOperator task
    SHELL_COMMAND = "shell_command"  # Run a shell command against a SHELL_PROCESS surface. Used for CLI-driven executors (e.g. `dbt run`, `playwright codegen`).

    # --- None ---
    NOOP = "noop"  # Sentinel executor that does nothing. Used for testing, dry-runs, and contracts in development. Returns immediately with success.


class JobTypeContract(BaseModel):
    # ── Identity ──────────────────────────────────────────────────────────────
    type: str
    version: str = "1.0"
    display_name: str | None = None
    description: str | None = None
    supported_actions: list[SupportedActions] = Field(default_factory=lambda: list(DEFAULT_ACTIONS))
    # ── Schema ────────────────────────────────────────────────────────────────
    deterministic: bool = False
    config: InputSchema = Field(default_factory=InputSchema)  # job-level config (set once, reused across runs)
    params: InputSchema = Field(default_factory=InputSchema)  # run-time parameters
    # ── Execution Wiring ──────────────────────────────────────────────────────
    executor: str
    """Per-instance payload interpreted by the resolved"""
    executor_type: ExecutorType
    """Registry key into the executor registry (e.g. 'mcp', 'agent')."""
    requires: list[ExecutionRequirement] = Field(default_factory=list)
    features: RunFeatures = Field(default_factory=RunFeatures)
    artifact: ArtifactSpec | None = None
    # ── Governance & Provenance ────────────────────────────────────────────────────────────
    policy: GovernancePolicy = Field(default_factory=GovernancePolicy)
    source: JobTypeSource = "system"
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

    # User-authored contracts can't self-declare deterministic=True or skip created_by/domain
    @model_validator(mode="after")
    def _validate_provenance(self) -> "JobTypeContract":
        if self.source == "system":
            if self.created_by is not None:
                raise ValueError("source='system' contracts cannot set created_by")
        else:
            if self.created_by is None:
                raise ValueError(f"source='{self.source}' contracts must set created_by")
            if self.source == "user":
                if self.domain is None:
                    raise ValueError("source='user' contracts must set domain")
                if self.deterministic:
                    raise ValueError("source='user' contracts cannot self-declare deterministic=True")
        return self
