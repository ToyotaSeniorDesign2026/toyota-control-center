from __future__ import annotations

# Standard Library
import warnings
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Final, Generic, Self, TypeVar

# Third-Party
import pydantic_core
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

if TYPE_CHECKING:
    from mcp.types import AudioContent, CallToolResult, ContentBlock, EmbeddedResource, ImageContent, TextContent
else:
    try:  # pragma: no cover
        from mcp.types import (
            AudioContent,
            CallToolResult,
            ContentBlock,
            EmbeddedResource,
            ImageContent,
            TextContent,
        )
    except Exception:  # pragma: no cover
        class ContentBlock(BaseModel):
            type: str

        class TextContent(ContentBlock):
            text: str

        class ImageContent(ContentBlock):
            pass

        class AudioContent(ContentBlock):
            pass

        class EmbeddedResource(ContentBlock):
            pass

        class CallToolResult(BaseModel):
            content: list[ContentBlock] = Field(default_factory=list)
            structuredContent: dict[str, Any] | None = None
            isError: bool = False

__all__ = ["ExecutionError", "ExecutionResult", "MCPToolResult"]

T = TypeVar("T")
U = TypeVar("U")


# ── Serialization Helpers ─────────────────────────────────────────────────────

def default_serializer(value: Any) -> str:
    """Serialize arbitrary Python data into a JSON string. Falls back to `str(...)` for non-serializable values."""
    return pydantic_core.to_json(value, fallback=str).decode()


def to_jsonable(value: Any) -> Any:
    """Convert arbitrary Python values into JSON-safe Python primitives."""
    return pydantic_core.to_jsonable_python(value=value)


# ── ExecutionError ────────────────────────────────────────────────────────────

class ExecutionError(BaseModel):
    """Structured error payload for deterministic execution flows."""
    model_config = ConfigDict(extra="forbid")
    code: str = Field(description="Machine-readable snake_case error code.")
    message: str = Field(description="Human-readable explanation of the failure.")
    meta: dict[str, Any] = Field(default_factory=dict, description="Optional error-specific diagnostics or metadata.")


# ── ExecutionResult (Generic, MCP-agnostic) ───────────────────────────────────

# _MISSING Sentinel — signals that a _clone() argument was not supplied by the caller.
_MISSING: Final[object] = object()


