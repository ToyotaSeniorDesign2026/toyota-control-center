from __future__ import annotations

"""Pydantic schemas for run creation, run state views, logs, and event payloads."""

from pydantic import BaseModel, ConfigDict, Field


class RunCreateRequest(BaseModel):
    action: str = Field(default="run")
    target_environment: str = Field(default="dev")
    params: dict = Field(default_factory=dict)
    prompt: str | None = None


class RunCreate(BaseModel):
    job_id: str
    action: str = Field(default="run")
    target_environment: str = Field(default="dev")
    params: dict = Field(default_factory=dict)
    prompt: str | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
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
    trigger_source: str | None = None
    execution_backend: str | None = None
    execution_mode: str | None = None
    submitted_config_json: dict | None = None
    resolved_job_spec_json: dict | None = None
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


class RunLogsPurgeOut(BaseModel):
    run_id: str
    deleted_logs: int
