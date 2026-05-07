"""Chat API router — guided SQL flow and agent flow."""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.models.job import Job
from app.services.chat_job_service import (
    maybe_run_sql_job_from_chat,
    register_sql_job_from_chat,
    run_job_by_id,
    update_sql_job_from_chat,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns — guided SQL flow only
# ---------------------------------------------------------------------------

_FLOW_ABANDONMENT_PATTERN = re.compile(
    r"\b(nevermind|never\s+mind|nvm|forget\s+it|forget\s+this|forget\s+that|"
    r"cancel\s+(?:that|this|it|everything)|cancel|start\s+over|start\s+fresh|"
    r"abort|go\s+back|ignore\s+that|scrap\s+(?:it|this|that)|changed\s+my\s+mind|"
    r"stop\s+(?:this|that|it|creating|the\s+job)|please\s+stop|just\s+stop|"
    r"stop\s+it|stop\s+now|exit\s+(?:this|flow)|"
    r"reset\s+(?:everything|the\s+draft|draft)|i\s+don[''']?t\s+want\s+to\s+(?:do\s+this|create\s+this|continue)|"
    r"quit|exit)\b"
    r"|(?:\blet[''']?s\s+(?:do|try)\s+something\s+(?:else|different)\b)",
    re.IGNORECASE,
)
SQL_RUN_REQUEST_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b", re.IGNORECASE)
SQL_RUN_CONTEXT_PATTERN = re.compile(r"\b(job|sql|query|resource)\b", re.IGNORECASE)
_UPDATE_RESOURCE_PATTERN = re.compile(
    r"\b(update|change|modify|edit|rename|configure|set)\b.{0,80}\b(schedule|query|name|owner|connection|run.?type|environment)\b"
    r"|\b(schedule|query|run.?type)\b.{0,60}\b(to|as|should|=|every|daily|weekly|hourly|monthly|manually)\b",
    re.IGNORECASE,
)
AFFIRMATIVE_RUN_RESPONSE_PATTERN = re.compile(
    r"^(yes|yep|yeah|sure|please do|go ahead|run it|run now|do it)[\s.!?]*$", re.IGNORECASE
)
_AFFIRMATIVE_RESPONSE_PATTERN = re.compile(
    r"^(yes|yep|yeah|sure|please|go ahead|do it|run it|create it|ok|okay|confirm|y|sounds good|looks good)\b",
    re.IGNORECASE,
)
SQL_CREATE_REQUEST_PATTERN = re.compile(
    r"\b(create|save|register|finali[sz]e|set up)\b.{0,40}\b(job|resource)\b"
    r"|\bcreate the job\b|\bsave this job\b|\bfinali[sz]e (?:the )?job\b",
    re.IGNORECASE,
)
_SQL_TYPE_SELECTION_PATTERN = re.compile(
    r"^(sql|a\s+sql(\s+job)?|sql\s+job|sql\s+query|use\s+sql)\s*$",
    re.IGNORECASE,
)
_ASKED_JOB_TYPE_PATTERN = re.compile(
    r"\b(airflow|excel|powerpoint)\b|\btype of job\b|\brepository\s+connection\b|\bsql\s+job\b",
    re.IGNORECASE,
)
_SIMPLE_VALUE_PATTERN = re.compile(r"^(?:(?:it[''`]?s|the \w+ is|use|is|just)\s+)?([^\s,;]+)\s*$", re.IGNORECASE)
_PORT_DIGITS_PATTERN = re.compile(r"\b(\d{2,5})\b")
_SQL_STATEMENT_PATTERN = re.compile(
    r"^\s*(?:"
    r"SELECT\s+|INSERT\s+INTO\s+|UPDATE\s+\w[\w.]*\s+SET\s+|DELETE\s+FROM\s+"
    r"|CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE)\s+"
    r"|DROP\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE)\s+"
    r"|ALTER\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE)\s+"
    r"|TRUNCATE\s+(?:TABLE\s+)?\w+|WITH\s+\w+\s+AS\s*\(|SHOW\s+|DESCRIBE\s+|EXPLAIN\s+"
    r")",
    re.IGNORECASE,
)
_NL_TABLE_EXTRACT_PATTERN = re.compile(
    r"\b(?:get|fetch|show|list|select|retrieve|find|display)\b\s+(?:me\s+)?(?:all\s+)?(?:the\s+)?(\w+?)(?:\s+(?:from|in|records?|data|table|entries?|rows?)|\s*$)",
    re.IGNORECASE,
)
_NL_CREATE_TABLE_EXTRACT_PATTERN = re.compile(
    r"\bcreate\b.{0,40}\b(?:table)\b.{0,20}\b(?:called|named)\s+[`\"']?([A-Za-z_][A-Za-z0-9_]*)[`\"']?",
    re.IGNORECASE,
)
NEW_DATABASE_REQUEST_PATTERN = re.compile(
    r"\b(connect|use|switch|try)\b.{0,40}\b(different|new|another|other)\b.{0,40}\b(database|db|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b"
    r"|\b(different|new|another|other)\b.{0,40}\b(database|db|connection)\b"
    r"|\bconnect\s+to\s+(?:a\s+)?(?:different|new|another)\s+(?:database|db)\b",
    re.IGNORECASE,
)
_NAMED_RESOURCE_REF_PATTERN = re.compile(
    r'\b(?:for|of|named?|called?|on|resource|job)\s+([a-zA-Z0-9][a-zA-Z0-9_.-]{1,})\b'
    r'|([a-z][a-z0-9]{1,}(?:-[a-z0-9]+){1,})\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# SQL connection form field definitions
# ---------------------------------------------------------------------------

SQL_SESSION_ENV_FIELDS = [
    {"key": "SQL_DB_HOST", "label": "Database host", "placeholder": "e.g. db.example.com", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_PORT", "label": "Database port", "placeholder": "e.g. 5432", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_DATABASE", "label": "Database name", "placeholder": "e.g. my_database", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_USERNAME", "label": "Database username", "placeholder": "e.g. db_user", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_PASSWORD", "label": "Database password", "placeholder": "Enter your database password", "secret": True, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_CONNECTION_ID", "label": "Connection ID (optional)", "placeholder": "e.g. my-connection (leave blank to skip)", "secret": False, "required": False},
]
_SQLITE_SESSION_ENV_FIELDS: list[dict] = [
    {"key": "SQL_DB_DATABASE", "label": "SQLite database file path", "placeholder": "e.g. /path/to/database.db  (or :memory: for in-memory)", "secret": False, "required": True, "group": "sql_connection_string"},
]
_SNOWFLAKE_SESSION_ENV_FIELDS: list[dict] = [
    {"key": "SQL_DB_HOST", "label": "Snowflake account identifier", "placeholder": "e.g. myaccount.snowflakecomputing.com", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_DATABASE", "label": "Database and schema", "placeholder": "e.g. MY_DATABASE/PUBLIC", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_WAREHOUSE", "label": "Warehouse", "placeholder": "e.g. COMPUTE_WH", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_USERNAME", "label": "Username", "placeholder": "e.g. my_snowflake_user", "secret": False, "required": True, "group": "sql_connection_string"},
    {"key": "SQL_DB_PASSWORD", "label": "Password", "placeholder": "Enter your Snowflake password", "secret": True, "required": True, "group": "sql_connection_string"},
]
_SQL_DRIVER_DISPLAY: dict[str, str] = {
    "sqlite": "SQLite",
    "snowflake": "Snowflake",
    "postgresql+psycopg": "PostgreSQL",
    "mysql+pymysql": "MySQL",
}

_REGISTRY_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "control_center" / "registry" / "registry.json"
)
_FIELD_LABELS: dict[str, str] = {
    "job_name": "job name",
    "owner": "job owner",
    "run_type": "run type (manual or scheduled)",
    "schedule": "schedule expression",
    "query": "SQL query",
    "database": "database name",
    "connection_id": "connection ID",
    "username": "database username",
    "password": "database password",
    "host": "database host",
    "port": "database port",
}
_SQL_FIELD_QUESTIONS_FALLBACK: dict[str, str] = {
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

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None
    current_draft_data: Optional[dict[str, Any]] = None
    available_resources: Optional[list[dict[str, Any]]] = None
    github_personal_access_token: Optional[str] = None
    session_env: Optional[dict[str, Any]] = None


class SecretRequest(BaseModel):
    kind: str
    prompt: str
    submit_label: Optional[str] = None


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


class DbTypeOption(BaseModel):
    label: str
    value: str
    description: Optional[str] = None


_DB_TYPE_OPTIONS = [
    DbTypeOption(label="PostgreSQL", value="postgresql+psycopg", description="Host-based, port 5432"),
    DbTypeOption(label="MySQL", value="mysql+pymysql", description="Host-based, port 3306"),
    DbTypeOption(label="SQLite", value="sqlite", description="Local file or :memory:"),
    DbTypeOption(label="Snowflake", value="snowflake", description="Cloud data warehouse"),
]


class ChatResponse(BaseModel):
    response: str
    job_creation_intent: Optional[bool] = None
    extracted_fields: Optional[dict[str, Any]] = None
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    run_status: Optional[str] = None
    sql_job_executed: Optional[bool] = None
    mcp_tool_executed: Optional[bool] = None
    mcp_servers: Optional[list[str]] = None
    mcp_tool_executions: Optional[list[dict[str, Any]]] = None
    secret_request: Optional[SecretRequest] = None
    config_request: Optional[ConfigRequest] = None
    db_type_options: Optional[list[DbTypeOption]] = None
    reset_draft: Optional[bool] = None
    reset_session_env: Optional[bool] = None


_ALL_SQL_CONNECTION_FIELDS: list[ConfigRequestField] = [ConfigRequestField(**f) for f in SQL_SESSION_ENV_FIELDS]
_SQLITE_CONNECTION_FIELDS: list[ConfigRequestField] = [ConfigRequestField(**f) for f in _SQLITE_SESSION_ENV_FIELDS]
_SNOWFLAKE_CONNECTION_FIELDS: list[ConfigRequestField] = [ConfigRequestField(**f) for f in _SNOWFLAKE_SESSION_ENV_FIELDS]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _non_empty_str(value: Any) -> str | None:
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    return None


def _detect_sql_driver(message: str) -> str | None:
    lower = (message or "").lower()
    if re.search(r"\bsqlite\b", lower):
        return "sqlite"
    if re.search(r"\bsnowflake\b", lower):
        return "snowflake"
    if re.search(r"\bpostgres(?:ql)?\b|\bpsycopg\b", lower):
        return "postgresql+psycopg"
    if re.search(r"\bmysql\b|\bmariadb\b", lower):
        return "mysql+pymysql"
    return None


def _coerce_to_sql(message: str) -> str:
    stripped = message.strip()
    if _SQL_STATEMENT_PATTERN.match(stripped):
        return stripped
    create_match = _NL_CREATE_TABLE_EXTRACT_PATTERN.search(stripped)
    if create_match:
        table = create_match.group(1)
        return f"CREATE TABLE {table} (id SERIAL PRIMARY KEY);"
    _NL_STOPWORDS = {"all", "me", "data", "records", "result", "results", "rows", "everything",
                     "from", "database", "db", "the", "some", "those", "these", "any"}
    m = _NL_TABLE_EXTRACT_PATTERN.search(stripped)
    if m:
        table = m.group(1).lower()
        if table not in _NL_STOPWORDS:
            return f"SELECT * FROM {table};"
    return stripped


def _load_registry() -> dict[str, Any]:
    try:
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
        return registry if isinstance(registry, dict) else {}
    except Exception:
        return {}


def _load_registry_field_info() -> str:
    registry = _load_registry()
    lines: list[str] = []
    universal = registry.get("universal_job_fields", {})
    req = universal.get("required", [])
    opt = universal.get("optional", [])
    if req:
        lines.append(f"Universal required fields: {', '.join(req)}")
    if opt:
        lines.append(f"Universal optional fields: {', '.join(opt)}")
    for name, srv in registry.get("approved_servers", {}).items():
        if srv.get("required_fields") or srv.get("optional_fields"):
            display = srv.get("display_name") or name
            job_type = srv.get("job_type", name)
            r = srv.get("required_fields") or []
            o = srv.get("optional_fields") or []
            lines.append(f"{display} (job_type={job_type}) required: {r}  optional: {o}")
    return "\n".join(lines)


def _validate_against_registry(connector: str, environment: str) -> list[str]:
    errors: list[str] = []
    registry = _load_registry()
    approved = registry.get("approved_servers", {})
    if not connector:
        return []
    if connector not in approved:
        errors.append(
            f"Connector `{connector}` is not in the approved servers list. "
            f"Available SQL connectors: {', '.join(k for k, v in approved.items() if v.get('job_type') == 'sql')}."
        )
        return errors
    server = approved[connector]
    if not server.get("active", True):
        errors.append(f"Connector `{connector}` is currently marked inactive in the registry.")
    if environment:
        allowed = server.get("allowed_environments", [])
        if allowed and allowed != ["*"] and environment not in allowed:
            errors.append(
                f"Environment `{environment}` is not allowed for `{connector}`. "
                f"Allowed: {', '.join(allowed)}."
            )
    return errors


def _sql_ordered_required_fields() -> list[str]:
    registry = _load_registry()
    universal = registry.get("universal_job_fields", {}) if isinstance(registry.get("universal_job_fields"), dict) else {}
    approved = registry.get("approved_servers", {}) if isinstance(registry.get("approved_servers"), dict) else {}
    sql_server = approved.get("sql-mcp", {}) if isinstance(approved.get("sql-mcp"), dict) else {}
    fields: list[str] = []
    for field in [*(universal.get("required") or []), *(sql_server.get("required_fields") or [])]:
        if isinstance(field, str) and field not in fields:
            fields.append(field)
    return fields or ["job_name", "owner", "run_type", "query", "database", "host", "port", "username", "password"]


def _sql_field_has_value(field: str, draft: dict, session_env: dict) -> bool:
    _raw = draft.get("config")
    config: dict = _raw if isinstance(_raw, dict) else {}
    if field == "job_name":
        return bool(_non_empty_str(draft.get("job_name") or draft.get("name")))
    if field == "run_type":
        return bool(_non_empty_str(draft.get("run_type")))
    if field == "schedule":
        return bool(_non_empty_str(draft.get("schedule") or config.get("schedule")))
    if field == "query":
        return bool(_non_empty_str(draft.get("query") or config.get("query")))
    if field == "database":
        return bool(_non_empty_str(draft.get("database") or config.get("database") or session_env.get("SQL_DB_DATABASE")))
    if field == "host":
        return bool(_non_empty_str(draft.get("host") or config.get("host") or session_env.get("SQL_DB_HOST")))
    if field == "port":
        return bool(_non_empty_str(draft.get("port") or config.get("port") or session_env.get("SQL_DB_PORT")))
    if field == "username":
        return bool(_non_empty_str(draft.get("username") or config.get("username") or session_env.get("SQL_DB_USERNAME")))
    if field == "password":
        return bool(_non_empty_str(draft.get("password") or config.get("password") or session_env.get("SQL_DB_PASSWORD")))
    if field == "connection_id":
        return bool(_non_empty_str(draft.get("connection_id") or config.get("connection_id") or session_env.get("SQL_CONNECTION_ID")))
    return bool(_non_empty_str(draft.get(field) or config.get(field)))


def _next_missing_sql_field(draft: dict, session_env: dict) -> str | None:
    for field in _sql_ordered_required_fields():
        if not _sql_field_has_value(field, draft, session_env):
            return field
    if str(draft.get("run_type") or "").strip().lower() == "scheduled" and not _sql_field_has_value("schedule", draft, session_env):
        return "schedule"
    driver = _non_empty_str(draft.get("db_driver") or (draft.get("config") or {}).get("db_driver")) or ""
    _no_connection_id_drivers = {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
    if driver.lower() not in _no_connection_id_drivers and not draft.get("_connection_id_asked") and not _sql_field_has_value("connection_id", draft, session_env):
        return "connection_id"
    return None


def _openai_extract_sql_fields(message: str, draft: dict, history: list[dict] | None) -> dict[str, Any]:
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
            "query (valid SQL), database, connection_id, username, password, host, port, "
            "db_driver (one of: sqlite, snowflake, postgresql+psycopg, mysql+pymysql).\n"
            "Rules:\n"
            "- ONLY extract a field if the user's message directly provides or clearly describes its value.\n"
            "- For 'db_driver': set to 'sqlite' if SQLite, 'snowflake' for Snowflake, "
            "'postgresql+psycopg' for PostgreSQL/Postgres, 'mysql+pymysql' for MySQL/MariaDB.\n"
            "- For 'query': if the user provides SQL, return it exactly. If they describe in natural "
            "language (e.g. 'get all orders'), GENERATE the SQL. NEVER invent from vague intent.\n"
            "- For 'run_type': output exactly 'manual' or 'scheduled'.\n"
            "- If unsure, omit the field. Returning {} is valid.\n"
            "- Return a JSON object with only found fields.\n"
            f"Already-known fields (do not repeat unless user explicitly changes): {existing}"
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
        raw = json.loads(resp.choices[0].message.content or "{}")
        if not isinstance(raw, dict):
            return {}
        allowed = {"job_name", "owner", "run_type", "schedule", "query",
                   "database", "connection_id", "username", "password", "host", "port", "db_driver"}
        _valid_drivers = {"sqlite", "snowflake", "postgresql+psycopg", "mysql+pymysql"}
        result: dict[str, Any] = {}
        for k, v in raw.items():
            if k not in allowed or not isinstance(v, str) or not v.strip():
                continue
            result[k] = _coerce_to_sql(v) if k == "query" else v.strip()
        if "run_type" in result and result["run_type"] not in {"manual", "scheduled", "triggered"}:
            del result["run_type"]
        if "db_driver" in result and result["db_driver"] not in _valid_drivers:
            del result["db_driver"]
        _driver_words = {"sqlite", "postgresql", "postgres", "snowflake", "mysql", "mariadb"}
        if result.get("database", "").strip().lower() in _driver_words:
            del result["database"]
        existing_driver = str(draft.get("db_driver") or result.get("db_driver") or "").strip().lower()
        if existing_driver == "sqlite" and "connection_id" in result:
            del result["connection_id"]
        return result
    except Exception:
        logger.debug("OpenAI SQL field extraction failed", exc_info=True)
        return {}


def _extract_sql_field_value(field: str, message: str) -> str | None:
    stripped = message.strip()
    if not stripped:
        return None
    if field == "db_driver":
        return _detect_sql_driver(stripped)
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


def _build_sql_job_summary(draft: dict, session_env: dict) -> str:
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    db_driver = _non_empty_str(draft.get("db_driver") or config.get("db_driver")) or ""
    driver_label = _SQL_DRIVER_DISPLAY.get(db_driver.lower(), db_driver.capitalize() if db_driver else "SQL")
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
        f"**Database Type:** {driver_label}",
        "",
        "**SQL Query:**",
        f"```sql\n{query}\n```",
    ]
    if db_driver == "sqlite":
        lines.append(f"**Database file:** {database}")
    elif db_driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        lines += [f"**Snowflake account:** {host}", f"**Database/Schema:** {database}", f"**Username:** {username}"]
    else:
        lines += [f"**Database:** {database}", f"**Host:** {host}:{port}", f"**Username:** {username}"]
        if connection_id:
            lines.append(f"**Connection ID:** {connection_id}")
    lines.append("")
    if run_type == "scheduled":
        lines.append("Shall I create this scheduled job? (yes / no)")
    else:
        lines.append("Shall I create and run this job now? (yes / no)")
    return "\n".join(lines)


def _sql_config_with_session_env(merged: dict[str, Any], session_env: dict[str, str]) -> dict[str, Any]:
    cfg: dict[str, Any] = {**(merged.get("config") or {})}
    cfg.pop("target_environment", None)
    cfg.pop("environment", None)
    for fld, env_key in (
        ("db_driver", "SQL_DB_DRIVER"),
        ("host", "SQL_DB_HOST"),
        ("port", "SQL_DB_PORT"),
        ("database", "SQL_DB_DATABASE"),
        ("username", "SQL_DB_USERNAME"),
        ("password", "SQL_DB_PASSWORD"),
    ):
        if not cfg.get(fld) and session_env.get(env_key):
            cfg[fld] = session_env[env_key]
    for fld in ("query", "database", "username", "password", "host", "port", "connection_id", "db_driver"):
        if merged.get(fld) and not cfg.get(fld):
            cfg[fld] = merged[fld]
    if merged.get("schedule"):
        cfg["schedule"] = merged["schedule"]
    _driver = _non_empty_str(cfg.get("db_driver") or merged.get("db_driver") or "")
    if _driver and _driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}:
        cfg.pop("connection_id", None)
    return cfg


def _resolved_job_environment(fields: dict[str, Any]) -> str:
    config = fields.get("config") if isinstance(fields.get("config"), dict) else {}
    return (
        _non_empty_str(fields.get("target_environment"))
        or _non_empty_str(fields.get("environment"))
        or _non_empty_str(config.get("target_environment"))
        or _non_empty_str(config.get("environment"))
        or "dev"
    )


def _clear_sql_transient_fields(fields: dict[str, Any]) -> dict[str, Any]:
    base = {k: v for k, v in fields.items() if k not in {"_pending_field", "awaiting_confirmation"}}
    return {**base, "_pending_field": False, "awaiting_confirmation": False}


def _sql_connection_check_key(draft: dict, session_env: dict[str, str]) -> str | None:
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
    host = _non_empty_str(draft.get("host") or config.get("host") or session_env.get("SQL_DB_HOST"))
    port = _non_empty_str(draft.get("port") or config.get("port") or session_env.get("SQL_DB_PORT"))
    database = _non_empty_str(draft.get("database") or config.get("database") or session_env.get("SQL_DB_DATABASE")) or ""
    username = _non_empty_str(draft.get("username") or config.get("username") or session_env.get("SQL_DB_USERNAME")) or ""
    if not host or not port:
        return None
    return f"{host}:{port}/{database}@{username}"


async def _tcp_ping(host: str, port: str | int, timeout: float = 3.0) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(str(host), int(port)), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def _sql_connection_status_message(
    draft: dict, session_env: dict[str, str]
) -> tuple[str | None, dict[str, Any]]:
    check_key = _sql_connection_check_key(draft, session_env)
    if not check_key or draft.get("_connection_check_key") == check_key:
        return None, {}
    host, rest = check_key.split(":", 1)
    port = rest.split("/", 1)[0]
    reachable = await _tcp_ping(host, port)
    status = "reachable" if reachable else "unreachable"
    update = {"_connection_check_key": check_key, "_connection_check_status": status}
    if reachable:
        return f"I successfully reached the database endpoint at `{host}:{port}`.", update
    return (
        f"I received the database details, but I couldn't reach `{host}:{port}` yet. "
        "You can update the host or port, or continue drafting the job.",
        update,
    )


def _connection_fields_for_driver(driver: str) -> list[ConfigRequestField]:
    d = (driver or "").strip().lower()
    if d == "sqlite":
        return _SQLITE_CONNECTION_FIELDS
    if d in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        return _SNOWFLAKE_CONNECTION_FIELDS
    pg_fields = [f for f in SQL_SESSION_ENV_FIELDS if f["key"] != "SQL_CONNECTION_ID"]
    return [ConfigRequestField(**f) for f in pg_fields]


def _sql_connection_config_request(
    prompt: str, fields: list[ConfigRequestField] | None = None
) -> ConfigRequest:
    return ConfigRequest(
        kind="sql_session_env",
        prompt=prompt,
        submit_label="Connect database",
        fields=fields if fields is not None else _ALL_SQL_CONNECTION_FIELDS,
    )


def _ask_llm_for_next_field(
    next_field: str, draft: dict, session_env: dict, history: list[dict] | None
) -> str:
    try:
        from app.core.config import settings
        if not settings.openai_api_key:
            return _SQL_FIELD_QUESTIONS_FALLBACK.get(next_field, f"What is the {next_field}?")
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        config = draft.get("config") or {}
        collected: dict[str, str] = {}
        for f in ("job_name", "owner", "run_type", "schedule", "query",
                  "database", "connection_id", "username", "host", "port"):
            v = (
                str(draft.get(f) or config.get(f) or "").strip()
                or str(session_env.get(f"SQL_DB_{f.upper()}") or "").strip()
            )
            if v:
                collected[f] = v
        if draft.get("password") or config.get("password") or session_env.get("SQL_DB_PASSWORD"):
            collected["password"] = "***"
        registry_info = _load_registry_field_info()
        field_label = _FIELD_LABELS.get(next_field, next_field)
        system_prompt = (
            "You are CC Assistant helping a user create a SQL job step by step.\n"
            f"Job field reference from registry:\n{registry_info}\n\n"
            "Rules:\n"
            "- Ask exactly ONE short, friendly question to collect the next field.\n"
            "- Be conversational. Include a brief hint or example in backticks if helpful.\n"
            "- Do NOT re-ask fields already collected.\n"
            "- Do NOT list all fields — only ask about the one field requested.\n"
            "- NEVER ask about the connector — it is always `sql-mcp`.\n"
            f"Already collected: {json.dumps(collected)}\n"
            f"Next field to ask about: {field_label} (key: {next_field})"
        )
        msgs: list[Any] = [{"role": "system", "content": system_prompt}]
        for h in (history or [])[-4:]:
            if isinstance(h, dict) and h.get("role") in {"user", "assistant"}:
                msgs.append({"role": h["role"], "content": str(h.get("content") or "")})
        resp = client.chat.completions.create(
            model=settings.openai_model, messages=msgs, max_tokens=120, temperature=0.7
        )
        question = (resp.choices[0].message.content or "").strip()
        return question or _SQL_FIELD_QUESTIONS_FALLBACK.get(next_field, f"What is the {next_field}?")
    except Exception:
        logger.debug("LLM field question generation failed", exc_info=True)
        return _SQL_FIELD_QUESTIONS_FALLBACK.get(next_field, f"What is the {next_field}?")


def _is_sql_type_selection(message: str, history: list[dict] | None) -> bool:
    if not _SQL_TYPE_SELECTION_PATTERN.match((message or "").strip()):
        return False
    for msg in reversed(history or []):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        return bool(_ASKED_JOB_TYPE_PATTERN.search(str(msg.get("content") or "")))
    return False


def _is_new_database_request(message: str, draft: dict) -> bool:
    if not NEW_DATABASE_REQUEST_PATTERN.search(message or ""):
        return False
    return str((draft or {}).get("job_type", "")).strip().lower() == "sql"


def _draft_without_connection_details(draft: dict) -> dict:
    connection_keys = {
        "host", "port", "database", "username", "password",
        "connection_id", "_connection_id_asked", "_connection_form_shown",
    }
    clean = {k: v for k, v in draft.items() if k not in connection_keys}
    if isinstance(clean.get("config"), dict):
        clean["config"] = {k: v for k, v in clean["config"].items() if k not in connection_keys}
    return clean


def _is_explicit_sql_run_request(request: "ChatRequest") -> bool:
    message = request.message or ""
    draft = request.current_draft_data or {}
    if str(draft.get("job_type", "")).strip().lower() != "sql":
        return False
    if draft.get("job_id") and AFFIRMATIVE_RUN_RESPONSE_PATTERN.search(message.strip()):
        return True
    return bool(SQL_RUN_REQUEST_PATTERN.search(message) and SQL_RUN_CONTEXT_PATTERN.search(message))


def _is_explicit_sql_create_request(message: str) -> bool:
    return bool(SQL_CREATE_REQUEST_PATTERN.search(message or ""))


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
    if "manual" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields["run_type"] = "manual"
    if "create" in message and SQL_RUN_REQUEST_PATTERN.search(message) is not None:
        fields.update({"creation_requested": True, "run_after_create": True, "action": "run"})
    if "create" in message and "job" in message:
        fields["creation_requested"] = True
    return fields


def _is_abandoning_current_flow(message: str, draft: dict) -> bool:
    """Regex-only abandonment check — no LLM call."""
    if not draft:
        return False
    draft_type = str(draft.get("job_type") or draft.get("type") or "").strip().lower()
    if not draft_type:
        return False
    if draft_type == "sql" and (
        SQL_CREATE_REQUEST_PATTERN.search(message or "")
        or (SQL_RUN_REQUEST_PATTERN.search(message or "") and SQL_RUN_CONTEXT_PATTERN.search(message or ""))
        or _AFFIRMATIVE_RESPONSE_PATTERN.match((message or "").strip())
    ):
        return False
    return bool(_FLOW_ABANDONMENT_PATTERN.search(message))


def _find_named_job_in_message(db, message: str) -> "Job | None":
    candidates: list[str] = []
    for m in _NAMED_RESOURCE_REF_PATTERN.finditer(message):
        name = m.group(1) or m.group(2)
        if name:
            candidates.append(name.strip())
    if not candidates:
        return None
    from sqlalchemy import func
    for name in candidates:
        job = db.query(Job).filter(func.lower(Job.name) == name.lower()).first()
        if job:
            return job
    return None


def _missing_sql_session_env(session_env: dict[str, str], db_driver: str = "") -> list[ConfigRequestField]:
    driver = (db_driver or "").strip().lower()
    if driver == "sqlite":
        fields_to_check = _SQLITE_SESSION_ENV_FIELDS
    elif driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        fields_to_check = _SNOWFLAKE_SESSION_ENV_FIELDS
    else:
        fields_to_check = SQL_SESSION_ENV_FIELDS
    missing: list[ConfigRequestField] = []
    derived_connection_string = _build_sql_connection_string(session_env) if driver != "sqlite" else None
    for field in fields_to_check:
        key = field["key"]
        if session_env.get(key):
            continue
        if field.get("group") == "sql_connection_string" and derived_connection_string:
            continue
        missing.append(ConfigRequestField(**field))
    return missing


def _build_sql_connection_string(session_env: dict[str, str]) -> str | None:
    host = session_env.get("SQL_DB_HOST")
    port = session_env.get("SQL_DB_PORT")
    database = session_env.get("SQL_DB_DATABASE")
    username = session_env.get("SQL_DB_USERNAME")
    password = session_env.get("SQL_DB_PASSWORD")
    if not all([host, port, database, username, password]):
        return None
    return f"Host={host};Port={port};Database={database};Username={username};Password={password}"



def _effective_session_env(request: "ChatRequest") -> dict[str, str]:
    session_env = request.session_env or {}
    return {str(key): str(value) for key, value in session_env.items() if str(value).strip()}


# ---------------------------------------------------------------------------
# Guided SQL endpoint
# ---------------------------------------------------------------------------

@router.post("/guided", response_model=ChatResponse)
async def guided_chat(request: ChatRequest, db=Depends(get_db)) -> ChatResponse:
    """Deterministic, state-machine-driven SQL job creation flow."""
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        draft = request.current_draft_data or {}
        _form_already_shown = bool(draft.get("_connection_form_shown"))
        history_dicts = [{"role": m.role, "content": m.content} for m in (request.conversation_history or [])]
        session_env = _effective_session_env(request)

        # Abandonment — regex only, no LLM call
        if not _form_already_shown and _is_abandoning_current_flow(request.message, draft):
            return ChatResponse(
                response="No problem — I've cleared the job draft. What would you like to do next?",
                job_creation_intent=False,
                extracted_fields=None,
                reset_draft=True,
            )

        # "SQL" selected after job-type prompt
        if _is_sql_type_selection(request.message, history_dicts) and not _form_already_shown:
            return ChatResponse(
                response="Great choice! Which database are you connecting to?",
                job_creation_intent=True,
                extracted_fields={**(request.current_draft_data or {}), "job_type": "SQL"},
                db_type_options=_DB_TYPE_OPTIONS,
                reset_session_env=True,
            )

        # New/different database — clear connection fields, re-show form
        if _is_new_database_request(request.message, draft):
            clean_draft = _draft_without_connection_details(draft)
            return ChatResponse(
                response="Sure! To connect to the new database, I'll need its connection details.",
                job_creation_intent=True,
                extracted_fields={
                    "job_type": "SQL",
                    **clean_draft,
                    "_connection_form_shown": True,
                    "_connection_id_asked": True,
                },
                config_request=_sql_connection_config_request("Enter the connection details for the new database."),
                reset_session_env=True,
            )

        # Named resource update: "change the query for job-name-3"
        if _UPDATE_RESOURCE_PATTERN.search(request.message) and not draft.get("job_id"):
            named_resource = _find_named_job_in_message(db, request.message)
            if named_resource is not None:
                ai_fields = _openai_extract_sql_fields(request.message, draft, history_dicts)
                update_msg, draft_updates = update_sql_job_from_chat(db, named_resource.id, ai_fields)
                seed_draft: dict[str, Any] = {
                    "job_type": "SQL",
                    "job_id": named_resource.id,
                    "job_name": named_resource.name,
                    "name": named_resource.name,
                }
                new_draft = _clear_sql_transient_fields({**seed_draft, **draft_updates})
                config_patch: dict[str, Any] = {}
                if "config" in draft_updates and isinstance(draft_updates["config"], dict):
                    config_patch.update(draft_updates["config"])
                for _f in ("query", "schedule", "connection_id", "run_type"):
                    if _f in draft_updates:
                        config_patch[_f] = draft_updates[_f]
                if config_patch:
                    existing_cfg = getattr(named_resource, "config", None) or {}
                    new_draft["config"] = {**existing_cfg, **config_patch}
                return ChatResponse(response=update_msg, job_creation_intent=True, extracted_fields=new_draft)

        # Detect driver early so the right connection form is shown before field extraction
        _early_draft = request.current_draft_data or {}
        _early_db_driver = _non_empty_str(
            _early_draft.get("db_driver") or (_early_draft.get("config") or {}).get("db_driver")
        ) or ""
        if not _early_db_driver:
            detected_early = _detect_sql_driver(request.message)
            if detected_early:
                _early_db_driver = detected_early
                _early_draft = {**_early_draft, "db_driver": detected_early}

        missing_sql_session_fields = _missing_sql_session_env(session_env, _early_db_driver)
        if missing_sql_session_fields and not _form_already_shown:
            if not _early_db_driver:
                return ChatResponse(
                    response="Which database are you connecting to?",
                    job_creation_intent=True,
                    extracted_fields={**_early_draft, "job_type": "SQL"},
                    db_type_options=_DB_TYPE_OPTIONS,
                )
            _early_driver_label = _SQL_DRIVER_DISPLAY.get(_early_db_driver.lower(), "SQL")
            _skip_conn_id = _early_db_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
            return ChatResponse(
                response=f"Enter the {_early_driver_label} connection details for this session.",
                job_creation_intent=True,
                extracted_fields={
                    **_early_draft,
                    "job_type": "SQL",
                    "_connection_form_shown": True,
                    "_connection_id_asked": _skip_conn_id,
                },
                config_request=_sql_connection_config_request(
                    f"Enter the {_early_driver_label} connection details for this chat session.",
                    fields=missing_sql_session_fields,
                ),
            )

        # --- SQL state machine ---
        if _is_abandoning_current_flow(request.message, draft):
            return ChatResponse(
                response="No problem — I've cleared the job draft. What would you like to do next?",
                job_creation_intent=False,
                extracted_fields=None,
                reset_draft=True,
            )

        pending_field = str(draft.get("_pending_field") or "").strip() or None
        last_asked = "confirm" if draft.get("awaiting_confirmation") else pending_field

        new_ef: dict[str, Any] = {"job_type": "SQL"}
        if last_asked not in (None, "confirm"):
            ai_fields = _openai_extract_sql_fields(request.message, draft, history_dicts)
            for fld, val in ai_fields.items():
                if fld in {"host", "port", "database", "username", "password"}:
                    new_ef.setdefault("config", {})[fld] = val
                else:
                    new_ef[fld] = val
            if "connection_id" in ai_fields:
                new_ef["_connection_id_asked"] = True
            if last_asked:
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

        merged: dict[str, Any] = {**draft, **new_ef}
        if "config" in new_ef:
            merged["config"] = {**(draft.get("config") or {}), **new_ef["config"]}
        if isinstance(merged.get("config"), dict):
            merged["config"] = {
                k: v for k, v in merged["config"].items()
                if k not in {"target_environment", "environment"}
            }
        if not _non_empty_str(merged.get("target_environment")) and _non_empty_str(merged.get("environment")):
            merged["target_environment"] = merged["environment"]
        merged.pop("environment", None)
        if merged.get("db_driver") and not (merged.get("config") or {}).get("db_driver"):
            merged.setdefault("config", {})["db_driver"] = merged["db_driver"]
        _active_driver = _non_empty_str(
            merged.get("db_driver") or (merged.get("config") or {}).get("db_driver")
        ) or ""
        if _active_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}:
            merged.pop("connection_id", None)
            merged.pop("connector", None)
            if isinstance(merged.get("config"), dict):
                merged["config"].pop("connection_id", None)
            if isinstance(merged.get("params"), dict):
                merged["params"].pop("connection_id", None)
        # Persist session_env connection values into the draft so they survive across turns
        if merged.get("_connection_form_shown") and session_env:
            for _fld, _env_key in (
                ("db_driver", "SQL_DB_DRIVER"),
                ("database", "SQL_DB_DATABASE"),
                ("host", "SQL_DB_HOST"),
                ("port", "SQL_DB_PORT"),
                ("warehouse", "SQL_DB_WAREHOUSE"),
                ("username", "SQL_DB_USERNAME"),
                ("password", "SQL_DB_PASSWORD"),
            ):
                _env_val = _non_empty_str(session_env.get(_env_key))
                if _env_val and not _non_empty_str((merged.get("config") or {}).get(_fld)):
                    merged.setdefault("config", {})[_fld] = _env_val
        if not merged.get("db_driver") and (merged.get("config") or {}).get("db_driver"):
            merged["db_driver"] = merged["config"]["db_driver"]
        if last_asked not in (None, "confirm"):
            if last_asked in ("connection_id", "db_driver") or _sql_field_has_value(last_asked, merged, session_env):
                merged.pop("_pending_field", None)
        if "awaiting_confirmation" in merged and last_asked != "confirm":
            merged.pop("awaiting_confirmation", None)

        connection_status_message, connection_status_fields = await _sql_connection_status_message(merged, session_env)
        if connection_status_fields:
            merged.update(connection_status_fields)

        # Confirmation step
        if last_asked == "confirm":
            if _AFFIRMATIVE_RESPONSE_PATTERN.match(request.message.strip()):
                cfg = _sql_config_with_session_env(merged, session_env)
                run_type = str(merged.get("run_type") or "manual").strip().lower()

                if run_type == "scheduled":
                    registration_result = register_sql_job_from_chat(
                        db,
                        extracted_fields={**merged, "config": cfg, "creation_requested": True},
                        current_draft=merged,
                    )
                    job_label = merged.get("job_name") or merged.get("name") or "your SQL job"
                    schedule = merged.get("schedule") or cfg.get("schedule") or ""
                    schedule_msg = f" It is scheduled to run `{schedule}`." if schedule else ""
                    return ChatResponse(
                        response=(
                            f"Registered SQL job `{job_label}`.{schedule_msg}"
                            if registration_result.job_id
                            else registration_result.message
                        ),
                        job_creation_intent=True,
                        extracted_fields=_clear_sql_transient_fields({
                            **merged, "config": cfg, "job_id": registration_result.job_id,
                            "name": registration_result.job_name or merged.get("job_name") or merged.get("name"),
                        }),
                        job_id=registration_result.job_id,
                    )

                exec_fields: dict[str, Any] = {
                    "job_type": "SQL",
                    "name": merged.get("job_name") or merged.get("name"),
                    "owner": merged.get("owner"),
                    "run_type": run_type,
                    "connector": "sql-mcp",
                    "config": cfg,
                    "connection_id": merged.get("connection_id") or cfg.get("connection_id"),
                    "query": merged.get("query") or cfg.get("query"),
                    "target_environment": _resolved_job_environment(merged),
                    "job_id": merged.get("job_id"),
                    "action": "run",
                }
                try:
                    sql_result = maybe_run_sql_job_from_chat(
                        db, message="run sql job", extracted_fields=exec_fields, current_draft=merged,
                    )
                except Exception as exec_err:
                    logger.exception("SQL job execution failed after chat confirmation")
                    err_str = str(exec_err)
                    user_msg = (
                        "I couldn't execute the SQL job — the SQL MCP server is not reachable. "
                        "Please start the SQL MCP server and try again."
                        if "ConnectError" in err_str or "connection" in err_str.lower()
                        else f"Execution failed: {err_str}"
                    )
                    return ChatResponse(
                        response=user_msg,
                        job_creation_intent=True,
                        extracted_fields=_clear_sql_transient_fields(merged),
                    )
                if sql_result is not None:
                    return ChatResponse(
                        response=sql_result.message,
                        job_creation_intent=False,
                        extracted_fields=_clear_sql_transient_fields({
                            **merged, "job_id": sql_result.job_id,
                            "name": merged.get("job_name") or merged.get("name"),
                        }),
                        job_id=sql_result.job_id,
                        run_id=sql_result.run_id,
                        run_status=sql_result.run_status,
                        sql_job_executed=sql_result.executed,
                    )
                return ChatResponse(
                    response="I wasn't able to create the job. Please verify the connection details and try again.",
                    job_creation_intent=True,
                    extracted_fields=_clear_sql_transient_fields(merged),
                )
            else:
                # User said something other than yes — extract any field edits and re-show summary
                ai_fields = _openai_extract_sql_fields(request.message, draft, history_dicts)
                for fld, val in ai_fields.items():
                    if fld in {"host", "port", "database", "username", "password"}:
                        merged.setdefault("config", {})[fld] = val
                    elif fld == "config" and isinstance(val, dict):
                        merged["config"] = {**(merged.get("config") or {}), **val}
                    else:
                        merged[fld] = val
                merged.pop("awaiting_confirmation", None)
                merged.pop("_pending_field", None)
                if ai_fields:
                    summary = _build_sql_job_summary(merged, session_env)
                    return ChatResponse(
                        response=summary,
                        job_creation_intent=True,
                        extracted_fields={**merged, "awaiting_confirmation": True, "_pending_field": "confirm"},
                    )
                return ChatResponse(
                    response="No problem — what would you like to change?",
                    job_creation_intent=True,
                    extracted_fields=merged,
                )

        # Determine SQL driver before showing connection form
        if not merged.get("_connection_form_shown"):
            db_driver = _non_empty_str(merged.get("db_driver") or (merged.get("config") or {}).get("db_driver"))
            if not db_driver:
                detected = _detect_sql_driver(request.message)
                if not detected:
                    for _hm in reversed(history_dicts or []):
                        if _hm.get("role") == "user":
                            detected = _detect_sql_driver(str(_hm.get("content") or ""))
                            if detected:
                                break
                if detected:
                    merged["db_driver"] = detected
                    merged.setdefault("config", {})["db_driver"] = detected
                elif last_asked == "db_driver":
                    return ChatResponse(
                        response=(
                            "I didn't catch that. Which database type would you like to use?\n\n"
                            "- **PostgreSQL** — standard relational database\n"
                            "- **SQLite** — local file-based database\n"
                            "- **Snowflake** — cloud data warehouse"
                        ),
                        job_creation_intent=True,
                        extracted_fields={**merged, "_pending_field": "db_driver"},
                    )
                else:
                    return ChatResponse(
                        response=(
                            "What type of SQL database would you like to connect to?\n\n"
                            "- **PostgreSQL** — standard relational database\n"
                            "- **SQLite** — local file-based database\n"
                            "- **Snowflake** — cloud data warehouse"
                        ),
                        job_creation_intent=True,
                        extracted_fields={**merged, "_pending_field": "db_driver"},
                    )

        # Show connection form on first entry into the SQL flow
        if not merged.get("_connection_form_shown"):
            db_driver = _non_empty_str(merged.get("db_driver") or (merged.get("config") or {}).get("db_driver")) or ""
            driver_label = _SQL_DRIVER_DISPLAY.get(db_driver.lower(), db_driver.capitalize() if db_driver else "SQL")
            skip_connection_id = db_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
            return ChatResponse(
                response=f"Great, I'll set up a **{driver_label}** SQL job. Please fill in the connection details below.",
                job_creation_intent=True,
                extracted_fields={**merged, "_connection_form_shown": True, "_connection_id_asked": skip_connection_id},
                config_request=_sql_connection_config_request(
                    f"Enter the {driver_label} connection details for this job.",
                    fields=_connection_fields_for_driver(db_driver),
                ),
                reset_session_env=True,
            )

        # Ask for next missing field
        next_field = _next_missing_sql_field(merged, session_env)
        if next_field:
            question = _ask_llm_for_next_field(next_field, merged, session_env, history_dicts)
            if connection_status_message:
                question = f"{connection_status_message}\n\n{question}"
            return ChatResponse(
                response=question,
                job_creation_intent=True,
                extracted_fields={**merged, "_pending_field": next_field},
            )

        # All fields present — validate before showing confirmation summary
        cfg = merged.get("config") or {}
        connector = str(merged.get("connector") or "sql-mcp").strip().lower()
        environment = _resolved_job_environment(merged).strip().lower()
        registry_errors = _validate_against_registry(connector, environment)
        if registry_errors:
            error_lines = "\n".join(f"- {e}" for e in registry_errors)
            return ChatResponse(
                response=f"I found a configuration issue:\n{error_lines}\n\nWhat would you like to change?",
                job_creation_intent=True,
                extracted_fields=merged,
            )

        explicit_run_request = _is_explicit_sql_run_request(request)
        explicit_create_request = _is_explicit_sql_create_request(request.message)

        if explicit_create_request and not explicit_run_request and not merged.get("job_id"):
            cfg = _sql_config_with_session_env(merged, session_env)
            registration_result = register_sql_job_from_chat(
                db,
                extracted_fields={
                    **merged, "config": cfg,
                    "connection_id": merged.get("connection_id") or cfg.get("connection_id"),
                    "query": merged.get("query") or cfg.get("query"),
                    "creation_requested": True,
                },
                current_draft=merged,
            )
            return ChatResponse(
                response=registration_result.message,
                job_creation_intent=True,
                extracted_fields=_clear_sql_transient_fields({
                    **merged, "config": cfg, "job_id": registration_result.job_id,
                    "name": registration_result.job_name or merged.get("job_name") or merged.get("name"),
                    "creation_requested": True,
                }),
                job_id=registration_result.job_id,
            )

        # TCP reachability check
        host = str(merged.get("host") or cfg.get("host") or session_env.get("SQL_DB_HOST") or "").strip()
        port = str(merged.get("port") or cfg.get("port") or session_env.get("SQL_DB_PORT") or "").strip()
        if host and port:
            reachable = await _tcp_ping(host, port)
            if not reachable:
                return ChatResponse(
                    response=(
                        f"I couldn't reach the database at `{host}:{port}` — "
                        "the host may be wrong or the server may not be running. "
                        "Would you like to update the host or port?"
                    ),
                    job_creation_intent=True,
                    extracted_fields=merged,
                )

        if explicit_run_request:
            try:
                sql_result = maybe_run_sql_job_from_chat(
                    db, message=request.message,
                    extracted_fields={**merged, "action": "run"},
                    current_draft=merged,
                )
            except Exception as exec_err:
                logger.exception("Immediate SQL execution failed from chat")
                return ChatResponse(
                    response=f"I couldn't run the SQL job: {exec_err}",
                    job_creation_intent=True,
                    extracted_fields=merged,
                )
            if sql_result is not None:
                return ChatResponse(
                    response=sql_result.message,
                    job_creation_intent=False,
                    extracted_fields={
                        **merged, "job_id": sql_result.job_id,
                        "name": merged.get("job_name") or merged.get("name"),
                    },
                    job_id=sql_result.job_id,
                    run_id=sql_result.run_id,
                    run_status=sql_result.run_status,
                    sql_job_executed=sql_result.executed,
                )

        if explicit_create_request and not merged.get("job_id"):
            registration_result = register_sql_job_from_chat(
                db,
                extracted_fields={**merged, "creation_requested": True},
                current_draft=merged,
            )
            return ChatResponse(
                response=registration_result.message,
                job_creation_intent=True,
                extracted_fields=_clear_sql_transient_fields({
                    **merged, "job_id": registration_result.job_id,
                    "name": registration_result.job_name or merged.get("job_name") or merged.get("name"),
                    "creation_requested": True,
                }),
                job_id=registration_result.job_id,
            )

        # Job already registered — update fields or run it
        if merged.get("job_id"):
            msg = request.message.strip()
            if _UPDATE_RESOURCE_PATTERN.search(msg):
                ai_fields = _openai_extract_sql_fields(msg, merged, history_dicts)
                update_msg, draft_updates = update_sql_job_from_chat(db, merged["job_id"], ai_fields)
                new_draft = _clear_sql_transient_fields({**merged, **draft_updates})
                config_patch: dict[str, Any] = {}
                if "config" in draft_updates and isinstance(draft_updates["config"], dict):
                    config_patch.update(draft_updates["config"])
                for _f in ("query", "schedule", "connection_id", "run_type"):
                    if _f in draft_updates:
                        config_patch[_f] = draft_updates[_f]
                if config_patch:
                    new_draft["config"] = {**(merged.get("config") or {}), **config_patch}
                return ChatResponse(response=update_msg, job_creation_intent=True, extracted_fields=new_draft)

            wants_run = (
                AFFIRMATIVE_RUN_RESPONSE_PATTERN.match(msg)
                or _AFFIRMATIVE_RESPONSE_PATTERN.match(msg)
                or (SQL_RUN_REQUEST_PATTERN.search(msg) and not _UPDATE_RESOURCE_PATTERN.search(msg))
            )
            if wants_run:
                run_result = run_job_by_id(db, merged["job_id"])
                return ChatResponse(
                    response=run_result.message,
                    job_creation_intent=False,
                    extracted_fields=_clear_sql_transient_fields({
                        **merged, "job_id": run_result.job_id,
                        "name": merged.get("job_name") or merged.get("name"),
                    }),
                    job_id=run_result.job_id,
                    run_id=run_result.run_id,
                    run_status=run_result.run_status,
                    sql_job_executed=run_result.executed,
                )
            job_label = merged.get("job_name") or merged.get("name") or "your SQL job"
            return ChatResponse(
                response=f"Your SQL job `{job_label}` is registered. You can run it or update its fields.",
                job_creation_intent=True,
                extracted_fields=_clear_sql_transient_fields(merged),
            )

        # All fields collected — show confirmation summary
        summary = _build_sql_job_summary(merged, session_env)
        if connection_status_message:
            summary = f"{connection_status_message}\n\n{summary}"
        return ChatResponse(
            response=summary,
            job_creation_intent=True,
            extracted_fields={**merged, "awaiting_confirmation": True, "_pending_field": "confirm"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled guided chat error")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


# ---------------------------------------------------------------------------
# Agent endpoint
# ---------------------------------------------------------------------------

class AgentChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None
    server_env_overrides: Optional[dict[str, dict[str, str]]] = None
    session_env: Optional[dict[str, str]] = None


class AgentChatResponse(BaseModel):
    response: str
    config_request: Optional[dict[str, Any]] = None
    db_type_options: Optional[list[dict[str, Any]]] = None
    run_id: Optional[str] = None
    secret_request: Optional[dict[str, Any]] = None


@router.post("/agent", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    user=Depends(get_current_user),
) -> AgentChatResponse:
    """Agent-driven chat endpoint backed by the Control Center MCP server."""
    from app.services.agent_chat_service import run_agent

    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    history = [{"role": m.role, "content": m.content} for m in (request.conversation_history or [])]

    result = await run_agent(
        message=request.message.strip(),
        conversation_history=history or None,
        user=user,
        model=request.model,
        server_env_overrides=request.server_env_overrides,
        session_env=request.session_env or None,
    )
    return AgentChatResponse(
        response=result.response,
        config_request=result.config_request,
        db_type_options=result.db_type_options,
        run_id=result.run_id,
        secret_request=result.secret_request,
    )
