from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityKind = Literal["tool", "prompt", "resource"]


@dataclass(frozen=True)
class BoundCapability:
    """
    A binding between a framework-exposed function name and the underlying MCP target.
    """

    framework_name: str
    server_name: str
    remote_name: str  # tool name, prompt name, or resource URI
    kind: CapabilityKind
    description: str | None = None
