from __future__ import annotations

from pydantic import BaseModel, Field


class GithubActionsWebhookPayload(BaseModel):
    event: str = Field(default="workflow_update")
    status: str = Field(description="queued|in_progress|success|failed|cancelled")
    run_id: str | None = None
    resource_id: str | None = None
    workflow_run_id: str | None = None
    workflow_url: str | None = None
    conclusion: str | None = None
    git_ref: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None


class GithubWebhookAck(BaseModel):
    ok: bool = True
    matched_run_id: str | None = None
    message: str
