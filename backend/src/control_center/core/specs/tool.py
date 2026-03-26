from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field, computed_field


class ToolAnnotations(BaseModel):
    """Canonical, framework-agnostic metadata describing a tool’s expected behavior and side effects."""

    title: str | None = None
    read_only_hint: bool | None = None
    destructive_hint: bool | None = None
    idempotent_hint: bool | None = None
    open_world_hint: bool | None = None


class ToolSpec(BaseModel):
    """
    Canonical internal representation of a tool definition.

    This model normalizes tool specifications from various sources (e.g., MCP servers, SDK-based implementations,
    and future compatible frameworks) into a stable internal format used for execution, validation, and governance.
    """

    # --- Identity ---
    name: str
    server: str
    version: str | int | None = None

    # --- Documentation ---
    description: str = ""

    # --- Interface Contracts ---
    raw_input_schema: dict[str, Any] = Field(default_factory=dict)
    normalized_input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None

    # --- Behavioral Semantics ---
    annotations: ToolAnnotations = Field(default_factory=ToolAnnotations)

    # --- Governance / Classification ---
    tags: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- Runtime Hints ---
    timeout_seconds: float | None = None
    enabled: bool | None = None

    # --- Provenance ---
    framework: str | None = None
    raw_definition: dict[str, Any] | None = None

    # --- Derived Identity ---
    @computed_field
    @property
    def qualified_name(self) -> str:
        return f"{self.server}.{self.name}"

    # --- Derived Documentation ---
    @property
    def title(self) -> str:
        return self.annotations.title or self.name

    # --- Derived Behavioral Semantics ---

    @property
    def is_read_only(self) -> bool | None:
        return self.annotations.read_only_hint

    @property
    def is_destructive(self) -> bool | None:
        return self.annotations.destructive_hint

    @property
    def is_idempotent(self) -> bool | None:
        return self.annotations.idempotent_hint

    @property
    def is_open_world(self) -> bool | None:
        return self.annotations.open_world_hint
