"""Control Center MCP server.

Exposes Toyota Control Center jobs and runs as MCP tools so that MCPAgent
can orchestrate them without going through the OpenAI function-calling loop.

Required environment variables:
    CC_API_BASE_URL     — Base URL of the Control Center API (default: http://localhost:8000)
    CC_SERVICE_TOKEN    — Internal service token set as CC_INTERNAL_SERVICE_TOKEN on the API
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("CC_API_BASE_URL", "http://localhost:8000").rstrip("/")
_TOKEN = os.environ.get("CC_SERVICE_TOKEN", "")

mcp = FastMCP("control-center")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_TOKEN}", "Content-Type": "application/json"}


def _get(path: str, params: dict | None = None) -> Any:
    url = f"{_BASE_URL}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: dict) -> Any:
    url = f"{_BASE_URL}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=_headers(), content=json.dumps(body))
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def list_jobs(job_type: str | None = None, status: str | None = None) -> list[dict]:
    """List all registered jobs.

    Args:
        job_type: Filter by job type (e.g. 'sql', 'repo_connection', 'mcp').
        status:   Filter by status (e.g. 'active', 'paused', 'archived').

    Returns a list of job objects with id, name, type, kind, status, connector.
    """
    try:
        params: dict[str, str] = {}
        if job_type:
            params["job_type"] = job_type
        if status:
            params["status"] = status
        result = _get("/jobs", params=params or None)
        items = result.get("items", result) if isinstance(result, dict) else result
        return [
            {
                "id": j.get("id"),
                "name": j.get("name"),
                "type": j.get("type"),
                "kind": j.get("kind"),
                "status": j.get("status"),
                "connector": j.get("connector"),
                "environment": j.get("environment"),
                "description": j.get("description"),
            }
            for j in (items or [])
        ]
    except Exception as exc:
        raise ValueError(f"Failed to list jobs: {exc}") from exc


@mcp.tool()
def get_job(job_id: str) -> dict:
    """Get details for a specific job by ID.

    Args:
        job_id: The job UUID.

    Returns the full job object.
    """
    try:
        return _get(f"/jobs/{job_id}")
    except Exception as exc:
        raise ValueError(f"Failed to get job '{job_id}': {exc}") from exc


@mcp.tool()
def list_runs(job_id: str | None = None, limit: int = 20) -> list[dict]:
    """List recent job runs.

    Args:
        job_id: If given, only return runs for this job.
        limit:  Maximum number of runs to return (default 20).

    Returns a list of run objects with id, job_id, status, created_at, finished_at.
    """
    try:
        params: dict[str, Any] = {"limit": limit}
        if job_id:
            params["job_id"] = job_id
        result = _get("/runs", params=params)
        items = result.get("items", result) if isinstance(result, dict) else result
        return [
            {
                "id": r.get("id"),
                "job_id": r.get("job_id"),
                "status": r.get("status"),
                "action": r.get("action"),
                "created_at": r.get("created_at"),
                "finished_at": r.get("finished_at"),
                "error": r.get("error"),
            }
            for r in (items or [])
        ]
    except Exception as exc:
        raise ValueError(f"Failed to list runs: {exc}") from exc


@mcp.tool()
def get_run_status(run_id: str) -> dict:
    """Get the current status of a specific run.

    Args:
        run_id: The run UUID.

    Returns status, timestamps, and any error details.
    """
    try:
        return _get(f"/runs/{run_id}/status")
    except Exception as exc:
        raise ValueError(f"Failed to get run status for '{run_id}': {exc}") from exc


@mcp.tool()
def trigger_run(
    job_id: str,
    action: str = "run",
    params: str = "{}",
    target_environment: str = "dev",
) -> dict:
    """Trigger a new run for a job.

    Args:
        job_id:             The job UUID to run.
        action:             Action to perform (default 'run').
        params:             JSON string of run parameters (e.g. '{"query": "SELECT 1"}').
        target_environment: Deployment environment (default 'dev').

    Returns the newly created run object.
    """
    try:
        parsed_params = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"params must be a valid JSON string: {exc}") from exc

    try:
        body = {
            "action": action,
            "target_environment": target_environment,
            "params": parsed_params,
        }
        return _post(f"/jobs/{job_id}/runs", body)
    except Exception as exc:
        raise ValueError(f"Failed to trigger run for job '{job_id}': {exc}") from exc


if __name__ == "__main__":
    mcp.run(transport="stdio")