class ExecutionResult(BaseModel, Generic[T]):
    """Deterministic execution result. Success is defined by the absence of `error`; `data` may be present or None"""
    model_config = ConfigDict(extra="forbid")
    data: T | None = Field(default=None, description="Primary machine-readable result.")
    error: ExecutionError | None = Field(default=None, description="Structured error for failed execution.")
    meta: dict[str, Any] = Field(default_factory=dict, description="Optional runtime, tracing, or provenance metadata.")

    # --- Core Predicates ---

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return self.error is not None

    # --- Validation ---

    @model_validator(mode="after")
    def _validate_result(self) -> Self:
        """Enforce that failure results can not include `data`."""
        if self.is_failure and self.data is not None:
            raise ValueError("Failure result cannot include `data`.")
        return self

    # --- Internal Clone Hook ---

    def _clone(self, *, data: Any = _MISSING, error: Any = _MISSING, meta: Any = _MISSING) -> Self:
        """
        Return a new instance of the *concrete* subclass (`Self`) with selected
        fields replaced.  Using `type(self)(...)` preserves the subclass so
        that `map`, `bind`, and `map_error` never silently demote callers.
        """
        return type(self)(
            data=self.data if data is _MISSING else data,
            error=self.error if error is _MISSING else error,
            meta=self.meta.copy() if meta is _MISSING else meta,
        )

    # --- Factory Methods ---

    @classmethod
    def success(cls, data: T | None = None, *, meta: dict[str, Any] | None = None) -> Self:
        """Create a successful result."""
        return cls(data=data, error=None, meta=meta or {})

    @classmethod
    def failure(cls, code: str, message: str, *,
                error_meta: dict[str, Any] | None = None,
                meta: dict[str, Any] | None = None) -> Self:
        """Create a failure result with a structured error."""
        return cls(data=None, error=ExecutionError(code=code, message=message, meta=error_meta or {}), meta=meta or {})

    # --- Accessors ---

    def unwrap(self) -> T | None:
        """Return `data` on success, raise `RuntimeError` on failure."""
        if self.is_failure:
            if self.error is None:
                raise RuntimeError("Invariant violated: `is_failure` is True but `error` is None.")
            raise RuntimeError(f"Unwrap failed: {self.error.code} - {self.error.message}")
        return self.data

    def unwrap_error(self) -> ExecutionError:
        """Return the error on failure, raise `RuntimeError` on success."""
        if self.is_success:
            raise RuntimeError(f"Called unwrap_error() on a success result. Data present: {self.data}")
        if self.error is None:
            raise RuntimeError("Invariant violated: `is_failure` is True but `error` is None.")
        return self.error

    # --- Functional Transforms ---

    def map(self, fn: Callable[[T | None], U]) -> Self:
        """Transform success `data`, propagate errors as-is."""
        if self.is_failure:
            return self._clone(data=None)
        return self._clone(data=fn(self.data), error=None)

    def map_error(self, fn: Callable[[ExecutionError], ExecutionError]) -> Self:
        """Transform the `error` payload, propagate success as-is."""
        if self.is_success:
            return self._clone()
        if self.error is None:
            raise RuntimeError("Invariant violated: `is_failure` is True but `error` is None.")
        return self._clone(error=fn(self.error))

    def bind(self, fn: Callable[[T], ExecutionResult[U]]) -> Self:
        """
        Chain another result-returning operation (FlatMap / monadic bind).
        Meta from both results is merged; the chained result's type is preserved via `_clone`.
        """
        if self.is_failure:
            return self._clone(data=None)
        inner = fn(self.data)  # type: ignore[arg-type]
        merged_meta = {**self.meta, **inner.meta}
        return self._clone(data=inner.data, error=inner.error, meta=merged_meta)


# ── MCPToolResult (MCP Protocol Adapter) ──────────────────────────────────────

