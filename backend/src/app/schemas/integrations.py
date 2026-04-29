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


class OpenAIChatMessage(BaseModel):
    role: str = Field(description="user|assistant|system")
    content: str


class OpenAIChatRequest(BaseModel):
    messages: list[OpenAIChatMessage] = Field(default_factory=list)
    goal: str | None = None
    workflow_state: dict = Field(default_factory=dict)
    fallback_response: str | None = None


class OpenAIChatResponse(BaseModel):
    content: str
    model: str
    response_id: str | None = None


class MCPServerSummary(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    allowed_environments: list[str] = Field(default_factory=list)
    active: bool = True


class MCPServerListResponse(BaseModel):
    items: list[MCPServerSummary] = Field(default_factory=list)


class MCPConnectionBundleSummary(BaseModel):
    id: str
    title: str
    summary: str
    primary_server: str
    server_names: list[str] = Field(default_factory=list)
    companion_servers: list[str] = Field(default_factory=list)
    manual_connection_supported: bool = True
    chat_connection_supported: bool = True
    resource_type: str
    required_config_fields: list[str] = Field(default_factory=list)
    optional_config_fields: list[str] = Field(default_factory=list)
    recommended_use_cases: list[str] = Field(default_factory=list)


class MCPConnectionBundleListResponse(BaseModel):
    items: list[MCPConnectionBundleSummary] = Field(default_factory=list)
