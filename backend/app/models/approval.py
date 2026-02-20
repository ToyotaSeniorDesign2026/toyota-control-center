from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
