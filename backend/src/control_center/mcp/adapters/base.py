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
      - sanitizes JSON Schemas for provider quirks (`fix_schema`)
      - drives the provider's model-generation endpoint via `generate()`
        to produce one model turn (text + requested tool calls). Endpoint
        differs per provider:
            Anthropic : client.messages.create(...)         (Messages API)
            OpenAI    : client.responses.create(...)        (Responses API)
            Google    : client.models.generate_content(...) (Gemini API)
      - normalizes raw MCP protocol object payloads—`CallToolResult`, `ReadResourceResult`,
        and `GetPromptResult`—into plain text via `parse_result()`.

    Sits above `BaseClient` (transport) and below the agent loop. Knows
    nothing about transport, sessions, or orchestration — only about the
    shape mismatch between MCP and the LLM provider it targets.

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
      - `fix_schema(schema)`
            extra JSON Schema dialect rewrites beyond the defaults
            (e.g. strip `default` for OpenAI strict mode, drop `format: "uri"` for Gemini).
      - `parse_result(result)`
            Override only if the provider returns a non-MCP-shaped result.
            Default handles raw `CallToolResult` / `ReadResourceResult` / `GetPromptResult`.

    Convention (most adapters implement their own; not in base):
      - `_make_exposed_name(server_name, raw_name) -> str`
            Sanitize + prefix to satisfy the provider's tool-name regex.

    Configure-don't-override:
      - `disallowed_tools=[...]` —> `_convert_tool` returns `None` for matches.
      - `unsupported_schema_keys={...}` —> keys stripped by `sanitize_schema`.

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
        `format` keywords; encode workarounds in `fix_schema` and
        `unsupported_schema_keys`)
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
                  exact SDK version tested against — e.g.
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
      - `fix_schema`         → recommended-only; required if overridden,
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

        self.tools: list[T] = []
        self.resources: list[T] = []
        self.prompts: list[T] = []

    @property
    def all_capabilities(self) -> list[T]:
        return [*self.tools, *self.resources, *self.prompts]

    # ── Creation & Caching of MCP Primitives ─────────────────────────────────────

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
        if server_name in self._server_tool_cache:
            return list(self._server_tool_cache[server_name])

        converted: list[T] = []
        for tool in await client.list_tools(server_name):
            item = self._convert_tool(tool, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_tool_cache[server_name] = converted
        return list(converted)

    async def load_resources_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_resource_cache:
            return list(self._server_resource_cache[server_name])

        converted: list[T] = []
        for resource in await client.list_resources(server_name) or []:
            item = self._convert_resource(resource, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_resource_cache[server_name] = converted
        return list(converted)

    async def load_prompts_for_server(self, client: BaseClient, server_name: str) -> list[T]:
        if server_name in self._server_prompt_cache:
            return list(self._server_prompt_cache[server_name])

        converted: list[T] = []
        for prompt in await client.list_prompts(server_name) or []:
            item = self._convert_prompt(prompt, client, server_name)
            if item is not None:
                converted.append(item)

        self._server_prompt_cache[server_name] = converted
        return list(converted)

    # ── Binding Registry ─────────────────────────────────────────────────────────

    def _register_binding(self, binding: BoundPrimitive) -> None:
        if binding.exposed_name in self._bindings:
            raise ValueError(f"Duplicate exposed primitive name: {binding.exposed_name}")
        self._bindings[binding.exposed_name] = binding

    def get_binding(self, exposed_name: str) -> BoundPrimitive:
        try:
            return self._bindings[exposed_name]
        except KeyError as exc:
            raise KeyError(f"No bound primitive found for '{exposed_name}'.") from exc

    # ── Result & Schema Helpers ──────────────────────────────────────────────────

    def parse_result(self, result: Any) -> str:
        """Normalize MCP operation results into text."""
        if hasattr(result, "messages"):  # prompt result
            return "\n".join(str(m) for m in result.messages)

        if hasattr(result, "contents"):  # resource read result
            return "\n".join(
                c.decode() if isinstance(c, bytes) else str(c)
                for c in result.contents
            )

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

    def normalize_schema(self, schema: Any) -> Any:
        """Normalize schemas for LLM vendors that dislike union-style 'type' arrays."""
        if isinstance(schema, dict):
            schema = dict(schema)

            if "type" in schema and isinstance(schema["type"], list):
                schema["anyOf"] = [{"type": t} for t in schema["type"]]
                del schema["type"]

            if "enum" in schema and "type" not in schema:
                schema["type"] = "string"

            for key, value in list(schema.items()):
                schema[key] = self.normalize_schema(value)
            return schema

        if isinstance(schema, list):
            return [self.normalize_schema(item) for item in schema]

        return schema

    def sanitize_schema(self, schema: Any) -> Any:
        """Strip schema keys that are valid JSON Schema but unsupported by provider SDKs."""
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
        self.tools = []
        self.resources = []
        self.prompts = []

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
        """Drive one model turn. Translate canonical message history
        into the provider's request shape, call its model-generation
        endpoint, and parse the response into a `ModelTurnResult`."""
        ...

    # ── Subclass-required Provider Converters ────────────────────────────────────

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
    return set(values)
