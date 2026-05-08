from __future__ import annotations

"""MCP_AGENT executor — LLM-driven tool-calling loop over MCP servers.

Reads:
    contract.executor       — agent profile name (currently informational; "default" supported)
    contract.requires[].names — preferred MCP servers to connect; empty = auto-select
    job.config.prompt       — default prompt
    payload.prompt          — per-run prompt (preferred)
    payload.params.prompt   — per-run prompt fallback

If no explicit servers are listed and no prompt is supplied, falls back to
agent auto-selection driven by the prompt itself.
"""

import logging
import os
from typing import Any

from control_center.agent import build_agent_from_registry, default_mcp_model

from app.services.execution_service_v2 import ExecutionRequestV2

from .base import V2Executor

logger = logging.getLogger(__name__)


def _resolve_server_names(request: ExecutionRequestV2) -> list[str]:
    """Collect server names across all MCP_SERVER requirements on the contract."""
    names: list[str] = []
    for req in request.contract.requires:
        for n in req.names:
            if n and n not in names:
                names.append(n)
    return names


def _resolve_prompt(request: ExecutionRequestV2) -> str | None:
    """Pull the prompt from payload (preferred) or job.config."""
    payload = request.payload
    payload_prompt = (getattr(payload, "prompt", None) or "").strip() or None
    if payload_prompt:
        return payload_prompt

    params = payload.params or {}
    params_prompt = (params.get("prompt") or "").strip() or None
    if params_prompt:
        return params_prompt

    job_config = getattr(request.job, "config", None) or {}
    if isinstance(job_config, dict):
        config_prompt = (job_config.get("prompt") or "").strip() or None
        if config_prompt:
            return config_prompt

    return None


class MCPAgentExecutor(V2Executor):
    """Build an MCPAgent and run a single user message through it."""

    async def execute_async(self, request: ExecutionRequestV2) -> dict[str, Any]:
        prompt = _resolve_prompt(request)
        if not prompt:
            return {
                "status": "failed",
                "result": None,
                "error": (
                    "MCP_AGENT execution requires a prompt. Provide one in run "
                    "payload.prompt, payload.params['prompt'], or job.config['prompt']."
                ),
                "metadata": {"executor_type": "mcp_agent"},
            }

        server_names = _resolve_server_names(request)

        try:
            agent = await build_agent_from_registry(
                environment=request.target_environment,
                server_names=server_names or None,
                # No explicit servers ⇒ let the selection model pick from registry.
                selection_prompt=prompt if not server_names else None,
                model=default_mcp_model(),
                instructor_model=os.getenv("CONTROL_CENTER_MCP_INSTRUCTOR_MODEL") or default_mcp_model(),
                verbose=False,
            )
        except Exception as exc:
            logger.exception("MCP_AGENT build failed")
            return {
                "status": "failed",
                "result": None,
                "error": f"Failed to build agent: {exc}",
                "metadata": {"executor_type": "mcp_agent", "server_names": server_names},
            }

        try:
            response = await agent.run(prompt)
            return {
                "status": "succeeded",
                "result": {
                    "final_text": response.final_text,
                    "tool_executions": [
                        {
                            "name": getattr(item, "exposed_name", None) or getattr(item, "framework_name", None),
                            "server": item.server_name,
                            "arguments": item.arguments,
                            "parsed_result": item.parsed_result,
                        }
                        for item in response.tool_executions
                    ],
                },
                "error": None,
                "metadata": {
                    "executor_type": "mcp_agent",
                    "server_names": agent.client.connected_servers,
                    "prompt": prompt,
                },
            }
        except Exception as exc:
            logger.exception("MCP_AGENT run failed")
            return {
                "status": "failed",
                "result": None,
                "error": str(exc),
                "metadata": {"executor_type": "mcp_agent", "prompt": prompt},
            }
        finally:
            try:
                await agent.cleanup()
            except Exception:
                logger.warning("MCP_AGENT cleanup raised; ignoring", exc_info=True)
