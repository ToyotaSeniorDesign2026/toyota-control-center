from __future__ import annotations

from pydantic import BaseModel, Field


class AuditEventOut(BaseModel):
    id: str
    actor_id: str | None = None
    action: str
    metadata: dict = Field(default_factory=dict)
    created_at: str
