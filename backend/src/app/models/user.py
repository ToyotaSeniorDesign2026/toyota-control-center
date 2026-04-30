from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    # Core identity
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False)

    # Profile customization
    avatar_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uploaded_image: Mapped[str | None] = mapped_column(Text(), nullable=True)
    selected_color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # User profile information (editable)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text(), nullable=True)

    # Organization & Team Information (managed by HR, not user-editable)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manager: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)

    # Security & Access
    mfa_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    approval_authority: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allowed_environments: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_last_changed: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    cli_token: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    # User preferences
    theme: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notifications: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
