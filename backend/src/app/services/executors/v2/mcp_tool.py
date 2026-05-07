from __future__ import annotations

"""MCP_TOOL executor — single deterministic call to one named MCP tool.

Reads:
    contract.executor       — the tool name (e.g. "execute_sql")
    contract.requires[0]    — the MCP server requirement; .names[0] is the server name
    job.config              — defaults for tool args
    payload.params          — per-run overrides for tool args (preferred)

The merged config+params dict is passed straight to the tool. For sql-mcp
specifically, connection details (host, db, user, pass, db_driver) are also
passed through as env overrides on the subprocess (until the sql-mcp refactor
in Phase 5 makes them tool args).
"""

import logging
import os
from typing import Any

from control_center.mcp import call_tool_once
from control_center.registry import RegistryManager
from control_center.specs import MCPToolResult

from app.services.execution_service_v2 import ExecutionRequestV2

from .base import V2Executor

logger = logging.getLogger(__name__)


# Tool args we pull from config/params and pass to the tool (whitelist).
# For sql-mcp's execute_sql, only `query` and `connection_id` are accepted today.
_TOOL_ARG_KEYS = {"query", "connection_id", "topic", "max_results"}

# Connection-related fields that go to env overrides for sql-mcp specifically.
_SQL_CONN_KEYS = {"db_driver", "database", "host", "port", "username", "password", "warehouse"}


def _merged_inputs(request: ExecutionRequestV2) -> dict[str, Any]:
    """Merge job.config and payload.params; payload wins on conflict."""
    job_config = getattr(request.job, "config", None) or {}
    if not isinstance(job_config, dict):
        job_config = {}
    params = request.payload.params or {}
    return {**job_config, **params}


def _build_tool_arguments(merged: dict[str, Any]) -> dict[str, Any]:
    """Pull only the whitelisted tool-arg keys from the merged dict."""
    return {k: v for k, v in merged.items() if k in _TOOL_ARG_KEYS and v not in (None, "")}


def _sql_env_overrides(server_name: str, merged: dict[str, Any]) -> dict[str, str] | None:
    """For sql-mcp: build env vars that configure the SQLAlchemy engine.

    Phase 5 will move this into the tool args and make sql-mcp accept a
    connection dict per call. Until then, env overrides keep the existing
    server contract working.
    """
    if server_name != "sql-mcp":
        return None

    driver = str(merged.get("db_driver") or "").strip().lower()
    database = str(merged.get("database") or "").strip()

    if driver == "sqlite":
        if not database:
            return None
        return {"SQL_DB_DRIVER": "sqlite", "SQL_DB_DATABASE": database}

    host = str(merged.get("host") or "").strip()
    port = str(merged.get("port") or "").strip()
    username = str(merged.get("username") or "").strip()
    password = str(merged.get("password") or "").strip()
    warehouse = str(merged.get("warehouse") or "").strip()

    if not all([host, database, username, password]):
        return None

    overrides: dict[str, str] = {
        "SQL_DB_HOST": host,
        "SQL_DB_DATABASE": database,
        "SQL_DB_USERNAME": username,
        "SQL_DB_PASSWORD": password,
    }
    if driver:
        overrides["SQL_DB_DRIVER"] = driver
    if warehouse:
        overrides["SQL_DB_WAREHOUSE"] = warehouse
    if port:
        overrides["SQL_DB_PORT"] = port
        overrides["SQL_CONNECTION_STRING"] = (
            f"Host={host};Port={port};Database={database};"
            f"Username={username};Password={password}"
        )
    return overrides


def _resolve_server_name(request: ExecutionRequestV2) -> str:
    """Pick the MCP server from contract.requires[0].names[0]."""
    if not request.contract.requires:
        raise RuntimeError(
            f"contract {request.contract.type!r} declares executor_type=MCP_TOOL "
            f"but has no requires[]; cannot resolve server name."
        )
    req = request.contract.requires[0]
    if not req.names:
        raise RuntimeError(
            f"contract {request.contract.type!r} requires[0].names is empty; "
            f"cannot resolve server name for MCP_TOOL execution."
        )
    return req.names[0]


class MCPToolExecutor(V2Executor):
    """Direct call to an MCP tool. No agent loop, no LLM."""

    async def execute_async(self, request: ExecutionRequestV2) -> dict[str, Any]:
        tool_name = request.contract.executor
        server_name = _resolve_server_name(request)

        merged = _merged_inputs(request)
        arguments = _build_tool_arguments(merged)

        # Resolve server config + apply env overrides (sql-mcp connection details).
        manager = RegistryManager(environment=request.target_environment)
        server_config = manager.get_server_config(server_name)
        env_overrides = _sql_env_overrides(server_name, merged)
        if env_overrides:
            base_env = dict(os.environ)
            existing = server_config.get("env")
            if isinstance(existing, dict):
                base_env.update(existing)
            server_config = {**server_config, "env": {**base_env, **env_overrides}}

        try:
            raw_result = await call_tool_once(
                server_name=server_name,
                tool_name=tool_name,
                arguments=arguments,
                server_config=server_config,
            )
            tool_result = MCPToolResult.from_call_tool_result(raw_result)
        except Exception as exc:
            logger.exception("MCP_TOOL execution failed")
            return {
                "status": "failed",
                "result": None,
                "error": str(exc),
                "metadata": {
                    "executor_type": "mcp_tool",
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            }

        return {
            "status": "failed" if tool_result.is_error else "succeeded",
            "result": tool_result.serialize(),
            "error": tool_result.error.message if tool_result.error else None,
            "metadata": {
                "executor_type": "mcp_tool",
                "server_name": server_name,
                "tool_name": tool_name,
                "arguments": arguments,
            },
        }
