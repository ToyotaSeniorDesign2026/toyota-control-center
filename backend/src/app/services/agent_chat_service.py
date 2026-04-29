from __future__ import annotations

"""Agent-driven chat: MCPAgent + Control Center MCP server."""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.chat_mcp_service import run_prompt_native_mcp

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are CC Assistant for the Toyota Control Center.
You help users manage automated jobs and monitor run history.

CAPABILITIES (tools available):
- list_jobs        — see all registered jobs (filter by type or status)
- get_job          — get full details for one job
- list_runs        — see recent runs (optionally filtered by job)
- get_run_status   — check the current status of a specific run
- trigger_run      — kick off a new run for a job

BEHAVIOR:
- Be concise — one to three sentences unless more detail is clearly needed.
- Always call a tool first when the user asks about jobs or runs.
- After triggering a run, confirm the run ID and status.
- If a tool returns an error, explain it plainly and suggest next steps.
"""


def _build_prompt(message: str, conversation_history: list[dict[str, Any]] | None) -> str:
    parts = [_SYSTEM_PROMPT, ""]
    for turn in conversation_history or []:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
    parts.append(f"User: {message}")
    return "\n".join(parts)


async def run_agent(
    *,
    message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    db: Session,
    user: Any,
    model: str | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
) -> str:
    """Run the control center agent for one user turn. Returns the final text reply."""
    full_prompt = _build_prompt(message, conversation_history)

    try:
        result = await run_prompt_native_mcp(
            message=full_prompt,
            server_names=["control-center"],
            model=model,
            server_env_overrides=server_env_overrides,
        )
        return result.response or "Done."
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        return f"Sorry, something went wrong: {exc}"
