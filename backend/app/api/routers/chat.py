"""Chat API router for handling AI chat messages."""

import asyncio
import json
import logging
import os
import re
import base64
from heapq import nlargest
from pathlib import Path
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, Depends
import httpx
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.job import Job
from app.services.chat_service import get_chat_service
from app.services.field_extraction_service import get_field_extraction_service
from app.services.chat_job_service import (
    get_chat_actor,
    get_github_token_for_repo,
    maybe_run_sql_job_from_chat,
    register_github_write_job_from_chat,
    register_sql_job_from_chat,
    run_job_by_id,
    save_github_token_for_repo,
    update_sql_job_from_chat,
)
from app.services.job_service import delete_job as delete_job_service, list_jobs as list_jobs_service
from app.services.chat_mcp_service import run_prompt_native_mcp, github_write_file
from app.services.run_service import list_runs

router = APIRouter()
logger = logging.getLogger(__name__)
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
_TASK_SWITCH_PATTERN = re.compile(
    r"\b(?:instead|switch|want\s+to\s+do|rather\s+do)\b.{0,80}\b(?:github|repo|repository|filesystem|fetch|api|webhook|arxiv)\b"
    r"|\b(?:github|repo|repository|filesystem|fetch|arxiv)\b.{0,80}\b(?:instead|now|first|rather)\b"
    r"|\bi\s+(?:want|need|'?d\s+like)\s+to\s+(?:connect|link|add|create|set\s+up).{0,80}\b(?:github|repo|repository)\b",
    re.IGNORECASE,
)
SQL_RUN_REQUEST_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b", re.IGNORECASE)
_UPDATE_RESOURCE_PATTERN = re.compile(
    r"\b(update|change|modify|edit|rename|configure|set)\b.{0,80}\b(schedule|query|name|owner|connection|run.?type|environment)\b"
    r"|\b(schedule|query|run.?type)\b.{0,60}\b(to|as|should|=|every|daily|weekly|hourly|monthly|manually)\b",
    re.IGNORECASE,
)
RUN_JOB_MARKER_PATTERN = re.compile(r'\[RUN_JOB:([a-zA-Z0-9\-_]+)\]')
# Extracts a potential resource name from update messages like "change the query for create-tables-3"
_NAMED_RESOURCE_REF_PATTERN = re.compile(
    r'\b(?:for|of|named?|called?|on|resource|job)\s+([a-zA-Z0-9][a-zA-Z0-9_.-]{1,})\b'
    r'|([a-z][a-z0-9]{1,}(?:-[a-z0-9]+){1,})\b',  # kebab-case identifier
    re.IGNORECASE,
)
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
    r"|\b(sql|query)\b.{0,60}\b(github|repo|repository|\.sql)\b"
    # Code-authoring intent — no GitHub keyword needed; writing a "script" implies version control
    r"|\b(?:create|write|draft|build|make|generate|author)\b.{0,60}\b(?:sql\s+script|sql\s+code|sql\s+file)\b"
    r"|\b(?:sql\s+script|sql\s+code|sql\s+file)\b.{0,60}\b(?:create|write|draft|build|make|generate)\b",
    re.IGNORECASE,
)
SQL_LOOKUP_ACTION_PATTERN = re.compile(
    r"\b(get|fetch|list|show|read|query|search|find|look up|lookup|inspect|summarize|summarise|run|execute|select|describe|explain|count)\b",
    re.IGNORECASE,
)
SQL_LOOKUP_CONTEXT_PATTERN = re.compile(
    r"\b(database|db|sql|postgres|postgresql|mysql|snowflake|redshift|bigquery|table|tables|row|rows|record|records)\b",
    re.IGNORECASE,
)
ENV_VAR_NAME_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
NEW_DATABASE_REQUEST_PATTERN = re.compile(
    r"\b(connect|use|switch|try)\b.{0,40}\b(different|new|another|other)\b.{0,40}\b(database|db|postgres|postgresql|mysql|snowflake|redshift|bigquery)\b"
    r"|\b(different|new|another|other)\b.{0,40}\b(database|db|connection)\b"
    r"|\bconnect\s+to\s+(?:a\s+)?(?:different|new|another)\s+(?:database|db)\b",
    re.IGNORECASE,
)
# Matches a bare job-type selection like "SQL", "a SQL job", "sql job"
_SQL_TYPE_SELECTION_PATTERN = re.compile(
    r"^(sql|a\s+sql(\s+job)?|sql\s+job|sql\s+query|use\s+sql)\s*$",
    re.IGNORECASE,
)
# Detects that the previous assistant turn was asking the user to pick a job type
_ASKED_JOB_TYPE_PATTERN = re.compile(
    r"\b(airflow|excel|powerpoint)\b"
    r"|\btype of job\b"
    r"|\brepository\s+connection\b"
    r"|\bsql\s+job\b",
    re.IGNORECASE,
)
# Patterns for detecting which connection field was last asked in conversation
_ASKED_HOST_PATTERN = re.compile(r"\bdatabase host\b|\bdb host\b|\bhost address\b|\bserver host\b", re.IGNORECASE)
_ASKED_PORT_PATTERN = re.compile(r"\bdatabase port\b|\bport number\b", re.IGNORECASE)
_ASKED_DATABASE_PATTERN = re.compile(r"\bdatabase name\b|\bdb name\b", re.IGNORECASE)
_ASKED_USERNAME_PATTERN = re.compile(r"\bdatabase username\b|\bdb username\b", re.IGNORECASE)
_ASKED_PASSWORD_PATTERN = re.compile(r"\bdatabase password\b|\bdb password\b", re.IGNORECASE)
_ASKED_GW_QUERY_PATTERN = re.compile(r"\bwhat sql query\b|\bsql query should i write\b|\bsql content\b|\bwhat sql script\b|\bwrite to the repository\b", re.IGNORECASE)
_ASKED_GW_REPO_PATTERN = re.compile(r"\bwhich (github )?repository\b|\bwhich repo\b|\bowner/repo\b|\bwrite this (sql\s+)?(script|query|code) to\b", re.IGNORECASE)
_ASKED_GW_PATH_PATTERN = re.compile(r"\bfile path\b|\bfile name\b|\bwhich file\b", re.IGNORECASE)
_ASKED_GW_JOB_NAME_PATTERN = re.compile(r"\bwhat name would you like to give this job\b|\bgive this job\b|\bjob name\b", re.IGNORECASE)
_ASKED_GW_OWNER_PATTERN = re.compile(r"\bwho is the owner\b|\bowner of this job\b", re.IGNORECASE)
_ASKED_GW_RUN_TYPE_PATTERN = re.compile(r"\bone-time.*manual.*run\b|\bscheduled job\b|\bmanual.*or.*scheduled\b|\bone-time.*or.*scheduled\b", re.IGNORECASE)
_ASKED_GW_SCHEDULE_PATTERN = re.compile(r"\bwhat schedule should i use\b|\bschedule.*cron\b|\bevery day at\b", re.IGNORECASE)
_SIMPLE_VALUE_PATTERN = re.compile(r"^(?:(?:it[''`]?s|the \w+ is|use|is|just)\s+)?([^\s,;]+)\s*$", re.IGNORECASE)
_PORT_DIGITS_PATTERN = re.compile(r"\b(\d{2,5})\b")
_ASKED_SQL_QUERY_PATTERN = re.compile(
    r"\bsql query\b|\bquery (?:to run|you would like|to execute|should i)\b|\bwhat query\b|\bprovide.*query\b|\bspecify.*query\b",
    re.IGNORECASE,
)
_SQL_STATEMENT_PATTERN = re.compile(
    r"^\s*(?:"
    r"SELECT\s+"
    r"|INSERT\s+INTO\s+"
    r"|UPDATE\s+\w[\w.]*\s+SET\s+"
    r"|DELETE\s+FROM\s+"
    r"|CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE)\s+"
    r"|DROP\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE|SEQUENCE)\s+"
    r"|ALTER\s+(?:TABLE|VIEW|INDEX|SCHEMA|DATABASE)\s+"
    r"|TRUNCATE\s+(?:TABLE\s+)?\w+"
    r"|WITH\s+\w+\s+AS\s*\("
    r"|SHOW\s+"
    r"|DESCRIBE\s+"
    r"|EXPLAIN\s+"
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
_SQL_FLOW_ASKED_PATTERNS: dict[str, re.Pattern] = {
    "job_name": re.compile(r"\bjob.*name\b|\bname.*(?:this )?job\b|\bwhat name\b|\bgive this job\b", re.IGNORECASE),
    "owner": re.compile(r"\bwho (?:is|will be|should be) the owner\b|\bowner of this job\b|\bjob.*owner\b", re.IGNORECASE),
    "run_type": re.compile(r"\bone-time.*run\b|\bscheduled job\b|\brun type\b|\bmanual.*or.*scheduled\b|\bone-time.*or.*scheduled\b", re.IGNORECASE),
    "schedule": re.compile(r"\bwhat schedule\b|\bschedule should i use\b|\bschedule.*use\b", re.IGNORECASE),
    "query": re.compile(
        r"\bsql query.*run\b|\bsql query.*execute\b|\bprovide.*sql query\b|\bquery.*run\b|"
        r"\bquery.*execute\b|\bwhat.*query\b|\bplain english\b|\bdescribe it\b|\bquery.*like to run\b",
        re.IGNORECASE,
    ),
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
SQL_CREATE_REQUEST_PATTERN = re.compile(
    r"\b(create|save|register|finali[sz]e|set up)\b.{0,40}\b(job|resource)\b"
    r"|\bcreate the job\b|\bsave this job\b|\bfinali[sz]e (?:the )?job\b",
    re.IGNORECASE,
)
LAST_RUN_QUESTION_PATTERN = re.compile(
    r"\b(last|latest|most recent)\b.{0,40}\b(job|run)\b"
    r"|\bwhat was the last job i ran\b"
    r"|\bwhat was my last run\b",
    re.IGNORECASE,
)
RECENT_RUNS_QUESTION_PATTERN = re.compile(
    r"\b(recent|latest|last)\b.{0,40}\b(jobs|runs)\b"
    r"|\bwhat jobs have i run\b"
    r"|\bshow my recent runs\b",
    re.IGNORECASE,
)
DELETE_JOB_PATTERN = re.compile(
    r"\b(delete|remove|destroy|drop)\b.{0,60}\bjob\b"
    r"|\bdelete\b.{0,60}\b(script|workflow|task)\b"
    r"|\bget rid of\b.{0,60}\bjob\b",
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
        "placeholder": "e.g. db.example.com",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PORT",
        "label": "Database port",
        "placeholder": "e.g. 5432",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_DATABASE",
        "label": "Database name",
        "placeholder": "e.g. my_database",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_USERNAME",
        "label": "Database username",
        "placeholder": "e.g. db_user",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PASSWORD",
        "label": "Database password",
        "placeholder": "Enter your database password",
        "secret": True,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_CONNECTION_ID",
        "label": "Connection ID (optional)",
        "placeholder": "e.g. my-connection (leave blank to skip)",
        "secret": False,
        "required": False,
    },
]
_SQLITE_SESSION_ENV_FIELDS: list[dict] = [
    {
        "key": "SQL_DB_DATABASE",
        "label": "SQLite database file path",
        "placeholder": "e.g. /path/to/database.db  (or :memory: for in-memory)",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
]
_SNOWFLAKE_SESSION_ENV_FIELDS: list[dict] = [
    {
        "key": "SQL_DB_HOST",
        "label": "Snowflake account identifier",
        "placeholder": "e.g. myaccount.snowflakecomputing.com",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_DATABASE",
        "label": "Database and schema",
        "placeholder": "e.g. MY_DATABASE/PUBLIC",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_WAREHOUSE",
        "label": "Warehouse",
        "placeholder": "e.g. COMPUTE_WH",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_USERNAME",
        "label": "Username",
        "placeholder": "e.g. my_snowflake_user",
        "secret": False,
        "required": True,
        "group": "sql_connection_string",
    },
    {
        "key": "SQL_DB_PASSWORD",
        "label": "Password",
        "placeholder": "Enter your Snowflake password",
        "secret": True,
        "required": True,
        "group": "sql_connection_string",
    },
]
SQL_REQUIRED_JOB_FIELDS = [
    ("job_name", "job/resource name"),
    ("owner", "owner"),
    ("target_environment", "target environment"),
    ("run_type", "run type"),
]
_SQL_DRIVER_DISPLAY: dict[str, str] = {
    "sqlite": "SQLite",
    "snowflake": "Snowflake",
    "postgresql+psycopg": "PostgreSQL",
    "mysql+pymysql": "MySQL",
}


def _detect_sql_driver(message: str) -> str | None:
    """Return a SQLAlchemy driver string inferred from keywords in message, or None."""
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
            "query (valid SQL), database, connection_id, username, password, host, port, folder_hint, "
            "db_driver (one of: sqlite, snowflake, postgresql+psycopg, mysql+pymysql).\n"
            "Rules:\n"
            "- ONLY extract a field if the user's message directly provides or clearly describes its value.\n"
            "- For 'db_driver': set to 'sqlite' if the user mentions SQLite, 'snowflake' for Snowflake, "
            "'postgresql+psycopg' for PostgreSQL/Postgres/pg, 'mysql+pymysql' for MySQL/MariaDB. "
            "Only set if the user explicitly names a database type.\n"
            "- For 'query': if the user provides actual SQL, return it exactly. If they describe an "
            "operation in natural language (e.g. 'get all orders', 'create a table called customers', "
            "'show me all users', 'delete old records from logs'), GENERATE the correct SQL for it "
            "(e.g. 'SELECT * FROM orders;', 'CREATE TABLE customers (id SERIAL PRIMARY KEY, name VARCHAR(100));'). "
            "NEVER invent a query from vague intents with no specific target (e.g. 'run a SQL query').\n"
            "- For 'run_type': output exactly 'manual' or 'scheduled'.\n"
            "- For 'folder_hint': extract the Git folder path the user wants to save the file in. "
            "Examples: 'under a collections jobs folder' → 'collections_jobs', "
            "'in the reporting directory' → 'reporting', 'save to etl/jobs' → 'etl/jobs', "
            "'in a scripts folder' → 'scripts'. Use snake_case. Only set if user mentions a folder.\n"
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
                   "database", "connection_id", "username", "password", "host", "port",
                   "folder_hint", "db_driver"}
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
        # Reject driver keywords being misidentified as the database name
        _driver_words = {"sqlite", "postgresql", "postgres", "snowflake", "mysql", "mariadb"}
        if result.get("database", "").strip().lower() in _driver_words:
            del result["database"]
        # connection_id is not applicable for SQLite
        existing_driver = str(draft.get("db_driver") or result.get("db_driver") or "").strip().lower()
        if existing_driver == "sqlite" and "connection_id" in result:
            del result["connection_id"]
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


def _next_missing_sql_field(draft: dict, session_env: dict) -> str | None:
    """Return the next field to collect in the SQL flow, or None when all are present."""
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


def _build_sql_job_summary(draft: dict, session_env: dict) -> str:
    """Build the confirmation summary shown before creating the job."""
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
        lines += [
            f"**Snowflake account:** {host}",
            f"**Database/Schema:** {database}",
            f"**Username:** {username}",
        ]
    else:
        lines += [
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


def _sql_config_with_session_env(merged: dict[str, Any], session_env: dict[str, str]) -> dict[str, Any]:
    """Build SQL config from draft fields plus session-level connection details."""
    cfg: dict[str, Any] = {**(merged.get("config") or {})}
    cfg.pop("target_environment", None)
    cfg.pop("environment", None)
    for fld, env_key in (
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
    # connection_id is only meaningful for PostgreSQL managed connections; remove it for other drivers
    _driver = _non_empty_str(cfg.get("db_driver") or merged.get("db_driver") or "")
    if _driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}:
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
    # Explicit false (not removed) so the frontend merge overwrites previous truthy values.
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


async def _sql_connection_status_message(
    draft: dict,
    session_env: dict[str, str],
) -> tuple[str | None, dict[str, Any]]:
    check_key = _sql_connection_check_key(draft, session_env)
    if not check_key or draft.get("_connection_check_key") == check_key:
        return None, {}

    host, rest = check_key.split(":", 1)
    port = rest.split("/", 1)[0]
    reachable = await _tcp_ping(host, port)
    status = "reachable" if reachable else "unreachable"
    update = {
        "_connection_check_key": check_key,
        "_connection_check_status": status,
    }
    if reachable:
        return f"I successfully reached the database endpoint at `{host}:{port}`.", update
    return (
        f"I received the database details, but I couldn't reach `{host}:{port}` yet. "
        "You can update the host or port, or continue drafting the job.",
        update,
    )


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
        if _ASKED_GW_JOB_NAME_PATTERN.search(content):
            return "job_name"
        if _ASKED_GW_OWNER_PATTERN.search(content):
            return "owner"
        if _ASKED_GW_RUN_TYPE_PATTERN.search(content):
            return "run_type"
        if _ASKED_GW_SCHEDULE_PATTERN.search(content):
            return "schedule"
        if _ASKED_GW_QUERY_PATTERN.search(content):
            return "query"
        if _ASKED_GW_REPO_PATTERN.search(content):
            return "repo"
        if _ASKED_GW_PATH_PATTERN.search(content):
            return "file_path"
        return None
    return None


_GW_TABLE_NAME_PATTERN = re.compile(
    r"\b(?:CREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?TABLE|DROP\s+TABLE|INSERT\s+INTO"
    r"|UPDATE|DELETE\s+FROM|ALTER\s+TABLE|TRUNCATE(?:\s+TABLE)?)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
    r"([a-zA-Z_][a-zA-Z0-9_.]*)",
    re.IGNORECASE,
)
_GW_FROM_TABLE_PATTERN = re.compile(r"\bFROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.IGNORECASE)


def _suggest_sql_filename(query: str) -> str:
    """Return a descriptive filename (no folder prefix) based on the SQL content."""
    q = query.strip()
    upper = q.upper()
    if upper.startswith("CREATE"):
        op = "create"
    elif upper.startswith("DROP"):
        op = "drop"
    elif upper.startswith("INSERT"):
        op = "insert"
    elif upper.startswith("UPDATE"):
        op = "update"
    elif upper.startswith("DELETE"):
        op = "delete"
    elif upper.startswith("ALTER"):
        op = "alter"
    elif upper.startswith(("SELECT", "WITH")):
        op = "query"
    else:
        op = "script"

    tables: list[str] = []
    for m in _GW_TABLE_NAME_PATTERN.finditer(q):
        name = m.group(1).lower().split(".")[-1]
        if name not in tables:
            tables.append(name)
    if not tables and op == "query":
        for m in _GW_FROM_TABLE_PATTERN.finditer(q):
            name = m.group(1).lower().split(".")[-1]
            if name not in tables:
                tables.append(name)

    if tables:
        return f"{op}_{'_'.join(tables[:2])}.sql"
    return f"{op}.sql"


_SCHEDULE_HAS_TIME_PATTERN = re.compile(
    r"\b(\d{1,2})(:\d{2})?\s*(am|pm)\b"           # "9am", "6:30pm"
    r"|\b(\d{1,2}):\d{2}\b"                         # "09:00", "18:30"
    r"|\b(noon|midnight|midday)\b"                   # named times
    r"|\b(\d{1,2})\s+o[''']?clock\b"                # "9 o'clock"
    r"|\b(cron|[0-5]?\d\s+[01]?\d\s+[\*\d])",       # raw cron expression
    re.IGNORECASE,
)
_SCHEDULE_VAGUE_PATTERN = re.compile(
    r"^\s*(daily|every\s+day|weekly|every\s+week|monthly|every\s+month"
    r"|hourly|every\s+hour|each\s+day|each\s+week|weekdays?|weekends?)\s*$",
    re.IGNORECASE,
)


def _schedule_needs_time(schedule: str) -> bool:
    """Return True when the schedule string is too vague — has a cadence but no time-of-day."""
    s = schedule.strip()
    if _SCHEDULE_HAS_TIME_PATTERN.search(s):
        return False  # already has a time component
    return bool(_SCHEDULE_VAGUE_PATTERN.match(s))


def _suggest_gw_file_path(query: str, folder_hint: str | None) -> str:
    """Build a Git file path from a pre-extracted folder hint and the SQL query.

    ``folder_hint`` comes from the field extractor that already ran on this request,
    so no additional OpenAI call is needed here.
    """
    folder = (folder_hint or "").strip().strip("/")
    if not folder:
        folder = "queries"
    # sanitize folder: allow alphanumeric, underscores, hyphens, slashes
    folder = re.sub(r"[^a-z0-9_\-/]", "_", folder.lower())
    filename = _suggest_sql_filename(query)
    return f"{folder}/{filename}"


def _openai_classify_abandonment(message: str, draft_type: str, awaiting_confirmation: bool) -> bool:
    """Ask OpenAI whether the user wants to abandon the current flow. Returns False on any error."""
    try:
        from app.core.config import settings
        if not settings.openai_api_key:
            return False
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        state_desc = "waiting for user confirmation" if awaiting_confirmation else "collecting required fields"
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"The user is in the middle of creating a {draft_type} job ({state_desc}). "
                        "Classify whether their message means they want to STOP/ABANDON creating this job "
                        "and do something completely DIFFERENT, OR whether they are CONTINUING to provide "
                        "information, asking a question about the current job, or giving a yes/no answer.\n"
                        "Respond with exactly one word: 'abandon' or 'continue'."
                    ),
                },
                {"role": "user", "content": message},
            ],
            max_tokens=5,
            temperature=0,
        )
        return (resp.choices[0].message.content or "").strip().lower().startswith("abandon")
    except Exception:
        logger.debug("OpenAI abandonment classification failed", exc_info=True)
        return False


