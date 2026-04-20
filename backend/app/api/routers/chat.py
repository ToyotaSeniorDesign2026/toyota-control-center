"""Chat API router for handling AI chat messages."""

import logging
import os
import re
import base64
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends
import httpx
from pydantic import BaseModel

from app.api.deps import get_db
from app.services.chat_service import get_chat_service
from app.services.field_extraction_service import get_field_extraction_service
from app.services.chat_job_service import maybe_run_sql_job_from_chat, run_resource_by_id
from app.services.chat_mcp_service import (
    needs_github_personal_access_token,
    run_prompt_native_mcp,
    should_run_prompt_native_mcp,
)

router = APIRouter()
logger = logging.getLogger(__name__)
SQL_RUN_REQUEST_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b", re.IGNORECASE)
RUN_JOB_MARKER_PATTERN = re.compile(r'\[RUN_JOB:([a-zA-Z0-9\-_]+)\]')
SQL_RUN_CONTEXT_PATTERN = re.compile(r"\b(job|sql|query|resource)\b", re.IGNORECASE)
AFFIRMATIVE_RUN_RESPONSE_PATTERN = re.compile(r"^(yes|yep|yeah|sure|please do|go ahead|run it|run now|do it)[\s.!?]*$", re.IGNORECASE)
REPO_CONNECTION_REQUEST_PATTERN = re.compile(r"\b(connect|link|attach|add)\b.*\b(github|repo|repository)\b|\b(github|repo|repository)\b.*\b(connect|link|attach|add)\b", re.IGNORECASE)
REPO_SLUG_PATTERN = re.compile(r"(?:github\.com[/:])?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?(?=$|[\s/#?])", re.IGNORECASE)
REPO_REF_PATTERN = re.compile(r"\b(?:branch|ref)\s+([A-Za-z0-9._/-]+)\b", re.IGNORECASE)
REPO_PATH_PATTERN = re.compile(r"\b(?:path|folder|directory)\s+([^\s,]+)", re.IGNORECASE)
GITHUB_REPO_OPTIONS_LIMIT = 12
SQL_CONNECT_REQUEST_PATTERN = re.compile(
    r"\b(sql|database|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b.*\b(connect|connection|query|run|execute|select|insert|update|delete)\b|\b(connect|connection|query|run|execute|select|insert|update|delete)\b.*\b(sql|database|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b",
    re.IGNORECASE,
)
SQL_GITHUB_WRITE_PATTERN = re.compile(
    r"\b(write|save|commit|push|add|store)\b.{0,60}\b(sql|query|script)\b.{0,60}\b(github|repo|repository|file|\.sql)\b"
    r"|\b(github|repo|repository)\b.{0,60}\b(write|save|commit|push|add)\b.{0,60}\b(sql|query|script)\b"
    r"|\b(sql|query)\b.{0,60}\b(github|repo|repository|\.sql)\b",
    re.IGNORECASE,
)
ENV_VAR_NAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
# Patterns for detecting which connection field was last asked in conversation
_ASKED_HOST_PATTERN = re.compile(r"\bdatabase host\b|\bdb host\b|\bhost address\b|\bserver host\b", re.IGNORECASE)
_ASKED_PORT_PATTERN = re.compile(r"\bdatabase port\b|\bport number\b", re.IGNORECASE)
_ASKED_DATABASE_PATTERN = re.compile(r"\bdatabase name\b|\bdb name\b", re.IGNORECASE)
_ASKED_USERNAME_PATTERN = re.compile(r"\bdatabase username\b|\bdb username\b", re.IGNORECASE)
_ASKED_PASSWORD_PATTERN = re.compile(r"\bdatabase password\b|\bdb password\b", re.IGNORECASE)
_ASKED_GW_QUERY_PATTERN = re.compile(r"\bwhat sql query\b|\bsql query should i write\b|\bsql content\b", re.IGNORECASE)
_ASKED_GW_REPO_PATTERN = re.compile(r"\bwhich (github )?repository\b|\bwhich repo\b|\bowner/repo\b", re.IGNORECASE)
_ASKED_GW_PATH_PATTERN = re.compile(r"\bfile path\b|\bfile name\b|\bwhich file\b", re.IGNORECASE)
_SIMPLE_VALUE_PATTERN = re.compile(r"^(?:(?:it[''`]?s|the \w+ is|use|is|just)\s+)?([^\s,;]+)\s*$", re.IGNORECASE)
_PORT_DIGITS_PATTERN = re.compile(r"\b(\d{2,5})\b")
_ASKED_SQL_QUERY_PATTERN = re.compile(
    r"\bsql query\b|\bquery (?:to run|you would like|to execute|should i)\b|\bwhat query\b|\bprovide.*query\b|\bspecify.*query\b",
    re.IGNORECASE,
)
_SQL_STATEMENT_PATTERN = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|SHOW|DESCRIBE|EXPLAIN)\b",
    re.IGNORECASE,
)
_NL_TABLE_EXTRACT_PATTERN = re.compile(
    r"\b(?:get|fetch|show|list|select|retrieve|find|display)\b\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(\w+?)(?:\s+(?:from|in|records?|data|table|entries?|rows?)|\s*$)",
    re.IGNORECASE,
)
_SQL_FIELD_QUESTIONS: dict[str, str] = {
    "job_name": "What name would you like to give this job?",
    "owner": "Who is the owner of this job?",
    "run_type": "Should this be a **one-time** (manual) run or a **scheduled** job?",
    "schedule": "What schedule should I use? (e.g., `every day at 9am`, `30 8 * * 1-5`)",
    "query": 'What SQL query would you like to run? (Plain English is fine, e.g. "get all users")',
    "database": "What is the database name?",
    "connection_id": "What is the connection ID? (type `skip` to leave empty)",
    "username": "What is the database username?",
    "password": "What is the database password?",
    "host": "What is the database host? (e.g., `localhost` or `db.example.com`)",
    "port": "What is the database port? (e.g., `5432` for PostgreSQL)",
}
_SQL_FLOW_ASKED_PATTERNS: dict[str, re.Pattern] = {
    "job_name": re.compile(r"\bjob.*name\b|\bname.*(?:this )?job\b|\bwhat name\b|\bgive this job\b", re.IGNORECASE),
    "owner": re.compile(r"\bwho is the owner\b|\bowner of this job\b|\bjob.*owner\b", re.IGNORECASE),
    "run_type": re.compile(r"\bone-time.*run\b|\bscheduled job\b|\brun type\b|\bmanual.*or.*scheduled\b|\bone-time.*or.*scheduled\b", re.IGNORECASE),
    "schedule": re.compile(r"\bwhat schedule\b|\bschedule should i use\b|\bschedule.*use\b", re.IGNORECASE),
    "query": re.compile(r"\bsql query.*run\b|\bquery.*run\b|\bwhat.*query\b|\bplain english\b|\bdescribe it\b|\bquery.*like to run\b", re.IGNORECASE),
    "database": re.compile(r"\bdatabase name\b|\bdb name\b|\bwhat is the database name\b", re.IGNORECASE),
    "connection_id": re.compile(r"\bconnection id\b|\bconnection_id\b", re.IGNORECASE),
    "username": re.compile(r"\bdatabase username\b|\bdb username\b|\bwhat is the.*username\b", re.IGNORECASE),
    "password": re.compile(r"\bdatabase password\b|\bdb password\b|\bwhat is the.*password\b", re.IGNORECASE),
    "host": re.compile(r"\bdatabase host\b|\bdb host\b|\bhost address\b|\bserver host\b|\bwhat is the.*host\b", re.IGNORECASE),
    "port": re.compile(r"\bdatabase port\b|\bport number\b|\bwhat is the.*port\b", re.IGNORECASE),
    "confirm": re.compile(r"\bshall i create\b|\bcreate.*run.*now\b|\bcreate and run\b|\bcreate this scheduled\b", re.IGNORECASE),
}
_AFFIRMATIVE_RESPONSE_PATTERN = re.compile(
    r"^(yes|yep|yeah|sure|please|go ahead|do it|run it|create it|ok|okay|confirm|y|sounds good|looks good)\b",
    re.IGNORECASE,
)
REPO_ENV_DISCOVERY_FILES = [
    ".env.example",
    ".env",
    "backend/.env.example",
    "backend/.env",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "README.md",
]
SQL_SESSION_ENV_FIELDS = [
    {
        "key": "SQL_DB_HOST",
        "label": "Database host",
        "placeholder": "localhost",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PORT",
        "label": "Database port",
        "placeholder": "5432",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_DATABASE",
        "label": "Database name",
        "placeholder": "control_center",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_USERNAME",
        "label": "Database username",
        "placeholder": "postgres",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PASSWORD",
        "label": "Database password",
        "placeholder": "Password",
        "secret": True,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_CONNECTION_ID",
        "label": "Connection ID",
        "placeholder": "postgres",
        "secret": False,
        "required": False,
    },
]
SQL_REQUIRED_JOB_FIELDS = [
    ("job_name", "job/resource name"),
    ("owner", "owner"),
    ("target_environment", "target environment"),
    ("run_type", "run type"),
]


