from __future__ import annotations

"""Single-shot MCP tool invocation helper."""

from typing import Any

from control_center.mcp.client import LLMClient


async def call_tool_once(
    server_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    server_config: dict[str, Any],
) -> Any:
    """Connect to a server, call one tool, then disconnect.

    Returns the raw MCP call-tool result (use MCPToolResult to normalize).
    """
    client = LLMClient()
    try:
        await client.connect_to_server(server_name, server_config)
        return await client.call_tool(server_name, tool_name, arguments)
    finally:
        await client.cleanup()
