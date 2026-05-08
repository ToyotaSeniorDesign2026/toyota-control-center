"""Control Center MCP server.

Exposes Toyota Control Center jobs and runs as MCP tools so that MCPAgent
can orchestrate them without going through the OpenAI function-calling loop.

Required environment variables:
    CC_API_BASE_URL     — Base URL of the Control Center API (default: http://localhost:8000)
    CC_SERVICE_TOKEN    — Internal service token set as CC_INTERNAL_SERVICE_TOKEN on the API
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_BASE_URL = (os.environ.get("CC_API_BASE_URL") or "http://localhost:8000").rstrip("/")
_TOKEN = os.environ.get("CC_SERVICE_TOKEN", "")
_USER_TOKEN = os.environ.get("CC_USER_TOKEN", "")

mcp = FastMCP("control-center")


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    tok = token or _TOKEN
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _get(path: str, params: dict | None = None) -> Any:
    url = f"{_BASE_URL}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: dict, token: str | None = None) -> Any:
    url = f"{_BASE_URL}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=_headers(token), content=json.dumps(body))
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def list_jobs(job_type: str | None = None, status: str | None = None) -> list[dict]:
    """List all registered jobs.

    Args:
        job_type: Filter by job type (e.g. 'sql', 'repo_connection', 'mcp').
        status:   Filter by status (e.g. 'active', 'paused', 'archived').

    Returns a list of job objects with id, name, type, kind, status, connector.
    """
    try:
        params: dict[str, str] = {}
        if job_type:
            params["job_type"] = job_type
        if status:
            params["status"] = status
        result = _get("/jobs", params=params or None)
        items = result.get("items", result) if isinstance(result, dict) else result
        return [
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "type": j.get("type"),
                "kind": j.get("kind"),
                "status": j.get("status"),
                "connector": j.get("connector"),
                "environment": j.get("environment"),
                "description": j.get("description"),
            }
            for j in (items or [])
        ]
    except Exception as exc:
        raise ValueError(f"Failed to list jobs: {exc}") from exc


@mcp.tool()
def get_job(job_id: str) -> dict:
    """Get details for a specific job by ID.

    Args:
        job_id: The job UUID.

    Returns the full job object.
    """
    try:
        return _get(f"/jobs/{job_id}")
    except Exception as exc:
        raise ValueError(f"Failed to get job '{job_id}': {exc}") from exc


@mcp.tool()
def list_runs(job_id: str | None = None, limit: int = 20) -> list[dict]:
    """List recent job runs.

    Args:
        job_id: If given, only return runs for this job.
        limit:  Maximum number of runs to return (default 20).

    Returns a list of run objects with id, job_id, status, created_at, finished_at.
    """
    try:
        params: dict[str, Any] = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        result = _get("/runs", params=params)
        items = result.get("items", result) if isinstance(result, dict) else result
        return [
            {
                "id": r.get("id"),
                "job_id": r.get("job_id"),
                "status": r.get("status"),
                "action": r.get("action"),
                "created_at": r.get("created_at"),
                "finished_at": r.get("finished_at"),
                "error": r.get("error"),
            }
            for r in (items or [])
        ]
    except Exception as exc:
        raise ValueError(f"Failed to list runs: {exc}") from exc


@mcp.tool()
def get_run_status(run_id: str) -> dict:
    """Get the current status of a specific run.

    Args:
        run_id: The run UUID.

    Returns status, timestamps, and any error details.
    """
    try:
        return _get(f"/runs/{run_id}/status")
    except Exception as exc:
        raise ValueError(f"Failed to get run status for '{run_id}': {exc}") from exc


@mcp.tool()
def trigger_run(
    job_id: str,
    action: str = "run",
    params: str = "{}",
    target_environment: str = "dev",
    prompt: str = "",
) -> dict:
    """Trigger a new run for an existing job.

    Routes through the v2 endpoint (POST /api/chat/run) so it handles all
    executor types — sql, mcp_agent, airflow_python — uniformly. Falls back
    to the legacy /jobs/{id}/runs endpoint if the v2 path is unavailable.

    Args:
        job_id:             The job UUID to run.
        action:             Action to perform (default 'run'; v2 ignores this).
        params:             JSON string of run parameters (e.g. '{"query": "SELECT 1"}').
        target_environment: Deployment environment (default 'dev').
        prompt:             Optional prompt — used by mcp_agent jobs. If omitted,
                            a generic 'run job' prompt is sent.

    Returns the newly created run object (v2 wraps it under .run; legacy returns it flat).
    """
    try:
        parsed_params = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"params must be a valid JSON string: {exc}") from exc

    # Try v2 first — handles every executor_type via the contract registry.
    try:
        body_v2 = {
            "prompt": prompt or "run",
            "job_id": job_id,
            "params": parsed_params,
            "target_environment": target_environment,
        }
        result = _post("/api/chat/run", body_v2, token=_USER_TOKEN or None)
        # v2 wraps run under "run" — flatten for backward-compat.
        if isinstance(result, dict) and "run" in result and isinstance(result["run"], dict):
            run = dict(result["run"])
            run["_v2_wrapper"] = {
                "executor_type": result.get("executor_type"),
                "contract_type": result.get("contract_type"),
            }
            return run
        return result
    except Exception as v2_exc:
        # Fall back to legacy. Useful if /api/chat/run isn't mounted yet.
        try:
            body_legacy = {
                "action": action,
                "target_environment": target_environment,
                "params": parsed_params,
            }
            return _post(f"/jobs/{job_id}/runs", body_legacy)
        except Exception as legacy_exc:
            raise ValueError(
                f"Failed to trigger run for job '{job_id}'. "
                f"v2 error: {v2_exc}; legacy error: {legacy_exc}"
            ) from legacy_exc


@mcp.tool()
def request_db_type_selection() -> dict:
    """Render a database type picker in the user's browser.

    YOU MUST CALL THIS TOOL — do not describe the options in plain text.
    Calling this tool is what physically renders the picker UI. Without it,
    the user has no way to select a database type.

    Call this whenever the user wants to create a SQL job and has not yet
    specified which database system they are connecting to.

    After calling this tool, ask "Which database are you connecting to?" and stop.
    Wait for the user's selection before proceeding.
    """
    return {"signal": "db_type_selection", "status": "Database type selection form shown to user."}


@mcp.tool()
def request_db_connection_form(db_type: str, prompt: str = "", prefill: dict | None = None) -> dict:
    """Render a database credentials form in the user's browser.

    YOU MUST CALL THIS TOOL — do not ask for credentials in plain text.
    Calling this tool is what physically renders the input form. Without it,
    the user has no way to enter their connection details.

    Call this as soon as the database type is known and credentials are needed.

    Args:
        db_type:  The database driver string.
                  Valid values: 'postgresql+psycopg', 'mysql+pymysql', 'sqlite', 'snowflake'.
        prompt:   Optional message to display above the form.
        prefill:  Optional dict of SQL_DB_* keys to pre-populate from values already known.
                  Mapping from extract_job_fields output → prefill key:
                    database  → SQL_DB_DATABASE
                    host      → SQL_DB_HOST
                    port      → SQL_DB_PORT
                    username  → SQL_DB_USERNAME
                  Example: {"SQL_DB_DATABASE": "customer_accounts", "SQL_DB_HOST": "db.example.com"}

    After calling this tool, say "Please fill in your connection details below." and stop.
    Wait for the user to submit the form — credentials will appear in the next turn's context.
    """
    return {
        "signal": "connection_form",
        "db_type": db_type,
        "prefill": prefill or {},
        "prompt": prompt or f"Enter your connection details for {db_type.split('+')[0].title()}.",
        "status": "Connection credentials form shown to user.",
    }


@mcp.tool()
def create_sql_job(
    name: str,
    query: str,
    db_driver: str,
    host: str = "",
    port: str = "",
    database: str = "",
    username: str = "",
    password: str = "",
    run_type: str = "manual",
    schedule: str = "",
    environment: str = "dev",
) -> dict:
    """Create a new SQL job in the Control Center.

    Only call this after completing the full workflow in extract_job_fields:
    extract fields → get db type → get connection form → discover schema → write query → confirm.

    Required fields vary by driver:
      - postgresql+psycopg / mysql+pymysql: host, port, database, username, password
      - sqlite:                             database (file path or ':memory:')
      - snowflake:                          host (account identifier), database, username, password

    Args:
        name:        Unique, descriptive job name.
        query:       The SQL query to execute. Use actual table names discovered via list_tables.
        db_driver:   Database driver string (e.g. 'postgresql+psycopg', 'sqlite', 'snowflake').
        host:        Database host or Snowflake account identifier (empty for SQLite).
        port:        Database port as a string (empty for SQLite and Snowflake).
        database:    Database name, file path, or Snowflake DATABASE/SCHEMA.
        username:    Database username (empty for SQLite).
        password:    Database password (empty for SQLite).
        run_type:    'manual' for one-off runs or 'scheduled' for recurring runs. Default 'manual'.
        schedule:    Cron expression — required when run_type is 'scheduled' (e.g. '0 8 * * 1-5').
                     Translate natural language schedules: "every weekday at 8 AM" → '0 8 * * 1-5'.
        environment: Target environment — 'dev', 'semi-prod', or 'prod'. Default 'dev'.

    Returns the created job object including its ID.
    """
    _ENV_ALIASES = {"development": "dev", "production": "prod", "staging": "semi-prod"}
    environment = _ENV_ALIASES.get(environment.lower(), environment.lower())

    config: dict[str, Any] = {"query": query, "db_driver": db_driver, "run_type": run_type}
    if host:
        config["host"] = host
    if port:
        config["port"] = port
    if database:
        config["database"] = database
    if username:
        config["username"] = username
    if password:
        config["password"] = password
    if schedule:
        config["schedule"] = schedule

    payload = {
        "name": name,
        "kind": "runtime",
        "type": "sql",
        "connector": "sql-mcp",
        "environment": environment,
        "config": config,
        "data_sensitivity": "low",
        "tags": [],
    }
    try:
        result = _post("/jobs", payload, token=_USER_TOKEN or None)
        return {
            "id": result.get("id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "message": f"SQL job '{name}' created successfully.",
        }
    except Exception as exc:
        raise ValueError(f"Failed to create SQL job '{name}': {exc}") from exc


@mcp.tool()
def create_airflow_job(
    name: str,
    script: str,
    run_mode: str = "subprocess",
    params: str = "{}",
    schedule: str = "",
    environment: str = "dev",
    data_sensitivity: str = "low",
) -> dict:
    """Create a new Airflow Python job in the Control Center.

    The job runs a Python file under backend/scripts/airflow/ via the
    AIRFLOW_PYTHON executor. Bundled scripts: 'hello_world', 'daily_metrics',
    'data_validation'. Custom scripts must be added to that directory.

    Args:
        name:             Unique, descriptive job name.
        script:           Script identifier (bare name → /app/scripts/airflow/<name>.py).
        run_mode:         'subprocess' (default; runs python <file>) or 'trigger_dag'
                          (POSTs to Airflow REST — requires airflow_url + airflow_token).
        params:           JSON string of params forwarded to the script as --params.
                          Example: '{"region": "WEST", "rows": 5000}'
        schedule:         Cron expression for recurring runs (optional).
        environment:      'dev', 'semi-prod', or 'prod'. Default 'dev'.
        data_sensitivity: 'low', 'medium', or 'high'. Affects approval policy.

    Returns the created job object including its ID.
    """
    _ENV_ALIASES = {"development": "dev", "production": "prod", "staging": "semi-prod"}
    environment = _ENV_ALIASES.get(environment.lower(), environment.lower())

    try:
        parsed_params = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"params must be valid JSON: {exc}") from exc

    config: dict[str, Any] = {
        "run_mode": run_mode,
        "script": script,
        **parsed_params,
    }
    if schedule:
        config["schedule"] = schedule

    payload = {
        "name": name,
        "kind": "runtime",
        "type": "airflow_python",
        "connector": script,  # mirrors the script identifier for surface lookup
        "environment": environment,
        "config": config,
        "data_sensitivity": data_sensitivity,
        "tags": [],
    }
    try:
        result = _post("/jobs", payload, token=_USER_TOKEN or None)
        return {
            "id": result.get("id"),
            "name": result.get("name"),
            "type": result.get("type"),
            "status": result.get("status"),
            "message": f"Airflow job '{name}' created (script={script}, mode={run_mode}).",
        }
    except Exception as exc:
        raise ValueError(f"Failed to create Airflow job '{name}': {exc}") from exc


_REGISTRY_PATH = Path(
    os.environ.get("CC_REGISTRY_PATH", "")
    or str(Path(__file__).parent.parent.parent / "src" / "control_center" / "registry" / "registry.json")
)


def _load_registry() -> dict[str, Any]:
    try:
        with open(_REGISTRY_PATH) as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not load registry from %s: %s", _REGISTRY_PATH, exc)
        return {}


@mcp.tool()
def get_job_type_schema(job_type: str | None = None, driver: str | None = None) -> dict:
    """Return required and optional fields for a job type, sourced from the registry.

    Call this before creating a job to know exactly which fields to collect from the user.

    Args:
        job_type: The job type to look up — e.g. 'sql', 'repo_connection', 'mcp'.
                  Omit (or pass None) to list all available job types.
        driver:   For SQL jobs only, the database driver to get driver-specific field
                  requirements — e.g. 'sqlite', 'postgresql', 'snowflake'.

    Returns a dict with:
        universal_required    Fields every job must have (job_name, owner, run_type)
        universal_optional    Fields any job may optionally have
        job_required          Fields required for this specific job type
        job_optional          Fields optionally used by this job type
        driver_required       (SQL + driver only) additional required fields for the driver
        driver_optional       (SQL + driver only) optional fields for the driver
        driver_notes          (SQL + driver only) usage notes for the driver
        db_driver_value       (SQL + driver only) exact db_driver string to pass to create_sql_job
        available_job_types   (no job_type given) list of {job_type, display_name, description}
    """
    registry = _load_registry()
    universal = registry.get("universal_job_fields", {})
    approved = registry.get("approved_servers", {})

    if not job_type:
        seen: set[str] = set()
        types: list[dict[str, Any]] = []
        for server_key, srv in approved.items():
            jt = srv.get("job_type")
            if not jt or jt in seen:
                continue
            seen.add(jt)
            types.append({
                "job_type": jt,
                "display_name": srv.get("display_name", server_key),
                "description": srv.get("description", ""),
            })
        return {
            "universal_required": universal.get("required", []),
            "universal_optional": universal.get("optional", []),
            "available_job_types": types,
        }

    matched: dict[str, Any] = {}
    for srv in approved.values():
        if srv.get("job_type") == job_type:
            matched = srv
            break

    # Built-in fallbacks for KNOWN_CONTRACTS types not present in registry.json.
    # Keep these in sync with control_center/specs/known_contracts.py.
    # Yes, this is brittle — ideally the registry would be the single enterprise source of truth for MCP Servers,
    # while JobTypeContracts are a separate layer registered by users, admins, or system defaults.
    # However, this file is already built around the quick-and-dirty hard-coding approach,
    # so a full refactor is needed to remove these fallbacks and address its underlying issues.
    _BUILTIN_FALLBACKS: dict[str, dict[str, Any]] = {
        "airflow_python": {
            "required_fields": [],
            "optional_fields": ["run_mode", "script", "schedule", "airflow_url", "airflow_token"],
            "notes": "Subprocess mode runs scripts under /app/scripts/airflow/. trigger_dag mode hits Airflow REST.",
        },
        "mcp": {
            "required_fields": [],
            "optional_fields": ["prompt", "description", "schedule", "timezone"],
            "notes": "Prompt-driven agent loop across approved MCP servers.",
        },
        "sql": {
            "required_fields": ["query"],
            "optional_fields": ["db_driver", "database", "schedule", "timezone"],
            "notes": "Deterministic execute_sql via the sql-mcp server.",
        },
    }
    if not matched and job_type in _BUILTIN_FALLBACKS:
        matched = _BUILTIN_FALLBACKS[job_type]

    result: dict[str, Any] = {
        "universal_required": universal.get("required", []),
        "universal_optional": universal.get("optional", []),
        "job_required": matched.get("required_fields", []),
        "job_optional": matched.get("optional_fields", []),
    }
    if matched.get("notes"):
        result["job_notes"] = matched["notes"]

    if driver and matched.get("drivers"):
        driver_info: dict[str, Any] = matched["drivers"].get(driver, {})
        result["driver_required"] = driver_info.get("required_fields", [])
        result["driver_optional"] = driver_info.get("optional_fields", [])
        if driver_info.get("notes"):
            result["driver_notes"] = driver_info["notes"]
        if driver_info.get("db_driver_value"):
            result["db_driver_value"] = driver_info["db_driver_value"]

    return result


@mcp.tool()
def extract_job_fields(message: str, job_type: str, driver: str | None = None) -> dict:
    """Extract structured job field values from a natural language user message.

    For SQL jobs, use this tool only for scheduling/config fields — NOT for the query.
    The query must be written after connecting to the database and inspecting real schema
    via list_tables and get_table_columns. Generating a query before schema discovery
    produces wrong table/column names.

    SQL job workflow — follow this exact order:
    1. Call this tool to extract: job_name, run_type, schedule, environment, database (hint only).
    2. Ask which database type to use (or call request_db_type_selection).
    3. Call request_db_connection_form, passing a prefill dict that maps every extracted value:
         extracted["database"] → prefill["SQL_DB_DATABASE"]
         extracted["host"]     → prefill["SQL_DB_HOST"]
         extracted["port"]     → prefill["SQL_DB_PORT"]
         extracted["username"] → prefill["SQL_DB_USERNAME"]
       Always include SQL_DB_DATABASE in prefill if the database name was extracted — even as a hint.
    4. After the user submits credentials, call test_connection first to verify connectivity.
       If it fails, show the exact error to the user and ask them to correct the details.
    5. Call list_tables then get_table_columns on the relevant table(s) to learn real schema.
    6. Write the SQL query using actual table and column names.
    7. Show a full summary (including the query) and ask for confirmation.
    8. Call create_sql_job only after the user confirms.

    Args:
        message:  The user's full request (can be a complete paragraph).
        job_type: The job type to create — e.g. 'sql'. Call get_job_type_schema
                  first if you are not sure which type the user wants.
        driver:   For SQL jobs, the database driver if already known
                  ('sqlite', 'postgresql', 'snowflake', 'mysql'). Omit otherwise.

    Returns:
        extracted:        {field_name: value} for every non-query field found in the message.
                          Note: if 'database' is extracted, it is a description hint only —
                          the user must confirm the actual database name on their server.
        missing_required: Required fields not present in the message (query is always deferred).
        summary:          Human-readable summary of what was extracted so far.
    """
    registry = _load_registry()
    universal = registry.get("universal_job_fields", {})
    approved = registry.get("approved_servers", {})

    # owner: always set from authenticated user — never ask the user for it
    # query: must be written after schema discovery (list_tables + get_table_columns)
    _SKIP_FIELDS = {"owner", "query"}

    required: list[str] = [f for f in universal.get("required", []) if f not in _SKIP_FIELDS]
    optional: list[str] = [f for f in universal.get("optional", []) if f not in _SKIP_FIELDS]

    for srv in approved.values():
        if srv.get("job_type") != job_type:
            continue
        required += srv.get("required_fields", [])
        optional += srv.get("optional_fields", [])
        if driver:
            driver_info: dict[str, Any] = srv.get("drivers", {}).get(driver, {})
            required += driver_info.get("required_fields", [])
            optional += driver_info.get("optional_fields", [])
        break

    seen: set[str] = set()
    unique_required: list[str] = []
    for f in required:
        if f not in seen:
            seen.add(f)
            unique_required.append(f)
    all_fields = unique_required + [f for f in optional if f not in seen]

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return {
            "extracted": {},
            "missing_required": unique_required,
            "summary": "Field extraction unavailable — OPENAI_API_KEY not configured.",
        }

    try:
        from openai import OpenAI as _OpenAI
        client = _OpenAI(api_key=api_key)

        system_prompt = (
            f"Extract job configuration field values from the user message.\n"
            f"Job type: {job_type}\n"
            f"Fields to extract: {all_fields}\n\n"
            "Rules:\n"
            "- Only extract a value if it is explicitly stated or unambiguously implied.\n"
            "- 'run_type': output 'scheduled' if any recurring schedule or frequency is mentioned, "
            "otherwise 'manual'.\n"
            "- 'schedule': translate natural language to a cron expression. Examples:\n"
            "    'every weekday at 8 AM'  → '0 8 * * 1-5'\n"
            "    'every day at midnight'  → '0 0 * * *'\n"
            "    'every Monday at 9 AM'   → '0 9 * * 1'\n"
            "    'hourly'                 → '0 * * * *'\n"
            "- 'environment': one of 'dev', 'semi-prod', 'prod'. Use 'dev' if not stated.\n"
            "- 'job_name': use the exact name if stated (e.g. 'Name the job X' → X).\n"
            "- For SQL 'database': infer a snake_case name from context when possible "
            "(e.g. 'customer accounts database' → 'customer_accounts').\n"
            "- Return a flat JSON object with only the fields you found. Omit fields you are unsure about."
        )

        resp = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=400,
        )

        raw: dict[str, Any] = json.loads(resp.choices[0].message.content or "{}")
        extracted = {k: v for k, v in raw.items() if k in all_fields and v not in (None, "", [])}
        missing = [f for f in unique_required if f not in extracted]

        parts = [f"{k}: {v}" for k, v in extracted.items()]
        summary = ("Extracted from your message — " + ", ".join(parts) + ".") if parts else "No fields could be extracted from the message."
        if missing:
            summary += f" Still needed: {', '.join(missing)}."

        return {"extracted": extracted, "missing_required": missing, "summary": summary}

    except Exception as exc:
        return {
            "extracted": {},
            "missing_required": unique_required,
            "summary": f"Extraction failed: {exc}",
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
