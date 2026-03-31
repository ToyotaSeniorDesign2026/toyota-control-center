from __future__ import annotations

"""Execution backend selector and dispatcher."""

import time

from app.services.execution_service import ExecutionRequest
from app.services.executors import BaseJobExecutor, MCPJobExecutor, NativeJobExecutor, SQLJobExecutor


_EXECUTORS: dict[str, BaseJobExecutor] = {
    "mcp": MCPJobExecutor(),
    "native": NativeJobExecutor(),
}
_SQL_EXECUTOR = SQLJobExecutor()


def get_executor(execution_request: ExecutionRequest) -> BaseJobExecutor:
    if execution_request.execution_backend == "native" and execution_request.resource.type.lower() == "sql":
        return _SQL_EXECUTOR
    try:
        return _EXECUTORS[execution_request.execution_backend]
    except KeyError as exc:
        raise RuntimeError(
            f"No executor registered for backend '{execution_request.execution_backend}'."
        ) from exc


def dispatch_execution(execution_request: ExecutionRequest):
    started_at = time.perf_counter()
    executor = get_executor(execution_request)
    result = executor.execute(execution_request)
    result["duration_ms"] = int((time.perf_counter() - started_at) * 1000)
    return result
