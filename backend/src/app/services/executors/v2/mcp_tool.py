from __future__ import annotations

"""MCP_TOOL executor — single deterministic call to one named MCP tool.

Reads:
    contract.executor       — the tool name (e.g. "execute_sql")
    contract.requires[0]    — the MCP server requirement; .names[0] is the server name
    job.config              — defaults for tool args
    payload.params          — per-run overrides for tool args (preferred)

For sql-mcp specifically, connection details (db_driver, host, port, database,
username, password, warehouse) are bundled into a `connection` dict and passed
as a tool arg — sql-mcp's tools accept it directly. No env-var injection.
"""

import logging
from typing import Any

from control_center.mcp import call_tool_once
from control_center.registry import RegistryManager
from control_center.specs import MCPToolResult

from app.services.execution_service_v2 import ExecutionRequestV2

from .base import V2Executor

logger = logging.getLogger(__name__)


# Tool args we pull from config/params and pass directly to the tool (whitelist).
_DIRECT_ARG_KEYS = {"query", "connection_id", "topic", "max_results"}

# For sql-mcp: keys to bundle into a `connection` dict tool arg.
_SQL_CONN_KEYS = {"db_driver", "host", "port", "database", "username", "password", "warehouse"}


def _merged_inputs(request: ExecutionRequestV2) -> dict[str, Any]:
    """Merge job.config and payload.params; payload wins on conflict."""
    job_config = getattr(request.job, "config", None) or {}
    if not isinstance(job_config, dict):
        job_config = {}
    params = request.payload.params or {}
    return {**job_config, **params}


def _build_tool_arguments(server_name: str, merged: dict[str, Any]) -> dict[str, Any]:
    """Build the dict of arguments to send to the tool.

    For all servers: pull whitelisted direct args (query, connection_id, etc.).
    For sql-mcp: also bundle SQL connection fields under `connection`.
    """
    args: dict[str, Any] = {
        k: v for k, v in merged.items()
        if k in _DIRECT_ARG_KEYS and v not in (None, "")
    }

    if server_name == "sql-mcp":
        connection = {
            k: v for k, v in merged.items()
            if k in _SQL_CONN_KEYS and v not in (None, "")
        }
        if connection:
            args["connection"] = connection

    return args


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
        arguments = _build_tool_arguments(server_name, merged)

        manager = RegistryManager(environment=request.target_environment)
        server_config = manager.get_server_config(server_name)

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
