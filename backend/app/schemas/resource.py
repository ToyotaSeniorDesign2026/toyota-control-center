from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["runtime", "artifact"] = "runtime"
    type: str = Field(min_length=1, max_length=80)
    connector: str = Field(min_length=1, max_length=80)
    environment: str = Field(default="dev")
    config: dict = Field(default_factory=dict)
    data_sensitivity: str = Field(default="low")
    tags: list[str] = Field(default_factory=list)


class ResourceUpdate(BaseModel):
    name: str | None = None
    kind: Literal["runtime", "artifact"] | None = None
    type: str | None = None
    connector: str | None = None
    environment: str | None = None
    config: dict | None = None
    status: str | None = None
    data_sensitivity: str | None = None
    tags: list[str] | None = None


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kind: Literal["runtime", "artifact"]
    type: str
    connector: str
    owner_id: str
    owner_domain: str
    environment: str
    status: str
    data_sensitivity: str
    config: dict
    tags: list[str] = Field(default_factory=list)
    risk_score: int | None = None
    risk_level: str | None = None
    owner_name: str | None = None
    last_run_at: str | None = None
    last_run_status: str | None = None
    created_at: str
    updated_at: str


class ResourceListOut(BaseModel):
    items: list[ResourceOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class ImportGithubRequest(BaseModel):
    repo: str = Field(min_length=1)
    path: str | None = None
    ref: str | None = "main"
    resource_type: str = "sql"


class ImportGithubResponse(BaseModel):
    imported_count: int
    resources: list[ResourceOut]
