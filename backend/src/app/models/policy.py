from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluations"

    evaluation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    overall_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evaluated_at: Mapped[str] = mapped_column(String(64), nullable=False)


class PolicyCheckResult(Base):
    __tablename__ = "policy_check_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    evaluation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(1024), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actual_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