def _is_abandoning_current_flow(message: str, draft: dict) -> bool:
    """Return True when the user wants to abandon an in-progress multi-step flow."""
    if not draft:
        return False
    # Repo selection ("Connect the GitHub repo X") is always a valid action in the write flow.
    if draft.get("sql_subtype") == "sql_github_write":
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
    # Fast path: unambiguous abandonment phrases — no API call needed
    if _FLOW_ABANDONMENT_PATTERN.search(message) or _TASK_SWITCH_PATTERN.search(message):
        return True
    # Short messages are almost always field answers (names, IDs, dates, single words)
    # not abandonment signals — skip the API call entirely
    if len(message.split()) <= 5:
        return False
    # Slow path: ask OpenAI to classify ambiguous longer messages
    return _openai_classify_abandonment(message, draft_type, bool(draft.get("awaiting_confirmation")))


_REGISTRY_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "src" / "control_center" / "core" / "registry" / "registry.json"
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

# Fallback questions used when OpenAI is unavailable
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


def _load_registry_field_info() -> str:
    """Return a compact field-reference string from registry.json for use in prompts."""
    try:
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
    except Exception:
        return ""
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
    """Check connector exists/is active and environment is allowed. Returns error strings."""
    errors: list[str] = []
    try:
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
    except Exception:
        return []

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


