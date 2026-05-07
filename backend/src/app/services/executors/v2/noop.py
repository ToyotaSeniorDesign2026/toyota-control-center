from __future__ import annotations

"""NOOP executor — sentinel for tests, dry-runs, and contracts in development."""

from typing import Any

from app.services.execution_service_v2 import ExecutionRequestV2

from .base import V2Executor


class NoopExecutor(V2Executor):
    async def execute_async(self, request: ExecutionRequestV2) -> dict[str, Any]:
        return {
            "status": "succeeded",
            "result": {"message": "noop executor — nothing was executed"},
            "error": None,
            "metadata": {
                "executor_type": "noop",
                "job_id": getattr(request.job, "id", None),
                "contract_type": request.contract.type,
            },
        }
