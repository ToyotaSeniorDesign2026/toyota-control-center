from __future__ import annotations

"""Agent-driven chat: MCPAgent + Control Center MCP server."""

<<<<<<< HEAD
import logging
=======
import json
import logging
from dataclasses import dataclass, field
>>>>>>> polishing-agent-chat
from typing import Any

from sqlalchemy.orm import Session

from app.services.chat_mcp_service import run_prompt_native_mcp

logger = logging.getLogger(__name__)

<<<<<<< HEAD
_SYSTEM_PROMPT = """\
You are CC Assistant for the Toyota Control Center.
You help users manage automated jobs and monitor run history.

CAPABILITIES (tools available):
- list_jobs        — see all registered jobs (filter by type or status)
- get_job          — get full details for one job
- list_runs        — see recent runs (optionally filtered by job)
- get_run_status   — check the current status of a specific run
- trigger_run      — kick off a new run for a job

BEHAVIOR:
- Be concise — one to three sentences unless more detail is clearly needed.
- Always call a tool first when the user asks about jobs or runs.
- After triggering a run, confirm the run ID and status.
- If a tool returns an error, explain it plainly and suggest next steps.
"""


def _build_prompt(message: str, conversation_history: list[dict[str, Any]] | None) -> str:
    parts = [_SYSTEM_PROMPT, ""]
=======
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
You are CC Assistant for the Toyota Control Center.
You help users manage automated jobs, monitor run history, and create new jobs.

AVAILABLE TOOLS:
- list_jobs                  — list all registered jobs (filter by type or status)
- get_job                    — get full details for a specific job
- list_runs                  — see recent run history
- get_run_status             — check the status of a specific run
- trigger_run                — kick off an existing job by its ID
- request_db_type_selection  — show the user a database type picker (use when DB type is unknown)
- request_db_connection_form — show the user a credentials form (use when DB type is known)
- create_sql_job             — create a new SQL job (only once ALL required fields are known)

GENERAL BEHAVIOR:
- Be concise — one to three sentences unless more detail is clearly needed.
- Always call a tool first when the user asks about existing jobs or runs.
- After triggering a run, confirm the run ID and status in your reply.
- If a tool returns an error, explain it plainly and suggest next steps.
- If the user asks to run an existing job by name, call list_jobs first to get the ID, then call trigger_run.

SQL JOB CREATION WORKFLOW — follow these steps in order, do not skip ahead:

  STEP 1 — Understand the request:
    Ask for (or confirm) the job name and what the SQL query should do.
    A plain-English description is fine; you will convert it to SQL internally.

  STEP 2 — Determine the database type:
    • If the user has already told you the database type → go to STEP 3.
    • Otherwise → call request_db_type_selection() and say "Which database are you connecting to?"
      Then STOP and wait for the user to select a type before proceeding.

  STEP 3 — Collect connection credentials:
    Call request_db_connection_form(db_type=<the driver string>) and say
    "Please fill in the connection details below."
    Then STOP and wait for the user to submit the form before proceeding.

  STEP 4 — Create the job:
    Once the SESSION CONNECTION DETAILS section below is populated, call create_sql_job() using:
      • name        — from the conversation
      • query       — the SQL query (translate plain English if needed)
      • db_driver   — the driver you used in request_db_connection_form
      • host        — SQL_DB_HOST from session (empty string for SQLite)
      • port        — SQL_DB_PORT from session (empty string for SQLite/Snowflake)
      • database    — SQL_DB_DATABASE from session
      • username    — SQL_DB_USERNAME from session (empty string for SQLite)
      • password    — SQL_DB_PASSWORD from session (empty string for SQLite)
    After creation, confirm the job name and offer to trigger it.

IMPORTANT:
- Never invent or assume connection credentials.
- Do not call create_sql_job() unless SESSION CONNECTION DETAILS is populated below.
- When the user sends a raw driver string (e.g. "postgresql+psycopg") as their entire message,
  it means they selected that database type from the picker — proceed immediately to STEP 3.
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
>>>>>>> polishing-agent-chat
    for turn in conversation_history or []:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
    parts.append(f"User: {message}")
    return "\n".join(parts)


<<<<<<< HEAD
=======
# ── Tool-call inspection ───────────────────────────────────────────────────────

def _extract_run_id(tool_executions: list[dict]) -> str | None:
    for te in tool_executions:
        if te.get("remote_name") != "trigger_run":
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


def _build_config_request(db_type: str, prompt: str) -> dict:
    fields = _CONNECTION_FIELDS.get(db_type, _DEFAULT_CONNECTION_FIELDS)
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
        name = te.get("remote_name", "")
        args = te.get("arguments") or {}

        if name == "request_db_type_selection":
            db_type_options = _DB_TYPE_OPTIONS

        elif name == "request_db_connection_form":
            db_type = args.get("db_type", "") if isinstance(args, dict) else ""
            prompt = args.get("prompt", "") if isinstance(args, dict) else ""
            config_request = _build_config_request(db_type, prompt)

    return config_request, db_type_options


# ── Public entry point ─────────────────────────────────────────────────────────

>>>>>>> polishing-agent-chat
async def run_agent(
    *,
    message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    db: Session,
    user: Any,
    model: str | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
<<<<<<< HEAD
) -> str:
    """Run the control center agent for one user turn. Returns the final text reply."""
    full_prompt = _build_prompt(message, conversation_history)
=======
    session_env: dict[str, str] | None = None,
) -> AgentResult:
    """Run the control center agent for one user turn. Returns AgentResult."""
    full_prompt = _build_full_prompt(message, conversation_history, session_env)
>>>>>>> polishing-agent-chat

    try:
        result = await run_prompt_native_mcp(
            message=full_prompt,
            server_names=["control-center"],
            model=model,
            server_env_overrides=server_env_overrides,
        )
<<<<<<< HEAD
        return result.response or "Done."
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        return f"Sorry, something went wrong: {exc}"
=======

        config_request, db_type_options = _parse_signal_tools(result.tool_executions)
        run_id = _extract_run_id(result.tool_executions)

        return AgentResult(
            response=result.response or "Done.",
            config_request=config_request,
            db_type_options=db_type_options,
            run_id=run_id,
        )

    except Exception as exc:
        logger.error("Agent error: %s", exc)
        return AgentResult(response=f"Sorry, something went wrong: {exc}")
>>>>>>> polishing-agent-chat
