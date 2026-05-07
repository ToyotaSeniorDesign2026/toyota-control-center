from __future__ import annotations

"""Agent-driven chat: MCPAgent + Control Center MCP server."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from control_center.agent import build_agent_from_registry

logger = logging.getLogger(__name__)

# ── Form specs ─────────────────────────────────────────────────────────────────

_DB_TYPE_OPTIONS = [
    {"label": "PostgreSQL", "value": "postgresql+psycopg", "description": "Host-based, port 5432"},
    {"label": "MySQL",      "value": "mysql+pymysql",      "description": "Host-based, port 3306"},
    {"label": "SQLite",     "value": "sqlite",             "description": "Local file or :memory:"},
    {"label": "Snowflake",  "value": "snowflake",          "description": "Cloud data warehouse"},
]

_CONNECTION_FIELDS: dict[str, list[dict]] = {
    "postgresql+psycopg": [
        {"key": "SQL_DB_HOST",     "label": "Database host",     "placeholder": "e.g. db.example.com", "secret": False, "required": True},
        {"key": "SQL_DB_PORT",     "label": "Database port",     "placeholder": "e.g. 5432",           "secret": False, "required": True},
        {"key": "SQL_DB_DATABASE", "label": "Database name",     "placeholder": "e.g. my_database",    "secret": False, "required": True},
        {"key": "SQL_DB_USERNAME", "label": "Database username", "placeholder": "e.g. db_user",        "secret": False, "required": True},
        {"key": "SQL_DB_PASSWORD", "label": "Database password", "placeholder": "Enter your password", "secret": True,  "required": True},
    ],
    "mysql+pymysql": [
        {"key": "SQL_DB_HOST",     "label": "Database host",     "placeholder": "e.g. db.example.com", "secret": False, "required": True},
        {"key": "SQL_DB_PORT",     "label": "Database port",     "placeholder": "e.g. 3306",           "secret": False, "required": True},
        {"key": "SQL_DB_DATABASE", "label": "Database name",     "placeholder": "e.g. my_database",    "secret": False, "required": True},
        {"key": "SQL_DB_USERNAME", "label": "Database username", "placeholder": "e.g. db_user",        "secret": False, "required": True},
        {"key": "SQL_DB_PASSWORD", "label": "Database password", "placeholder": "Enter your password", "secret": True,  "required": True},
    ],
    "sqlite": [
        {"key": "SQL_DB_DATABASE", "label": "SQLite file path",  "placeholder": "e.g. /path/to/db.sqlite  or  :memory:", "secret": False, "required": True},
    ],
    "snowflake": [
        {"key": "SQL_DB_HOST",     "label": "Snowflake account",  "placeholder": "e.g. myaccount.snowflakecomputing.com", "secret": False, "required": True},
        {"key": "SQL_DB_DATABASE", "label": "Database / schema",  "placeholder": "e.g. MY_DB/PUBLIC",                    "secret": False, "required": True},
        {"key": "SQL_DB_USERNAME", "label": "Username",           "placeholder": "e.g. my_user",                         "secret": False, "required": True},
        {"key": "SQL_DB_PASSWORD", "label": "Password",           "placeholder": "Enter your Snowflake password",         "secret": True,  "required": True},
    ],
}

_DEFAULT_CONNECTION_FIELDS = _CONNECTION_FIELDS["postgresql+psycopg"]


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    response: str
    config_request: dict | None = None
    db_type_options: list[dict] | None = None
    run_id: str | None = None


# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are CC Assistant for the Toyota Control Center — a platform for managing, scheduling, and running automated data jobs.

Be concise. Always use your available tools to answer questions about jobs and runs; never guess at IDs or status.

CRITICAL — job creation rule: before calling any create_*_job tool, you MUST present a confirmation summary to the user that lists every field you are about to submit (name, type, schedule, environment, query, connector, etc.) and explicitly ask them to confirm. Only proceed with creation after the user says yes or approves. Never skip this step.
"""


def _session_env_section(session_env: dict[str, str] | None) -> str:
    if not session_env:
        return ""
    lines = ["SESSION CONNECTION DETAILS (user-provided — use these when calling create_sql_job):"]
    for key, value in session_env.items():
        lines.append(f"  {key} = {value}")
    return "\n".join(lines)


def _build_full_prompt(
    message: str,
    conversation_history: list[dict[str, Any]] | None,
    session_env: dict[str, str] | None,
) -> str:
    env_block = _session_env_section(session_env)
    system = _SYSTEM_PROMPT + ("\n\n" + env_block if env_block else "")

    parts = [system, ""]
    for turn in conversation_history or []:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
    parts.append(f"User: {message}")
    return "\n".join(parts)


# ── Tool-call inspection ───────────────────────────────────────────────────────

