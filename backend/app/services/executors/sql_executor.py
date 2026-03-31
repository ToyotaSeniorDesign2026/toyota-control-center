from __future__ import annotations

"""Read-only SQL executor for deterministic native job execution."""

from typing import Any

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.db import new_id
from app.services.execution_service import ExecutionRequest

from .base import BaseJobExecutor


def _resolve_query(execution_request: ExecutionRequest) -> str | None:
    query = execution_request.params.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()

    resource_query = execution_request.resource.config.get("query")
    if isinstance(resource_query, str) and resource_query.strip():
        return resource_query.strip()

    return None


def _is_read_only_query(query: str) -> bool:
    normalized = query.strip().lower().lstrip("(")
    if ";" in normalized.rstrip(";"):
        return False
    return normalized.startswith("select") or normalized.startswith("with")


class SQLJobExecutor(BaseJobExecutor):
    backend_name = "native-sql"

    def execute(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        query = _resolve_query(execution_request)
        if not query:
            return {
                "connector_run_id": new_id("sql"),
                "status": "failed",
                "duration_ms": 0,
                "metadata": {
                    "execution_request": execution_request.model_dump(),
                    "resource_id": execution_request.resource.resource_id,
                },
                "error": "SQL execution requires params.query or resource.config.query",
            }

        if not _is_read_only_query(query):
            return {
                "connector_run_id": new_id("sql"),
                "status": "failed",
                "duration_ms": 0,
                "metadata": {
                    "execution_request": execution_request.model_dump(),
                    "resource_id": execution_request.resource.resource_id,
                    "query": query,
                },
                "error": "Only single-statement read-only SELECT/WITH queries are supported",
            }

        engine = create_engine(settings.database_url, future=True)
        try:
            with engine.connect() as connection:
                result = connection.execute(text(query))
                rows = result.fetchmany(100)
                columns = list(result.keys())
        finally:
            engine.dispose()

        serialized_rows = [dict(zip(columns, row)) for row in rows]
        return {
            "connector_run_id": new_id("sql"),
            "status": "succeeded",
            "duration_ms": 0,
            "metadata": {
                "execution_request": execution_request.model_dump(),
                "resource_id": execution_request.resource.resource_id,
                "query": query,
                "row_count": len(serialized_rows),
                "columns": columns,
                "rows": serialized_rows,
                "truncated": len(serialized_rows) == 100,
                "connection_id": execution_request.resource.config.get("connection_id"),
            },
            "error": None,
        }
