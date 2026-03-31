from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_environment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_score: Mapped[int] = mapped_column(nullable=False, default=0)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connector_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    promotion_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    git_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_number: Mapped[int | None] = mapped_column(nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    trigger_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    execution_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    submitted_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resolved_job_spec_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class RunExecutionStatus(Base):
    __tablename__ = "run_execution_status"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    last_log_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    log_count: Mapped[int] = mapped_column(nullable=False, default=0)