def _load_registry() -> dict[str, Any]:
    try:
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
        return registry if isinstance(registry, dict) else {}
    except Exception:
        return {}


def _sql_ordered_required_fields() -> list[str]:
    """Return universal required fields followed by SQL required fields from registry.json."""
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
    config = draft.get("config") if isinstance(draft.get("config"), dict) else {}
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


async def _tcp_ping(host: str, port: str | int, timeout: float = 3.0) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout seconds."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(str(host), int(port)),
            timeout=timeout,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _ask_llm_for_next_field(
    next_field: str,
    draft: dict,
    session_env: dict,
    history: list[dict] | None,
) -> str:
    """Ask the LLM to generate a natural question for the next missing SQL job field.
    Falls back to _SQL_FIELD_QUESTIONS_FALLBACK on any error."""
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
            "- Be conversational. You may include a brief hint or example in backticks if helpful.\n"
            "- Do NOT re-ask or mention fields already collected.\n"
            "- Do NOT list all the fields — only ask about the one field requested.\n"
            "- NEVER ask about the connector or database type — the connector is always `sql-mcp` and is set automatically. Database connection details (host, port, database name, username, password) are collected via a form, not conversationally.\n"
            f"Already collected: {json.dumps(collected)}\n"
            f"Next field to ask about: {field_label} (key: {next_field})"
        )

        msgs: list[Any] = [{"role": "system", "content": system_prompt}]
        for h in (history or [])[-4:]:
            if isinstance(h, dict) and h.get("role") in {"user", "assistant"}:
                msgs.append({"role": h["role"], "content": str(h.get("content") or "")})

        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=msgs,  # type: ignore[arg-type]
            max_tokens=120,
            temperature=0.7,
        )
        question = (resp.choices[0].message.content or "").strip()
        return question or _SQL_FIELD_QUESTIONS_FALLBACK.get(next_field, f"What is the {next_field}?")
    except Exception:
        logger.debug("LLM field question generation failed", exc_info=True)
        return _SQL_FIELD_QUESTIONS_FALLBACK.get(next_field, f"What is the {next_field}?")


