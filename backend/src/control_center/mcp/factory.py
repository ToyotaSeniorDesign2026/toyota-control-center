from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
import os
import re
from typing import Any, TypeAlias

from pydantic import BaseModel, Field, create_model, field_validator

from control_center.core.registry import RegistryManager
from control_center.mcp.adapters.base import BaseAdapter
from control_center.mcp.adapters.google import GoogleAdapter
from control_center.mcp.adapters.openai import OpenAIAdapter
from control_center.mcp.agent import MCPAgent
from control_center.mcp.client import BaseClient, LLMClient

try:
    import instructor  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional dependency
    instructor = None

ConnectorSelectionModel: TypeAlias = type[BaseModel]

__all__ = [
    "build_agent",
    "build_agent_from_registry",
    "build_connector_selection_model",
    "default_mcp_model",
    "make_adapter_for_model",
    "select_registry_connectors",
]


def _to_enum_member_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not normalized:
        normalized = "CONNECTOR"
    if normalized[0].isdigit():
        normalized = f"CONNECTOR_{normalized}"
    return normalized


def build_connector_selection_model(connector_names: Iterable[str]) -> ConnectorSelectionModel:
    connector_values = list(dict.fromkeys(connector_names))
    if not connector_values:
        raise ValueError("At least one connector must be available to build a selection model.")

    connector_enum = Enum(
        "ConnectorEnum",
        {_to_enum_member_name(name): name for name in connector_values},
        type=str,
    )

    @field_validator("connectors", mode="before")
    @classmethod
    def _coerce_connectors(cls, value: Any) -> list[Any]:
        if value is None:
            return value

        if not isinstance(value, list):
            raise TypeError("connectors must be provided as a list")

        coerced: list[Any] = []
        for item in value:
            if isinstance(item, connector_enum):
                coerced.append(item)
                continue
            coerced.append(connector_enum(str(item)))
        return coerced

    return create_model(
        "ConnectorSelection",
        __validators__={"coerce_connectors": _coerce_connectors},
        connectors=(
            list[connector_enum],  # type: ignore[valid-type]
            Field(
                ...,
                description="The approved MCP connectors required to satisfy the user request.",
            ),
        ),
        decision_reasoning=(
            str,
            Field(
                ...,
                description="Short explanation of why these connectors were selected.",
            ),
        ),
    )


def _create_instructor_client(provider_model: str):
    if instructor is None:
        raise RuntimeError("Instructor dependency is not installed. Add it with `uv add instructor`.")
    if provider_model.startswith("google/") and not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY must be set to use Instructor with Google models.")
    if provider_model.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY must be set to use Instructor with OpenAI models.")
    return instructor.from_provider(provider_model)


def default_mcp_model() -> str:
    return (
        os.getenv("CONTROL_CENTER_MCP_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "gpt-4o-mini"
    )


def _default_instructor_model() -> str:
    return (
        os.getenv("CONTROL_CENTER_MCP_INSTRUCTOR_MODEL")
        or f"openai/{os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}"
    )


def make_adapter_for_model(model: str) -> BaseAdapter[Any]:
    normalized = model.lower()
    if normalized.startswith("google/") or normalized.startswith("gemini"):
        return GoogleAdapter()
    return OpenAIAdapter()


async def select_registry_connectors(
    *,
    prompt: str,
    environment: str | None = "dev",
    registry_manager: RegistryManager | None = None,
    instructor_client: Any | None = None,
    provider_model: str | None = None,
    max_retries: int = 3,
) -> tuple[list[str], str]:
    """
    Use Instructor to choose which approved MCP servers should be connected.
    """

    manager = registry_manager or RegistryManager(environment=environment)
    available_connectors = manager.get_available_servers_list()
    selection_model = build_connector_selection_model(available_connectors)

    resolved_provider_model = provider_model or _default_instructor_model()
    client = instructor_client or _create_instructor_client(resolved_provider_model)
    result = client.create(
        response_model=selection_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are selecting approved MCP connectors for a Control Center runtime. "
                    "Choose only from the available connectors and include concise reasoning."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Available connectors: {', '.join(available_connectors)}\n"
                    f"User request: {prompt}"
                ),
            },
        ],
        max_retries=max_retries,
    )

    selected = list(dict.fromkeys(str(connector.value) for connector in result.connectors))
    reasoning = str(result.decision_reasoning).strip()
    print(f"Selected connectors: {selected}\nReasoning: {reasoning}")
    return selected, reasoning


async def build_agent(
    *,
    server_name: str,
    server_config: dict[str, Any],
    model: str | None = None,
    client: BaseClient | None = None,
    adapter: BaseAdapter[Any] | None = None,
    max_tool_rounds: int = 5,
    verbose: bool = False,
) -> MCPAgent:
    """
    Convenience builder for the common single-server MCP agent flow.

    Example:
        agent = await build_agent(
            server_name="filesystem",
            server_config={"command": "uvx", "args": ["mcp-server-filesystem", "/tmp"]},
        )
    """

    runtime_client = client or LLMClient()
    await runtime_client.connect_to_server(server_name, server_config)

    resolved_model = model or default_mcp_model()
    runtime_adapter = adapter or make_adapter_for_model(resolved_model)
    return MCPAgent(
        client=runtime_client,
        adapter=runtime_adapter,
        model=resolved_model,
        max_tool_rounds=max_tool_rounds,
        verbose=verbose,
    )


async def build_agent_from_registry(
    *,
    environment: str | None = "dev",
    server_names: Iterable[str] | None = None,
    selection_prompt: str | None = None,
    model: str | None = None,
    registry_manager: RegistryManager | None = None,
    client: BaseClient | None = None,
    adapter: BaseAdapter[Any] | None = None,
    max_tool_rounds: int = 5,
    instructor_client: Any | None = None,
    instructor_model: str | None = None,
    verbose: bool = False,
) -> MCPAgent:
    """
    Build an MCP agent from approved registry entries.

    If `selection_prompt` is provided, Instructor selects the approved connectors.
    Otherwise, `server_names` are used directly, or all available servers are connected.
    """

    manager = registry_manager or RegistryManager(environment=environment)
    resolved_server_names: Iterable[str] | None = server_names
    if selection_prompt:
        resolved_server_names, _ = await select_registry_connectors(
            prompt=selection_prompt,
            environment=environment,
            registry_manager=manager,
            instructor_client=instructor_client,
            provider_model=instructor_model,
        )

    server_configs = manager.get_server_configs(resolved_server_names)

    runtime_client = client or LLMClient()
    for server_name, server_config in server_configs.items():
        await runtime_client.connect_to_server(server_name, server_config)

    resolved_model = model or default_mcp_model()
    runtime_adapter = adapter or make_adapter_for_model(resolved_model)
    return MCPAgent(
        client=runtime_client,
        adapter=runtime_adapter,
        model=resolved_model,
        max_tool_rounds=max_tool_rounds,
        verbose=verbose,
    )
