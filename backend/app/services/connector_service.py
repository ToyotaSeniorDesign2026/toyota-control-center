from __future__ import annotations

"""Connector execution service with MCP-backed resource support."""

import time

from app.core.db import new_id
from app.services.execution_service import ExecutionRequest
from app.services.mcp_job_service import execute_job_via_mcp


def execute_resource(execution_request: ExecutionRequest):
    if execution_request.execution_backend == "mcp":
        started_at = time.perf_counter()
        result = execute_job_via_mcp(execution_request)
        result["connector_run_id"] = new_id("mcp")
        result["duration_ms"] = int((time.perf_counter() - started_at) * 1000)
        return result

    connector_run_id = new_id("mcp")
    # Default stub result for non-MCP resources until other connectors are implemented.
    return {
        "connector_run_id": connector_run_id,
        "status": "succeeded",
        "duration_ms": 420,
        "metadata": {
            "execution_request": execution_request.model_dump(),
            "resource_id": execution_request.resource.resource_id,
            "target_environment": execution_request.target_environment,
        },
        "error": None,
    }