def _is_sql_type_selection(message: str, history: list[dict] | None) -> bool:
    """Return True when the user is selecting SQL as the job type.

    Matches bare messages like "SQL" or "sql job" that follow an assistant turn
    which listed the available job types (identified by mentioning Airflow/Excel/PowerPoint).
    """
    if not _SQL_TYPE_SELECTION_PATTERN.match((message or "").strip()):
        return False
    for msg in reversed(history or []):
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        return bool(_ASKED_JOB_TYPE_PATTERN.search(str(msg.get("content") or "")))
    return False


def _is_new_database_request(message: str, draft: dict) -> bool:
    """Return True when user explicitly wants to connect to a new/different database."""
    if not NEW_DATABASE_REQUEST_PATTERN.search(message or ""):
        return False
    draft_type = str((draft or {}).get("job_type", "")).strip().lower()
    return draft_type == "sql" or bool(SQL_LOOKUP_CONTEXT_PATTERN.search(message or ""))


def _draft_without_connection_details(draft: dict) -> dict:
    """Return draft with all database connection fields cleared, preserving other job fields."""
    connection_keys = {"host", "port", "database", "username", "password", "connection_id", "_connection_id_asked", "_connection_form_shown"}
    clean = {k: v for k, v in draft.items() if k not in connection_keys}
    if isinstance(clean.get("config"), dict):
        clean["config"] = {k: v for k, v in clean["config"].items() if k not in connection_keys}
    return clean


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
    session_env: Optional[dict[str, Any]] = None


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


_ALL_SQL_CONNECTION_FIELDS: list[ConfigRequestField] = [
    ConfigRequestField(**field) for field in SQL_SESSION_ENV_FIELDS
]
_SQLITE_CONNECTION_FIELDS: list[ConfigRequestField] = [
    ConfigRequestField(**f) for f in _SQLITE_SESSION_ENV_FIELDS
]
_SNOWFLAKE_CONNECTION_FIELDS: list[ConfigRequestField] = [
    ConfigRequestField(**f) for f in _SNOWFLAKE_SESSION_ENV_FIELDS
]


def _connection_fields_for_driver(driver: str) -> list[ConfigRequestField]:
    """Return the connection form fields appropriate for the given SQL driver."""
    d = (driver or "").strip().lower()
    if d == "sqlite":
        return _SQLITE_CONNECTION_FIELDS
    if d in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        return _SNOWFLAKE_CONNECTION_FIELDS
    # PostgreSQL, MySQL, and other network databases — full set minus optional connection_id
    pg_fields = [f for f in SQL_SESSION_ENV_FIELDS if f["key"] != "SQL_CONNECTION_ID"]
    return [ConfigRequestField(**f) for f in pg_fields]


def _sql_connection_config_request(prompt: str, fields: list[ConfigRequestField] | None = None) -> ConfigRequest:
    return ConfigRequest(
        kind="sql_session_env",
        prompt=prompt,
        submit_label="Connect database",
        fields=fields if fields is not None else _ALL_SQL_CONNECTION_FIELDS,
    )


class ChatResponse(BaseModel):
    """Response from chat API."""
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
    repository_options: Optional[list[RepositoryOption]] = None
    config_request: Optional[ConfigRequest] = None
    reset_draft: Optional[bool] = None  # True when user abandons current flow
    reset_session_env: Optional[bool] = None  # True when frontend should clear stored DB credentials


def _job_name_for_run(db, job_id: str) -> str:
    job = db.get(Job, job_id)
    if job and getattr(job, "name", None):
        return str(job.name)
    return job_id


def _find_named_job_in_message(db, message: str) -> "Job | None":
    """Try to find an existing job whose name appears in an update message."""
    candidates: list[str] = []
    for m in _NAMED_RESOURCE_REF_PATTERN.finditer(message):
        name = m.group(1) or m.group(2)
        if name:
            candidates.append(name.strip())
    if not candidates:
        return None
    from sqlalchemy import func
    for name in candidates:
        job = (
            db.query(Job)
            .filter(func.lower(Job.name) == name.lower())
            .first()
        )
        if job:
            return job
    return None


def _answer_run_history_question(db, message: str) -> str | None:
    actor = get_chat_actor(db)
    runs = list_runs(db, actor)
    if not runs:
        return "I couldn't find any runs for you yet."

    key = lambda run: run["updated_at"]  # noqa: E731
    if LAST_RUN_QUESTION_PATTERN.search(message):
        last_run = nlargest(1, runs, key=key)[0]
        resource_name = _job_name_for_run(db, last_run["job_id"])
        return (
            f"Your most recent run was `{resource_name}`. "
            f"It is currently `{last_run['status']}` in `{last_run['target_environment']}` "
            f"and was last updated at `{last_run['updated_at']}`."
        )

    lines = ["Here are your most recent runs:"]
    for index, run in enumerate(nlargest(5, runs, key=key), start=1):
        resource_name = _job_name_for_run(db, run["job_id"])
        lines.append(
            f"{index}. `{resource_name}` — status `{run['status']}` — environment `{run['target_environment']}` — updated `{run['updated_at']}`"
        )
    return "\n".join(lines)


def _connected_github_repos(available_resources: list[dict[str, Any]] | None) -> list[RepositoryOption]:
    """Return RepositoryOption objects for GitHub repos the user has already connected."""
    if not available_resources:
        return []
    options: list[RepositoryOption] = []
    seen: set[str] = set()
    for resource in available_resources:
        connector = str(resource.get("connector") or "").strip().lower()
        rtype = str(resource.get("type") or "").strip().lower()
        if connector != "github" and rtype != "repo_connection":
            continue
        config = resource.get("config") or {}
        repo = str(config.get("repo") or "").strip()
        if not repo or repo in seen:
            continue
        seen.add(repo)
        parts = repo.split("/", 1)
        owner = parts[0] if len(parts) == 2 else ""
        name = parts[1] if len(parts) == 2 else repo
        default_branch = str(config.get("ref") or config.get("default_branch") or "").strip() or None
        options.append(RepositoryOption(full_name=repo, owner=owner, name=name, default_branch=default_branch))
    return options


def _get_stored_github_token(available_resources: list[dict[str, Any]] | None, repo: str) -> str | None:
    """Return a previously-saved GitHub PAT for *repo* if one exists in available_resources."""
    if not available_resources or not repo:
        return None
    for resource in available_resources:
        connector = str(resource.get("connector") or "").strip().lower()
        rtype = str(resource.get("type") or "").strip().lower()
        if connector != "github" and rtype != "repo_connection":
            continue
        config = resource.get("config") or {}
        if str(config.get("repo") or "").strip() == repo:
            token = str(config.get("github_token") or "").strip()
            if token:
                return token
    return None


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


