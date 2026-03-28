from __future__ import annotations

"""Executor contracts for run execution backends."""

from abc import ABC, abstractmethod
from typing import Any

from app.services.execution_service import ExecutionRequest


class BaseJobExecutor(ABC):
    backend_name: str = "unknown"

    @abstractmethod
    def execute(self, execution_request: ExecutionRequest) -> dict[str, Any]:
        raise NotImplementedError
