from __future__ import annotations

from pydantic import BaseModel


class ApprovalOut(BaseModel):
    id: str
    run_id: str
    status: str
    requested_by: str
    reviewer_id: str | None = None
    risk_level: str
    comment: str | None = None
    created_at: str
    reviewed_at: str | None = None
