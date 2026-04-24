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


async def github_write_file(
    *,
    owner: str,
    repo: str,
    path: str,
    content: str,
    commit_message: str,
    branch: str | None = None,
    github_token: str,
    environment: str = "dev",
) -> dict[str, Any]:
    """Write a file to GitHub directly via the MCP tool, bypassing the LLM."""
    ensure_control_center_importable()
    from control_center.mcp.client import LLMClient
    from control_center.core.registry import RegistryManager

    manager = RegistryManager(environment=environment)
    server_configs = manager.get_server_configs(["github"])
    server_config = {
        **server_configs["github"],
        "env": {
            **server_configs["github"].get("env", {}),
            "GITHUB_PERSONAL_ACCESS_TOKEN": github_token,
        },
    }

    arguments: dict[str, Any] = {
        "owner": owner,
        "repo": repo,
        "path": path,
        "message": commit_message,
        "content": content,
    }
    if branch:
        arguments["branch"] = branch

    client = LLMClient()
    try:
        await client.connect_to_server("github", server_config)
        result = await client.call_tool("github", "create_or_update_file", arguments)
        return {"success": True, "result": str(result)}
    finally:
        await client.cleanup()
