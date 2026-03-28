from __future__ import annotations

"""Placeholder native executor for non-MCP jobs."""

from app.core.db import new_id
from app.services.execution_service import ExecutionRequest

from .base import BaseJobExecutor


class NativeJobExecutor(BaseJobExecutor):
    backend_name = "native"

    def execute(self, execution_request: ExecutionRequest) -> dict:
        return {
            "connector_run_id": new_id("native"),
            "status": "succeeded",
            "duration_ms": 420,
            "metadata": {
                "execution_request": execution_request.model_dump(),
                "resource_id": execution_request.resource.resource_id,
                "target_environment": execution_request.target_environment,
            },
            "error": None,
        }
