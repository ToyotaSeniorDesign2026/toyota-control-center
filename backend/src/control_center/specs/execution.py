from __future__ import annotations

"""MCP execution specs — the two modes a run can take."""

from typing import Annotated, Union
from pydantic import BaseModel, Field


class DirectToolCall(BaseModel):
    """Call a single MCP tool directly — no LLM involved."""

    kind: str = "direct_tool"
    server_name: str
    tool_name: str
    arguments: dict = Field(default_factory=dict)


class AgentRun(BaseModel):
    """Run an LLM agent over one or more MCP servers."""

    kind: str = "agent"
    server_names: list[str] = Field(default_factory=list)
    prompt: str
    allow_auto_selection: bool = False
    selection_prompt: str | None = None


MCPRunSpec = Annotated[Union[DirectToolCall, AgentRun], Field(discriminator="kind")]
