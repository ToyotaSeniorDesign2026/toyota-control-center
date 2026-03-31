from __future__ import annotations

import asyncio

from control_center.mcp import MCPAgent, build_agent_from_registry


async def build_agent(connector_selection_prompt: str | None = None) -> MCPAgent:
    return await build_agent_from_registry(
        environment="dev",
        selection_prompt=connector_selection_prompt,
        model="gemini-3.1-pro-preview",
        max_tool_rounds=30,
        verbose=True,
    )


async def main() -> None:
    user_prompt = "Has there been any research into training LLMs / artificial intelligence to fear death?"
    agent = await build_agent(connector_selection_prompt=user_prompt)
    try:
        response = await agent.run(user_prompt)
        print(response.final_text)
    finally:
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
