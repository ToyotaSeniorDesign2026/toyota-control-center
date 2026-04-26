from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_event import RunLog
from app.models.job import Job
from app.models.run import Run
from app.models.user import User
from app.schemas.job import JobCreate, JobUpdate
from app.schemas.run import RunCreate
from app.services.job_service import create_job, update_job
from app.services.run_service import create_run_and_maybe_execute


SQL_MCP_CONNECTORS = {"sql-mcp"}
_SQL_ERROR_INDICATORS = re.compile(
    r"\b(already exists|does not exist|syntax error|permission denied|"
    r"violates|duplicate key|duplicate table|relation .{0,60} already|"
    r"table .{0,60} already|column .{0,60} does not|invalid input syntax|"
    r"resulted in an error|error message|execution error)\b",
    re.IGNORECASE,
)
GITHUB_WRITE_INTENT_PATTERN = re.compile(
    r"\b(write|save|commit|push|add|store)\b.{0,60}\b(sql|query|script)\b.{0,60}\b(github|repo|repository|file|\.sql)\b"
    r"|\b(github|repo|repository)\b.{0,60}\b(write|save|commit|push|add)\b.{0,60}\b(sql|query|script)\b"
    r"|\b(sql|query)\b.{0,60}\b(github|repo|repository|\.sql)\b",
    re.IGNORECASE,
)
# Connector for SQL jobs is always sql-mcp; no database-specific aliases.
SQL_CONNECTOR_ALIASES: dict[str, str] = {}
RUN_INTENT_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b")
SQL_EXECUTION_CONTEXT_PATTERN = re.compile(r"\b(sql|query|job|resource)\b")


@dataclass(frozen=True)
class ChatJobExecutionResult:
    executed: bool
    message: str
    job_id: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    job_created: bool = False
    result_preview: str | None = None


@dataclass(frozen=True)
class ChatJobRegistrationResult:
    message: str
    job_id: str | None = None
    job_name: str | None = None
    job_created: bool = False


