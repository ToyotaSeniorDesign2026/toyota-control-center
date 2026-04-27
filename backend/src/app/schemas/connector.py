from __future__ import annotations

"""Pydantic schemas for Connector CRUD."""

from pydantic import BaseModel, ConfigDict, Field


class ConnectorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    connector_type: str = Field(min_length=1, max_length=80)
    environment: str = Field(default="dev")
    config: dict = Field(default_factory=dict)
    is_shared: bool = False


class ConnectorUpdate(BaseModel):
    name: str | None = None
    connector_type: str | None = None
    environment: str | None = None
    config: dict | None = None
    status: str | None = None
    is_shared: bool | None = None


class ConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    connector_type: str
    owner_id: str
    owner_domain: str
    environment: str
    status: str
    config: dict
    is_shared: bool
    created_at: str
    updated_at: str


class ConnectorListOut(BaseModel):
    items: list[ConnectorOut]
    total: int
    page: int
    page_size: int
    has_more: bool
