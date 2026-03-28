from __future__ import annotations

"""Normalize orchestration input into a single executor-facing request."""

import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.run import MCPExecutionConfig, MCPJobConfig, RunCreate

ExecutionBackend = Literal["mcp", "native"]
ExecutionMode = Literal["direct_tool", "agent", "native"]
TriggerSource = Literal["api", "ui", "cli", "schedule", "github_pr", "github_actions"]


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_control_center_importable() -> None:
    src_root = _workspace_root() / "src"
    src_root_str = str(src_root)
    if src_root.exists() and src_root_str not in sys.path:
        sys.path.insert(0, src_root_str)


class ResourceExecutionTarget(BaseModel):
    resource_id: str
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
    resource: ResourceExecutionTarget
    params: dict = Field(default_factory=dict)
    job_config: MCPJobConfig = Field(default_factory=MCPJobConfig)
    mcp_config: MCPExecutionConfig = Field(default_factory=MCPExecutionConfig)
    job_spec: dict = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


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

    if target_environment in {"semi-prod", "staging"}:
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
        "resource_id": resource.id,
        "resource_name": resource.name,
        "resource_type": resource.type,
        "connector": resource.connector,
        "resource_config": getattr(resource, "config", {}) or {},
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

    server_names = list(supplied.server_names)
    connector = (getattr(resource, "connector", "") or "").strip().lower()
    if not server_names and connector:
        server_names = [connector]

    tool_name = supplied.tool_name
    tool_arguments = dict(supplied.tool_arguments)
    prompt = supplied.prompt

    if (
        not tool_name
        and not prompt
        and ((getattr(resource, "type", "") or "").strip().lower() == "research" or connector == "arxiv-research")
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
    resource_type = (resource.type or "").strip().lower()
    connector = (resource.connector or "").strip().lower()

    is_mcp = bool(payload.mcp_config) or connector in {
        "arxiv-research",
        "fastmcp-docs",
        "fetch",
        "filesystem",
        "wordsmith-mcp",
    } or resource_type in {"research", "mcp"}

    resolved_mcp_config = resolve_effective_mcp_config(resource, payload) if is_mcp else MCPExecutionConfig()
    if not is_mcp:
        backend: ExecutionBackend = "native"
        mode: ExecutionMode = "native"
    elif resolved_mcp_config.tool_name:
        backend = "mcp"
        mode = "direct_tool"
    else:
        backend = "mcp"
        mode = "agent"

    job_spec = build_job_spec(resource, payload, resolved_mcp_config) if is_mcp else {}

    return ExecutionRequest(
        run_id=run_id,
        trigger_source=trigger_source,
        action=payload.action,
        target_environment=payload.target_environment,
        execution_backend=backend,
        execution_mode=mode,
        resource=ResourceExecutionTarget(
            resource_id=resource.id,
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
            "resource_owner_id": resource.owner_id,
            "resource_owner_domain": resource.owner_domain,
        },
    )
