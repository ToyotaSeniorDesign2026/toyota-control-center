from __future__ import annotations

"""MCP execution dispatcher."""

import time

from app.services.execution_service import ExecutionRequest
from app.services.executors import MCPJobExecutor

_EXECUTOR = MCPJobExecutor()


def dispatch_execution(execution_request: ExecutionRequest):
    started_at = time.perf_counter()
    result = _EXECUTOR.execute(execution_request)
    result["duration_ms"] = int((time.perf_counter() - started_at) * 1000)
    return result
