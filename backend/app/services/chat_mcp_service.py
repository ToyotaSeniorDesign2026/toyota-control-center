from __future__ import annotations

"""Prompt-native MCP execution for chatbot requests that do not need a saved resource."""

from dataclasses import dataclass
import os
import re
from typing import Any

from app.services.execution_service import ensure_control_center_importable


PROMPT_NATIVE_ACTION_PATTERN = re.compile(
    r"\b(get|fetch|list|show|read|query|search|find|look up|lookup|inspect|summarize|summarise|what|which)\b",
    re.IGNORECASE,
)
PROMPT_NATIVE_CONTEXT_PATTERN = re.compile(
    r"\b(database|db|sql|table|record|records|resource|resources|run|runs|user|users|paper|papers|arxiv|web|url|file|files|docs|documentation|github|repo|repository|pull requests?|pr|branch|commit)\b",
    re.IGNORECASE,
)
JOB_CREATION_PATTERN = re.compile(r"\b(create|new|set up|setup|build|make)\b.*\b(job|resource)\b", re.IGNORECASE)
GITHUB_CONTEXT_PATTERN = re.compile(
    r"\b(github|repo|repository|pull requests?|issues?|branch|commit)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PromptNativeMCPResult:
    response: str
    server_names: list[str]
    tool_executions: list[dict[str, Any]]


def should_run_prompt_native_mcp(message: str, current_draft: dict[str, Any] | None = None) -> bool:
    normalized = (message or "").strip()
    if not normalized:
        return False

    draft = current_draft or {}
    draft_type = str(draft.get("job_type", "")).strip().lower()
    if draft_type and not draft.get("resource_id"):
        return False

    if draft_type and JOB_CREATION_PATTERN.search(normalized):
        return False

    if JOB_CREATION_PATTERN.search(normalized):
        return False

    return bool(
        PROMPT_NATIVE_ACTION_PATTERN.search(normalized)
        and PROMPT_NATIVE_CONTEXT_PATTERN.search(normalized)
    )


def needs_github_personal_access_token(
    message: str,
    current_draft: dict[str, Any] | None = None,
    supplied_token: str | None = None,
) -> bool:
    if supplied_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"):
        return False

    draft = current_draft or {}
    draft_connector = str(draft.get("connector", "")).strip().lower()
    draft_server_names = [str(item).strip().lower() for item in (draft.get("server_names") or [])]
    if not isinstance(draft.get("server_names"), list):
        draft_server_names = []

    github_requested = bool(GITHUB_CONTEXT_PATTERN.search(message or ""))
    github_requested = github_requested or draft_connector == "github" or "github" in draft_server_names

    return github_requested and should_run_prompt_native_mcp(message, current_draft)


async def run_prompt_native_mcp(
    *,
    message: str,
    environment: str = "dev",
    model: str | None = None,
    server_env_overrides: dict[str, dict[str, str]] | None = None,
) -> PromptNativeMCPResult:
    ensure_control_center_importable()
    from control_center.mcp import build_agent_from_registry

    agent = await build_agent_from_registry(
        environment=environment,
        selection_prompt=message,
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