class MCPToolResult(ExecutionResult[T]):
    """
    MCP-specific tool result wrapper.
    - Translates between the internal `ExecutionResult` model and the MCP wire format (`types.CallToolResult`).

    Principles:
    - Generic payload lives in `data`.
    - Failure is explicit in `error`.
    - Runtime / tracing / provenance details live in `meta`.
    - `is_error` is derived from `is_failure` — no two-source-of-truth risk.
    - `content` or `structured_content` give the LLM everything it needs.
    """

    model_config = ConfigDict(extra="forbid")

    # --- [MCP ALIGNMENT] ---
    #  -- MCP Fields --

    @computed_field(alias="isError")  # type: ignore[prop-decorator]
    @property
    def is_error(self) -> bool:
        """Standard MCP `isError` flag, derived from internal error state."""
        return self.is_failure

    structured_content: dict[str, Any] | None = Field(
        default=None,
        alias="structuredContent",
        description=(
            "Machine-readable structured output, parallel to `content`. "
            "Only populated when the tool has a declared output schema."
        ),
    )

    @cached_property
    def content(self) -> list[ContentBlock]:
        """
        Converts internal data into MCP `ContentBlock`s, following FastMCP behavior.
        Preserves rich content (text, image, audio, linked/embedded resources); aggregates raw data into one text block.
        """

        if self.is_failure:
            if self.error is None:
                raise RuntimeError("Invariant violated: is_failure is True but error is None.")
            parts = [f"Error [{self.error.code}]: {self.error.message}"]
            if self.error.meta:
                parts.append(f"Details: {default_serializer(self.error.meta)}")
            return [TextContent(type="text", text="\n".join(parts))]

        # Explicit sentinel rather than [] — some MCP clients treat an empty content list as a failure or no-op
        if self.data is None:
            return [TextContent(type="text", text="(no content)")]

        # Single non-sequence item
        if not isinstance(self.data, (list, tuple)):
            return [self._convert_item(self.data)]

        # All items are already ContentBlocks
        if all(isinstance(item, ContentBlock) for item in self.data):
            return list(self.data)

        # Mixed / rich sequence — convert each item individually
        rich_types = (ContentBlock, ImageContent, AudioContent, EmbeddedResource)
        if any(isinstance(item, rich_types) or hasattr(item, "to_image_content") for item in self.data):
            return [
                item if isinstance(item, ContentBlock) else self._convert_item(item) for item in self.data
            ]

        # Raw data aggregation — serialize the whole list into a single TextContent block
        return [TextContent(type="text", text=self._serialize_with_fallback(self.data))]

    #  -- MCP Round-Trip Format Conversion --

    def to_call_tool_result(self) -> CallToolResult:
        """Emit a spec-compliant `CallToolResult` for MCP wire transmission."""
        kwargs: dict[str, Any] = {}
        if self.meta is not None and self.meta:
            kwargs["_meta"] = self.meta  # type: ignore[arg-type]
        return CallToolResult(
            content=self.content,
            structuredContent=self.structured_content,
            isError=self.is_error,
            **kwargs,
        )

    @classmethod
    def from_call_tool_result(cls, result: CallToolResult) -> MCPToolResult[list[ContentBlock]]:
        """
        Reconstruct an `MCPToolResult` from a raw `CallToolResult` received from a remote MCP server.
        `structuredContent` is preserved so that a round-trip through to and from `call_tool_result` is lossless.
        """
        if result.isError:
            text = next((block.text for block in result.content if isinstance(block, TextContent)), "Unknown MCP error")
            return cls.failure(code="mcp_error", message=text)
        return cls.success(data=list(result.content), structured_content=result.structuredContent)

    # --- Factory Overrides ---

    @classmethod
    def success(cls, data: T | None = None, *, structured_content: dict[str, Any] | None = None,
                meta: dict[str, Any] | None = None) -> Self:
        """Create a successful result, optionally with `structured_content` for tools with defined output schemas."""
        return cls(data=data, error=None, structured_content=structured_content, meta=meta or {})

    @classmethod
    def failure(cls, code: str, message: str, *, error_meta: dict[str, Any] | None = None,
                meta: dict[str, Any] | None = None) -> Self:
        """Create a failure result with a structured error."""
        return cls(
            data=None,
            error=ExecutionError(code=code, message=message, meta=error_meta or {}),
            structured_content=None,
            meta=meta or {},
        )

    # --- Specialized Factories ---

    @classmethod
    def from_model[ModelT: BaseModel](cls, model: ModelT, *, meta: dict[str, Any] | None = None) -> Self:
        return cls(data=model, structured_content=model.model_dump(mode="json"), meta=meta or {})

    # --- Item Conversion ---

    def serialize(self, serializer: Callable[[Any], str] | None = None) -> str:
        """High-performance JSON serialization with a safety-first fallback."""
        target = self.error if self.is_failure else self.data
        if serializer is not None:
            try:
                return serializer(target)
            except Exception as e:
                warnings.warn(f"Error serializing tool result: {e}")

        return default_serializer(target)

    # --- Serialization ---

    @staticmethod
    def _convert_item(item: Any) -> ContentBlock:
        """Converts an arbitrary item into an MCP `ContentBlock`, following FastMCP behavior."""
        # Item is already a ContentBlock
        if isinstance(item, ContentBlock):
            return item

        # If available, use item's specialized conversion method (polymorphic content types).
        if hasattr(item, "to_image_content"):
            return item.to_image_content()
        if hasattr(item, "to_audio_content"):
            return item.to_audio_content()
        if hasattr(item, "to_resource_content"):
            return item.to_resource_content()

        # Item is standard text content
        if isinstance(item, str):
            return TextContent(type="text", text=item)

        # Fallback Case: Serialize complex objects to JSON, with a safety-first fallback to string conversion
        # TODO: See if this code introduces any security risks, especially if `item` can be influenced externally.
        try:
            if hasattr(item, "model_dump_json"):
                return TextContent(type="text", text=item.model_dump_json(indent=2))
            else:
                return TextContent(type="text", text=default_serializer(item))
        except Exception as e:
            warnings.warn(f"Error serializing tool result while converting item: {e}")
            return TextContent(type="text", text=str(item))
