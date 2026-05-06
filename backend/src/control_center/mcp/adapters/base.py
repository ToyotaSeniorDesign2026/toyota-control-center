from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from mcp.types import Prompt, Resource, Tool
from control_center.specs import BoundCapability
from control_center.mcp import BaseClient, ModelTurnResult
T = TypeVar("T")


class BaseAdapter(Generic[T], ABC):
    """
    Convert MCP capabilities into framework-native objects.

    This adapter is aligned to BaseClient, not connector/session internals.
    """

    framework: str = "unknown"

    def __init__(
        self,
        disallowed_tools: list[str] | None = None,
        banned_schema_keys: set[str] | None = None,
    ) -> None:
        self.disallowed_tools = set(disallowed_tools or [])
        self.banned_schema_keys = set(banned_schema_keys or [])

        self._server_tool_map: dict[str, list[T]] = {}
        self._server_resource_map: dict[str, list[T]] = {}
        self._server_prompt_map: dict[str, list[T]] = {}

        self._bindings: dict[str, BoundCapability] = {}

        self.tools: list[T] = []
        self.resources: list[T] = []
        self.prompts: list[T] = []

    def parse_result(self, result: Any) -> str:
        """Normalize MCP operation results into text per the MCP spec."""
        if hasattr(result, "contents"):  # resource read result
            return "\n".join(
                c.decode() if isinstance(c, bytes) else str(c)
                for c in result.contents
            )

        if hasattr(result, "messages"):  # prompt result
            return "\n".join(str(m) for m in result.messages)

        if hasattr(result, "content") and isinstance(result.content, list):
            # tool result — content is list[TextContent | ImageContent | ...]
            parts: list[str] = []
            for item in result.content:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(text)
                else:
                    # image / audio / resource_link — represent as a label
                    mime = getattr(item, "mimeType", "")
                    kind = getattr(item, "type", "binary")
                    parts.append(f"[{kind}: {mime}]" if mime else f"[{kind}]")
            result_text = "\n".join(parts) if parts else ""
            if getattr(result, "isError", False):
                return f"Error: {result_text or 'tool returned an error'}"
            return result_text

        return str(result)

    def fix_schema(self, schema: Any) -> Any:
        """
        Normalize schemas for LLM vendors that dislike union-style 'type' arrays.
        """
        if isinstance(schema, dict):
            schema = dict(schema)

            if "type" in schema and isinstance(schema["type"], list):
                schema["anyOf"] = [{"type": t} for t in schema["type"]]
                del schema["type"]

            if "enum" in schema and "type" not in schema:
                schema["type"] = "string"

            for key, value in list(schema.items()):
                schema[key] = self.fix_schema(value)
            return schema

        if isinstance(schema, list):
            return [self.fix_schema(item) for item in schema]

        return schema

    def sanitize_schema(self, schema: Any) -> Any:
        """
        Strip schema keys that are valid JSON Schema but unsupported by provider SDKs.
        """
        if isinstance(schema, dict):
            return {
                key: self.sanitize_schema(value)
                for key, value in schema.items()
                if key not in self.banned_schema_keys
            }

        if isinstance(schema, list):
            return [self.sanitize_schema(item) for item in schema]

        return schema

    @property
    def all_capabilities(self) -> list[T]:
        return [*self.tools, *self.resources, *self.prompts]

    def clear_cache(self) -> None:
        self._server_tool_map.clear()
        self._server_resource_map.clear()
        self._server_prompt_map.clear()
        self._bindings.clear()
        self.tools = []
        self.resources = []
        self.prompts = []

    def _register_binding(self, binding: BoundCapability) -> None:
        if binding.framework_name in self._bindings:
            raise ValueError(f"Duplicate framework capability name: {binding.framework_name}")
        self._bindings[binding.framework_name] = binding

    def get_binding(self, framework_name: str) -> BoundCapability:
        try:
            return self._bindings[framework_name]
        except KeyError as exc:
            raise KeyError(f"No bound capability found for '{framework_name}'.") from exc

    async def create_all(self, client: BaseClient) -> None:
        await self.create_tools(client)

        try:
            await self.create_resources(client)
        except Exception:
            self.resources = []

        try:
            await self.create_prompts(client)
        except Exception:
            self.prompts = []

    async def create_tools(self, client: BaseClient) -> list[T]:
        tools: list[T] = []
        for server_name in client.connected_servers:
            tools.extend(await self.load_tools_for_server(client, server_name))
        self.tools = tools
        return self.tools

    async def create_resources(self, client: BaseClient) -> list[T]:
        resources: list[T] = []
        for server_name in client.connected_servers:
            resources.extend(await self.load_resources_for_server(client, server_name))
        self.resources = resources
        return self.resources

    async def create_prompts(self, client: BaseClient) -> list[T]:
        prompts: list[T] = []
        for server_name in client.connected_servers:
            prompts.extend(await self.load_prompts_for_server(client, server_name))
        self.prompts = prompts
        return self.prompts

    async def load_tools_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_tool_map:
            return list(self._server_tool_map[server_name])

        converted: list[T] = []
        for tool in await client.list_tools(server_name):
            item = self._convert_tool(tool, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_tool_map[server_name] = converted
        return list(converted)

    async def load_resources_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_resource_map:
            return list(self._server_resource_map[server_name])

        converted: list[T] = []
        for resource in await client.list_resources(server_name) or []:
            item = self._convert_resource(resource, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_resource_map[server_name] = converted
        return list(converted)

    async def load_prompts_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_prompt_map:
            return list(self._server_prompt_map[server_name])

        converted: list[T] = []
        for prompt in await client.list_prompts(server_name) or []:
            item = self._convert_prompt(prompt, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_prompt_map[server_name] = converted
        return list(converted)

    async def invoke(self, client: BaseClient, framework_name: str, arguments: dict[str, Any]) -> Any:
        binding = self.get_binding(framework_name)

        if binding.kind == "tool":
            return await client.call_tool(binding.server_name, binding.remote_name, arguments)

        if binding.kind == "prompt":
            return await client.get_prompt(binding.server_name, binding.remote_name, arguments)

        if binding.kind == "resource":
            return await client.read_resource(binding.server_name, binding.remote_name)

        raise ValueError(f"Unsupported capability kind: {binding.kind}")

    async def generate(
        self,
        *,
        model: str,
        messages: list[Any],
        tools: list[T],
    ) -> ModelTurnResult:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement model generation for '{model}'."
        )

    @abstractmethod
    def _convert_tool(self, mcp_tool: Tool, client: BaseClient, server_name: str) -> T | None:
        ...

    @abstractmethod
    def _convert_resource(
        self,
        mcp_resource: Resource,
        client: BaseClient,
        server_name: str,
    ) -> T | None:
        ...

    @abstractmethod
    def _convert_prompt(
        self,
        mcp_prompt: Prompt,
        client: BaseClient,
        server_name: str,
    ) -> T | None:
        ...
