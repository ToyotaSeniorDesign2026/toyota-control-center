from __future__ import annotations

"""
import asyncio
import json
import re
from collections.abc import Mapping
from typing import Any

from mcp.types import Prompt, Resource, Tool
from control_center.specs import BoundCapability
from control_center.mcp import BaseClient, ModelTurnResult, RequestedToolCall

from .base import BaseAdapter

__all__ = ["GoogleAdapter"]


def _sanitize_for_tool_name(name: str) -> str:
    # Google function names allow letters, digits, and underscores up to 64 chars.

    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")[:64]


def _require_google_genai() -> tuple[Any, Any]:
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "google-genai is required for GoogleAdapter. Install it with `uv add google-genai`."
        ) from exc
    return genai, types


class GoogleAdapter(BaseAdapter[dict[str, Any]]):
    framework: str = "google"
    _DEFAULT_BANNED_SCHEMA_KEYS = {
        "$schema",
        "$id",
        "$defs",
        "definitions",
        "$ref",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "additionalProperties",
        "additional_properties",
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
        self._google_client = client

    @property
    def client(self) -> Any:
        if self._google_client is None:
            genai, _ = _require_google_genai()
            self._google_client = genai.Client()
        return self._google_client

    def _make_framework_name(self, server_name: str, raw_name: str) -> str:
        return _sanitize_for_tool_name(f"{server_name}_{raw_name}")

    def _function_declaration(
        self,
        *,
        framework_name: str,
        description: str | None,
        parameters_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "name": framework_name,
            "description": description or "",
            "parameters": parameters_schema,
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

        return self._function_declaration(
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

        return self._function_declaration(
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

        return self._function_declaration(
            framework_name=framework_name,
            description=mcp_prompt.description,
            parameters_schema=parameters_schema,
        )

    # TODO: Refactor generate to properly handle messages logic in Google's API schema
    async def generate(
        self,
        *,
        model: str,
        messages: list[Any],
        tools: list[dict[str, Any]],
    ) -> ModelTurnResult:
        _, types = _require_google_genai()

        # prompt = message
        # if tool_results:
        #     serialized_results = json.dumps(tool_results, default=str, indent=2)
        #     prompt = (
        #         f"{message}\n\n"
        #         "Tool results are available below as JSON. Use them to continue reasoning. "
        #         "If the task is complete, answer directly. Otherwise request another tool.\n"
        #         f"{serialized_results}"
        #     )

        function_declarations = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("parameters", {"type": "object", "properties": {}}),
            )
            for tool in tools
        ]

        config = None
        if function_declarations:
            config = types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=function_declarations)]
            )

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=model,
            contents=messages,
            config=config,
        )

        requested_tools: list[RequestedToolCall] = []
        text_fragments: list[str] = []

        direct_text = getattr(response, "text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            text_fragments.append(direct_text.strip())

        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    text_fragments.append(text.strip())

                function_call = getattr(part, "function_call", None)
                if function_call is None:
                    continue

                name = getattr(function_call, "name", None)
                raw_args = getattr(function_call, "args", None) or {}
                arguments = dict(raw_args) if isinstance(raw_args, Mapping) else {}
                if name:
                    requested_tools.append(
                        RequestedToolCall(name=name, arguments=arguments)
                    )

        final_text = "\n".join(fragment for fragment in text_fragments if fragment) or None
        return ModelTurnResult(text=final_text, tool_calls=requested_tools, raw=response)
"""
