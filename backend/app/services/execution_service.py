from __future__ import annotations

"""Normalize orchestration input into a single executor-facing request."""

import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.run import MCPExecutionConfig, MCPJobConfig, RunCreate

ExecutionBackend = Literal["mcp"]
ExecutionMode = Literal["direct_tool", "agent"]
TriggerSource = Literal["api", "ui", "cli", "schedule", "github_pr", "github_actions"]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_control_center_importable() -> None:
    src_root = _workspace_root() / "src"
    src_root_str = str(src_root)
    if src_root.exists() and src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)


class JobExecutionTarget(BaseModel):
    job_id: str
    name: str
    kind: str
    type: str
    connector: str
    environment: str
    data_sensitivity: str
    config: dict = Field(default_factory=dict)
    tags: list = Field(default_factory=list)


class ExecutionRequest(BaseModel):
    run_id: str
    trigger_source: TriggerSource = "api"
    action: str
    target_environment: str
    execution_backend: ExecutionBackend
    execution_mode: ExecutionMode
    resource: JobExecutionTarget
    params: dict = Field(default_factory=dict)
    job_config: MCPJobConfig = Field(default_factory=MCPJobConfig)
    mcp_config: MCPExecutionConfig = Field(default_factory=MCPExecutionConfig)
    job_spec: dict = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _build_sql_mcp_prompt(query: str, connection_id: str | None = None) -> str:
    connection_hint = f" using connection `{connection_id}`" if connection_id else ""
    return (
        "Execute the following SQL query exactly as written"
        f"{connection_hint} against the registered SQL MCP resource. "
        "Treat this as a one-time SQL job run and return the query results with a brief execution summary.\n\n"
        f"SQL query:\n```sql\n{query}\n```"
    )


def _derive_risk_inputs(resource, target_environment: str, mcp_config: MCPExecutionConfig | None) -> list[str]:
    risk_inputs: list[str] = []
    sensitivity = (resource.data_sensitivity or "").strip().lower()
    if sensitivity:
        risk_inputs.append(sensitivity)
        if sensitivity in {"high", "medium"}:
            risk_inputs.append("pii")

    connector = (resource.connector or "").strip().lower()
    if connector in {"fetch", "airflow", "powerbi", "tableau"}:
        risk_inputs.append("external_egress")

    if target_environment == "semi-prod":
        risk_inputs.append("semi_prod")
    elif target_environment == "prod":
        risk_inputs.append("prod")

    if mcp_config and mcp_config.tool_name:
        risk_inputs.append(f"tool:{mcp_config.tool_name}")
    return sorted(set(risk_inputs))


def build_job_spec(resource, payload: RunCreate, resolved_mcp_config: MCPExecutionConfig | None = None) -> dict:
    ensure_control_center_importable()
    from control_center.core.specs import JobSpec

    job_config = payload.job_config or MCPJobConfig()
    mcp_config = resolved_mcp_config or payload.mcp_config or MCPExecutionConfig()

    metadata = {
        "job_id": resource.id,
        "job_name": resource.name,
        "job_type": resource.type,
        "connector": resource.connector,
        "job_config_data": getattr(resource, "config", {}) or {},
        "params": payload.params,
        "job_config": job_config.model_dump(),
        "mcp_config": mcp_config.model_dump(),
    }
    metadata.update(job_config.metadata)

    tasks = list(job_config.tasks)
    if mcp_config.tool_name and mcp_config.tool_name not in tasks:
        tasks.append(mcp_config.tool_name)

    spec = JobSpec(
        intent=job_config.intent or payload.action,
        environment=payload.target_environment,
        risk_score_input=_derive_risk_inputs(resource, payload.target_environment, mcp_config),
        schedule=job_config.schedule,
        tasks=tasks,
        metadata=metadata,
    )
    return spec.model_dump()


def resolve_effective_mcp_config(resource, payload: RunCreate) -> MCPExecutionConfig:
    supplied = payload.mcp_config or MCPExecutionConfig()
    resource_config = getattr(resource, "config", {}) or {}
    resource_type = (getattr(resource, "type", "") or "").strip().lower()

    server_names = list(supplied.server_names)
    connector = (getattr(resource, "connector", "") or "").strip().lower()
    if not server_names and connector:
        server_names = [connector]

    tool_name = supplied.tool_name
    tool_arguments = dict(supplied.tool_arguments)
    prompt = supplied.prompt

    if resource_type == "sql":
        query = _non_empty_string(payload.params.get("query")) or _non_empty_string(resource_config.get("query"))
        db_driver = (
            _non_empty_string(payload.params.get("db_driver"))
            or _non_empty_string(resource_config.get("db_driver"))
            or ""
        ).lower()
        # connection_id is only meaningful for PostgreSQL managed connections
        _pg_driver = db_driver not in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
        connection_id = (
            (
                _non_empty_string(payload.params.get("connection_id"))
                or _non_empty_string(resource_config.get("connection_id"))
            )
            if _pg_driver
            else None
        )

        if tool_name:
            if query and "query" not in tool_arguments:
                tool_arguments["query"] = query
            if connection_id and "connection_id" not in tool_arguments:
                tool_arguments["connection_id"] = connection_id
        elif not prompt and query:
            prompt = _build_sql_mcp_prompt(query, connection_id)

    if (
        not tool_name
        and not prompt
        and (resource_type == "research" or connector == "arxiv-research")
    ):
        tool_name = "search_papers"
        topic = payload.params.get("topic") or resource_config.get("topic")
        max_results = payload.params.get("max_results") or resource_config.get("max_results")
        if topic and "topic" not in tool_arguments:
            tool_arguments["topic"] = topic
        if max_results is not None and "max_results" not in tool_arguments:
            tool_arguments["max_results"] = max_results

    return MCPExecutionConfig(
        server_names=server_names,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        prompt=prompt,
        connector_selection_prompt=supplied.connector_selection_prompt,
        allow_auto_selection=supplied.allow_auto_selection,
    )


def build_execution_request(
    *,
    run_id: str,
    resource,
    payload: RunCreate,
    trigger_source: TriggerSource = "api",
) -> ExecutionRequest:
    resolved_mcp_config = resolve_effective_mcp_config(resource, payload)
    if not resolved_mcp_config.server_names:
        raise RuntimeError(
            f"Job '{resource.id}' is not associated with an approved MCP server. "
            "Set job.connector or mcp_config.server_names."
        )

    backend: ExecutionBackend = "mcp"
    mode: ExecutionMode = "direct_tool" if resolved_mcp_config.tool_name else "agent"
    job_spec = build_job_spec(resource, payload, resolved_mcp_config)

    return ExecutionRequest(
        run_id=run_id,
        trigger_source=trigger_source,
        action=payload.action,
        target_environment=payload.target_environment,
        execution_backend=backend,
        execution_mode=mode,
        resource=JobExecutionTarget(
            job_id=resource.id,
            name=resource.name,
            kind=resource.kind,
            type=resource.type,
            connector=resource.connector,
            environment=resource.environment,
            data_sensitivity=resource.data_sensitivity,
            config=resource.config or {},
            tags=resource.tags or [],
        ),
        params=payload.params,
        job_config=payload.job_config or MCPJobConfig(),
        mcp_config=resolved_mcp_config,
        job_spec=job_spec,
        metadata={
            "job_owner_id": resource.owner_id,
            "job_owner_domain": resource.owner_domain,
        },
    )