def _non_empty_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _merge_dicts(*parts: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for part in parts:
        if not isinstance(part, dict):
            continue
        for key, value in part.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _merge_dicts(merged[key], value)
            else:
                merged[key] = value
    return merged


def get_chat_actor(db: Session) -> User:
    actor = db.query(User).filter(User.email == "analyst@toyota.dev", User.is_active.is_(True)).one_or_none()
    if actor is not None:
        return actor

    actor = db.query(User).filter(User.is_active.is_(True)).order_by(User.created_at.asc()).first()
    if actor is None:
        raise RuntimeError("No active user is available to execute chat-driven jobs.")
    return actor


def _message_requests_github_write(
    message: str,
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> bool:
    merged = _merge_dicts(current_draft, extracted_fields)
    if str(merged.get("sql_subtype") or "").strip().lower() == "sql_github_write":
        return True
    return bool(GITHUB_WRITE_INTENT_PATTERN.search((message or "").strip()))


def _message_requests_sql_execution(
    message: str,
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> bool:
    normalized = message.lower()
    has_run_intent = RUN_INTENT_PATTERN.search(normalized) is not None
    has_execution_context = SQL_EXECUTION_CONTEXT_PATTERN.search(normalized) is not None
    if has_run_intent and has_execution_context:
        return True

    merged = _merge_dicts(current_draft, extracted_fields)
    if (
        str(merged.get("job_type", "")).strip().lower() == "sql"
        and has_run_intent
        and has_execution_context
    ):
        return True

    if str(merged.get("action", "")).strip().lower() == "run" and (
        merged.get("type") == "sql" or merged.get("job_type") == "SQL" or merged.get("query") or merged.get("params")
    ):
        return True

    return False


def _find_sql_job_for_actor(db: Session, actor: User, job_name: str) -> Job | None:
    normalized_name = job_name.strip().lower()
    if not normalized_name:
        return None

    query = db.query(Job).filter(func.lower(Job.name) == normalized_name, func.lower(Job.type) == "sql")
    if actor.role != "root":
        query = query.filter(
            (Job.owner_id == actor.id) | (Job.owner_domain == actor.domain)
        )
    return query.order_by(Job.updated_at.desc()).first()


def _infer_sql_connector(merged_fields: dict[str, Any]) -> str:
    connector = _non_empty_string(merged_fields.get("connector"))
    if connector:
        normalized_connector = connector.strip().lower()
        return SQL_CONNECTOR_ALIASES.get(
            normalized_connector,
            normalized_connector if normalized_connector in SQL_MCP_CONNECTORS else normalized_connector,
        )

    config = merged_fields.get("config")
    if isinstance(config, dict):
        connection_id = _non_empty_string(config.get("connection_id"))
        if connection_id in SQL_MCP_CONNECTORS:
            return connection_id

    connection_id = _non_empty_string(merged_fields.get("connection_id"))
    if connection_id in SQL_MCP_CONNECTORS:
        return connection_id

    return ""


def _resolved_sql_connector(merged_fields: dict[str, Any]) -> str:
    return "sql-mcp"


def _normalize_sql_job_connector(resource: Job | Any, fallback_fields: dict[str, Any]) -> None:
    connector = _infer_sql_connector({"connector": getattr(resource, "connector", None), **fallback_fields})
    if getattr(resource, "connector", None) != connector:
        resource.connector = connector


def _truncate(text: str, limit: int = 800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _format_rows_table(columns: list[Any], rows: list[Any], limit: int = 10) -> str | None:
    if not columns or not rows:
        return None

    normalized_columns = [str(col) for col in columns]
    normalized_rows = rows[:limit]
    if not normalized_rows:
        return None

    table_lines = [" | ".join(normalized_columns), " | ".join(["---"] * len(normalized_columns))]
    for row in normalized_rows:
        if isinstance(row, dict):
            table_lines.append(" | ".join(str(row.get(col, "")) for col in normalized_columns))
        elif isinstance(row, (list, tuple)):
            table_lines.append(" | ".join(str(value) for value in row))
        else:
            table_lines.append(str(row))
    return "\n".join(table_lines)


def _extract_sql_result_preview(db: Session, run_id: str) -> str | None:
    if not hasattr(db, "query"):
        return None

    log = (
        db.query(RunLog)
        .filter(RunLog.run_id == run_id, RunLog.message == "Connector execution finished")
        .order_by(RunLog.timestamp.desc(), RunLog.id.desc())
        .first()
    )
    if log is None:
        return None

    metadata = log.metadata_json or {}
    if not isinstance(metadata, dict):
        return None

    error = _non_empty_string(metadata.get("error"))
    if error:
        return f"Execution error: {_truncate(error, 500)}"

    execution = metadata.get("metadata", {}).get("execution") if isinstance(metadata.get("metadata"), dict) else None
    if isinstance(execution, dict):
        final_text = _non_empty_string(execution.get("final_text"))
        if final_text:
            return _truncate(final_text, 1200)

        result = execution.get("result")
        if isinstance(result, dict):
            structured = result.get("structured_content")
            if structured is not None:
                return _truncate(str(structured), 1200)
            content = result.get("content")
            if content:
                return _truncate(str(content), 1200)

    meta = metadata.get("metadata")
    if isinstance(meta, dict):
        columns = meta.get("columns")
        rows = meta.get("rows")
        row_count = meta.get("row_count")
        if isinstance(columns, list) and isinstance(rows, list):
            table = _format_rows_table(columns, rows)
            if table:
                prefix = f"Returned {row_count} row(s):\n" if row_count is not None else ""
                return _truncate(prefix + table, 1200)

    return None


def _is_sql_execution_error(preview: str | None) -> bool:
    """Return True when the result preview text describes a SQL-level failure."""
    if not preview:
        return False
    return bool(_SQL_ERROR_INDICATORS.search(preview)) or preview.startswith("Execution error:")


def _mark_run_failed(db: Session, run_id: str) -> None:
    """Directly force a run to failed status when SQL content indicates failure."""
    run_obj = db.get(Run, run_id)
    if run_obj and run_obj.status == "succeeded":
        run_obj.status = "failed"
        db.add(run_obj)
        db.commit()


def update_sql_job_from_chat(
    db: Session,
    job_id: str,
    new_fields: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Update a registered SQL job's config from chat. Returns (message, updated_fields_for_draft)."""
    actor = get_chat_actor(db)
    resource = db.get(Job, job_id)
    if resource is None:
        return "I couldn't find the registered job to update.", {}

    config = dict(resource.config or {})
    changed: list[str] = []
    draft_updates: dict[str, Any] = {}

    for field in ("query", "schedule", "connection_id"):
        val = _non_empty_string(str(new_fields.get(field) or ""))
        if val:
            config[field] = val
            changed.append(field)
            draft_updates[field] = val

    if "schedule" in changed:
        config["run_type"] = "scheduled"
        draft_updates["run_type"] = "scheduled"
    elif "run_type" in new_fields:
        rt = _non_empty_string(str(new_fields["run_type"] or ""))
        if rt in {"manual", "scheduled", "triggered"}:
            config["run_type"] = rt
            changed.append("run_type")
            draft_updates["run_type"] = rt

    name_val = _non_empty_string(str(new_fields.get("job_name") or new_fields.get("name") or ""))

    if not changed and not name_val:
        return (
            "I couldn't determine what to update. Please specify what you'd like to change "
            "(e.g. schedule, query, run type).",
            {},
        )

    try:
        payload_kwargs: dict[str, Any] = {"config": config}
        if name_val:
            payload_kwargs["name"] = name_val
        payload = JobUpdate(**payload_kwargs)
        update_job(db, actor, job_id, payload)
    except Exception as exc:
        return f"Couldn't update the job: {exc}", {}

    parts: list[str] = []
    if "schedule" in changed:
        parts.append(f"schedule → `{new_fields['schedule']}`")
    if "query" in changed:
        parts.append("SQL query updated")
    if "connection_id" in changed:
        parts.append(f"connection ID → `{new_fields['connection_id']}`")
    if "run_type" in changed:
        parts.append(f"run type → `{config['run_type']}`")
    if name_val:
        parts.append(f"name → `{name_val}`")
        draft_updates["name"] = name_val
        draft_updates["job_name"] = name_val

    summary = "; ".join(parts) if parts else "settings updated"
    return f"Updated **{resource.name}**: {summary}.", draft_updates


def _build_sql_resource_config(merged: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    next_config = dict(config)
    next_config.pop("target_environment", None)
    next_config.pop("environment", None)

    query = _non_empty_string(merged.get("query"))
    if query and "query" not in next_config:
        next_config["query"] = query

    connection_id = _non_empty_string(merged.get("connection_id"))
    if connection_id and "connection_id" not in next_config:
        next_config["connection_id"] = connection_id

    schedule = _non_empty_string(merged.get("schedule"))
    if schedule and "schedule" not in next_config:
        next_config["schedule"] = schedule

    for field in ("database", "username", "password", "host", "port"):
        value = _non_empty_string(merged.get(field))
        if value and field not in next_config:
            next_config[field] = value

    return next_config


def register_sql_job_from_chat(
    db: Session,
    *,
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> ChatJobRegistrationResult:
    actor = get_chat_actor(db)
    merged = _merge_dicts(current_draft, extracted_fields)
    config = _merge_dicts(
        current_draft.get("config") if isinstance(current_draft, dict) else None,
        extracted_fields.get("config") if isinstance(extracted_fields, dict) else None,
    )

    resource_name = (
        _non_empty_string(merged.get("name"))
        or _non_empty_string(merged.get("job_name"))
    )
    if not resource_name:
        return ChatJobRegistrationResult(
            message="I can create the SQL job from chat, but I still need the job name.",
        )

    resource = _find_sql_job_for_actor(db, actor, resource_name)
    if resource is not None:
        return ChatJobRegistrationResult(
            message=f"The SQL job `{resource.name}` is already registered and ready to run.",
            job_id=resource.id,
            job_name=resource.name,
            job_created=False,
        )

    connector = _resolved_sql_connector(merged)
    environment = (
        _non_empty_string(merged.get("target_environment"))
        or _non_empty_string(merged.get("environment"))
        or "dev"
    )
    data_sensitivity = _non_empty_string(merged.get("data_sensitivity")) or "low"
    tags = _coerce_string_list(merged.get("tags"))
    resource_config = _build_sql_resource_config(merged, config)

    job_out = create_job(
        db,
        actor,
        JobCreate(
            name=resource_name,
            kind="runtime",
            type="sql",
            connector=connector,
            environment=environment,
            config=resource_config,
            data_sensitivity=data_sensitivity,
            tags=tags,
        ),
    )
    return ChatJobRegistrationResult(
        message=f"Created SQL job `{resource_name}` and saved it as a Control Center job. Do you want me to run it now?",
        job_id=job_out["id"],
        job_name=resource_name,
        job_created=True,
    )


def register_github_write_job_from_chat(
    db: Session,
    *,
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
    github_token: str | None = None,
) -> ChatJobRegistrationResult:
    actor = get_chat_actor(db)
    merged = _merge_dicts(current_draft, extracted_fields)

    resource_name = (
        _non_empty_string(merged.get("name"))
        or _non_empty_string(merged.get("job_name"))
    )
    if not resource_name:
        return ChatJobRegistrationResult(message="I still need a job name to register this.")

    environment = (
        _non_empty_string(merged.get("target_environment"))
        or _non_empty_string(merged.get("environment"))
        or "dev"
    )
    data_sensitivity = _non_empty_string(merged.get("data_sensitivity")) or "low"
    tags = _coerce_string_list(merged.get("tags"))

    resource_config: dict[str, Any] = {}
    for field in ("query", "repo", "ref", "schedule"):
        val = _non_empty_string(merged.get(field))
        if val:
            resource_config[field] = val
    # Normalize file_path → path (both may appear depending on chat flow)
    path_val = _non_empty_string(merged.get("path")) or _non_empty_string(merged.get("file_path"))
    if path_val:
        resource_config["path"] = path_val
    # Store the PAT so scheduled runs can use it without prompting again
    token_val = github_token or _non_empty_string(merged.get("github_token"))
    if token_val:
        resource_config["github_token"] = token_val

    job_out = create_job(
        db,
        actor,
        JobCreate(
            name=resource_name,
            kind="runtime",
            type="sql",
            connector="github",
            environment=environment,
            config=resource_config,
            data_sensitivity=data_sensitivity,
            tags=tags,
        ),
    )
    return ChatJobRegistrationResult(
        message=f"Registered SQL write job `{resource_name}`.",
        job_id=job_out["id"],
        job_name=resource_name,
        job_created=True,
    )


def get_github_token_for_repo(db: Session, repo: str) -> str | None:
    """Look up a stored GitHub PAT for the given repo slug directly from the database.

    Checks both ``repo_connection`` jobs (created by the connection flow) and SQL/github
    write jobs (where the token is stored at registration time).  Returns the first
    non-empty token found, or None.
    """
    if not repo:
        return None
    candidates = (
        db.query(Job)
        .filter(Job.connector == "github")
        .all()
    )
    for job in candidates:
        cfg = job.config or {}
        if str(cfg.get("repo") or "").strip() != repo:
            continue
        token = str(cfg.get("github_token") or "").strip()
        if token:
            return token
    return None


def save_github_token_for_repo(db: Session, repo: str, ref: str | None, github_token: str) -> None:
    """Persist a GitHub PAT into the repo_connection job for this repo.

    On the first successful write the token is stored so future writes to the same
    repo can reuse it without asking the user again.  If no repo_connection job
    exists yet, one is created.  Existing repo_connection jobs are updated in-place.
    """
    if not repo or not github_token:
        return

    actor = get_chat_actor(db)

    existing = (
        db.query(Job)
        .filter(Job.type == "repo_connection", Job.connector == "github")
        .all()
    )
    target: Job | None = None
    for job in existing:
        cfg = job.config or {}
        if str(cfg.get("repo") or "").strip() == repo:
            target = job
            break

    if target:
        config = dict(target.config or {})
        config["github_token"] = github_token
        update_job(db, actor, target.id, JobUpdate(config=config))
    else:
        create_job(
            db,
            actor,
            JobCreate(
                name=repo.split("/")[-1] or repo,
                kind="runtime",
                type="repo_connection",
                connector="github",
                environment="dev",
                config={
                    "repo": repo,
                    "ref": ref or "main",
                    "github_token": github_token,
                    "server_names": ["github", "filesystem", "fastmcp-docs", "fetch"],
                },
                data_sensitivity="low",
                tags=[],
            ),
        )


def maybe_run_sql_job_from_chat(
    db: Session,
    *,
    message: str,
    extracted_fields: dict[str, Any] | None,
    current_draft: dict[str, Any] | None,
) -> ChatJobExecutionResult | None:
    if _message_requests_github_write(message, extracted_fields, current_draft):
        return None
    if not _message_requests_sql_execution(message, extracted_fields, current_draft):
        return None

    actor = get_chat_actor(db)
    merged = _merge_dicts(current_draft, extracted_fields)
    config = _merge_dicts(
        current_draft.get("config") if isinstance(current_draft, dict) else None,
        extracted_fields.get("config") if isinstance(extracted_fields, dict) else None,
    )

    if merged.get("creation_requested") and not _non_empty_string((current_draft or {}).get("job_id")):
        return None

    resource_name = (
        _non_empty_string(merged.get("name"))
        or _non_empty_string(merged.get("job_name"))
    )

    resource = _find_sql_job_for_actor(db, actor, resource_name) if resource_name else None
    created_job = False

    if resource is None:
        if not resource_name:
            return ChatJobExecutionResult(
                executed=False,
                message="I can run a SQL job from chat, but I still need the job name.",
            )

        connector = _resolved_sql_connector(merged)
        environment = _non_empty_string(merged.get("environment")) or "dev"
        data_sensitivity = _non_empty_string(merged.get("data_sensitivity")) or "low"
        tags = _coerce_string_list(merged.get("tags"))

        config = _build_sql_resource_config(merged, config)

        job_out = create_job(
            db,
            actor,
            JobCreate(
                name=resource_name,
                kind="runtime",
                type="sql",
                connector=connector,
                environment=environment,
                config=config,
                data_sensitivity=data_sensitivity,
                tags=tags,
            ),
        )
        resource = db.get(Job, job_out["id"])
        created_job = True
    elif resource is not None:
        _normalize_sql_job_connector(resource, merged)
        if hasattr(db, "add") and hasattr(db, "commit"):
            db.add(resource)
            db.commit()

    resource_query = _non_empty_string((resource.config or {}).get("query")) if resource is not None else None
    override_query = _non_empty_string(merged.get("query"))
    params = dict(merged.get("params") or {})
    if override_query and "query" not in params:
        params["query"] = override_query

    connection_id = _non_empty_string(merged.get("connection_id")) or _non_empty_string(config.get("connection_id"))
    if connection_id and "connection_id" not in params:
        params["connection_id"] = connection_id

    if not params.get("query") and not resource_query:
        return ChatJobExecutionResult(
            executed=False,
            message=f"I found the SQL job `{resource.name}`, but it does not have a default query and you did not provide a query override.",
            job_id=resource.id,
            job_created=created_job,
        )

    target_environment = (
        _non_empty_string(merged.get("target_environment"))
        or _non_empty_string(merged.get("environment"))
        or resource.environment
        or "dev"
    )
    action = _non_empty_string(merged.get("action")) or "run"

    run = create_run_and_maybe_execute(
        db,
        actor,
        RunCreate(
            job_id=resource.id,
            action=action,
            target_environment=target_environment,
            params=params,
        ),
    )

    result_preview = _extract_sql_result_preview(db, run["id"])
    effective_status = run["status"]
    if _is_sql_execution_error(result_preview) and effective_status == "succeeded":
        effective_status = "failed"
        _mark_run_failed(db, run["id"])

    summary = (
        f"I {'registered and ' if created_job else ''}started the SQL job "
        f"`{resource.name}`. Run ID: `{run['id']}`. Status: `{effective_status}`."
    )
    if params.get("query"):
        summary += " This run used a query override from chat."
    elif resource_query:
        summary += " This run used the job's registered default query."

    if result_preview:
        summary += f"\n\nSQL result:\n{result_preview}"

    return ChatJobExecutionResult(
        executed=True,
        message=summary,
        job_id=resource.id,
        run_id=run["id"],
        run_status=effective_status,
        job_created=created_job,
        result_preview=result_preview,
    )


def run_job_by_id(
    db: Session,
    job_id: str,
    extra_params: dict | None = None,
) -> ChatJobExecutionResult:
    """Run any existing job by its ID, regardless of type."""
    actor = get_chat_actor(db)
    job = db.get(Job, job_id)
    if job is None:
        return ChatJobExecutionResult(
            executed=False,
            message=f"I couldn't find a job with ID `{job_id}`. It may have been deleted.",
        )

    run = create_run_and_maybe_execute(
        db,
        actor,
        RunCreate(
            job_id=job.id,
            action="run",
            target_environment=job.environment or "dev",
            params=extra_params or {},
        ),
    )

    result_preview = _extract_sql_result_preview(db, run["id"])
    effective_status = run["status"]
    if _is_sql_execution_error(result_preview) and effective_status == "succeeded":
        effective_status = "failed"
        _mark_run_failed(db, run["id"])

    message = (
        f"Started a new run for **{job.name}** ({job.type}). "
        f"Run ID: `{run['id']}`. Status: `{effective_status}`."
    )
    if result_preview:
        message += f"\n\nResult:\n{result_preview}"

    return ChatJobExecutionResult(
        executed=True,
        message=message,
        job_id=job.id,
        run_id=run["id"],
        run_status=effective_status,
        result_preview=result_preview,
    )
