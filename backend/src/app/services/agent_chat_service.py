from __future__ import annotations

"""Agent-driven chat: MCPAgent + Control Center MCP server."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

_GITHUB_KEYWORDS = re.compile(
    r"\bgithub\b|\brepo(?:sitory)?\b|\bcommit\b|\bpush\b|\.sql\s+(?:to|in|into)\b",
    re.IGNORECASE,
)

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
    secret_request: dict | None = None


# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are CC Assistant for the Toyota Control Center — a platform for managing, scheduling, and running automated data jobs.

Be concise. Always use your available tools to answer questions about jobs and runs; never guess at IDs or status.

CRITICAL — full task sequence: when a task involves SQL and/or GitHub, follow these steps in order — do NOT skip or reorder:

Step 1 — DATABASE: If SQL connection details are missing from the session context, call request_db_type_selection, then request_db_connection_form. When calling request_db_connection_form, pass a prefill dict with any connection values the user already mentioned in their message (database name → SQL_DB_DATABASE, host → SQL_DB_HOST, port → SQL_DB_PORT, username → SQL_DB_USERNAME). For example, if the user said "the customer_accounts database", pass prefill={"SQL_DB_DATABASE": "customer_accounts"}. Say "Please fill in your database connection details below." and STOP. Do not continue until the user submits the form.

Step 2 — GITHUB TOKEN: If the task involves writing to GitHub AND the GITHUB STATUS below says NOT connected, call request_github_token immediately. Say "Please enter your GitHub Personal Access Token below." and STOP. Do not continue until the user submits the token. You MUST do this before inspecting schema or creating any job.

Step 3 — SCHEMA: Once you have both DB credentials and the GitHub token (if needed), inspect the schema: call list_tables, then describe_table for relevant tables. Use ONLY the real table and column names found — never guess.

Step 4 — CONFIRM: Draft the SQL query. Present a confirmation summary with all fields (name, query, db_driver, host, port, database, username, environment, run_type, schedule, schedule_end_date if applicable, and github_repo/path/branch if applicable). Wait for user approval.

Step 5 — CREATE: Call create_sql_job with all required fields EXCEPT schedule/schedule_end_date. Also pass github_repo, github_path, github_branch, and github_token (from GITHUB_PERSONAL_ACCESS_TOKEN in the session context) when applicable. Do not call create_or_update_file directly — the run handles the GitHub write.

Step 5b — SCHEDULE (scheduled jobs only): If run_type is 'scheduled', you MUST call schedule_job immediately after create_sql_job using the job ID it returned. Pass:
  - cron_expression: the 5-part cron string (translate "every weekday at 8 AM" → "0 8 * * 1-5", etc.)
  - end_date: ISO date from TODAY'S DATE context (e.g. if user says "until May 20th" and today is 2026-05-06, pass "2026-05-20"). Leave empty if no end date was specified.
  Do NOT call trigger_run for scheduled jobs. Tell the user when the job will next run.

Step 5c — RUN (manual jobs only): If run_type is 'manual', call trigger_run with the job ID to execute it immediately.
"""


def _session_env_section(session_env: dict[str, str] | None, github_token: str | None = None) -> str:
    lines: list[str] = []
    if session_env:
        lines.append("SESSION CONNECTION DETAILS (user-provided — use these when calling create_sql_job):")
        for key, value in session_env.items():
            lines.append(f"  {key} = {value}")
    if github_token:
        lines.append(f"  GITHUB_PERSONAL_ACCESS_TOKEN = {github_token}")
    return "\n".join(lines) if lines else ""


def _build_full_prompt(
    message: str,
    conversation_history: list[dict[str, Any]] | None,
    session_env: dict[str, str] | None,
    github_available: bool = False,
    github_token: str | None = None,
) -> str:
    from datetime import date as _date
    today_iso = _date.today().isoformat()

    env_block = _session_env_section(session_env, github_token)
    github_block = (
        "GITHUB STATUS: connected — GitHub tools (create_or_update_file, etc.) are available."
        if github_available
        else "GITHUB STATUS: NOT connected — you have NO GitHub tools. If the user wants to write to GitHub, call request_github_token immediately and then stop."
    )
    date_block = f"TODAY'S DATE: {today_iso} — use this when resolving relative dates like 'until May 20th' into ISO dates (e.g. '{today_iso[:4]}-05-20')."
    system = _SYSTEM_PROMPT + "\n\n" + date_block + "\n\n" + github_block + ("\n\n" + env_block if env_block else "")

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
        if te.get("remote_name") != "trigger_run":
            continue
        result = te.get("parsed_result")
        # The adapter's parse_result() returns a plain string (joined text content).
        # Fall back to list-of-blocks and raw-dict forms for forward compatibility.
        if isinstance(result, str):
            try:
                return json.loads(result).get("id")
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        elif isinstance(result, list):
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


