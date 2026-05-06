from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable, TypeVar
T = TypeVar("T")

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

    exposed_name: str
    server_name: str
    source_id: str
    arguments: dict[str, Any]
    raw_result: Any
    parsed_result: str


@runtime_checkable
class LLMProtocol(Protocol):
    """Provider-agnostic async generation protocol."""

    async def generate(
        self,
        *,
        inputs: Any,
        tools: list[T] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_choice: Any | None = None,
        max_retries: int | None = None,
        output_config: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ModelTurnResult:
        ...
