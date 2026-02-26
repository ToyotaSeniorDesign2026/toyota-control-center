from __future__ import annotations

"""Pydantic schemas for run creation, run state views, logs, and event payloads."""

from pydantic import BaseModel, ConfigDict, Field


class RunCreateRequest(BaseModel):
    action: str = Field(default="run")
    target_environment: str = Field(default="dev")
    params: dict = Field(default_factory=dict)


class RunCreate(BaseModel):
    resource_id: str
    action: str = Field(default="run")
    target_environment: str = Field(default="dev")
    params: dict = Field(default_factory=dict)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    resource_id: str
    requested_by: str
    domain: str
    action: str
    target_environment: str
    status: str
    risk_level: str
    risk_score: int
    requires_approval: bool
    approval_id: str | None = None
    connector_run_id: str | None = None
    error: str | None = None
    promotion_status: str | None = None
    git_ref: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    workflow_run_id: str | None = None
    workflow_url: str | None = None
    created_at: str
    updated_at: str


class RunLogEntry(BaseModel):
    run_id: str
    timestamp: str
    level: str
    message: str
    metadata: dict = Field(default_factory=dict)


class RunLogsOut(BaseModel):
    run_id: str
    status: str
    logs: list[RunLogEntry]
    next_cursor: str | None = None


class RunStatusOut(BaseModel):
    run_id: str
    status: str
    risk_level: str
    requires_approval: bool
    updated_at: str


class RunListOut(BaseModel):
    items: list[RunOut]
    next_cursor: str | None = None


class RunEventOut(BaseModel):
    event: str
    data: dict = Field(default_factory=dict)
