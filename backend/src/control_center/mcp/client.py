from __future__ import annotations

import abc
import os
import tempfile
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
else:
    ClientSession = None  # type: ignore[assignment]
    StdioServerParameters = None  # type: ignore[assignment]
    stdio_client = None  # type: ignore[assignment]
    _MCP_IMPORT_ERROR: Exception | None = None
    try:  # pragma: no cover
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:  # pragma: no cover
        _MCP_IMPORT_ERROR = exc

try:  # optional dependency in local environments
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv() -> None:
        return None

__all__ = ["BaseClient", "JSONPayload", "LLMClient"]

JSONPayload: TypeAlias = dict[str, Any]

load_dotenv()


def _require_mcp_runtime() -> None:
    if _MCP_IMPORT_ERROR is not None:
        raise RuntimeError(
            "The MCP Python SDK is required to use LLMClient. Install it with `uv add mcp`."
        ) from _MCP_IMPORT_ERROR


class BaseClient(abc.ABC):
    """Thin runtime abstraction for live MCP server interaction."""

    @abc.abstractmethod
    async def connect_to_server(self, server_name: str, server_config: JSONPayload) -> None:
        ...

    @abc.abstractmethod
    async def disconnect_server(self, server_name: str) -> None:
        ...

    @abc.abstractmethod
    async def list_tools(self, server_name: str) -> list[Any]:
        ...

    @abc.abstractmethod
    async def list_prompts(self, server_name: str) -> list[Any]:
        ...

    @abc.abstractmethod
    async def list_resources(self, server_name: str) -> list[Any]:
        ...

    @abc.abstractmethod
    async def call_tool(self, server_name: str, tool_name: str, arguments: JSONPayload) -> Any:
        ...

    @abc.abstractmethod
    async def get_prompt(self, server_name: str, prompt_name: str, arguments: JSONPayload) -> Any:
        ...

    @abc.abstractmethod
    async def read_resource(self, server_name: str, resource_uri: str) -> Any:
        ...

    @abc.abstractmethod
    async def cleanup(self) -> None:
        ...

    @property
    @abc.abstractmethod
    def connected_servers(self) -> list[str]:
        ...


class LLMClient(BaseClient):
    """
    MCP runtime client responsible only for transport and execution.

    This class intentionally avoids orchestration, policy, and model concerns so
    it can be reused by higher-level agents.
    """

    def __init__(self) -> None:
        os.environ.setdefault(
            "UV_CACHE_DIR",
            os.path.join(tempfile.gettempdir(), "control_center_uv_cache"),
        )
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.cleanup()

    @property
    def connected_servers(self) -> list[str]:
        return sorted(self._sessions.keys())

    def _require_session(self, server_name: str) -> ClientSession:
        session = self._sessions.get(server_name)
        if session is None:
            raise RuntimeError(f"Server '{server_name}' is not connected.")
        return session

    async def connect_to_server(self, server_name: str, server_config: JSONPayload) -> None:
        _require_mcp_runtime()
        try:
            server_params = StdioServerParameters(**server_config)
            transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
            read, write = transport
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[server_name] = session
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to server '{server_name}': {exc}") from exc

    async def disconnect_server(self, server_name: str) -> None:
        self._sessions.pop(server_name, None)

    async def list_tools(self, server_name: str) -> list[Any]:
        session = self._require_session(server_name)
        try:
            response = await session.list_tools()
            return list(getattr(response, "tools", None) or [])
        except Exception as exc:
            raise RuntimeError(f"Failed to list tools for server '{server_name}': {exc}") from exc

    async def list_prompts(self, server_name: str) -> list[Any]:
        session = self._require_session(server_name)
        try:
            response = await session.list_prompts()
            return list(getattr(response, "prompts", None) or [])
        except Exception as exc:
            raise RuntimeError(f"Failed to list prompts for server '{server_name}': {exc}") from exc

    async def list_resources(self, server_name: str) -> list[Any]:
        session = self._require_session(server_name)
        try:
            response = await session.list_resources()
            return list(getattr(response, "resources", None) or [])
        except Exception as exc:
            raise RuntimeError(f"Failed to list resources for server '{server_name}': {exc}") from exc

    async def call_tool(self, server_name: str, tool_name: str, arguments: JSONPayload) -> Any:
        session = self._require_session(server_name)
        try:
            return await session.call_tool(tool_name, arguments=arguments)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to call tool '{tool_name}' on server '{server_name}': {exc}"
            ) from exc

    async def get_prompt(self, server_name: str, prompt_name: str, arguments: JSONPayload) -> Any:
        session = self._require_session(server_name)
        try:
            return await session.get_prompt(prompt_name, arguments=arguments)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to get prompt '{prompt_name}' on server '{server_name}': {exc}"
            ) from exc

    async def read_resource(self, server_name: str, resource_uri: str) -> Any:
        session = self._require_session(server_name)
        try:
            return await session.read_resource(resource_uri)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to read resource '{resource_uri}' on server '{server_name}': {exc}"
            ) from exc

    async def cleanup(self) -> None:
        self._sessions.clear()
        await self._exit_stack.aclose()
