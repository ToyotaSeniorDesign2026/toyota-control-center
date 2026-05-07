from __future__ import annotations

"""Base class for v2 executors.

Each executor receives an ExecutionRequestV2 (job + payload + contract)
and returns a dict with at minimum: status, result, error, metadata.
The sync `execute()` wraps the async `execute_async()` so callers don't
have to know about asyncio.
"""

import asyncio
import os
import threading
from abc import ABC, abstractmethod
from typing import Any

from app.services.execution_service_v2 import ExecutionRequestV2


class V2Executor(ABC):
    """Abstract base for executors keyed by ExecutorType."""

    @abstractmethod
    async def execute_async(self, request: ExecutionRequestV2) -> dict[str, Any]:
        ...

    def execute(self, request: ExecutionRequestV2) -> dict[str, Any]:
        """Sync wrapper around execute_async.

        If we're already inside an event loop (e.g. called from a FastAPI
        async handler that wandered into sync territory), spin up a thread
        and run a fresh loop there. Honors MCP_EXECUTION_TIMEOUT_SECONDS.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.execute_async(request))

        result_holder: dict[str, Any] = {}
        error_holder: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_holder["execution"] = asyncio.run(self.execute_async(request))
            except BaseException as exc:
                error_holder["error"] = exc

        timeout_s = int(
            os.getenv(
                "MCP_EXECUTION_TIMEOUT_SECONDS",
                str(request.contract.features.max_runtime_seconds),
            )
        )
        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join(timeout=timeout_s)

        if thread.is_alive():
            raise RuntimeError(
                f"Execution timed out after {timeout_s}s for "
                f"executor_type={request.contract.executor_type.value!r}."
            )
        if "error" in error_holder:
            raise error_holder["error"]
        return result_holder["execution"]
