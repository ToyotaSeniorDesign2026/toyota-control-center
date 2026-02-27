from __future__ import annotations

"""Connector execution service with MCP-backed research resource support."""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.db import new_id
from app.models.resource import Resource


def _workspace_root() -> Path:
    # .../backend/app/services -> workspace root
    return Path(__file__).resolve().parents[3]


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_uv_bin() -> str:
    env_uv = os.environ.get("UV_BIN")
    if env_uv:
        return env_uv

    path_uv = shutil.which("uv")
    if path_uv:
        return path_uv

    for candidate in ("/opt/homebrew/bin/uv", "/usr/local/bin/uv"):
        if Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "Could not find 'uv'. Set UV_BIN to the absolute uv path (e.g., /opt/homebrew/bin/uv)."
    )


def _call_research_agent(topic: str, max_results: int) -> dict[str, Any]:
    demo_dir = _workspace_root() / "backend_demo"
    agent_script = demo_dir / "mcp_client.py"
    if not agent_script.exists():
        raise RuntimeError(f"Research agent client not found: {agent_script}")

    query = (
        f"Use the research MCP tool search_papers for topic '{topic}' "
        f"with max_results={max_results}. "
        "Return a concise summary and include the paper IDs."
    )
    uv_bin = _resolve_uv_bin()

    env = os.environ.copy()
    proc = subprocess.run(
        [uv_bin, "run", str(agent_script), "--query", query],
        cwd=str(demo_dir),
        text=True,
        capture_output=True,
        timeout=180,
        env=env,
    )

    combined_output = (proc.stdout or "").strip()
    if proc.stderr:
        combined_output = f"{combined_output}\n{proc.stderr.strip()}".strip()

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "uv_bin": uv_bin,
        "output": combined_output,
    }


def _execute_research_resource(resource: Resource, run: dict) -> dict[str, Any]:
    cfg = resource.config or {}
    params = run.get("params") or {}
    topic = (params.get("topic") or cfg.get("topic") or "").strip()
    max_results = _as_int(params.get("max_results", cfg.get("max_results", 5)), 5)

    if not topic:
        return {
            "connector_run_id": new_id("mcp"),
            "status": "failed",
            "duration_ms": 0,
            "metadata": {"resource_id": run["resource_id"], "reason": "missing_topic"},
            "error": "Research resource requires config.topic or run params.topic",
        }

    start = time.perf_counter()
    try:
        agent_result = _call_research_agent(topic=topic, max_results=max_results)
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "connector_run_id": new_id("mcp"),
            "status": "succeeded" if agent_result.get("ok") else "failed",
            "duration_ms": duration_ms,
            "metadata": {
                "resource_id": run["resource_id"],
                "target_environment": run["target_environment"],
                "topic": topic,
                "max_results": max_results,
                "mcp_server": "research",
                "tool": "search_papers (via agent)",
                "agent_result": agent_result,
            },
            "error": None if agent_result.get("ok") else "Research MCP agent execution failed",
        }
    except Exception as exc:  # pragma: no cover - runtime integration path
        duration_ms = int((time.perf_counter() - start) * 1000)
        return {
            "connector_run_id": new_id("mcp"),
            "status": "failed",
            "duration_ms": duration_ms,
            "metadata": {
                "resource_id": run["resource_id"],
                "target_environment": run["target_environment"],
                "topic": topic,
                "max_results": max_results,
                "mcp_server": "research",
                "tool": "search_papers (via agent)",
            },
            "error": f"Research MCP agent execution failed: {exc}",
        }


def execute_resource(db, user, run: dict):
    resource = db.get(Resource, run["resource_id"])
    if resource and (resource.type or "").lower() == "research":
        return _execute_research_resource(resource, run)

    connector_run_id = new_id("mcp")
    # Default stub result for non-research resources until other connectors are implemented.
    return {
        "connector_run_id": connector_run_id,
        "status": "succeeded",
        "duration_ms": 420,
        "metadata": {
            "resource_id": run["resource_id"],
            "target_environment": run["target_environment"],
        },
        "error": None,
    }
