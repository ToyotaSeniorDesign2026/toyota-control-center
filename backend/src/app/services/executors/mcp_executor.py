from __future__ import annotations

"""MCP-backed executor implementation."""

import asyncio
import logging
import os
import threading
from typing import Any

from control_center.agent import build_agent_from_registry, default_mcp_model
from control_center.mcp import call_tool_once
from control_center.registry import RegistryManager
from control_center.specs import MCPToolResult
from control_center.specs.execution import AgentRun, DirectToolCall

from app.services.execution_service import ExecutionRequest

from .base import BaseJobExecutor

logger = logging.getLogger(__name__)


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
            except BaseException as exc:
                error_holder["error"] = exc

        timeout_s = int(os.getenv("MCP_EXECUTION_TIMEOUT_SECONDS", "120"))
        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)

        if thread.is_alive():
            raise RuntimeError(
                f"MCP execution timed out after {timeout_s}s. "
                "Check that the target database is reachable and credentials are correct."
            )
        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder["execution"]

    async def _execute_direct_tool(self, execution_request: ExecutionRequest) -> MCPToolResult:
        run_spec = execution_request.run_spec
        assert isinstance(run_spec, DirectToolCall)

        manager = RegistryManager(environment=execution_request.target_environment)
        server_config = manager.get_server_config(run_spec.server_name)

        # Apply connection env overrides (e.g. SQL credentials) to the server subprocess env.
        env_overrides = self._sql_server_env_overrides(execution_request)
        if env_overrides and run_spec.server_name in env_overrides:
            overrides = env_overrides[run_spec.server_name]
            base_env = dict(os.environ)
            existing = server_config.get("env")
            if isinstance(existing, dict):
                base_env.update(existing)
            server_config = {**server_config, "env": {**base_env, **overrides}}

        raw_result = await call_tool_once(
            server_name=run_spec.server_name,
            tool_name=run_spec.tool_name,
            arguments=run_spec.arguments,
            server_config=server_config,
        )
        return MCPToolResult.from_call_tool_result(raw_result)

    def _sql_server_env_overrides(self, execution_request: ExecutionRequest) -> dict[str, dict[str, str]] | None:
        """Build server_env_overrides for sql-mcp from run params (preferred) or job config."""
        config = execution_request.resource.config if hasattr(execution_request.resource, "config") else {}
        if not isinstance(config, dict):
            config = {}
        params = execution_request.params or {}

        driver = str(params.get("db_driver") or config.get("db_driver") or "").strip().lower()
        database = str(params.get("database") or config.get("database") or "").strip()

        if driver == "sqlite":
            if not database:
                logger.warning("SQLite driver detected but database path is empty — no env overrides applied")
                return None
            return {"sql-mcp": {"SQL_DB_DRIVER": "sqlite", "SQL_DB_DATABASE": database}}

        host = str(params.get("host") or config.get("host") or "").strip()
        port = str(params.get("port") or config.get("port") or "").strip()
        username = str(params.get("username") or config.get("username") or "").strip()
        password = str(params.get("password") or config.get("password") or "").strip()
        warehouse = str(params.get("warehouse") or config.get("warehouse") or "").strip()

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
                f"Host={host};Port={port};Database={database};Username={username};Password={password}"
            )
        return {"sql-mcp": overrides}

    async def _execute_agent(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        run_spec = execution_request.run_spec
        assert isinstance(run_spec, AgentRun)

        server_env_overrides = self._sql_server_env_overrides(execution_request)

        agent = await build_agent_from_registry(
            environment=execution_request.target_environment,
            server_names=run_spec.server_names or None,
            selection_prompt=run_spec.selection_prompt if run_spec.allow_auto_selection else None,
            model=default_mcp_model(),
            instructor_model=os.getenv("CONTROL_CENTER_MCP_INSTRUCTOR_MODEL"),
            server_env_overrides=server_env_overrides,
            verbose=False,
        )
        try:
            response = await agent.run(run_spec.prompt)
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

    async def _execute_github_write(self, execution_request: ExecutionRequest) -> MCPToolResult:
        """Write a SQL script to GitHub. Token comes from run params."""
        from app.services.chat_mcp_service import github_write_file

        run_spec = execution_request.run_spec
        assert isinstance(run_spec, DirectToolCall)

        params = execution_request.params
        job_config = execution_request.resource.config or {}

        github_token = str(params.get("github_token") or job_config.get("github_token") or "").strip()
        if not github_token:
            return MCPToolResult.failure(code="missing_token", message="Missing github_token in run params.")

        args = run_spec.arguments
        if not args.get("owner") or not args.get("repo") or not args.get("content"):
            return MCPToolResult.failure(code="incomplete_args", message="Incomplete GitHub write arguments.")

        try:
            result = await github_write_file(
                owner=args["owner"],
                repo=args["repo"],
                path=args.get("path", ""),
                content=args["content"],
                commit_message=args.get("message", f"Add file {args.get('path', '')}"),
                branch=args.get("branch", "main"),
                github_token=github_token,
                environment=execution_request.target_environment,
            )
            return MCPToolResult.success(data=result)
        except Exception as exc:
            return MCPToolResult.failure(code="github_write_error", message=str(exc))

    async def _execute_async(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        run_spec = execution_request.run_spec

        if isinstance(run_spec, DirectToolCall):
            if run_spec.server_name == "github":
                tool_result = await self._execute_github_write(execution_request)
            else:
                tool_result = await self._execute_direct_tool(execution_request)

            # Single conversion point: MCPToolResult → executor output dict
            execution = {
                "status": "failed" if tool_result.is_error else "succeeded",
                "server_names": [run_spec.server_name],
                "tool_name": run_spec.tool_name,
                "tool_arguments": run_spec.arguments,
                "result": tool_result.serialize(),
                "error": tool_result.error.message if tool_result.error else None,
            }
        else:
            execution = await self._execute_agent(execution_request)

        execution["job_spec"] = execution_request.job_spec
        return execution

    def execute(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        execution = self._run_async_execution(execution_request)
        metadata = {
            "job_id": execution_request.resource.job_id,
            "job_type": execution_request.resource.type,
            "execution_request": execution_request.model_dump(),
            "job_spec": execution.pop("job_spec"),
            "execution": execution,
        }
        return {
            "connector_run_id": f"mcp-{execution_request.resource.job_id}",
            "status": execution.get("status", "failed"),
            "duration_ms": 0,
            "metadata": metadata,
            "error": execution.get("error"),
        }
