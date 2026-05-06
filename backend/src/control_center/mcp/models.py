from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "AgentToolExecution",
    "LLMProtocol",
    "ModelTurnResult",
    "RequestedToolCall",
]


@dataclass(frozen=True)
class RequestedToolCall:
    """Normalized tool call requested by a model provider."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str | None = None  # provider-assigned (OpenAI tool_call.id, etc., or none if not issued by provider)


@dataclass(frozen=True)
class ModelTurnResult:
    """Normalized single-turn model response."""

    text: str | None = None
    tool_calls: list[RequestedToolCall] = field(default_factory=list)
    raw: Any | None = None


@dataclass(frozen=True)
class AgentToolExecution:
    """Audit record for a single tool execution."""

    framework_name: str
    server_name: str
    remote_name: str
    arguments: dict[str, Any]
    raw_result: Any
    parsed_result: str


@runtime_checkable
class LLMProtocol(Protocol):
    """Provider-agnostic async generation protocol."""

    async def generate(
        self,
        *,
        messages: list[Any],
        tools: list[Any],
    ) -> ModelTurnResult:
        ...