def _extract_run_id(tool_executions: list[dict]) -> str | None:
    for te in tool_executions:
        if te.get("source_id") != "trigger_run":
            continue
        result = te.get("parsed_result")
        # parsed_result may be a list of content blocks or a plain dict
        if isinstance(result, list):
            for block in result:
                if isinstance(block, dict) and block.get("type") == "text":
                    try:
                        return json.loads(block["text"]).get("id")
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass
        elif isinstance(result, dict):
            return result.get("id")
    return None


def _build_config_request(db_type: str, prompt: str, prefill: dict | None = None) -> dict:
    base_fields = _CONNECTION_FIELDS.get(db_type, _DEFAULT_CONNECTION_FIELDS)
    if prefill:
        fields = [
            {**f, "default_value": prefill[f["key"]]} if f["key"] in prefill else f
            for f in base_fields
        ]
    else:
        fields = base_fields
    db_label = db_type.split("+")[0].title()
    return {
        "kind": "sql_session_env",
        "prompt": prompt or f"Enter your {db_label} connection details.",
        "submit_label": "Connect database",
        "fields": fields,
    }


def _parse_signal_tools(tool_executions: list[dict]) -> tuple[dict | None, list[dict] | None]:
    """Return (config_request, db_type_options) by inspecting signal tool calls."""
    config_request: dict | None = None
    db_type_options: list[dict] | None = None

    for te in tool_executions:
        name = te.get("source_id", "")
        args = te.get("arguments") or {}

        if name == "request_db_type_selection":
            db_type_options = _DB_TYPE_OPTIONS

        elif name == "request_db_connection_form":
            db_type = args.get("db_type", "") if isinstance(args, dict) else ""
            prompt = args.get("prompt", "") if isinstance(args, dict) else ""
            prefill = args.get("prefill") if isinstance(args, dict) else None
            config_request = _build_config_request(db_type, prompt, prefill)

    return config_request, db_type_options


# ── Server resolution ──────────────────────────────────────────────────────────

def _resolve_servers(
    session_env: dict[str, str] | None,
    server_env_overrides: dict[str, dict[str, str]] | None,
) -> tuple[list[str], dict[str, dict[str, str]]]:
    """Determine which MCP servers to connect to based on available credentials.

    Always includes "control-center". Adds "sql-mcp" when session_env contains
    any key starting with SQL_DB_, and adds "github" when server_env_overrides
    already contains a github entry with a GITHUB_PERSONAL_ACCESS_TOKEN.

    Returns (servers, overrides) where overrides is a merged dict ready to pass
    to build_agent_from_registry.
    """
    servers: list[str] = ["control-center"]
    overrides: dict[str, dict[str, str]] = dict(server_env_overrides or {})

    # Include sql-mcp if SQL connection details are available in session
    if session_env:
        sql_vars = {k: v for k, v in session_env.items() if k.startswith("SQL_DB_")}
        if sql_vars:
            servers.append("sql-mcp")
            existing_sql = dict(overrides.get("sql-mcp", {}))
            existing_sql.update(sql_vars)
            overrides["sql-mcp"] = existing_sql

    # Include github if a token is already in overrides
    github_overrides = overrides.get("github", {})
    if github_overrides.get("GITHUB_PERSONAL_ACCESS_TOKEN"):
        servers.append("github")

    return servers, overrides


# ── Public entry point ─────────────────────────────────────────────────────────

async def run_agent(
    *,
    message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    db: Session,
    user: Any,
    model: str | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
    session_env: dict[str, str] | None = None,
) -> AgentResult:
    """Run the control center agent for one user turn. Returns AgentResult."""
    full_prompt = _build_full_prompt(message, conversation_history, session_env)

    # Inject the real user's token so CC MCP server creates jobs owned by that user.
    merged_overrides = dict(server_env_overrides or {})
    cc_overrides = dict(merged_overrides.get("control-center", {}))
    cc_overrides["CC_USER_TOKEN"] = str(user.id)
    merged_overrides["control-center"] = cc_overrides

    servers, overrides = _resolve_servers(session_env, merged_overrides)

    try:
        agent = await build_agent_from_registry(
            environment="dev",
            server_names=servers,
            selection_prompt=None,
            model=model,
            server_env_overrides=overrides if overrides else None,
            max_tool_rounds=20,
            verbose=False,
        )
        try:
            response = await agent.run(full_prompt)
            tool_executions = [
                {
                    "exposed_name": item.exposed_name,
                    "server_name": item.server_name,
                    "source_id": item.source_id,
                    "arguments": item.arguments,
                    "parsed_result": item.parsed_result,
                }
                for item in response.tool_executions
            ]
        finally:
            await agent.cleanup()

        config_request, db_type_options = _parse_signal_tools(tool_executions)
        run_id = _extract_run_id(tool_executions)

        return AgentResult(
            response=response.final_text or "Done.",
            config_request=config_request,
            db_type_options=db_type_options,
            run_id=run_id,
        )

    except Exception as exc:
        logger.error("Agent error: %s", exc)
        return AgentResult(response=f"Sorry, something went wrong: {exc}")