def _parse_signal_tools(
    tool_executions: list[dict],
) -> tuple[dict | None, list[dict] | None, dict | None]:
    """Return (config_request, db_type_options, secret_request) from signal tool calls."""
    config_request: dict | None = None
    db_type_options: list[dict] | None = None
    secret_request: dict | None = None

    for te in tool_executions:
        name = te.get("remote_name", "")
        args = te.get("arguments") or {}

        if name == "request_db_type_selection":
            db_type_options = _DB_TYPE_OPTIONS

        elif name == "request_db_connection_form":
            db_type = args.get("db_type", "") if isinstance(args, dict) else ""
            prompt = args.get("prompt", "") if isinstance(args, dict) else ""
            prefill = args.get("prefill") if isinstance(args, dict) else None
            config_request = _build_config_request(db_type, prompt, prefill)

        elif name == "request_github_token":
            secret_request = {
                "kind": "github_personal_access_token",
                "prompt": "Enter your GitHub Personal Access Token to write to a repository.",
                "submit_label": "Use token",
            }

    return config_request, db_type_options, secret_request


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
    user: Any,
    model: str | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
    session_env: dict[str, str] | None = None,
) -> AgentResult:
    """Run the control center agent for one user turn. Returns AgentResult."""
    # Inject the real user's token so CC MCP server creates jobs owned by that user.
    merged_overrides = dict(server_env_overrides or {})
    cc_overrides = dict(merged_overrides.get("control-center", {}))
    cc_overrides["CC_USER_TOKEN"] = str(user.id)
    merged_overrides["control-center"] = cc_overrides

    servers, overrides = _resolve_servers(session_env, merged_overrides)
    github_available = "github" in servers
    github_token = overrides.get("github", {}).get("GITHUB_PERSONAL_ACCESS_TOKEN") if github_available else None

    # If the task mentions GitHub but no PAT has been provided yet, ask for it
    # immediately — don't hand off to the agent, which may skip this step.
    if not github_available and _GITHUB_KEYWORDS.search(message):
        return AgentResult(
            response="Please enter your GitHub Personal Access Token below.",
            secret_request={
                "kind": "github_personal_access_token",
                "prompt": "Enter your GitHub Personal Access Token to write to a repository.",
                "submit_label": "Use token",
            },
        )

    full_prompt = _build_full_prompt(message, conversation_history, session_env, github_available, github_token)

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
                    "framework_name": item.framework_name,
                    "server_name": item.server_name,
                    "remote_name": item.remote_name,
                    "arguments": item.arguments,
                    "parsed_result": item.parsed_result,
                }
                for item in response.tool_executions
            ]
        finally:
            await agent.cleanup()

        config_request, db_type_options, secret_request = _parse_signal_tools(tool_executions)
        run_id = _extract_run_id(tool_executions)

        return AgentResult(
            response=response.final_text or "Done.",
            config_request=config_request,
            db_type_options=db_type_options,
            run_id=run_id,
            secret_request=secret_request,
        )

    except Exception as exc:
        err_str = str(exc)
        if "429" in err_str or "rate_limit" in err_str.lower() or "rate limit" in err_str.lower():
            wait_match = re.search(r"try again in\s+([\d.]+)s", err_str, re.IGNORECASE)
            suggested = float(wait_match.group(1)) if wait_match else 0.0
            suggested_str = f" (wait ~{int(suggested) + 1}s)" if suggested > 0 else ""
            logger.warning("Rate limit hit — not retrying to avoid duplicate tool calls: %s", exc)
            return AgentResult(
                response=f"The AI service is temporarily rate-limited{suggested_str}. Please resend your message in a moment."
            )
        logger.error("Agent error: %s", exc)
        return AgentResult(response=f"Sorry, something went wrong: {exc}")
