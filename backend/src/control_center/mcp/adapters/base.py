from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Generic, TypeVar

from mcp.types import Tool, Resource, Prompt
from control_center.specs import BoundPrimitive
from control_center.mcp import BaseClient, ModelTurnResult
T = TypeVar("T")


class BaseAdapter(Generic[T], ABC):
    """
    Bridge between MCP primitives and an LLM provider's tool format.

    Each adapter:
      - lists primitives from connected MCP servers and converts them into
        the provider's native tool/resource/prompt shape (`T`)
      - maintains a binding registry (`exposed_name -> BoundPrimitive`)
        so `invoke()` can dispatch a model-issued tool call back to the
        right MCP server + source_id
      - sanitizes JSON Schemas for provider quirks (`normalize_schema`)
      - drives the provider's model-generation endpoint via `generate()`
        to produce one model turn (text + requested tool calls). Endpoint
        differs per provider:
            Anthropic : client.messages.create(...)         (Messages API)
            OpenAI    : client.responses.create(...)        (Responses API)
            Google    : client.models.generate_content(...) (Gemini API)
      - normalizes raw MCP protocol object payloads—`CallToolResult`, `ReadResourceResult`,
        and `GetPromptResult`—into plain text via `parse_result()`.

    Sits above `BaseClient` (the transport boundary) and below the agent loop.
    It depends only on the stable `BaseClient` interface, not connector/session
    internals, and handles the shape mismatch between MCP primitives and the
    LLM provider it targets.

    ──────────────────────────────────────────────────────────────────────
    Building a new provider adapter
    ──────────────────────────────────────────────────────────────────────

    Override surface
    ────────────────

    Required (enforced by `@abstractmethod` — instantiation fails until all four are overridden):
      - `_convert_tool` / `_convert_resource` / `_convert_prompt`
                `(mcp_obj, client, server_name) -> T | None`
            Convert the MCP primitive into the provider's native shape AND
            register the binding via `self._register_binding(...)`. Return
            `None` to skip. Per-kind: prompts synthesize an input schema from
            `mcp_prompt.arguments` if the provider expects one; resources
            have no arguments and are usually exposed as a no-arg "read" tool.
      - `generate(*, model, inputs, tools, ...) -> ModelTurnResult`
            Drive one model turn against the provider's API.

    Override only for known provider quirks:
      - `normalize_schema(schema)`
            extra JSON Schema dialect rewrites beyond the defaults
            (e.g. strip `default` for OpenAI strict mode, drop `format: "uri"` for Gemini).
      - `parse_result(result)`
            Override only if the provider returns a non-MCP-shaped result.
            Default handles raw `CallToolResult` / `ReadResourceResult` / `GetPromptResult`.

    Convention (most adapters implement their own; not in base):
      - `_make_exposed_name(server_name, raw_name) -> str`
            Sanitize + prefix to satisfy the provider's tool-name regex.

    Configure-don't-override:
      - `disallowed_tools=[...]`: `_convert_tool` returns `None` for matches.
      - `unsupported_schema_keys={...}`: keys stripped by `sanitize_schema`.

    Verify before writing code
    ──────────────────────────

    The provider's official API and SDK documentation is the source of
    truth for every shape this adapter produces or consumes. Verify
    BEFORE writing code, not after a runtime failure:

      - exact request payload (messages vs. input, role names, tool
        format, tool_choice values, content-block types)
      - exact response payload (text fragments, tool-call objects, id
        fields, stop reasons, usage/cost metadata, streaming chunks)
      - JSON Schema dialect and restrictions (some providers reject
        `additionalProperties: false`, `type: [a, b]` arrays, certain
        `format` keywords; encode workarounds in `normalize_schema`
        and `unsupported_schema_keys`)
      - tool-call id semantics — does the provider supply stable ids,
        and must the next tool-result message echo that same id back?
      - limits: max tools per request, max name length, name regex,
        parameter cap, context window

    ──────────────────────────────────────────────────────────────────────
    Citations
    ──────────────────────────────────────────────────────────────────────

    Every overridden method MUST carry these in its docstring:

        Spec:     URL of the provider's API REFERENCE page — the exact
                  request/response schema that defines this method's
                  contract. The reference page is the source of truth;
                  if the overview and the schema page disagree, the
                  schema page wins.

        ToolSpec: URL of the provider's tool / function-call schema
                  page. Required only when the provider exposes a
                  structured tool format (Anthropic tool_use blocks,
                  OpenAI function tools, Gemini FunctionDeclaration).
                  Cite alongside Spec.

        Verified: ISO date the citation was last validated, plus the
                  exact Python SDK version tested against — e.g.
                  `2026-05-07, openai==2.4.0`. Bump both fields together;
                  a date without a version is ambiguous, a version
                  without a date doesn't tell you whether the docs have
                  moved underneath you.

    And SHOULD carry (strongly recommended):

        Doc:      URL of the provider's API OVERVIEW or "build with X"
                  page — the prose explanation of how the schema is
                  used in practice. The reference page tells you the
                  *shape*; the overview page tells you the *intent*.
                  Cite both whenever an overview exists, plus any additional
                  pages (e.g. "Handle tool calls") that clarify the contract.

    Citations required on every overridden method:
      - `_convert_tool`      → provider's tool-definition schema page
      - `_convert_resource`  → provider's resource / attachment schema,
                                OR a one-line rationale if the method
                                returns `None`
      - `_convert_prompt`    → provider's prompt schema, OR a one-line
                                rationale if the provider has no
                                structured prompt concept and the
                                method returns `None`
      - `generate`           → provider's model-generation endpoint page
                                (REQUIRED — Spec + ToolSpec + Verified)
      - `normalize_schema`         → recommended-only; required if overridden,
                                cite the page enumerating JSON Schema
                                dialect quirks for this provider

    Example
    ───────

        async def generate(self, ...) -> ModelTurnResult:
            \"\"\"Drive one model turn via Anthropic's Messages API.

            Spec:     https://platform.claude.com/docs/en/api/messages/create
            ToolSpec: https://platform.claude.com/docs/en/docs/build-with-claude/tool-use
            Doc:      https://platform.claude.com/docs/en/docs/build-with-claude/working-with-messages
            Verified: 2026-05-07, anthropic==0.40.0
            \"\"\"

    When upgrading the SDK or targeting a new model, re-read EVERY cited
    page and bump BOTH the adapter implementation AND the Verified line
    before shipping. A stale Verified line on changed code is a review block.

    Reference URLs (verified 2026-05-07)
    ─────────────────────────────────────
      Anthropic Messages API (reference):
        https://platform.claude.com/docs/en/api/messages/create
      Anthropic Messages API (overview):
        https://platform.claude.com/docs/en/docs/build-with-claude/working-with-messages
      Anthropic tool use:
        https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
        https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls

      OpenAI Responses API (the standard and ONLY supported OpenAI endpoint for any adapter work) (reference):
        https://developers.openai.com/api/reference/resources/responses/methods/create
      OpenAI Responses API (overview / migration):
        https://developers.openai.com/api/docs/guides/migrate-to-responses
      OpenAI tool / function calling:
        https://developers.openai.com/api/docs/guides/function-calling
        https://developers.openai.com/api/docs/guides/tools

      Google Gemini generate_content (reference):
        https://ai.google.dev/api/generate-content
      Google Gemini generate_content (overview):
        https://ai.google.dev/gemini-api/docs/text-generation
      Google Gemini function calling:
        https://ai.google.dev/gemini-api/docs/function-calling
    """

    framework: str = "unknown"  # Provider/framework identifier, e.g. 'openai', 'anthropic', or 'google'.

    def __init__(
        self,
        disallowed_tools: Iterable[str] | None = None,
        unsupported_schema_keys: Iterable[str] | None = None,
    ) -> None:
        self.disallowed_tools = _to_string_set(disallowed_tools)
        self.unsupported_schema_keys = _to_string_set(unsupported_schema_keys)

        self._server_tool_cache: dict[str, list[T]] = {}
        self._server_resource_cache: dict[str, list[T]] = {}
        self._server_prompt_cache: dict[str, list[T]] = {}

        self._bindings: dict[str, BoundPrimitive] = {}

        self._tools: list[T] = []
        self._resources: list[T] = []
        self._prompts: list[T] = []

    @property
    def all_capabilities(self) -> list[T]:
        return [*self._tools, *self._resources, *self._prompts]

    @property
    def tools(self) -> list[T]:
        return list(self._tools)

    @property
    def resources(self) -> list[T]:
        return list(self._resources)

    @property
    def prompts(self) -> list[T]:
        return list(self._prompts)

    # ── Primitive Discovery & Caching ────────────────────────────────────────────

    async def create_all(self, client: BaseClient) -> None:
        await self.create_tools(client)

        try:
            await self.create_resources(client)
        except Exception:
            self._resources = []

        try:
            await self.create_prompts(client)
        except Exception:
            self._prompts = []

    async def create_tools(self, client: BaseClient) -> list[T]:
        tools: list[T] = []
        for server_name in client.connected_servers:
            tools.extend(await self.load_tools_for_server(client, server_name))
        self._tools = tools
        return self._tools

    async def create_resources(self, client: BaseClient) -> list[T]:
        resources: list[T] = []
        for server_name in client.connected_servers:
            resources.extend(await self.load_resources_for_server(client, server_name))
        self._resources = resources
        return self._resources

    async def create_prompts(self, client: BaseClient) -> list[T]:
        prompts: list[T] = []
        for server_name in client.connected_servers:
            prompts.extend(await self.load_prompts_for_server(client, server_name))
        self._prompts = prompts
        return self._prompts

    async def load_tools_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_tool_cache:
            return list(self._server_tool_cache[server_name])

        try:
            converted: list[T] = []
            for tool in await client.list_tools(server_name) or []:
                item = self._convert_tool(tool, client, server_name)
                if item is not None:
                    converted.append(item)

            self._server_tool_cache[server_name] = converted
            return list(converted)
        except Exception:
            self._remove_bindings_for_server(server_name, kind="tool")
            raise

    async def load_resources_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_resource_cache:
            return list(self._server_resource_cache[server_name])

        try:
            converted: list[T] = []
            for resource in await client.list_resources(server_name) or []:
                item = self._convert_resource(resource, client, server_name)
                if item is not None:
                    converted.append(item)

            self._server_resource_cache[server_name] = converted
            return list(converted)
        except Exception:
            self._remove_bindings_for_server(server_name, kind="resource")
            raise

    async def load_prompts_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_prompt_cache:
            return list(self._server_prompt_cache[server_name])

        try:
            converted: list[T] = []
            for prompt in await client.list_prompts(server_name) or []:
                item = self._convert_prompt(prompt, client, server_name)
                if item is not None:
                    converted.append(item)

                self._server_prompt_cache[server_name] = converted
                return list(converted)
        except Exception:
            self._remove_bindings_for_server(server_name, kind="prompt")
            raise

    def _remove_bindings_for_server(self, server_name: str, kind: str | None = None) -> None:
        self._bindings = {
            name: binding
            for name, binding in self._bindings.items()
            if not (
                    binding.server_name == server_name
                    and (kind is None or binding.kind == kind)
            )
        }

    # ── Binding Registry ─────────────────────────────────────────────────────────

    def _register_binding(self, binding: BoundPrimitive) -> None:
        if binding.exposed_name in self._bindings:
            existing = self._bindings[binding.exposed_name]
            raise ValueError(
                f"Duplicate exposed primitive name: {binding.exposed_name!r}. "
                f"Existing: {existing.kind} {existing.server_name}/{existing.source_id}; "
                f"New: {binding.kind} {binding.server_name}/{binding.source_id}"
            )
        self._bindings[binding.exposed_name] = binding

    def get_binding(self, exposed_name: str) -> BoundPrimitive:
        try:
            return self._bindings[exposed_name]
        except KeyError as exc:
            raise KeyError(f"No bound primitive found for '{exposed_name}'.") from exc

    # ── Result & Schema Helpers ──────────────────────────────────────────────────

    def parse_result(self, result: Any) -> str:
        """
        Convert raw MCP operation results into model-readable text.

        Preserves text content directly & represents non-text payloads with descriptive placeholders.
        """
        if hasattr(result, "messages"):  # GetPromptResult
            parts: list[str] = []

            for message in result.messages:
                role = getattr(message, "role", None)
                content = getattr(message, "content", None)
                text = getattr(content, "text", None)

                if text is not None:
                    parts.append(f"{role}: {text}" if role else text)
                else:
                    parts.append(str(message))

            return "\n".join(parts)

        if hasattr(result, "contents"):  # ReadResourceResult
            parts: list[str] = []

            for item in result.contents:
                if isinstance(item, bytes):
                    parts.append(item.decode(errors="replace"))
                    continue

                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(text)
                    continue

                blob = getattr(item, "blob", None)
                mime = getattr(item, "mimeType", "")
                uri = getattr(item, "uri", None)

                if isinstance(blob, bytes):
                    parts.append(blob.decode(errors="replace"))
                elif blob is not None:
                    parts.append(f"[blob: {mime}]" if mime else "[blob]")
                elif uri is not None:
                    parts.append(f"[resource: {uri}]")
                else:
                    parts.append(str(item))

            return "\n".join(parts)

        if hasattr(result, "content") and isinstance(result.content, list):  # CallToolResult
            parts: list[str] = []

            for item in result.content:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(text)
                    continue

                mime = getattr(item, "mimeType", "")
                kind = getattr(item, "type", "binary")
                uri = getattr(item, "uri", None)
                name = getattr(item, "name", None)

                if uri is not None:
                    parts.append(f"[{kind}: {name or uri}]")
                else:
                    parts.append(f"[{kind}: {mime}]" if mime else f"[{kind}]")

            result_text = "\n".join(parts)
            if getattr(result, "isError", False):
                return f"Error: {result_text or 'tool returned an error'}"
            return result_text

        return str(result)

    def normalize_schema(self, schema: Any) -> Any:
        """Normalize schemas for LLM vendors that dislike union-style 'type' arrays."""
        if isinstance(schema, dict):
            schema = dict(schema)

            if "type" in schema and isinstance(schema["type"], list):
                schema["anyOf"] = [{"type": t} for t in schema["type"]]
                del schema["type"]

            if "enum" in schema and "type" not in schema:
                values = schema["enum"]
                if values and all(isinstance(v, str) for v in values):
                    schema["type"] = "string"
                elif values and all(isinstance(v, bool) for v in values):
                    schema["type"] = "boolean"
                elif values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
                    schema["type"] = "integer"
                elif values and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                    schema["type"] = "number"

            for key, value in list(schema.items()):
                schema[key] = self.normalize_schema(value)
            return schema

        if isinstance(schema, list):
            return [self.normalize_schema(item) for item in schema]

        return schema

    def sanitize_schema(self, schema: Any) -> Any:
        """
        Strip schema keys that are valid JSON Schema but unsupported by provider SDKs.

        PLEASE NOTE: This does not resolve `$ref`/`$defs`. If those keys are
        stripped before de-referencing, the resulting schema may be weakened.
        """
        if isinstance(schema, dict):
            return {
                key: self.sanitize_schema(value)
                for key, value in schema.items()
                if key not in self.unsupported_schema_keys
            }

        if isinstance(schema, list):
            return [self.sanitize_schema(item) for item in schema]

        return schema

    # ── Cache & Refresh ──────────────────────────────────────────────────────────

    def clear_cache(self) -> None:
        self._server_tool_cache.clear()
        self._server_resource_cache.clear()
        self._server_prompt_cache.clear()
        self._bindings.clear()
        self._tools = []
        self._resources = []
        self._prompts = []

    def clear_server_cache(self, server_name: str) -> None:
        self._server_tool_cache.pop(server_name, None)
        self._server_resource_cache.pop(server_name, None)
        self._server_prompt_cache.pop(server_name, None)

        self._bindings = {
            name: binding
            for name, binding in self._bindings.items()
            if binding.server_name != server_name
        }

        self._tools = [
            item for items in self._server_tool_cache.values() for item in items
        ]
        self._resources = [
            item for items in self._server_resource_cache.values() for item in items
        ]
        self._prompts = [
            item for items in self._server_prompt_cache.values() for item in items
        ]

    async def refresh_all(self, client: BaseClient) -> None:
        self.clear_cache()
        await self.create_all(client)

    async def refresh_server(self, client: BaseClient, server_name: str) -> None:
        self.clear_server_cache(server_name)

        try:
            tools = await self.load_tools_for_server(client, server_name)
            resources = await self.load_resources_for_server(client, server_name)
            prompts = await self.load_prompts_for_server(client, server_name)
        except Exception:
            self.clear_server_cache(server_name)
            raise

        self._tools.extend(tools)
        self._resources.extend(resources)
        self._prompts.extend(prompts)

    # ── Invocation & Generation ──────────────────────────────────────────────────

    async def invoke(self, client: BaseClient, exposed_name: str, arguments: dict[str, Any]) -> Any:
        binding = self.get_binding(exposed_name)
        if binding.kind == "tool":
            return await client.call_tool(binding.server_name, binding.source_id, arguments)
        if binding.kind == "resource":
            return await client.read_resource(binding.server_name, binding.source_id)
        if binding.kind == "prompt":
            return await client.get_prompt(binding.server_name, binding.source_id, arguments)
        raise ValueError(f"Unsupported primitive kind: {binding.kind}")

    @abstractmethod
    async def generate(
        self,
        *,
        model: str,
        messages: Any,
        tools: list[T] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_choice: Any | None = None,
        max_retries: int | None = None,
        output_config: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ModelTurnResult:
        """Drive one model turn. Translate canonical message history
        into the provider's request shape, call its model-generation
        endpoint, and parse the response into a `ModelTurnResult`."""
        ...

    # ── Provider-Specific Conversion Hooks ───────────────────────────────────────

    @abstractmethod
    def _convert_tool(self, mcp_tool: Tool, client: BaseClient, server_name: str) -> T | None:
        ...

    @abstractmethod
    def _convert_resource(self, mcp_resource: Resource, client: BaseClient, server_name: str) -> T | None:
        ...

    @abstractmethod
    def _convert_prompt(self, mcp_prompt: Prompt, client: BaseClient, server_name: str) -> T | None:
        ...


# --- Helpers ---
def _to_string_set(values: Iterable[str] | None) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        raise TypeError("Expected an iterable of strings, not a single string.")

    result = set(values)
    if not all(isinstance(value, str) for value in result):
        raise TypeError("Expected an iterable containing only strings.")
    return result