def _should_extract_fields(request: "ChatRequest", job_creation_intent: bool) -> bool:
    if not job_creation_intent:
        return True

    message = (request.message or "").lower()
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type", "")).strip().lower()

    sql_keywords = ("sql", "query", "run", "execute", "launch", "trigger")
    if draft_type == "sql":
        return True
    if any(keyword in message for keyword in sql_keywords):
        return True
    return False


def _has_sql_draft(request: "ChatRequest") -> bool:
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type", "")).strip().lower()
    return draft_type == "sql"


def _is_sql_github_write_request(request: "ChatRequest") -> bool:
    """Return True when the user wants to write a SQL query into a GitHub repository."""
    message = request.message or ""
    draft = request.current_draft_data or {}
    if str(draft.get("sql_subtype") or "").strip().lower() == "sql_github_write":
        return True
    return bool(SQL_GITHUB_WRITE_PATTERN.search(message))


def _get_missing_sql_connection_details(draft: dict, session_env: dict) -> list[str]:
    """Return names of DB connection fields not yet collected in draft config or session_env."""
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    missing = []
    if not (session_env.get("SQL_DB_HOST") or config.get("host")):
        missing.append("host")
    if not (session_env.get("SQL_DB_PORT") or config.get("port")):
        missing.append("port")
    if not (session_env.get("SQL_DB_DATABASE") or config.get("database")):
        missing.append("database")
    if not (session_env.get("SQL_DB_USERNAME") or config.get("username")):
        missing.append("username")
    if not (session_env.get("SQL_DB_PASSWORD") or config.get("password")):
        missing.append("password")
    return missing


def _connection_detail_question(field: str) -> str:
    return {
        "host": "What is the database host? (e.g., `localhost` or `db.example.com`)",
        "port": "What is the database port? (e.g., `5432` for PostgreSQL)",
        "database": "What is the database name?",
        "username": "What is the database username?",
        "password": "What is the database password?",
    }.get(field, f"What is the `{field}`?")


def _last_asked_connection_detail(conversation_history: list[dict] | None) -> str | None:
    """Return which SQL connection field the assistant last asked for, scanning history backwards."""
    if not conversation_history:
        return None
    for msg in reversed(conversation_history):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        if _ASKED_HOST_PATTERN.search(content):
            return "host"
        if _ASKED_PORT_PATTERN.search(content):
            return "port"
        if _ASKED_DATABASE_PATTERN.search(content):
            return "database"
        if _ASKED_USERNAME_PATTERN.search(content):
            return "username"
        if _ASKED_PASSWORD_PATTERN.search(content):
            return "password"
        return None
    return None


def _last_assistant_asked_for_sql_query(conversation_history: list[dict] | None) -> bool:
    """Return True when the most recent assistant message asked the user for a SQL query."""
    if not conversation_history:
        return False
    for msg in reversed(conversation_history):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        return bool(_ASKED_SQL_QUERY_PATTERN.search(content))
    return False


def _coerce_to_sql(message: str) -> str:
    """Return message as-is if it looks like SQL, otherwise attempt natural-language → SQL."""
    stripped = message.strip()
    if _SQL_STATEMENT_PATTERN.match(stripped):
        return stripped
    _NL_STOPWORDS = {"all", "me", "data", "records", "result", "results", "rows", "everything",
                     "from", "database", "db", "the", "some", "those", "these", "any"}
    m = _NL_TABLE_EXTRACT_PATTERN.search(stripped)
    if m:
        table = m.group(1).lower()
        if table not in _NL_STOPWORDS:
            return f"SELECT * FROM {table};"
    return stripped


