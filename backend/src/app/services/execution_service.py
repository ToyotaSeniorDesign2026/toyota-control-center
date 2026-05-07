from __future__ import annotations

"""Normalize orchestration input into a single executor-facing ExecutionRequest."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.run import RunCreate
from control_center.policy.risk_engine import derive_risk_inputs
from control_center.specs.execution import AgentRun, DirectToolCall, MCPRunSpec

ExecutionBackend = Literal["mcp"]
TriggerSource = Literal["api", "ui", "cli", "schedule", "github_pr", "github_actions", "chat_agent"]


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
    resource: JobExecutionTarget
    params: dict = Field(default_factory=dict)
    run_spec: DirectToolCall | AgentRun
    job_spec: dict = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def execution_mode(self) -> str:
        return "direct_tool" if isinstance(self.run_spec, DirectToolCall) else "agent"


def _non_empty(value: Any) -> str | None:
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return None


def build_job_spec(resource, payload: RunCreate, run_spec: MCPRunSpec) -> dict:
    tool_name = run_spec.tool_name if isinstance(run_spec, DirectToolCall) else None
    risk_inputs = derive_risk_inputs(
        data_sensitivity=resource.data_sensitivity or "",
        connector=resource.connector or "",
        target_environment=payload.target_environment,
        tool_name=tool_name,
    )
    return {
        "intent": payload.action,
        "environment": payload.target_environment,
        "risk_score_input": risk_inputs,
        "tasks": [tool_name] if tool_name else [],
        "metadata": {
            "job_id": resource.id,
            "job_name": resource.name,
            "job_type": resource.type,
            "connector": resource.connector,
            "job_config_data": getattr(resource, "config", {}) or {},
            "params": payload.params,
        },
    }


def resolve_run_spec(resource, payload: RunCreate) -> MCPRunSpec:
    """Derive the concrete MCP execution spec from job type + run payload."""
    resource_config = getattr(resource, "config", {}) or {}
    resource_type = (_non_empty(getattr(resource, "type", "")) or "").lower()
    connector = (_non_empty(getattr(resource, "connector", "")) or "").lower()
    server_name = connector or resource_type

    # --- GitHub write (SQL artifact → GitHub) ---
    if resource_type == "sql" and connector == "github":
        # Handled as a special case in the executor; encode as a direct tool call
        # so the executor knows to skip the LLM path.
        owner_repo = _non_empty(payload.params.get("repo") or resource_config.get("repo")) or ""
        owner, _, repo_name = owner_repo.partition("/")
        path = _non_empty(payload.params.get("path") or resource_config.get("path") or resource_config.get("file_path")) or ""
        content = _non_empty(payload.params.get("query") or resource_config.get("query")) or ""
        branch = _non_empty(payload.params.get("branch") or resource_config.get("ref")) or "main"
        return DirectToolCall(
            server_name="github",
            tool_name="create_or_update_file",
            arguments={
                "owner": owner,
                "repo": repo_name,
                "path": path,
                "message": f"Add SQL script {path}",
                "content": content,
                "branch": branch,
            },
        )

    # --- SQL + GitHub write (compound agent run) ---
    if resource_type == "sql" and connector != "github":
        query = _non_empty(payload.params.get("query")) or _non_empty(resource_config.get("query"))
        github_repo = _non_empty(payload.params.get("github_repo") or resource_config.get("github_repo"))
        if query and github_repo:
            github_path = _non_empty(payload.params.get("github_path") or resource_config.get("github_path")) or "query.sql"
            github_branch = _non_empty(payload.params.get("github_branch") or resource_config.get("github_branch")) or "main"
            owner, _, repo_name = github_repo.partition("/")
            prompt = (
                "Before writing or executing any SQL, you MUST:\n"
                "1. Call list_tables to discover all available tables.\n"
                "2. Call describe_table for every table relevant to the task.\n"
                "3. Use only the real table and column names you find — do not guess.\n\n"
                f"Task: Execute the following SQL query against the database, then write the query text "
                f"to the file '{github_path}' in the GitHub repository '{github_repo}' on branch '{github_branch}'.\n\n"
                f"SQL query:\n{query}"
            )
            return AgentRun(
                server_names=["sql-mcp", "github"],
                prompt=prompt,
                allow_auto_selection=False,
            )

    # --- SQL direct execution ---
    if resource_type == "sql":
        query = _non_empty(payload.params.get("query")) or _non_empty(resource_config.get("query"))
        if query:
            db_driver = (
                _non_empty(payload.params.get("db_driver"))
                or _non_empty(resource_config.get("db_driver"))
                or ""
            ).lower()
            is_pg = db_driver not in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
            connection_id = (
                _non_empty(payload.params.get("connection_id"))
                or _non_empty(resource_config.get("connection_id"))
            ) if is_pg else None
            args: dict[str, Any] = {"query": query}
            if connection_id:
                args["connection_id"] = connection_id
            return DirectToolCall(
                server_name=server_name or "sql-mcp",
                tool_name="execute_sql",
                arguments=args,
            )

    # --- Research direct execution ---
    if resource_type == "research" or connector == "arxiv-research":
        topic = _non_empty(payload.params.get("topic")) or _non_empty(resource_config.get("topic"))
        if topic:
            args = {"topic": topic}
            max_results = payload.params.get("max_results") or resource_config.get("max_results")
            if max_results is not None:
                args["max_results"] = max_results
            return DirectToolCall(
                server_name=server_name or "arxiv-research",
                tool_name="search_papers",
                arguments=args,
            )

    # --- Agent (prompt-driven) ---
    prompt = (
        _non_empty(payload.prompt)
        or _non_empty(payload.params.get("prompt"))
        or _non_empty(resource_config.get("prompt"))
    )
    if not prompt:
        raise RuntimeError(
            f"Job type '{resource_type}' requires a prompt. "
            "Pass prompt in the run request or set a default in the job config."
        )

    # For SQL agent runs, prepend schema-inspection instructions so the agent
    # always verifies table and column names before writing or executing a query.
    # If a GitHub PAT is available the agent also has access to GitHub tools.
    _sql_connectors = {"sql-mcp", "sql-mcp-analytics", "sql"}
    if resource_type == "sql" or connector in _sql_connectors:
        prompt = (
            "Before writing or executing any SQL, you MUST:\n"
            "1. Call list_tables to discover all available tables.\n"
            "2. Call describe_table for every table relevant to the task.\n"
            "3. Use only the real table and column names you find — do not guess.\n\n"
            "If a GitHub repository is specified in the task, you may also use the "
            "GitHub tools to write the query or results to a file in that repository.\n\n"
            + prompt
        )

    server_names = [connector] if connector else []
    return AgentRun(
        server_names=server_names,
        prompt=prompt,
        allow_auto_selection=not server_names,
        selection_prompt=prompt if not server_names else None,
    )


def build_execution_request(
    *,
    run_id: str,
    resource,
    payload: RunCreate,
    trigger_source: TriggerSource = "api",
) -> ExecutionRequest:
    run_spec = resolve_run_spec(resource, payload)

    connector = (_non_empty(getattr(resource, "connector", "")) or "").lower()
    if isinstance(run_spec, AgentRun) and not run_spec.server_names and not connector:
        raise RuntimeError(
            f"Job '{resource.id}' has no connector and no server_names could be resolved."
        )

    return ExecutionRequest(
        run_id=run_id,
        trigger_source=trigger_source,
        action=payload.action,
        target_environment=payload.target_environment,
        execution_backend="mcp",
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
        run_spec=run_spec,
        job_spec=build_job_spec(resource, payload, run_spec),
        metadata={
            "job_owner_id": resource.owner_id,
            "job_owner_domain": resource.owner_domain,
        },
    )
