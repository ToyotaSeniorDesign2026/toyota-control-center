from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit_event import RunLog
from app.models.resource import Resource
from app.models.user import User
from app.schemas.resource import ResourceCreate
from app.schemas.run import RunCreate
from app.services.resource_service import create_resource
from app.services.run_service import create_run_and_maybe_execute


SQL_MCP_CONNECTORS = {"sql-dab", "sql-dab-analytics"}
GITHUB_WRITE_INTENT_PATTERN = re.compile(
    r"\b(write|save|commit|push|add|store)\b.{0,60}\b(sql|query|script)\b.{0,60}\b(github|repo|repository|file|\.sql)\b"
    r"|\b(github|repo|repository)\b.{0,60}\b(write|save|commit|push|add)\b.{0,60}\b(sql|query|script)\b"
    r"|\b(sql|query)\b.{0,60}\b(github|repo|repository|\.sql)\b",
    re.IGNORECASE,
)
SQL_CONNECTOR_ALIASES = {
    "control center dev database": "sql-dab",
    "control-center dev database": "sql-dab",
    "control center database": "sql-dab",
    "control-center database": "sql-dab",
    "postgres": "sql-dab",
    "postgresql": "sql-dab",
    "analytics reporting database": "sql-dab-analytics",
}
RUN_INTENT_PATTERN = re.compile(r"\b(run|execute|launch|trigger|start)\b")
SQL_EXECUTION_CONTEXT_PATTERN = re.compile(r"\b(sql|query|job|resource)\b")


@dataclass(frozen=True)
class ChatJobExecutionResult:
    executed: bool
    message: str
    resource_id: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    resource_created: bool = False
    result_preview: str | None = None


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


def _find_sql_resource_for_actor(db: Session, actor: User, resource_name: str) -> Resource | None:
    normalized_name = resource_name.strip().lower()
    if not normalized_name:
        return None

    query = db.query(Resource).filter(func.lower(Resource.name) == normalized_name, func.lower(Resource.type) == "sql")
    if actor.role != "root":
        query = query.filter(
            (Resource.owner_id == actor.id) | (Resource.owner_domain == actor.domain)
        )
    return query.order_by(Resource.updated_at.desc()).first()


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


def _normalize_sql_resource_connector(resource: Resource | Any, fallback_fields: dict[str, Any]) -> None:
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

    if merged.get("creation_requested") and not _non_empty_string((current_draft or {}).get("resource_id")):
        return None

    resource_name = (
        _non_empty_string(merged.get("name"))
        or _non_empty_string(merged.get("job_name"))
    )

    resource = _find_sql_resource_for_actor(db, actor, resource_name) if resource_name else None
    created_resource = False

    if resource is None:
        if not resource_name:
            return ChatJobExecutionResult(
                executed=False,
                message="I can run a SQL job from chat, but I still need the job/resource name.",
            )

        connector = _infer_sql_connector(merged)
        environment = _non_empty_string(merged.get("environment")) or "dev"
        data_sensitivity = _non_empty_string(merged.get("data_sensitivity")) or "low"
        tags = _coerce_string_list(merged.get("tags"))

        query = _non_empty_string(merged.get("query"))
        if query and "query" not in config:
            config["query"] = query

        connection_id = _non_empty_string(merged.get("connection_id"))
        if connection_id and "connection_id" not in config:
            config["connection_id"] = connection_id

        schedule = _non_empty_string(merged.get("schedule"))
        if schedule and "schedule" not in config:
            config["schedule"] = schedule

        resource_out = create_resource(
            db,
            actor,
            ResourceCreate(
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
        resource = db.get(Resource, resource_out["id"])
        created_resource = True
    elif resource is not None:
        _normalize_sql_resource_connector(resource, merged)
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
            message=f"I found the SQL resource `{resource.name}`, but it does not have a default query and you did not provide a query override.",
            resource_id=resource.id,
            resource_created=created_resource,
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
            resource_id=resource.id,
            action=action,
            target_environment=target_environment,
            params=params,
        ),
    )

    summary = (
        f"I {'registered and ' if created_resource else ''}started the SQL job for resource "
        f"`{resource.name}`. Run ID: `{run['id']}`. Current status: `{run['status']}`."
    )
    if params.get("query"):
        summary += " This run used a query override from chat."
    elif resource_query:
        summary += " This run used the resource's registered default query."

    result_preview = _extract_sql_result_preview(db, run["id"])
    if result_preview:
        summary += f"\n\nSQL result:\n{result_preview}"

    return ChatJobExecutionResult(
        executed=True,
        message=summary,
        resource_id=resource.id,
        run_id=run["id"],
        run_status=run["status"],
        resource_created=created_resource,
        result_preview=result_preview,
    )


def run_resource_by_id(
    db: Session,
    resource_id: str,
) -> ChatJobExecutionResult:
    """Run any existing resource by its ID, regardless of type."""
    from app.models.resource import Resource

    actor = get_chat_actor(db)
    resource = db.get(Resource, resource_id)
    if resource is None:
        return ChatJobExecutionResult(
            executed=False,
            message=f"I couldn't find a job with ID `{resource_id}`. It may have been deleted.",
        )

    run = create_run_and_maybe_execute(
        db,
        actor,
        RunCreate(
            resource_id=resource.id,
            action="run",
            target_environment=resource.environment or "dev",
            params={},
        ),
    )

    result_preview = _extract_sql_result_preview(db, run["id"])
    message = (
        f"Started a new run for **{resource.name}** ({resource.type}). "
        f"Run ID: `{run['id']}`. Status: `{run['status']}`."
    )
    if result_preview:
        message += f"\n\nResult:\n{result_preview}"

    return ChatJobExecutionResult(
        executed=True,
        message=message,
        resource_id=resource.id,
        run_id=run["id"],
        run_status=run["status"],
        result_preview=result_preview,
    )