def _openai_extract_sql_fields(message: str, draft: dict, history: list[dict] | None) -> dict[str, Any]:
    """Use OpenAI to extract any SQL job fields present in the user's message.
    Returns a (possibly empty) dict of recognised fields. Never raises — returns {} on any error."""
    try:
        from app.core.config import settings
        if not settings.openai_api_key:
            return {}
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        existing = {k: v for k, v in draft.items() if v and k not in {"config", "_connection_id_asked"}}
        config = draft.get("config") or {}
        for fld in ("host", "port", "database", "username", "password", "query", "connection_id"):
            if config.get(fld):
                existing[fld] = config[fld]

        system_prompt = (
            "You are a field extractor for SQL job creation. "
            "Given the user's message, extract ONLY fields that are explicitly stated or clearly described.\n"
            "Extractable fields: job_name, owner, run_type (manual|scheduled), schedule, "
            "query (valid SQL), database, connection_id, username, password, host, port.\n"
            "Rules:\n"
            "- ONLY extract a field if the user's message directly provides or clearly describes its value.\n"
            "- For 'query': only set this if the user states a specific SQL query or describes a specific "
            "table/operation (e.g. 'SELECT * FROM orders' or 'get all orders'). "
            "NEVER invent or assume a query from vague phrases like 'run a SQL query'.\n"
            "- For 'run_type': output exactly 'manual' or 'scheduled'.\n"
            "- If unsure, omit the field entirely. Returning an empty object {} is perfectly valid.\n"
            "- Return a JSON object with only the found fields.\n"
            f"Already-known fields (do not repeat unless the user explicitly changes them): {existing}"
        )
        msgs = [{"role": "system", "content": system_prompt}]
        for h in (history or [])[-6:]:
            if isinstance(h, dict) and h.get("role") in {"user", "assistant"}:
                msgs.append({"role": h["role"], "content": str(h.get("content") or "")})
        msgs.append({"role": "user", "content": message})

        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=msgs,
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"},
        )
        import json
        raw = json.loads(resp.choices[0].message.content or "{}")
        if not isinstance(raw, dict):
            return {}
        # Sanitise: only accept known field names, apply _coerce_to_sql for query
        allowed = {"job_name", "owner", "run_type", "schedule", "query",
                   "database", "connection_id", "username", "password", "host", "port"}
        result: dict[str, Any] = {}
        for k, v in raw.items():
            if k not in allowed or not isinstance(v, str) or not v.strip():
                continue
            result[k] = _coerce_to_sql(v) if k == "query" else v.strip()
        if "run_type" in result and result["run_type"] not in {"manual", "scheduled", "triggered"}:
            del result["run_type"]
        return result
    except Exception:
        logger.debug("OpenAI SQL field extraction failed", exc_info=True)
        return {}


def _last_asked_sql_flow_field(conversation_history: list[dict] | None) -> str | None:
    """Return which SQL flow field the assistant last asked for, or 'confirm' at the summary step."""
    if not conversation_history:
        return None
    for msg in reversed(conversation_history):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        # Check confirm first — the summary message also contains field name labels like "Job Name:"
        if _SQL_FLOW_ASKED_PATTERNS["confirm"].search(content):
            return "confirm"
        for field, pattern in _SQL_FLOW_ASKED_PATTERNS.items():
            if field == "confirm":
                continue
            if pattern.search(content):
                return field
        return None
    return None


def _extract_sql_field_value(field: str, message: str) -> str | None:
    """Extract the value for a SQL flow field from the user's answer."""
    stripped = message.strip()
    if not stripped:
        return None
    if field == "run_type":
        lower = stripped.lower()
        if any(w in lower for w in ("schedule", "recurring", "cron", "periodic", "repeating")):
            return "scheduled"
        if any(w in lower for w in ("one-time", "one time", "manual", "once", "single")):
            return "manual"
        if lower in {"manual", "scheduled", "triggered"}:
            return lower
        return None
    if field == "port":
        m = _PORT_DIGITS_PATTERN.search(stripped)
        return m.group(1) if m else None
    if field == "query":
        return _coerce_to_sql(stripped)
    if field == "connection_id":
        if stripped.lower() in {"skip", "none", "no", "n/a", "na", "-"}:
            return "__skip__"
        m = _SIMPLE_VALUE_PATTERN.match(stripped)
        return m.group(1) if m else (stripped if len(stripped) <= 100 else None)
    if field in {"owner", "schedule", "job_name"}:
        return stripped if len(stripped) <= 200 else None
    m = _SIMPLE_VALUE_PATTERN.match(stripped)
    if m:
        return m.group(1)
    return stripped if " " not in stripped and len(stripped) <= 100 else None


def _next_missing_sql_field(draft: dict, session_env: dict) -> str | None:
    """Return the next field to collect in the SQL flow, or None when all are present."""
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    # Phase 1 – universal
    if not _non_empty_str(draft.get("job_name") or draft.get("name")):
        return "job_name"
    if not _non_empty_str(draft.get("owner")):
        return "owner"
    run_type = str(draft.get("run_type") or "").strip().lower()
    if not run_type:
        return "run_type"
    if run_type == "scheduled" and not _non_empty_str(draft.get("schedule") or config.get("schedule")):
        return "schedule"
    # Phase 2 – SQL-specific
    if not _non_empty_str(draft.get("query") or config.get("query")):
        return "query"
    if not _non_empty_str(draft.get("database") or config.get("database") or session_env.get("SQL_DB_DATABASE")):
        return "database"
    if not draft.get("_connection_id_asked") and not _non_empty_str(
        draft.get("connection_id") or config.get("connection_id") or session_env.get("SQL_CONNECTION_ID")
    ):
        return "connection_id"
    if not _non_empty_str(draft.get("username") or config.get("username") or session_env.get("SQL_DB_USERNAME")):
        return "username"
    if not _non_empty_str(draft.get("password") or config.get("password") or session_env.get("SQL_DB_PASSWORD")):
        return "password"
    if not _non_empty_str(draft.get("host") or config.get("host") or session_env.get("SQL_DB_HOST")):
        return "host"
    if not _non_empty_str(draft.get("port") or config.get("port") or session_env.get("SQL_DB_PORT")):
        return "port"
    return None


