from __future__ import annotations

"""MCP-backed executor implementation."""

import asyncio
import os
import threading
from typing import Any

from app.services.execution_service import ExecutionRequest, ensure_control_center_importable

from .base import BaseJobExecutor


def _normalize_tool_result(result: Any) -> dict[str, Any]:
    if hasattr(result, "structuredContent"):
        structured = getattr(result, "structuredContent", None)
    else:
        structured = None

    if hasattr(result, "content"):
        content = getattr(result, "content", None)
        content_repr = [str(item) for item in content] if isinstance(content, list) else str(content)
    else:
        content_repr = str(result)

    return {
        "structured_content": structured,
        "content": content_repr,
        "is_error": bool(getattr(result, "isError", False)),
    }


class MCPJobExecutor(BaseJobExecutor):
    backend_name = "mcp"

    def _run_async_execution(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._execute_async(execution_request))

        result_holder: dict[str, Any] = {}
        error_holder: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_holder["execution"] = asyncio.run(self._execute_async(execution_request))
            except BaseException as exc:  # pragma: no cover - defensive handoff from worker thread
                error_holder["error"] = exc

        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder["execution"]

    async def _execute_direct_tool(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        ensure_control_center_importable()
        from control_center.core.registry import RegistryManager
        from control_center.mcp import LLMClient

        manager = RegistryManager(environment=execution_request.target_environment)
        runtime_client = LLMClient()

        mcp_config = execution_request.mcp_config
        server_names = list(mcp_config.server_names)
        if not server_names:
            raise RuntimeError("No MCP server_names were provided and the resource connector is empty.")
        if not mcp_config.tool_name:
            raise RuntimeError("Direct MCP execution requires mcp_config.tool_name.")

        try:
            for server_name in server_names:
                server_config = manager.get_server_config(server_name)
                await runtime_client.connect_to_server(server_name, server_config)

            target_server = server_names[0]
            tool_arguments = dict(execution_request.params)
            tool_arguments.update(mcp_config.tool_arguments)
            raw_result = await runtime_client.call_tool(target_server, mcp_config.tool_name, tool_arguments)
            normalized = _normalize_tool_result(raw_result)
            if normalized["is_error"]:
                return {
                    "status": "failed",
                    "server_names": server_names,
                    "tool_name": mcp_config.tool_name,
                    "tool_arguments": tool_arguments,
                    "result": normalized,
                    "error": f"MCP tool '{mcp_config.tool_name}' returned an error",
                }
            return {
                "status": "succeeded",
                "server_names": server_names,
                "tool_name": mcp_config.tool_name,
                "tool_arguments": tool_arguments,
                "result": normalized,
                "error": None,
            }
        finally:
            await runtime_client.cleanup()

    def _sql_server_env_overrides(self, execution_request: ExecutionRequest) -> dict[str, dict[str, str]] | None:
        """Build server_env_overrides for sql-dab from the resource's connection config."""
        config = {}
        if hasattr(execution_request.resource, "config"):
            cfg = execution_request.resource.config
            config = cfg if isinstance(cfg, dict) else {}

        host = str(config.get("host") or "").strip()
        port = str(config.get("port") or "").strip()
        database = str(config.get("database") or "").strip()
        username = str(config.get("username") or "").strip()
        password = str(config.get("password") or "").strip()

        if not all([host, port, database, username, password]):
            return None

        conn_str = f"Host={host};Port={port};Database={database};Username={username};Password={password}"
        return {
            "sql-dab": {
                "SQL_CONNECTION_STRING": conn_str,
                "SQL_DB_HOST": host,
                "SQL_DB_PORT": port,
                "SQL_DB_DATABASE": database,
                "SQL_DB_USERNAME": username,
                "SQL_DB_PASSWORD": password,
            }
        }

    async def _execute_agent(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        ensure_control_center_importable()
        from control_center.mcp import build_agent_from_registry, default_mcp_model

        mcp_config = execution_request.mcp_config
        server_names = list(mcp_config.server_names)
        selection_prompt = None
        if mcp_config.allow_auto_selection:
            selection_prompt = (
                mcp_config.connector_selection_prompt
                or mcp_config.prompt
                or execution_request.params.get("prompt")
                or execution_request.job_spec.get("intent")
            )

        final_prompt = (
            mcp_config.prompt
            or execution_request.params.get("prompt")
            or execution_request.job_spec.get("metadata", {}).get("prompt")
        )
        if not final_prompt:
            raise RuntimeError("Agent MCP execution requires a prompt in mcp_config.prompt or params.prompt.")

        server_env_overrides = self._sql_server_env_overrides(execution_request)

        agent = await build_agent_from_registry(
            environment=execution_request.target_environment,
            server_names=server_names or None,
            selection_prompt=selection_prompt,
            model=default_mcp_model(),
            instructor_model=os.getenv("CONTROL_CENTER_MCP_INSTRUCTOR_MODEL"),
            server_env_overrides=server_env_overrides,
            verbose=False,
        )
        try:
            response = await agent.run(final_prompt)
            return {
                "status": "succeeded",
                "server_names": agent.client.connected_servers,
                "tool_executions": [
                    {
                        "framework_name": item.framework_name,
                        "server_name": item.server_name,
                        "remote_name": item.remote_name,
                        "arguments": item.arguments,
                        "parsed_result": item.parsed_result,
                    }
                    for item in response.tool_executions
                ],
                "final_text": response.final_text,
                "error": None,
            }
        finally:
            await agent.cleanup()

    async def _execute_async(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        if execution_request.execution_mode == "direct_tool":
            execution = await self._execute_direct_tool(execution_request)
        else:
            execution = await self._execute_agent(execution_request)

        execution["job_spec"] = execution_request.job_spec
        return execution

    def execute(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        execution = self._run_async_execution(execution_request)
        metadata = {
            "resource_id": execution_request.resource.resource_id,
            "resource_type": execution_request.resource.type,
            "execution_request": execution_request.model_dump(),
            "job_spec": execution.pop("job_spec"),
            "execution": execution,
        }
        return {
            "connector_run_id": f"mcp-{execution_request.resource.resource_id}",
            "status": execution.get("status", "failed"),
            "duration_ms": 0,
            "metadata": metadata,
            "error": execution.get("error"),
        }
