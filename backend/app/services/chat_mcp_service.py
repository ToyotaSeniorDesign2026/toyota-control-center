from __future__ import annotations

"""Prompt-native MCP execution for chatbot requests that do not need a saved resource."""

from dataclasses import dataclass
from typing import Any

from app.services.execution_service import ensure_control_center_importable


@dataclass(frozen=True)
class PromptNativeMCPResult:
    response: str
    server_names: list[str]
    tool_executions: list[dict[str, Any]]


async def run_prompt_native_mcp(
    *,
    message: str,
    environment: str = "dev",
    model: str | None = None,
    server_names: list[str] | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
) -> PromptNativeMCPResult:
    ensure_control_center_importable()
    from control_center.mcp import build_agent_from_registry

    agent = await build_agent_from_registry(
        environment=environment,
        server_names=server_names,
        selection_prompt=None if server_names else message,
        model=model,
        server_env_overrides=server_env_overrides,
        verbose=False,
    )
    try:
        response = await agent.run(message)
        return PromptNativeMCPResult(
            response=response.final_text,
            server_names=list(agent.client.connected_servers),
            tool_executions=[
                {
                    "framework_name": item.framework_name,
                    "server_name": item.server_name,
                    "remote_name": item.remote_name,
                    "arguments": item.arguments,
                    "parsed_result": item.parsed_result,
                }
                for item in response.tool_executions
            ],
        )
    finally:
        await agent.cleanup()