def _build_sql_job_summary(draft: dict, session_env: dict) -> str:
    """Build the confirmation summary shown before creating the job."""
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    job_name = _non_empty_str(draft.get("job_name") or draft.get("name")) or "—"
    owner = _non_empty_str(draft.get("owner")) or "—"
    run_type = str(draft.get("run_type") or "manual").strip().lower()
    schedule = _non_empty_str(draft.get("schedule") or config.get("schedule")) or ""
    query = _non_empty_str(draft.get("query") or config.get("query")) or "—"
    database = _non_empty_str(draft.get("database") or config.get("database") or session_env.get("SQL_DB_DATABASE")) or "—"
    connection_id = _non_empty_str(draft.get("connection_id") or config.get("connection_id") or session_env.get("SQL_CONNECTION_ID")) or ""
    username = _non_empty_str(draft.get("username") or config.get("username") or session_env.get("SQL_DB_USERNAME")) or "—"
    host = _non_empty_str(draft.get("host") or config.get("host") or session_env.get("SQL_DB_HOST")) or "—"
    port = _non_empty_str(draft.get("port") or config.get("port") or session_env.get("SQL_DB_PORT")) or "—"
    run_type_display = run_type.capitalize()
    if run_type == "scheduled" and schedule:
        run_type_display = f"Scheduled — `{schedule}`"
    lines = [
        "Here's a summary of the SQL job I'll create:\n",
        f"**Job Name:** {job_name}",
        f"**Owner:** {owner}",
        f"**Run Type:** {run_type_display}",
        "",
        "**SQL Query:**",
        f"```sql\n{query}\n```",
        f"**Database:** {database}",
        f"**Host:** {host}:{port}",
        f"**Username:** {username}",
    ]
    if connection_id:
        lines.append(f"**Connection ID:** {connection_id}")
    lines.append("")
    if run_type == "scheduled":
        lines.append("Shall I create this scheduled job? (yes / no)")
    else:
        lines.append("Shall I create and run this job now? (yes / no)")
    return "\n".join(lines)


def _extract_connection_detail_from_answer(field: str, message: str) -> str | None:
    stripped = message.strip()
    if not stripped or len(stripped) > 200:
        return None
    if field == "port":
        m = _PORT_DIGITS_PATTERN.search(stripped)
        return m.group(1) if m else None
    m = _SIMPLE_VALUE_PATTERN.match(stripped)
    if m:
        return m.group(1)
    return stripped if " " not in stripped else None


def _last_asked_github_write_field(conversation_history: list[dict] | None) -> str | None:
    """Return which GitHub-write field the assistant last asked for."""
    if not conversation_history:
        return None
    for msg in reversed(conversation_history):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = str(msg.get("content") or "")
        if _ASKED_GW_QUERY_PATTERN.search(content):
            return "query"
        if _ASKED_GW_REPO_PATTERN.search(content):
            return "repo"
        if _ASKED_GW_PATH_PATTERN.search(content):
            return "file_path"
        return None
    return None


def _build_github_write_mcp_prompt(query: str, repo: str, file_path: str, ref: str | None = None) -> str:
    branch_part = f" on branch `{ref}`" if ref else ""
    return (
        f"Write the following SQL content to the file `{file_path}` in GitHub repository `{repo}`{branch_part}. "
        "Create or update the file with an appropriate commit message such as 'Add SQL query file'.\n\n"
        f"SQL content to write:\n```sql\n{query}\n```"
    )


def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return None


def _is_explicit_sql_run_request(request: "ChatRequest") -> bool:
    message = request.message or ""
    draft = request.current_draft_data or {}
    if not _has_sql_draft(request):
        return False
    if draft.get("resource_id") and AFFIRMATIVE_RUN_RESPONSE_PATTERN.search(message.strip()):
        return True
    return bool(SQL_RUN_REQUEST_PATTERN.search(message) and SQL_RUN_CONTEXT_PATTERN.search(message))


def _deterministic_sql_fields(request: "ChatRequest") -> dict[str, Any]:
    message = (request.message or "").strip().lower()
    draft = request.current_draft_data or {}
    if str(draft.get("job_type", "")).strip().lower() != "sql":
        return {}

    fields: dict[str, Any] = {}

    if message in {"looks good", "that looks good", "yes", "yes looks good", "use it", "that works"}:
        previous_query = (
            draft.get("query")
            or (draft.get("config") if isinstance(draft.get("config"), dict) else {}).get("query")
            or (draft.get("params") if isinstance(draft.get("params"), dict) else {}).get("query")
        )
        if previous_query:
            fields["query"] = previous_query

    if "runs" in message and ("database" in message or "control-center" in message or "control center" in message):
        fields.update(
            {
                "job_type": "SQL",
                "query": "SELECT * FROM runs;",
            }
        )

    if "manual" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["run_type"] = "manual"

    if "create" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["creation_requested"] = True
        fields["run_after_create"] = True
        fields["action"] = "run"

    if "create" in message and "job" in message:
        fields["creation_requested"] = True

    return fields


def _deterministic_repo_connection_fields(request: "ChatRequest") -> dict[str, Any]:
    message = (request.message or "").strip()
    if not message:
        return {}

    if REPO_CONNECTION_REQUEST_PATTERN.search(message) is None:
        return {}

    repo_match = REPO_SLUG_PATTERN.search(message)
    if repo_match is None:
        return {"connection_intent": "connect_repo", "connector": "github", "provider": "github"}

    repo = repo_match.group(1).rstrip("/")
    ref_match = REPO_REF_PATTERN.search(message)
    path_match = REPO_PATH_PATTERN.search(message)
    repo_name = repo.split("/")[-1]

    fields: dict[str, Any] = {
        "connection_intent": "connect_repo",
        "name": repo_name,
        "kind": "runtime",
        "type": "repo_connection",
        "connector": "github",
        "repo": repo,
        "provider": "github",
        "server_names": ["github"],
    }
    if ref_match is not None:
        fields["ref"] = ref_match.group(1)
    if path_match is not None:
        fields["path"] = path_match.group(1)
    return fields


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    conversation_history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None
    current_draft_data: Optional[dict[str, Any]] = None  # Current job draft state
    available_resources: Optional[list[dict[str, Any]]] = None
    github_personal_access_token: Optional[str] = None
    session_env: Optional[dict[str, str]] = None


class SecretRequest(BaseModel):
    kind: str
    prompt: str
    submit_label: Optional[str] = None


class RepositoryOption(BaseModel):
    full_name: str
    owner: str
    name: str
    default_branch: str | None = None
    private: bool = False


class ConfigRequestField(BaseModel):
    key: str
    label: str
    placeholder: str | None = None
    secret: bool = False
    required: bool = True
    group: str | None = None


class ConfigRequest(BaseModel):
    kind: str
    prompt: str
    submit_label: Optional[str] = None
    fields: list[ConfigRequestField]
    repository_hints: Optional[list[str]] = None


class ChatResponse(BaseModel):
    """Response from chat API."""
    response: str
    job_creation_intent: Optional[bool] = None  # True if user wants to create a job
    extracted_fields: Optional[dict[str, Any]] = None  # Extracted job fields from message
    resource_id: Optional[str] = None
    run_id: Optional[str] = None
    run_status: Optional[str] = None
    sql_job_executed: Optional[bool] = None
    mcp_tool_executed: Optional[bool] = None
    mcp_servers: Optional[list[str]] = None
    mcp_tool_executions: Optional[list[dict[str, Any]]] = None
    secret_request: Optional[SecretRequest] = None
    repository_options: Optional[list[RepositoryOption]] = None
    config_request: Optional[ConfigRequest] = None


