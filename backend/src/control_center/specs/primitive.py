from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias, Any, Literal, Mapping

PrimitiveKind: TypeAlias = Literal["tool", "prompt", "resource"]
JSONSchema: TypeAlias = dict[str, Any]
Annotations: TypeAlias = dict[str, Any]


@dataclass(frozen=True, slots=True)
class BoundPrimitive:
    """A binding between an LLM-facing function name and the underlying MCP primitive."""

    # --- Identity (always present; all required at construction) ---
    exposed_name: str  # Name shown to the LLM (adapter-constructed, sanitized, unique across all bindings)
    server_name: str  # MCP server that owns this primitive
    source_id: str  # MCP-side identifier: Tool.name, Prompt.name, or Resource.uri
    kind: PrimitiveKind

    # --- Metadata (optional; populated when the server provides it) ---
    title: str | None = None  # Human-readable label. Falls back through Tool.title -> Tool.annotations.title -> source_id
    description: str | None = None  # Server-supplied description string
    input_schema: JSONSchema | None = None  # For tools: Tool.inputSchema | For prompts: synthesized PromptArgument list
    output_schema: JSONSchema | None = None  # Tool result schema published by server (rare): Tool.outputSchema
    annotations: Annotations = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)

    # --- User Interface ---
    @property
    def display_title(self) -> str:
        """UI label. Prefers Tool.title, then ToolAnnotations.title, then source_id."""
        return self.title or self.annotations.get("title") or self.source_id

    # --- Annotated Behavior Hints ---
    @property
    def is_read_only(self) -> bool | None:
        return self.annotations.get("readOnlyHint")

    @property
    def is_destructive(self) -> bool | None:
        return self.annotations.get("destructiveHint")

    @property
    def is_idempotent(self) -> bool | None:
        return self.annotations.get("idempotentHint")

    @property
    def is_open_world(self) -> bool | None:
        return self.annotations.get("openWorldHint")

    # --- Primitive Factories ---

    @classmethod
    def from_mcp_tool(cls, tool: Any, *, exposed_name: str, server_name: str) -> "BoundPrimitive":
        """Build from an `mcp.types.Tool`."""
        return cls(
            exposed_name=exposed_name,
            server_name=server_name,
            source_id=tool.name,
            kind="tool",
            title=getattr(tool, "title", None),
            description=getattr(tool, "description", None),
            input_schema=getattr(tool, "inputSchema", None),
            output_schema=getattr(tool, "outputSchema", None),
            annotations=_dump_annotations(getattr(tool, "annotations", None)),
            meta=getattr(tool, "meta", None) or {},
        )

    @classmethod
    def from_mcp_prompt(cls, prompt: Any, *, exposed_name: str, server_name: str) -> "BoundPrimitive":
        """Build from an `mcp.types.Prompt`"""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for arg in getattr(prompt, "arguments", None) or []:
            properties[arg.name] = {
                "type": "string",
                "description": getattr(arg, "description", None) or "",
            }
            if getattr(arg, "required", False):
                required.append(arg.name)
        # Synthesizes a JSON Schema from the prompt's argument (not currently in the MCP spec, but a common practice)
        synthesized_schema = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        return cls(
            exposed_name=exposed_name,
            server_name=server_name,
            source_id=prompt.name,
            kind="prompt",
            title=getattr(prompt, "title", None),
            description=getattr(prompt, "description", None),
            input_schema=synthesized_schema,
            meta=getattr(prompt, "meta", None) or {},
        )

    @classmethod
    def from_mcp_resource(cls, resource: Any, *, exposed_name: str, server_name: str) -> "BoundPrimitive":
        """Build from an `mcp.types.Resource`. Uses `uri` as source_id and defaults read-only/non-destructive since resources are read-by-URI."""
        ann: dict[str, Any] = {"readOnlyHint": True, "destructiveHint": False}
        mime = getattr(resource, "mimeType", None)
        if mime:
            ann["mimeType"] = mime
        size = getattr(resource, "size", None)
        if size is not None:
            ann["size"] = size
        return cls(
            exposed_name=exposed_name,
            server_name=server_name,
            source_id=str(getattr(resource, "uri", resource.name)),
            kind="resource",
            title=getattr(resource, "title", None),
            description=getattr(resource, "description", None),
            annotations=ann,
            meta=getattr(resource, "meta", None) or {},
        )


# --- Helpers ---
def _dump_annotations(annotation_data: Any) -> Annotations:
    """Convert a pydantic ToolAnnotations to a plain dict, dropping unset fields."""
    if annotation_data is None:
        return {}
    dump = getattr(annotation_data, "model_dump", None)
    if not callable(dump):
        return {}
    try:
        return dict(dump(exclude_none=True))
    except TypeError:
        return dict(dump())


__all__ = [
    "BoundPrimitive",
    "PrimitiveKind",
    "JSONSchema",
]
