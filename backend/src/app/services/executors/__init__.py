from __future__ import annotations

from typing import Any

from app.services.execution_service import ExecutionRequest

from .base import BaseJobExecutor
from .mcp_executor import MCPJobExecutor

_EXECUTOR_REGISTRY: dict[str, type[BaseJobExecutor]] = {
    "mcp": MCPJobExecutor,
}


def dispatch_execution(execution_request: ExecutionRequest) -> dict[str, Any]:
    """Route an ExecutionRequest to the correct backend executor and return its result."""
    backend = execution_request.execution_backend
    executor_cls = _EXECUTOR_REGISTRY.get(backend)
    if executor_cls is None:
        raise RuntimeError(
            f"No executor registered for backend '{backend}'. "
            f"Available backends: {list(_EXECUTOR_REGISTRY)}"
        )
    return executor_cls().execute(execution_request)


__all__ = [
    "BaseJobExecutor",
    "MCPJobExecutor",
    "dispatch_execution",
]