async def _list_github_repository_options(personal_access_token: str) -> list[RepositoryOption]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {personal_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "sort": "updated",
        "per_page": str(GITHUB_REPO_OPTIONS_LIMIT),
        "affiliation": "owner,collaborator,organization_member",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get("https://api.github.com/user/repos", headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        return []

    options: list[RepositoryOption] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        full_name = str(item.get("full_name") or "").strip()
        owner = str((item.get("owner") or {}).get("login") or "").strip()
        name = str(item.get("name") or "").strip()
        if not full_name or not owner or not name:
            continue
        options.append(
            RepositoryOption(
                full_name=full_name,
                owner=owner,
                name=name,
                default_branch=str(item.get("default_branch") or "").strip() or None,
                private=bool(item.get("private", False)),
            )
        )
    return options


def _looks_like_sql_connect_request(request: "ChatRequest") -> bool:
    if _is_sql_github_write_request(request):
        return False
    message = request.message or ""
    draft = request.current_draft_data or {}
    draft_type = str(draft.get("job_type") or draft.get("type") or "").strip().lower()
    if draft_type == "sql" and str(draft.get("sql_subtype") or "").strip().lower() != "sql_github_write":
        return True
    return SQL_CONNECT_REQUEST_PATTERN.search(message) is not None


def _effective_session_env(request: "ChatRequest") -> dict[str, str]:
    session_env = request.session_env or {}
    return {str(key): str(value) for key, value in session_env.items() if str(value).strip()}


def _build_sql_connection_string(session_env: dict[str, str]) -> str | None:
    host = session_env.get("SQL_DB_HOST")
    port = session_env.get("SQL_DB_PORT")
    database = session_env.get("SQL_DB_DATABASE")
    username = session_env.get("SQL_DB_USERNAME")
    password = session_env.get("SQL_DB_PASSWORD")
    if not all([host, port, database, username, password]):
        return None
    return f"Host={host};Port={port};Database={database};Username={username};Password={password}"


def _missing_sql_session_env(session_env: dict[str, str]) -> list[ConfigRequestField]:
    missing: list[ConfigRequestField] = []
    derived_connection_string = _build_sql_connection_string(session_env)
    for field in SQL_SESSION_ENV_FIELDS:
        key = field["key"]
        if session_env.get(key):
            continue
        if field.get("group") == "sql_connection_string" and derived_connection_string:
            continue
        missing.append(ConfigRequestField(**field))
    return missing


def _merge_sql_fields(
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> dict[str, Any]:
    draft = current_draft or {}
    merged: dict[str, Any] = {
        **draft,
        **(extracted_fields or {}),
    }
    draft_config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    extracted_config = extracted_fields.get("config") if isinstance((extracted_fields or {}).get("config"), dict) else {}
    merged["config"] = {
        **draft_config,
        **extracted_config,
    }
    draft_params = draft.get("params") if isinstance(draft.get("params"), dict) else {}
    extracted_params = extracted_fields.get("params") if isinstance((extracted_fields or {}).get("params"), dict) else {}
    merged["params"] = {
        **draft_params,
        **extracted_params,
    }
    return merged


def _missing_sql_job_fields(
    extracted_fields: dict[str, Any],
    current_draft: dict[str, Any] | None,
) -> list[str]:
    merged = _merge_sql_fields(extracted_fields, current_draft)
    config = merged.get("config") if isinstance(merged.get("config"), dict) else {}

    missing: list[str] = []
    job_name = str(merged.get("job_name") or merged.get("name") or "").strip()
    owner = str(merged.get("owner") or "").strip()
    target_environment = str(
        merged.get("target_environment") or merged.get("environment") or config.get("target_environment") or ""
    ).strip()
    run_type = str(merged.get("run_type") or "").strip().lower()
    schedule = str(merged.get("schedule") or config.get("schedule") or "").strip()

    if not job_name:
        missing.append("job_name")
    if not owner:
        missing.append("owner")
    if not target_environment:
        missing.append("target_environment")
    if not run_type:
        missing.append("run_type")
    if run_type == "scheduled" and not schedule:
        missing.append("schedule")
    return missing


def _sql_followup_response(
    request: "ChatRequest",
    extracted_fields: dict[str, Any],
    session_env: dict[str, str],
) -> str | None:
    if not _looks_like_sql_connect_request(request):
        return None

    draft = request.current_draft_data or {}
    draft_config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    extracted_config = extracted_fields.get("config") if isinstance((extracted_fields or {}).get("config"), dict) else {}
    merged_config = {**draft_config, **extracted_config}

    has_connection = bool(
        (session_env.get("SQL_DB_HOST") or merged_config.get("host"))
        and (session_env.get("SQL_DB_PORT") or merged_config.get("port"))
        and (session_env.get("SQL_DB_DATABASE") or merged_config.get("database"))
        and (session_env.get("SQL_DB_USERNAME") or merged_config.get("username"))
        and (session_env.get("SQL_DB_PASSWORD") or merged_config.get("password"))
    )
    if not has_connection:
        return None

    merged = _merge_sql_fields(extracted_fields, request.current_draft_data)
    query = (
        str(merged.get("query") or "").strip()
        or str((merged.get("config") or {}).get("query") or "").strip()
        or str((merged.get("params") or {}).get("query") or "").strip()
    )
    connection_id = str(merged.get("connection_id") or session_env.get("SQL_CONNECTION_ID") or "").strip()

    if query:
        missing_job_fields = _missing_sql_job_fields(extracted_fields, request.current_draft_data)
        if missing_job_fields:
            next_field = missing_job_fields[0]
            if next_field == "job_name":
                return (
                    "I have the database connection details and the SQL query. "
                    f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
                    "Next I need the job/resource name you want to save and run this SQL job as."
                )
            if next_field == "owner":
                return (
                    "I have the SQL connection details, query, and job name. "
                    "Next I need the owner for this SQL job."
                )
            if next_field == "target_environment":
                return (
                    "I have the SQL connection details, query, job name, and owner. "
                    "Next I need the target environment for this job, like `dev`, `staging`, or `prod`."
                )
            if next_field == "run_type":
                return (
                    "I have the SQL connection details, query, job name, owner, and target environment. "
                    "Should this be a one-time run (`manual`), a `scheduled` recurring job, or `triggered`?"
                )
            if next_field == "schedule":
                return (
                    "This SQL job is marked as scheduled. What schedule should I use? "
                    "(e.g., `every day at 9am`, `30 8 * * 1-5`)"
                )

        return (
            "I have the database connection details and the SQL query. "
            f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
            "I also have the required job fields. Do you want me to create the job and run it now?"
        )

    return (
        "I have the database connection details. "
        f"{'I also have connection ID `' + connection_id + '`. ' if connection_id else ''}"
        "What SQL query would you like to run?"
    )


async def _read_github_repo_file(
    *,
    repo: str,
    path: str,
    ref: str | None,
    personal_access_token: str,
) -> str | None:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {personal_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"ref": ref} if ref else None
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            f"https://api.github.com/repos/{repo}/contents/{path}",
            headers=headers,
            params=params,
        )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("type") != "file":
        return None
    encoded = payload.get("content")
    if not isinstance(encoded, str) or not encoded.strip():
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="ignore")
    except Exception:
        return None


async def _discover_repository_env_hints(
    available_resources: list[dict[str, Any]] | None,
    personal_access_token: str | None,
) -> list[str]:
    if not personal_access_token or not available_resources:
        return []

    hints: list[str] = []
    for resource in available_resources:
        if not isinstance(resource, dict):
            continue
        resource_type = str(resource.get("type") or "").strip().lower()
        connector = str(resource.get("connector") or "").strip().lower()
        config = resource.get("config") if isinstance(resource.get("config"), dict) else {}
        repo = str(config.get("repo") or "").strip()
        if not repo or (resource_type != "repo_connection" and connector != "github"):
            continue

        ref = str(config.get("ref") or config.get("default_branch") or "").strip() or None
        candidate_paths = list(REPO_ENV_DISCOVERY_FILES)
        repo_path = str(config.get("path") or "").strip().strip("/")
        if repo_path:
            candidate_paths = [f"{repo_path}/{candidate}" for candidate in REPO_ENV_DISCOVERY_FILES] + candidate_paths

        for candidate_path in candidate_paths[:8]:
            try:
                content = await _read_github_repo_file(
                    repo=repo,
                    path=candidate_path,
                    ref=ref,
                    personal_access_token=personal_access_token,
                )
            except httpx.HTTPError:
                continue
            if not content:
                continue
            env_names = {match.group(0) for match in ENV_VAR_NAME_PATTERN.finditer(content)}
            matched = [
                name
                for name in [
                    "SQL_CONNECTION_STRING",
                    "SQL_DB_HOST",
                    "SQL_DB_PORT",
                    "SQL_DB_DATABASE",
                    "SQL_DB_USERNAME",
                    "SQL_DB_PASSWORD",
                ]
                if name in env_names
            ]
            if matched:
                hints.append(f"{repo}:{' @ ' + ref if ref else ''} {candidate_path} includes {', '.join(matched)}")
                break
        if len(hints) >= 3:
            break

    return hints


@router.post("/send", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest, db=Depends(get_db)) -> ChatResponse:
    """
    Send a message to the AI chat assistant.
    
    Args:
        request: Chat request with message and optional conversation history
        
    Returns:
        AI assistant response with optional job creation intent and extracted fields
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Detect job creation intent from user message
        job_creation_intent = detect_job_creation_intent(request.message)
        deterministic_repo_fields = _deterministic_repo_connection_fields(request)
        github_token = request.github_personal_access_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        session_env = _effective_session_env(request)
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in (request.conversation_history or [])]

        # --- SQL GitHub write flow: write a SQL query file into a GitHub repository ---
        if _is_sql_github_write_request(request):
            if not github_token:
                return ChatResponse(
                    response=(
                        "I can write the SQL query to a GitHub repository. "
                        "First I need a GitHub personal access token with repository write access."
                    ),
                    job_creation_intent=True,
                    extracted_fields={"sql_subtype": "sql_github_write"},
                    secret_request=SecretRequest(
                        kind="github_personal_access_token",
                        prompt="Enter a GitHub personal access token with repo write access.",
                        submit_label="Use token",
                    ),
                )

            draft = request.current_draft_data or {}
            last_asked_gw = _last_asked_github_write_field(history_dicts)
            new_gw: dict[str, Any] = {}
            if last_asked_gw:
                val = request.message.strip()
                if val:
                    new_gw[last_asked_gw] = val

            merged_gw = {**draft, **new_gw}
            gw_config = merged_gw.get("config") if isinstance(merged_gw.get("config"), dict) else {}
            gw_query = _non_empty_str(merged_gw.get("query")) or _non_empty_str(gw_config.get("query"))
            gw_repo = _non_empty_str(merged_gw.get("repo")) or _non_empty_str(gw_config.get("repo"))
            gw_file = _non_empty_str(merged_gw.get("file_path")) or _non_empty_str(merged_gw.get("path")) or "queries/query.sql"
            gw_ref = _non_empty_str(merged_gw.get("ref")) or _non_empty_str(merged_gw.get("branch"))
            base_ef: dict[str, Any] = {"sql_subtype": "sql_github_write", **new_gw}

            if not gw_query:
                return ChatResponse(
                    response="What SQL query should I write to the repository?",
                    job_creation_intent=True,
                    extracted_fields=base_ef,
                )
            if not gw_repo:
                return ChatResponse(
                    response="Which GitHub repository should I write it to? (format: `owner/repo-name`)",
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query},
                )

            write_prompt = _build_github_write_mcp_prompt(gw_query, gw_repo, gw_file, gw_ref)
            server_env_overrides = {"github": {"GITHUB_PERSONAL_ACCESS_TOKEN": github_token}}
            try:
                mcp_result = await run_prompt_native_mcp(
                    message=write_prompt,
                    environment="dev",
                    model=request.model,
                    server_names=["github"],
                    server_env_overrides=server_env_overrides,
                )
                return ChatResponse(
                    response=mcp_result.response,
                    job_creation_intent=False,
                    extracted_fields={"sql_subtype": "sql_github_write"},
                    mcp_tool_executed=True,
                    mcp_servers=mcp_result.server_names,
                    mcp_tool_executions=mcp_result.tool_executions,
                )
            except Exception as exc:
                logger.exception("GitHub write via MCP failed")
                return ChatResponse(
                    response=f"I ran into an issue writing to GitHub: {exc}. Please verify the token has repository write access.",
                    job_creation_intent=False,
                )

        # --- SQL flow: structured state machine (universal fields → SQL fields → confirm → run) ---
        if _looks_like_sql_connect_request(request):
            draft = request.current_draft_data or {}
            last_asked = _last_asked_sql_flow_field(history_dicts)
            # Fallback: if the draft already has awaiting_confirmation, we're in confirm mode
            if draft.get("awaiting_confirmation"):
                last_asked = "confirm"

            new_ef: dict[str, Any] = {"job_type": "SQL"}

            if last_asked not in (None, "confirm"):
                # OpenAI pass: extract all fields it can see in the message (handles multi-field answers)
                # Skip on the initial trigger message (last_asked=None) — nothing concrete to extract yet
                ai_fields = _openai_extract_sql_fields(request.message, draft, history_dicts)
                for fld, val in ai_fields.items():
                    if fld in {"host", "port", "database", "username", "password"}:
                        new_ef.setdefault("config", {})[fld] = val
                    else:
                        new_ef[fld] = val
                if "connection_id" in ai_fields:
                    new_ef["_connection_id_asked"] = True

                # Deterministic fallback: if OpenAI didn't capture the specifically-asked field, extract it
                if last_asked:
                    already_set = new_ef.get(last_asked) or (new_ef.get("config") or {}).get(last_asked)
                    if not already_set:
                        value = _extract_sql_field_value(last_asked, request.message)
                        if value is not None:
                            if last_asked == "connection_id":
                                new_ef["_connection_id_asked"] = True
                                if value != "__skip__":
                                    new_ef["connection_id"] = value
                            elif last_asked in {"host", "port", "database", "username", "password"}:
                                new_ef.setdefault("config", {})[last_asked] = value
                            else:
                                new_ef[last_asked] = value
                    if last_asked == "connection_id":
                        new_ef["_connection_id_asked"] = True

            # Merge new fields with the current draft
            merged: dict[str, Any] = {**draft, **new_ef}
            if "config" in new_ef:
                merged["config"] = {**(draft.get("config") or {}), **new_ef["config"]}

            # Confirmation step: user answered yes/no to the summary
            if last_asked == "confirm":
                if _AFFIRMATIVE_RESPONSE_PATTERN.match(request.message.strip()):
                    cfg: dict[str, Any] = {**(merged.get("config") or {})}
                    for fld, env_key in (
                        ("host", "SQL_DB_HOST"), ("port", "SQL_DB_PORT"),
                        ("database", "SQL_DB_DATABASE"), ("username", "SQL_DB_USERNAME"),
                        ("password", "SQL_DB_PASSWORD"),
                    ):
                        if not cfg.get(fld) and session_env.get(env_key):
                            cfg[fld] = session_env[env_key]
                    for fld in ("query", "database", "username", "password", "host", "port", "connection_id"):
                        if merged.get(fld) and not cfg.get(fld):
                            cfg[fld] = merged[fld]
                    if merged.get("schedule"):
                        cfg["schedule"] = merged["schedule"]
                    exec_fields: dict[str, Any] = {
                        "job_type": "SQL",
                        "name": merged.get("job_name") or merged.get("name"),
                        "owner": merged.get("owner"),
                        "run_type": str(merged.get("run_type") or "manual").strip().lower(),
                        "connector": "sql-dab",
                        "config": cfg,
                        "action": "run",
                    }
                    try:
                        sql_result = maybe_run_sql_job_from_chat(
                            db,
                            message="run sql job",
                            extracted_fields=exec_fields,
                            current_draft=None,
                        )
                    except Exception as exec_err:
                        logger.exception("SQL job execution failed after chat confirmation")
                        err_str = str(exec_err)
                        if "ConnectError" in err_str or "Connection" in err_str or "connection" in err_str:
                            user_msg = (
                                "The job was registered but I couldn't execute it — "
                                "the SQL MCP server at `http://localhost:5100/mcp` is not reachable. "
                                "Please start the SQL MCP server and try again."
                            )
                        else:
                            user_msg = f"The job was registered but execution failed: {err_str}"
                        return ChatResponse(
                            response=user_msg,
                            job_creation_intent=False,
                            extracted_fields=None,
                        )
                    if sql_result is not None:
                        return ChatResponse(
                            response=sql_result.message,
                            job_creation_intent=False,
                            extracted_fields=None,
                            resource_id=sql_result.resource_id,
                            run_id=sql_result.run_id,
                            run_status=sql_result.run_status,
                            sql_job_executed=sql_result.executed,
                        )
                    return ChatResponse(
                        response="I wasn't able to create the job. Please verify the connection details and try again.",
                        job_creation_intent=True,
                        extracted_fields={"job_type": "SQL"},
                    )
                else:
                    return ChatResponse(
                        response="No problem — what would you like to change?",
                        job_creation_intent=True,
                        extracted_fields={"job_type": "SQL"},
                    )

            # Ask for the next missing field
            next_field = _next_missing_sql_field(merged, session_env)
            if next_field:
                return ChatResponse(
                    response=_SQL_FIELD_QUESTIONS[next_field],
                    job_creation_intent=True,
                    extracted_fields=new_ef,
                )

            # All fields collected — show the confirmation summary
            summary = _build_sql_job_summary(merged, session_env)
            return ChatResponse(
                response=summary,
                job_creation_intent=True,
                extracted_fields={**new_ef, "awaiting_confirmation": True},
            )

        if deterministic_repo_fields.get("connection_intent") == "connect_repo" and not github_token:
            return ChatResponse(
                response=(
                    "I can help connect a GitHub repository, but I need a GitHub personal access token "
                    "for this live MCP session first."
                ),
                job_creation_intent=True,
                extracted_fields=None,
                secret_request=SecretRequest(
                    kind="github_personal_access_token",
                    prompt="Enter a GitHub personal access token to browse and connect repositories for this session.",
                    submit_label="Use token",
                ),
            )

        if (
            deterministic_repo_fields.get("connection_intent") == "connect_repo"
            and not deterministic_repo_fields.get("repo")
            and github_token
        ):
            try:
                repository_options = await _list_github_repository_options(github_token)
            except httpx.HTTPError as exc:
                logger.warning("Unable to list GitHub repositories for chat repo connection: %s", exc)
                raise HTTPException(
                    status_code=502,
                    detail="Unable to load repositories from GitHub with the provided token.",
                ) from exc

            return ChatResponse(
                response=(
                    "I found repositories available through that token. Choose one below and I’ll connect it "
                    "as a reusable GitHub repo resource."
                ),
                job_creation_intent=True,
                extracted_fields=None,
                repository_options=repository_options,
            )

        preflight_sql_job_result = None
        if _is_explicit_sql_run_request(request):
            preflight_sql_job_result = maybe_run_sql_job_from_chat(
                db,
                message=request.message,
                extracted_fields=None,
                current_draft=request.current_draft_data,
            )
        if preflight_sql_job_result is not None:
            return ChatResponse(
                response=preflight_sql_job_result.message,
                job_creation_intent=job_creation_intent,
                extracted_fields=None,
                resource_id=preflight_sql_job_result.resource_id,
                run_id=preflight_sql_job_result.run_id,
                run_status=preflight_sql_job_result.run_status,
                sql_job_executed=preflight_sql_job_result.executed,
            )

        if should_run_prompt_native_mcp(request.message, request.current_draft_data):
            if needs_github_personal_access_token(
                request.message,
                request.current_draft_data,
                supplied_token=request.github_personal_access_token,
            ):
                return ChatResponse(
                    response=(
                        "I can do that, but I need a GitHub personal access token for this live "
                        "GitHub MCP session. Enter it in the secure token field and I will use "
                        "it only for this request."
                    ),
                    job_creation_intent=False,
                    extracted_fields=None,
                    secret_request=SecretRequest(
                        kind="github_personal_access_token",
                        prompt="Enter a GitHub personal access token for this live MCP session.",
                        submit_label="Use token",
                    ),
                )

            server_env_overrides = None
            if request.github_personal_access_token:
                server_env_overrides = {
                    "github": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": request.github_personal_access_token,
                    }
                }
            mcp_result = await run_prompt_native_mcp(
                message=request.message,
                environment=str((request.current_draft_data or {}).get("target_environment") or (request.current_draft_data or {}).get("environment") or "dev"),
                model=request.model,
                server_names=["sql-dab"] if _looks_like_sql_connect_request(request) else None,
                server_env_overrides=server_env_overrides,
            )
            return ChatResponse(
                response=mcp_result.response,
                job_creation_intent=False,
                extracted_fields=None,
                mcp_tool_executed=True,
                mcp_servers=mcp_result.server_names,
                mcp_tool_executions=mcp_result.tool_executions,
            )
        
        # Convert conversation history to dict format if provided
        history = None
        if request.conversation_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]
        
        chat_service = get_chat_service()
        response = await chat_service.send_message(
            message=request.message,
            conversation_history=history,
            model=request.model,
            current_draft=request.current_draft_data,
            available_resources=request.available_resources,
        )
        
        # Handle [RUN_JOB:resource_id] marker emitted by the LLM
        sql_flow_active = _has_sql_draft(request) or _looks_like_sql_connect_request(request)
        run_marker_match = RUN_JOB_MARKER_PATTERN.search(response)
        if run_marker_match:
            resource_id_to_run = run_marker_match.group(1)
            clean_response = RUN_JOB_MARKER_PATTERN.sub("", response).strip()
            if not sql_flow_active:
                run_result = run_resource_by_id(db, resource_id_to_run)
                final_response = f"{clean_response}\n\n{run_result.message}".strip()
                return ChatResponse(
                    response=final_response,
                    job_creation_intent=job_creation_intent,
                    extracted_fields=None,
                    resource_id=run_result.resource_id,
                    run_id=run_result.run_id,
                    run_status=run_result.run_status,
                    sql_job_executed=run_result.executed,
                )
            response = clean_response

        # Extract job fields unless this is only a generic create-job opener with no
        # concrete details yet. SQL/run-style chat requests still need extraction.
        extracted_fields = {
            **deterministic_repo_fields,
            **_deterministic_sql_fields(request),
        }
        if _looks_like_sql_connect_request(request) and session_env:
            derived_connection_string = _build_sql_connection_string(session_env)
            database_name = str(session_env.get("SQL_DB_DATABASE") or "").strip()
            database_host = str(session_env.get("SQL_DB_HOST") or "").strip()
            database_port = str(session_env.get("SQL_DB_PORT") or "").strip()
            database_username = str(session_env.get("SQL_DB_USERNAME") or "").strip()
            extracted_fields = {
                **extracted_fields,
                "connector": extracted_fields.get("connector") or "sql-dab",
                "config": {
                    **(extracted_fields.get("config") or {}),
                    "session_env_keys": sorted(session_env.keys()),
                },
            }
            explicit_connection_id = extracted_fields.get("connection_id") or session_env.get("SQL_CONNECTION_ID")
            if explicit_connection_id:
                extracted_fields["connection_id"] = explicit_connection_id
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "connection_id": explicit_connection_id,
                }
            if database_name:
                extracted_fields["database"] = database_name
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "database": database_name,
                }
            if database_host:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "host": database_host,
                }
            if database_port:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "port": database_port,
                }
            if database_username:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "username": database_username,
                }
            if derived_connection_string:
                extracted_fields["config"] = {
                    **(extracted_fields.get("config") or {}),
                    "sql_connection_string": derived_connection_string,
                }
        if _should_extract_fields(request, job_creation_intent):
            extraction_service = get_field_extraction_service()
            llm_fields = await extraction_service.extract_fields(
                user_message=request.message,
                conversation_history=history,
                current_draft=request.current_draft_data,
                model=request.model
            )
            extracted_fields = {**(llm_fields or {}), **extracted_fields}
            # Only include extracted_fields if there are any
            if not extracted_fields:
                extracted_fields = None

        if extracted_fields:
            sql_followup_response = _sql_followup_response(request, extracted_fields, session_env)
            if sql_followup_response:
                return ChatResponse(
                    response=sql_followup_response,
                    job_creation_intent=True,
                    extracted_fields=extracted_fields,
                )

        sql_job_result = maybe_run_sql_job_from_chat(
            db,
            message=request.message,
            extracted_fields=extracted_fields,
            current_draft=request.current_draft_data,
        )
        if sql_job_result is not None:
            response = f"{response}\n\n{sql_job_result.message}"
        
        return ChatResponse(
            response=response,
            job_creation_intent=job_creation_intent,
            extracted_fields=extracted_fields,
            resource_id=sql_job_result.resource_id if sql_job_result is not None else None,
            run_id=sql_job_result.run_id if sql_job_result is not None else None,
            run_status=sql_job_result.run_status if sql_job_result is not None else None,
            sql_job_executed=sql_job_result.executed if sql_job_result is not None else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled chat error")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def detect_job_creation_intent(user_message: str) -> bool:
    """
    Detect if user is expressing intent to create a job.
    
    Args:
        user_message: The user's input message
        
    Returns:
        True if job creation intent is detected, False otherwise
    """
    message_lower = user_message.lower().strip()
    
    # Keywords that indicate job creation intent
    creation_keywords = [
        "create",
        "new job",
        "sql job",
        "start a job",
        "build a job",
        "set up a job",
        "make a job",
        "add a job",
        "design a job",
    ]
    
    # Check if message contains creation-related keywords
    for keyword in creation_keywords:
        if keyword in message_lower:
            # Also check that it's about a job
            if "job" in message_lower or "workflow" in message_lower:
                return True
    
    return False
