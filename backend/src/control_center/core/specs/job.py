from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

__all__ = ["JobSpec", "JobSpecList"]


class JobSpec(BaseModel):
    """
    Minimal MCP job description used by the prompt-to-job adapter.
    """

    intent: str | None = None
    environment: str  # Environment = Environment.DEV
    risk_score_input: list[str] = Field(default_factory=list)
    schedule: str | None = None
    tasks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobSpecList(BaseModel):
    jobs: list[JobSpec] = Field(default_factory=list)