def _looks_like_live_sql_lookup(request: "ChatRequest") -> bool:
    if _is_sql_github_write_request(request):
        return False
    message = request.message or ""
    return bool(
        SQL_LOOKUP_ACTION_PATTERN.search(message)
        and SQL_LOOKUP_CONTEXT_PATTERN.search(message)
    )


def _is_sql_job_flow_request(request: "ChatRequest", job_creation_intent: bool) -> bool:
    if _has_sql_draft(request):
        return True
    if _looks_like_live_sql_lookup(request) or _looks_like_sql_connect_request(request):
        return True
    if not job_creation_intent:
        return False
    return SQL_LOOKUP_CONTEXT_PATTERN.search(request.message or "") is not None


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


def _missing_sql_session_env(session_env: dict[str, str], db_driver: str = "") -> list[ConfigRequestField]:
    driver = (db_driver or "").strip().lower()
    if driver == "sqlite":
        fields_to_check = _SQLITE_SESSION_ENV_FIELDS
    elif driver in ("snowflake", "snowflake+snowflake-sqlalchemy"):
        fields_to_check = _SNOWFLAKE_SESSION_ENV_FIELDS
    else:
        fields_to_check = SQL_SESSION_ENV_FIELDS
    missing: list[ConfigRequestField] = []
    derived_connection_string = _build_sql_connection_string(session_env) if driver not in ("sqlite",) else None
    for field in fields_to_check:
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
        merged.get("target_environment") or merged.get("environment") or config.get("target_environment") or config.get("environment") or ""
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
                    "Next I need the target environment for this job: `dev`, `semi-prod`, or `prod`."
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
    """Route a chat message through SQL, GitHub, or generic LLM flows."""
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        draft = request.current_draft_data or {}
        # True when the connection form was just submitted: the frontend re-sends the
        # original message (e.g. "I want to run a SQL query") which would otherwise
        # be mis-classified as abandonment by the OpenAI classifier.
        _form_already_shown = bool(draft.get("_connection_form_shown"))

        if not _form_already_shown and _is_abandoning_current_flow(request.message, draft):
            return ChatResponse(
                response="No problem — I've cleared the job draft. What would you like to do next?",
                job_creation_intent=False,
                extracted_fields=None,
                reset_draft=True,
            )

        if LAST_RUN_QUESTION_PATTERN.search(request.message) or RECENT_RUNS_QUESTION_PATTERN.search(request.message):
            return ChatResponse(
                response=_answer_run_history_question(db, request.message),
                job_creation_intent=False,
            )

        # --- Delete job intent ---
        if DELETE_JOB_PATTERN.search(request.message) and not draft:
            actor = get_chat_actor(db)
            all_jobs = list_jobs_service(db, actor)
            # Try to match a job name from the message
            msg_lower = request.message.lower()
            matched = None
            for j in all_jobs:
                if str(j.name or "").lower() in msg_lower:
                    matched = j
                    break
            if not matched:
                # Ask which job
                job_names = ", ".join(f"`{j.name}`" for j in all_jobs) if all_jobs else "none"
                return ChatResponse(
                    response=(
                        f"Which job would you like to delete? Your current jobs are: {job_names}. "
                        "Please tell me the exact job name."
                    ),
                    job_creation_intent=False,
                )
            matched_name = str(matched.name or "")
            matched_id = str(matched.id or "")
            # Check if the previous bot turn was already a delete confirmation prompt for this job
            history_msgs = request.conversation_history or []
            last_bot = next(
                (m.content for m in reversed(history_msgs) if m.role == "assistant"), ""
            ) or ""
            if f'"{matched_name}"' in last_bot and "confirm" in last_bot.lower():
                # User replied after confirmation prompt — treat any affirmative as yes
                affirmatives = {"yes", "yeah", "yep", "confirm", "do it", "sure", "ok", "okay", "delete it", "proceed"}
                if any(a in msg_lower for a in affirmatives):
                    try:
                        delete_job_service(db, actor, matched_id)
                        return ChatResponse(
                            response=f'Job **"{matched_name}"** has been deleted along with its run history.',
                            job_creation_intent=False,
                        )
                    except Exception as exc:
                        logger.exception("Failed to delete job %s from chat", matched_id)
                        return ChatResponse(
                            response=f"Sorry, I couldn't delete the job: {exc}",
                            job_creation_intent=False,
                        )
                else:
                    return ChatResponse(
                        response=f'Got it — I won\'t delete **"{matched_name}"**. Let me know if there\'s anything else I can help with.',
                        job_creation_intent=False,
                    )
            # First time — ask for confirmation
            return ChatResponse(
                response=(
                    f'Are you sure you want to delete job **"{matched_name}"**? '
                    "This will permanently remove the job and all of its run history. "
                    "Reply **yes** to confirm or **no** to cancel."
                ),
                job_creation_intent=False,
            )

        # Detect job creation intent from user message
        job_creation_intent = detect_job_creation_intent(request.message)
        deterministic_repo_fields = _deterministic_repo_connection_fields(request)
        github_token = request.github_personal_access_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        session_env = _effective_session_env(request)
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in (request.conversation_history or [])]

        # --- SQL type selection: "SQL" after "what type of job?" → enter structured flow now ---
        if _is_sql_type_selection(request.message, history_dicts) and not _form_already_shown:
            return ChatResponse(
                response=(
                    "Great choice! To get started with your SQL job, I'll need the database "
                    "connection details. Please fill in the form below."
                ),
                job_creation_intent=True,
                extracted_fields={
                    **(request.current_draft_data or {}),
                    "job_type": "SQL",
                    "_connection_form_shown": True,
                    "_connection_id_asked": True,
                },
                config_request=_sql_connection_config_request("Enter the database connection details for this SQL job."),
                reset_session_env=True,
            )

        is_sql_job_flow = _is_sql_job_flow_request(request, job_creation_intent)

        # --- New/different database: always collect fresh connection details ---
        if _is_new_database_request(request.message, request.current_draft_data or {}):
            clean_draft = _draft_without_connection_details(request.current_draft_data or {})
            ef = {
                "job_type": "SQL",
                **clean_draft,
                "_connection_form_shown": True,
                "_connection_id_asked": True,
            }
            return ChatResponse(
                response=(
                    "Sure! To connect to the new database, I'll need its connection details. "
                    "Please provide the host, port, database name, username, and password below."
                ),
                job_creation_intent=is_sql_job_flow,
                extracted_fields=ef if is_sql_job_flow else None,
                config_request=_sql_connection_config_request("Enter the connection details for the new database."),
                reset_session_env=True,
            )

        # --- Named resource update: "change the query for create-tables-3" → skip connection form ---
        if _UPDATE_RESOURCE_PATTERN.search(request.message) and not draft.get("job_id"):
            named_resource = _find_named_job_in_message(db, request.message)
            if named_resource is not None:
                ai_fields = _openai_extract_sql_fields(request.message, draft, history_dicts)
                update_msg, draft_updates = update_sql_job_from_chat(
                    db, named_resource.id, ai_fields
                )
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
                return ChatResponse(
                    response=update_msg,
                    job_creation_intent=True,
                    extracted_fields=new_draft,
                )

        _early_draft = request.current_draft_data or {}
        _early_db_driver = _non_empty_str(_early_draft.get("db_driver") or (_early_draft.get("config") or {}).get("db_driver")) or ""
        # If the driver isn't in the draft yet, detect it from the current message so
        # the connection form shows the right fields before field extraction runs.
        if not _early_db_driver:
            _detected_early = _detect_sql_driver(request.message)
            if _detected_early:
                _early_db_driver = _detected_early
                _early_draft = {**_early_draft, "db_driver": _detected_early}
        missing_sql_session_fields = _missing_sql_session_env(session_env, _early_db_driver)
        if (
            missing_sql_session_fields
            and not _form_already_shown
            and (_looks_like_live_sql_lookup(request) or is_sql_job_flow)
            and not _is_sql_github_write_request(request)
        ):
            _early_driver_label = _SQL_DRIVER_DISPLAY.get(_early_db_driver.lower(), "SQL")
            _skip_conn_id = _early_db_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
            ef = {
                **_early_draft,
                "job_type": "SQL",
                "_connection_form_shown": True,
                "_connection_id_asked": _skip_conn_id,
            }
            return ChatResponse(
                response=(
                    f"Before we proceed, I need the **{_early_driver_label}** connection details for this session. "
                    "Please fill in the form below."
                    if _early_db_driver else
                    "Before I can run a live SQL query in this chat, I need the database connection details "
                    "for this session. Please provide the host, port, database name, username, and password."
                ),
                job_creation_intent=is_sql_job_flow,
                extracted_fields=ef if is_sql_job_flow else None,
                config_request=_sql_connection_config_request(
                    f"Enter the {_early_driver_label} connection details for this chat session.",
                    fields=missing_sql_session_fields,
                ),
            )

        # --- SQL GitHub write flow: write a SQL query file into a GitHub repository ---
        if _is_sql_github_write_request(request):
            draft = request.current_draft_data or {}
            last_asked_gw = _last_asked_github_write_field(history_dicts)
            new_gw: dict[str, Any] = {}
            if last_asked_gw and last_asked_gw != "query":
                val = request.message.strip()
                if val:
                    new_gw[last_asked_gw] = val

            # If the user clicked a RepositoryOption (sends "Connect the GitHub repo X branch Y"),
            # extract the repo slug and fold it into the draft rather than triggering a standalone flow.
            if deterministic_repo_fields.get("repo"):
                new_gw["repo"] = deterministic_repo_fields["repo"]
                if deterministic_repo_fields.get("ref"):
                    new_gw["ref"] = deterministic_repo_fields["ref"]

            merged_gw = {**draft, **new_gw}
            gw_config = merged_gw.get("config") if isinstance(merged_gw.get("config"), dict) else {}
            gw_query = _non_empty_str(merged_gw.get("query")) or _non_empty_str(gw_config.get("query"))
            gw_repo = _non_empty_str(merged_gw.get("repo")) or _non_empty_str(gw_config.get("repo"))
            gw_ref = _non_empty_str(merged_gw.get("ref")) or _non_empty_str(merged_gw.get("branch"))
            base_ef: dict[str, Any] = {"sql_subtype": "sql_github_write", **new_gw}

            # Extract/generate SQL from the current message.
            # Run when: (a) no query yet and the user hasn't been asked yet, OR
            #           (b) the bot just asked for the query (user may have replied in natural language).
            folder_hint: str | None = _non_empty_str(merged_gw.get("folder_hint"))
            if not gw_query or last_asked_gw == "query":
                ai_q = _openai_extract_sql_fields(request.message, merged_gw, history_dicts)
                if ai_q.get("query"):
                    gw_query = ai_q["query"]
                    new_gw["query"] = gw_query
                    base_ef["query"] = gw_query
                if ai_q.get("folder_hint"):
                    folder_hint = ai_q["folder_hint"]
                    new_gw["folder_hint"] = folder_hint
                # Persist any other inferred fields (run_type, schedule, job_name, owner)
                # so we don't ask for things the user already told us
                for _f in ("run_type", "schedule", "job_name", "owner"):
                    if ai_q.get(_f) and not _non_empty_str(merged_gw.get(_f)):
                        new_gw[_f] = str(ai_q[_f]).strip()
                        base_ef[_f] = new_gw[_f]
                # Refresh merged_gw so field-checks below see the inferred values
                merged_gw = {**merged_gw, **new_gw}

            if not gw_query:
                return ChatResponse(
                    response="What SQL script would you like to write to the repository?",
                    job_creation_intent=True,
                    extracted_fields=base_ef,
                )

            # Derive a descriptive filename once we know the query; persist it in the draft
            explicit_file = _non_empty_str(merged_gw.get("file_path")) or _non_empty_str(merged_gw.get("path"))
            if explicit_file:
                gw_file = explicit_file
            else:
                gw_file = _suggest_gw_file_path(gw_query, folder_hint)
                base_ef["file_path"] = gw_file

            # No repo chosen yet — offer connected repos first, then fall back to PAT
            if not gw_repo:
                file_note = f"I'll save it as `{gw_file}`. "
                connected_repos = _connected_github_repos(request.available_resources)
                if connected_repos:
                    return ChatResponse(
                        response=(
                            f"{file_note}Which repository should I write this to? "
                            "You have these repositories already connected — pick one below, "
                            "or provide a different repo in `owner/repo-name` format."
                        ),
                        job_creation_intent=True,
                        extracted_fields={**base_ef, "query": gw_query},
                        repository_options=connected_repos,
                    )
                if not github_token:
                    return ChatResponse(
                        response=(
                            f"{file_note}To write the SQL to a GitHub repository, I need a personal "
                            "access token with repository write access."
                        ),
                        job_creation_intent=True,
                        extracted_fields={**base_ef, "query": gw_query},
                        secret_request=SecretRequest(
                            kind="github_personal_access_token",
                            prompt="Enter a GitHub personal access token with repo write access.",
                            submit_label="Use token",
                        ),
                    )
                try:
                    repo_options = await _list_github_repository_options(github_token)
                except httpx.HTTPError as exc:
                    logger.warning("Unable to list GitHub repositories: %s", exc)
                    return ChatResponse(
                        response=f"{file_note}Which GitHub repository should I write it to? (format: `owner/repo-name`)",
                        job_creation_intent=True,
                        extracted_fields={**base_ef, "query": gw_query},
                    )
                return ChatResponse(
                    response=(
                        f"{file_note}Which repository should I write this to? "
                        "Here are your available repositories — pick one or provide a different repo."
                    ),
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query},
                    repository_options=repo_options,
                )

            # Both query and repo are known — collect universal job fields before writing.
            # merged_gw was refreshed above after AI extraction, so inferred values are visible here.
            gw_job_name = _non_empty_str(merged_gw.get("job_name") or merged_gw.get("name"))
            gw_owner_field = _non_empty_str(merged_gw.get("owner"))
            gw_run_type = str(merged_gw.get("run_type") or "").strip().lower()
            gw_schedule = _non_empty_str(merged_gw.get("schedule"))

            if not gw_job_name:
                return ChatResponse(
                    response="What name would you like to give this job?",
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo, "_pending_field": "job_name"},
                )
            if not gw_owner_field:
                return ChatResponse(
                    response="Who is the owner of this job?",
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo, "_pending_field": "owner"},
                )
            if not gw_run_type:
                return ChatResponse(
                    response="Should this be a **one-time** (manual) run or a **scheduled** job?",
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo, "_pending_field": "run_type"},
                )
            if gw_run_type == "scheduled" and not gw_schedule:
                return ChatResponse(
                    response="What schedule should I use? (e.g., `every day at 9am`, `30 8 * * 1-5`)",
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo, "_pending_field": "schedule"},
                )
            # If a schedule was inferred but is too vague (no time-of-day), ask for clarification
            if gw_run_type == "scheduled" and gw_schedule and _schedule_needs_time(gw_schedule):
                return ChatResponse(
                    response=(
                        f"I see you want to run this **{gw_schedule}** — what time of day should it run? "
                        "(e.g., `every day at 9am`, `daily at 6pm`)"
                    ),
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo, "_pending_field": "schedule"},
                )

            # All fields collected — look up a stored PAT from the database first
            if not github_token:
                github_token = get_github_token_for_repo(db, gw_repo)

            if not github_token:
                return ChatResponse(
                    response=(
                        f"Almost done! I just need a GitHub personal access token with "
                        "repository write access to commit the file."
                    ),
                    job_creation_intent=True,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo},
                    secret_request=SecretRequest(
                        kind="github_personal_access_token",
                        prompt="Enter a GitHub personal access token with repo write access.",
                        submit_label="Use token",
                    ),
                )

            try:
                reg = register_github_write_job_from_chat(
                    db,
                    extracted_fields={**base_ef, "query": gw_query, "repo": gw_repo},
                    current_draft=merged_gw,
                    github_token=github_token,
                )
            except Exception:
                logger.exception("GitHub write job registration failed")
                return ChatResponse(
                    response="I ran into an error registering the job. Please try again.",
                    job_creation_intent=False,
                    extracted_fields={"sql_subtype": "sql_github_write"},
                )

            # Store the PAT in the repo_connection job so future chat sessions skip the credential prompt
            try:
                save_github_token_for_repo(db, gw_repo, gw_ref, github_token)
            except Exception:
                logger.warning("Failed to save GitHub token for repo %s", gw_repo)

            # Scheduled jobs: just confirm registration — the scheduler will run them at the right time.
            # One-time (manual) jobs: execute immediately so the file is committed now.
            if gw_run_type == "scheduled":
                schedule_desc = gw_schedule or "the configured schedule"
                return ChatResponse(
                    response=(
                        f"Done! I've registered **{reg.job_name}** as a scheduled job. "
                        f"It will write `{gw_file}` to `{gw_repo}` according to: *{schedule_desc}*."
                    ),
                    job_creation_intent=False,
                    extracted_fields={"sql_subtype": "sql_github_write"},
                    job_id=reg.job_id,
                )

            run_result = run_job_by_id(
                db,
                job_id=reg.job_id,
                extra_params={
                    "github_token": github_token,
                    "query": gw_query,
                    "path": gw_file,
                    "repo": gw_repo,
                    "branch": gw_ref or "main",
                },
            )
            if not run_result.executed:
                return ChatResponse(
                    response=f"Job **{reg.job_name}** was registered, but I couldn't start the run: {run_result.message}",
                    job_creation_intent=False,
                    extracted_fields={"sql_subtype": "sql_github_write"},
                    job_id=reg.job_id,
                )

            return ChatResponse(
                response=(
                    f"Done! I've registered **{reg.job_name}** and started a run to write "
                    f"`{gw_file}` to `{gw_repo}`.\n\n{run_result.message}"
                ),
                job_creation_intent=False,
                extracted_fields={"sql_subtype": "sql_github_write"},
                mcp_tool_executed=True,
                mcp_servers=["github"],
                job_id=reg.job_id,
            )

        # --- SQL flow: structured state machine (universal fields → SQL fields → confirm → run) ---
        if is_sql_job_flow:
            draft = request.current_draft_data or {}

            # Belt-and-suspenders abandonment check inside the SQL flow
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

                # Deterministic fallback: always apply for the specifically-asked field so the
                # user's direct answer overrides anything the LLM inferred from draft context.
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

            # Merge new fields with the current draft
            merged: dict[str, Any] = {**draft, **new_ef}
            if "config" in new_ef:
                merged["config"] = {**(draft.get("config") or {}), **new_ef["config"]}
            if isinstance(merged.get("config"), dict):
                merged["config"] = {k: v for k, v in merged["config"].items() if k not in {"target_environment", "environment"}}
            if not _non_empty_str(merged.get("target_environment")) and _non_empty_str(merged.get("environment")):
                merged["target_environment"] = merged["environment"]
            merged.pop("environment", None)
            # Keep db_driver in sync between top-level draft and config so the executor always sees it
            if merged.get("db_driver") and not (merged.get("config") or {}).get("db_driver"):
                merged.setdefault("config", {})["db_driver"] = merged["db_driver"]
            # Strip connection_id and connector from the draft for non-PostgreSQL drivers — they are
            # not needed and confuse the agent prompt.  The frontend echoes back old state so we must
            # remove it here on every turn, not just at extraction time.
            _active_driver = _non_empty_str(merged.get("db_driver") or (merged.get("config") or {}).get("db_driver") or "")
            if _active_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}:
                merged.pop("connection_id", None)
                merged.pop("connector", None)
                if isinstance(merged.get("config"), dict):
                    merged["config"].pop("connection_id", None)
                if isinstance(merged.get("params"), dict):
                    merged["params"].pop("connection_id", None)
            # Persist session_env connection values into the draft so they survive across turns.
            # session_env is only present in the turn where the form is submitted; without this,
            # the database path / credentials are gone by the "yes" confirmation turn.
            if merged.get("_connection_form_shown") and session_env:
                for _fld, _env_key in (
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
            if last_asked not in (None, "confirm"):
                if last_asked in ("connection_id", "db_driver") or _sql_field_has_value(last_asked, merged, session_env):
                    merged.pop("_pending_field", None)
            if "awaiting_confirmation" in merged and last_asked != "confirm":
                merged.pop("awaiting_confirmation", None)

            connection_status_message, connection_status_fields = await _sql_connection_status_message(merged, session_env)
            if connection_status_fields:
                merged.update(connection_status_fields)

            # Confirmation step: user answered yes/no to the summary
            if last_asked == "confirm":
                if _AFFIRMATIVE_RESPONSE_PATTERN.match(request.message.strip()):
                    cfg = _sql_config_with_session_env(merged, session_env)
                    run_type = str(merged.get("run_type") or "manual").strip().lower()

                    # Scheduled jobs: register only — the schedule triggers future runs
                    if run_type == "scheduled":
                        registration_result = register_sql_job_from_chat(
                            db,
                            extracted_fields={**merged, "config": cfg, "creation_requested": True},
                            current_draft=merged,
                        )
                        job_label = merged.get("job_name") or merged.get("name") or "your SQL job"
                        schedule = merged.get("schedule") or cfg.get("schedule") or ""
                        schedule_msg = f" It is scheduled to run `{schedule}`." if schedule else ""
                        reg_msg = (
                            f"Registered SQL job `{job_label}`.{schedule_msg}"
                            if registration_result.job_id
                            else registration_result.message
                        )
                        return ChatResponse(
                            response=reg_msg,
                            job_creation_intent=True,
                            extracted_fields=_clear_sql_transient_fields({
                                **merged,
                                "config": cfg,
                                "job_id": registration_result.job_id,
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
                            db,
                            message="run sql job",
                            extracted_fields=exec_fields,
                            current_draft=merged,
                        )
                    except Exception as exec_err:
                        logger.exception("SQL job execution failed after chat confirmation")
                        err_str = str(exec_err)
                        if "ConnectError" in err_str or "Connection" in err_str or "connection" in err_str:
                            user_msg = (
                                "I couldn't execute the SQL job — "
                                "the SQL MCP server at `http://localhost:5100/mcp` is not reachable. "
                                "Please start the SQL MCP server and try again."
                            )
                        else:
                            user_msg = f"Execution failed: {err_str}"
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
                                **merged,
                                "job_id": sql_result.job_id,
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
                    # Extract any field updates the user mentioned (e.g. "change the query to X")
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

            # Determine SQL driver — ask if not yet known (only before connection form is shown)
            if not merged.get("_connection_form_shown"):
                db_driver = _non_empty_str(merged.get("db_driver") or (merged.get("config") or {}).get("db_driver"))
                if not db_driver:
                    # Try to auto-detect from the current or initial message
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
                        # User just answered but we still couldn't detect — ask again
                        return ChatResponse(
                            response=(
                                "I didn't catch that. Which database type would you like to use?\n\n"
                                "- **PostgreSQL** — standard relational database\n"
                                "- **SQLite** — local file-based database (no server needed)\n"
                                "- **Snowflake** — cloud data warehouse"
                            ),
                            job_creation_intent=True,
                            extracted_fields={**merged, "_pending_field": "db_driver"},
                        )
                    else:
                        # No type known yet — ask the user
                        return ChatResponse(
                            response=(
                                "What type of SQL database would you like to connect to?\n\n"
                                "- **PostgreSQL** — standard relational database\n"
                                "- **SQLite** — local file-based database (no server needed)\n"
                                "- **Snowflake** — cloud data warehouse"
                            ),
                            job_creation_intent=True,
                            extracted_fields={**merged, "_pending_field": "db_driver"},
                        )

            # Show the connection form on first entry; merged preserves any fields already collected.
            if not merged.get("_connection_form_shown"):
                db_driver = _non_empty_str(merged.get("db_driver") or (merged.get("config") or {}).get("db_driver")) or ""
                driver_label = _SQL_DRIVER_DISPLAY.get(db_driver.lower(), db_driver.capitalize() if db_driver else "SQL")
                connection_prompt = f"Enter the {driver_label} connection details for this job."
                connection_response = (
                    f"Great, I'll set up a **{driver_label}** SQL job. "
                    "Please fill in the connection details below."
                )
                skip_connection_id = db_driver.lower() in {"sqlite", "snowflake", "snowflake+snowflake-sqlalchemy"}
                return ChatResponse(
                    response=connection_response,
                    job_creation_intent=True,
                    extracted_fields={
                        **merged,
                        "_connection_form_shown": True,
                        "_connection_id_asked": skip_connection_id,
                    },
                    config_request=_sql_connection_config_request(
                        connection_prompt,
                        fields=_connection_fields_for_driver(db_driver),
                    ),
                    reset_session_env=True,
                )

            # Ask for the next missing field
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

            # All fields collected — validate before showing confirmation
            cfg: dict[str, Any] = merged.get("config") or {}
            connector = str(merged.get("connector") or "sql-mcp").strip().lower()
            environment = _resolved_job_environment(merged).strip().lower()

            # 1 & 2: Registry checks — connector active + environment allowed
            registry_errors = _validate_against_registry(connector, environment)
            if registry_errors:
                error_lines = "\n".join(f"- {e}" for e in registry_errors)
                return ChatResponse(
                    response=(
                        f"I found a configuration issue before creating the job:\n{error_lines}\n\n"
                        "What would you like to change?"
                    ),
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
                        **merged,
                        "config": cfg,
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
                        **merged,
                        "config": cfg,
                        "job_id": registration_result.job_id,
                        "name": registration_result.job_name or merged.get("job_name") or merged.get("name"),
                        "creation_requested": True,
                    }),
                    job_id=registration_result.job_id,
                )

            # 3: TCP reachability check — verify host:port is accessible
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

            # All validated — show the confirmation summary
            if explicit_run_request:
                exec_fields = {
                    **merged,
                    "action": "run",
                }
                try:
                    sql_result = maybe_run_sql_job_from_chat(
                        db,
                        message=request.message,
                        extracted_fields=exec_fields,
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
                            **merged,
                            "job_id": sql_result.job_id,
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
                    extracted_fields={
                        **merged,
                        "creation_requested": True,
                    },
                    current_draft=merged,
                )
                return ChatResponse(
                    response=registration_result.message,
                    job_creation_intent=True,
                    extracted_fields=_clear_sql_transient_fields({
                        **merged,
                        "job_id": registration_result.job_id,
                        "name": registration_result.job_name or merged.get("job_name") or merged.get("name"),
                        "creation_requested": True,
                    }),
                    job_id=registration_result.job_id,
                )

            # Job already registered — update fields, run it, or inform the user
            if merged.get("job_id"):
                msg = request.message.strip()

                # Update request: "change the schedule to...", "update the query", etc.
                if _UPDATE_RESOURCE_PATTERN.search(msg):
                    ai_fields = _openai_extract_sql_fields(msg, merged, history_dicts)
                    update_msg, draft_updates = update_sql_job_from_chat(
                        db, merged["job_id"], ai_fields
                    )
                    new_draft = _clear_sql_transient_fields({**merged, **draft_updates})
                    # Merge updated config fields back into draft["config"] so frontend reflects changes
                    config_patch: dict[str, Any] = {}
                    if "config" in draft_updates and isinstance(draft_updates["config"], dict):
                        config_patch.update(draft_updates["config"])
                    for _f in ("query", "schedule", "connection_id", "run_type"):
                        if _f in draft_updates:
                            config_patch[_f] = draft_updates[_f]
                    if config_patch:
                        new_draft["config"] = {**(merged.get("config") or {}), **config_patch}
                    return ChatResponse(
                        response=update_msg,
                        job_creation_intent=True,
                        extracted_fields=new_draft,
                    )

                # "run it" / "yes" / explicit run verb without update context
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
                            **merged,
                            "job_id": run_result.job_id,
                            "name": merged.get("job_name") or merged.get("name"),
                        }),
                        job_id=run_result.job_id,
                        run_id=run_result.run_id,
                        run_status=run_result.run_status,
                        sql_job_executed=run_result.executed,
                    )
                job_label = merged.get("job_name") or merged.get("name") or "your SQL job"
                return ChatResponse(
                    response=f"Your SQL job `{job_label}` is registered. You can run it or update its fields (schedule, query, etc.).",
                    job_creation_intent=True,
                    extracted_fields=_clear_sql_transient_fields(merged),
                )

            summary = _build_sql_job_summary(merged, session_env)
            if connection_status_message:
                summary = f"{connection_status_message}\n\n{summary}"
            return ChatResponse(
                response=summary,
                job_creation_intent=True,
                extracted_fields={**merged, "awaiting_confirmation": True, "_pending_field": "confirm"},
            )

        # Standalone "connect repo" intent → redirect into the SQL GitHub write flow.
        # Repository connections are not a job type on their own; they are part of writing SQL to a repo.
        if deterministic_repo_fields.get("connection_intent") == "connect_repo":
            gw_ef: dict[str, Any] = {"sql_subtype": "sql_github_write"}
            if deterministic_repo_fields.get("repo"):
                gw_ef["repo"] = deterministic_repo_fields["repo"]
            if deterministic_repo_fields.get("ref"):
                gw_ef["ref"] = deterministic_repo_fields["ref"]
            connected_repos = _connected_github_repos(request.available_resources)
            if connected_repos and not gw_ef.get("repo"):
                return ChatResponse(
                    response=(
                        "To write SQL to a repository, pick one you’ve already connected below "
                        "or provide a different repo in `owner/repo-name` format. "
                        "What SQL query would you like to save?"
                    ),
                    job_creation_intent=True,
                    extracted_fields=gw_ef,
                    repository_options=connected_repos,
                )
            if not github_token:
                return ChatResponse(
                    response=(
                        "I can write SQL code to a GitHub repository. "
                        "First I need a personal access token with repository write access."
                    ),
                    job_creation_intent=True,
                    extracted_fields=gw_ef,
                    secret_request=SecretRequest(
                        kind="github_personal_access_token",
                        prompt="Enter a GitHub personal access token with repo write access.",
                        submit_label="Use token",
                    ),
                )
            try:
                repo_opts = await _list_github_repository_options(github_token)
            except httpx.HTTPError as exc:
                logger.warning("Unable to list GitHub repositories: %s", exc)
                repo_opts = []
            return ChatResponse(
                response=(
                    "I can write SQL code to a GitHub repository. "
                    "Pick one below or provide a repo in `owner/repo-name` format. "
                    "What SQL query would you like to save?"
                ),
                job_creation_intent=True,
                extracted_fields=gw_ef,
                repository_options=repo_opts or None,
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
                job_id=preflight_sql_job_result.job_id,
                run_id=preflight_sql_job_result.run_id,
                run_status=preflight_sql_job_result.run_status,
                sql_job_executed=preflight_sql_job_result.executed,
            )

        chat_service = get_chat_service()
        response = await chat_service.send_message(
            message=request.message,
            conversation_history=history_dicts or None,
            model=request.model,
            current_draft=request.current_draft_data,
            available_resources=request.available_resources,
        )
        
        # Handle [RUN_JOB:job_id] marker emitted by the LLM
        sql_flow_active = _has_sql_draft(request) or _looks_like_sql_connect_request(request)
        run_marker_match = RUN_JOB_MARKER_PATTERN.search(response)
        if run_marker_match:
            job_id_to_run = run_marker_match.group(1)
            clean_response = RUN_JOB_MARKER_PATTERN.sub("", response).strip()
            if not sql_flow_active:
                run_result = run_job_by_id(db, job_id_to_run)
                final_response = f"{clean_response}\n\n{run_result.message}".strip()
                return ChatResponse(
                    response=final_response,
                    job_creation_intent=job_creation_intent,
                    extracted_fields=None,
                    job_id=run_result.job_id,
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
                "connector": extracted_fields.get("connector") or "sql-mcp",
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
                conversation_history=history_dicts or None,
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
            job_id=sql_job_result.job_id if sql_job_result is not None else None,
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
