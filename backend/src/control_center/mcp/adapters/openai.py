from __future__ import annotations

import json
import re
from typing import Any

from mcp.types import Prompt, Resource, Tool
from control_center.specs import BoundPrimitive
from control_center.mcp import BaseClient, ModelTurnResult, RequestedToolCall

from .base import BaseAdapter

__all__ = ["OpenAIAdapter"]


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

    _DEFAULT_UNSUPPORTED_SCHEMA_KEYS = {
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
            unsupported_schema_keys=self._DEFAULT_UNSUPPORTED_SCHEMA_KEYS,
        )
        self._openai_client = client

    @property
    def client(self) -> Any:
        if self._openai_client is None:
            async_openai = _require_openai()
            self._openai_client = async_openai()
        return self._openai_client

    def _make_exposed_name(self, server_name: str, raw_name: str) -> str:
        return _sanitize_for_tool_name(f"{server_name}_{raw_name}")

    def _function_tool(
        self,
        *,
        exposed_name: str,
        description: str | None,
        parameters_schema: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "name": exposed_name,
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
        exposed_name = self._make_exposed_name(server_name, mcp_tool.name)

        if exposed_name in self.disallowed_tools or mcp_tool.name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundPrimitive(
                exposed_name=exposed_name,
                server_name=server_name,
                source_id=mcp_tool.name,
                kind="tool",
                description=mcp_tool.description,
            )
        )

        return self._function_tool(
            exposed_name=exposed_name,
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
        exposed_name = self._make_exposed_name(server_name, f"resource_{mcp_resource.name}")

        if exposed_name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundPrimitive(
                exposed_name=exposed_name,
                server_name=server_name,
                source_id=str(mcp_resource.uri),
                kind="resource",
                description=mcp_resource.description,
            )
        )

        return self._function_tool(
            exposed_name=exposed_name,
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
        exposed_name = self._make_exposed_name(server_name, mcp_prompt.name)

        if exposed_name in self.disallowed_tools or mcp_prompt.name in self.disallowed_tools:
            return None

        self._register_binding(
            BoundPrimitive(
                exposed_name=exposed_name,
                server_name=server_name,
                source_id=mcp_prompt.name,
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
            exposed_name=exposed_name,
            description=mcp_prompt.description,
            parameters_schema=parameters_schema,
        )

    @staticmethod
    def _to_responses_input(inputs: Any) -> Any:
        """Translate generic chat-style messages into Responses API items.

        Responses API rejects assistant messages with `tool_calls` arrays and
        `role: "tool"` messages — they must be `function_call` /
        `function_call_output` items instead.
        """
        if not isinstance(inputs, list):
            return inputs

        converted: list[dict[str, Any]] = []
        for msg in inputs:
            if not isinstance(msg, dict):
                converted.append(msg)
                continue

            role = msg.get("role")

            if role == "tool":
                converted.append({
                    "type": "function_call_output",
                    "call_id": msg.get("tool_call_id"),
                    "output": str(msg.get("content") or ""),
                })
                continue

            if role == "assistant":
                text = msg.get("content")
                tool_calls = msg.get("tool_calls") or []

                if text:
                    converted.append({
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    })

                for tc in tool_calls:
                    fn = tc.get("function") or {}
                    arguments = fn.get("arguments")
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments or {}, default=str)
                    converted.append({
                        "type": "function_call",
                        "call_id": tc.get("id"),
                        "name": fn.get("name"),
                        "arguments": arguments,
                    })
                continue

            converted.append(msg)

        return converted

    async def generate(
        self,
        *,
        model: str,
        inputs: Any,
        tools: list[dict[str, Any]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_choice: Any | None = None,
        max_retries: int | None = None,
        output_config: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ModelTurnResult:

        request: dict[str, Any] = {
            "model": model,
            "input": self._to_responses_input(inputs),
        }

        if system_prompt:
            request["instructions"] = system_prompt

        if tools:
            request["tools"] = tools
            request["tool_choice"] = tool_choice or "auto"

        if max_tokens is not None:
            request["max_output_tokens"] = max_tokens

        if temperature is not None:
            request["temperature"] = temperature

        if output_config is not None:
            # Responses API structured outputs are passed under `text.format`.
            # See: https://developers.openai.com/api/reference/resources/responses/methods/create
            request["text"] = output_config

        if extra:
            request.update(extra)

        request["reasoning"] = {"effort": "medium"}

        response = await self.client.responses.create(**request)

        requested_tools: list[RequestedToolCall] = []

        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "function_call":
                continue

            name = getattr(item, "name", None)
            raw_args = getattr(item, "arguments", None) or "{}"

            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else {}
            except json.JSONDecodeError:
                arguments = {}

            if name:
                requested_tools.append(
                    RequestedToolCall(
                        name=name,
                        arguments=arguments,
                        id=getattr(item, "call_id", None) or getattr(item, "id", None),
                    )
                )

        final_text = getattr(response, "output_text", None) or None

        return ModelTurnResult(
            text=final_text,
            tool_calls=requested_tools,
            raw=response,
        )
