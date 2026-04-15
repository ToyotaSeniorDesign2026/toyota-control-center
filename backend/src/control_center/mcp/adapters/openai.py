from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.types import Prompt, Resource, Tool
else:
    Prompt = Resource = Tool = Any

from control_center.core.specs import BoundCapability
from control_center.mcp.client import BaseClient
from control_center.mcp.models import ModelTurnResult, RequestedToolCall

from .base import BaseAdapter

__all__ = ["OpenAIAdapter", "OpenAIMCPAdapter"]


def _sanitize_for_tool_name(name: str) -> str:
    """OpenAI function names allow letters, digits, underscores, and hyphens."""

    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")[:64]


def _require_openai() -> Any:
    try:
        from openai import AsyncOpenAI  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "openai is required for OpenAIAdapter. Install it with `uv add openai`."
        ) from exc
    return AsyncOpenAI


class OpenAIAdapter(BaseAdapter[dict[str, Any]]):
    framework: str = "openai"
    _DEFAULT_BANNED_SCHEMA_KEYS = {
        "$schema",
        "$id",
        "$defs",
        "definitions",
        "$ref",
    }

    def __init__(
        self,
        *,
        client: Any | None = None,
        disallowed_tools: list[str] | None = None,
    ) -> None:
        super().__init__(
            disallowed_tools=disallowed_tools,
            banned_schema_keys=self._DEFAULT_BANNED_SCHEMA_KEYS,
        )
        self._openai_client = client

    @property
    def client(self) -> Any:
        if self._openai_client is None:
            async_openai = _require_openai()
            self._openai_client = async_openai()
        return self._openai_client

    def _make_framework_name(self, server_name: str, raw_name: str) -> str:
        return _sanitize_for_tool_name(f"{server_name}_{raw_name}")

    def _function_tool(
        self,
        *,
        framework_name: str,
        description: str | None,
        parameters_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": framework_name,
                "description": description or "",
                "parameters": parameters_schema,
            },
        }

    def _convert_tool(
        self,
        mcp_tool: Tool,
        client: BaseClient,
        server_name: str,
    ) -> dict[str, Any] | None:
        del client
        framework_name = self._make_framework_name(server_name, mcp_tool.name)

        if framework_name in self.disallowed_tools or mcp_tool.name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundCapability(
                framework_name=framework_name,
                server_name=server_name,
                remote_name=mcp_tool.name,
                kind="tool",
                description=mcp_tool.description,
            )
        )

        return self._function_tool(
            framework_name=framework_name,
            description=mcp_tool.description,
            parameters_schema=self.fix_schema(self.sanitize_schema(mcp_tool.inputSchema)),
        )

    def _convert_resource(
        self,
        mcp_resource: Resource,
        client: BaseClient,
        server_name: str,
    ) -> dict[str, Any] | None:
        del client
        framework_name = self._make_framework_name(server_name, f"resource_{mcp_resource.name}")

        if framework_name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundCapability(
                framework_name=framework_name,
                server_name=server_name,
                remote_name=str(mcp_resource.uri),
                kind="resource",
                description=mcp_resource.description,
            )
        )

        return self._function_tool(
            framework_name=framework_name,
            description=mcp_resource.description or f"Read resource '{mcp_resource.name}'",
            parameters_schema={"type": "object", "properties": {}},
        )

    def _convert_prompt(
        self,
        mcp_prompt: Prompt,
        client: BaseClient,
        server_name: str,
    ) -> dict[str, Any] | None:
        del client
        framework_name = self._make_framework_name(server_name, mcp_prompt.name)

        if framework_name in self.disallowed_tools or mcp_prompt.name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundCapability(
                framework_name=framework_name,
                server_name=server_name,
                remote_name=mcp_prompt.name,
                kind="prompt",
                description=mcp_prompt.description,
            )
        )

        properties: dict[str, Any] = {}
        required: list[str] = []

        for arg in mcp_prompt.arguments or []:
            prop: dict[str, Any] = {"type": "string"}
            if arg.description:
                prop["description"] = arg.description
            properties[arg.name] = prop
            if arg.required:
                required.append(arg.name)

        parameters_schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            parameters_schema["required"] = required

        return self._function_tool(
            framework_name=framework_name,
            description=mcp_prompt.description,
            parameters_schema=parameters_schema,
        )

    async def generate(
        self,
        *,
        model: str,
        message: str,
        tools: list[dict[str, Any]],
        tool_results: list[dict[str, Any]] | None = None,
    ) -> ModelTurnResult:
        prompt = message
        if tool_results:
            serialized_results = json.dumps(tool_results, default=str, indent=2)
            prompt = (
                f"{message}\n\n"
                "Tool results are available below as JSON. Use them to continue reasoning. "
                "If the task is complete, answer directly. Otherwise request another tool.\n"
                f"{serialized_results}"
            )

        request: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**request)

        requested_tools: list[RequestedToolCall] = []
        text_fragments: list[str] = []

        for choice in getattr(response, "choices", None) or []:
            response_message = getattr(choice, "message", None)
            content = getattr(response_message, "content", None)
            if isinstance(content, str) and content.strip():
                text_fragments.append(content.strip())

            for tool_call in getattr(response_message, "tool_calls", None) or []:
                function_call = getattr(tool_call, "function", None)
                name = getattr(function_call, "name", None)
                raw_args = getattr(function_call, "arguments", None) or "{}"
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else {}
                except json.JSONDecodeError:
                    arguments = {}

                if name:
                    requested_tools.append(
                        RequestedToolCall(name=name, arguments=arguments)
                    )

        final_text = "\n".join(fragment for fragment in text_fragments if fragment) or None
        return ModelTurnResult(text=final_text, tool_calls=requested_tools, raw=response)


OpenAIMCPAdapter = OpenAIAdapter
