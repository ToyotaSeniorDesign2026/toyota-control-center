"""add user settings fields for account preferences and profile customization

Revision ID: 20260429_000005
Revises: 20260328_000004
Create Date: 2026-04-29 00:00:05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260429_000005"
down_revision = "20260328_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Profile customization
    if not any(column["name"] == "first_name" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("first_name", sa.String(length=120), nullable=True))
    if not any(column["name"] == "last_name" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("last_name", sa.String(length=120), nullable=True))
    if not any(column["name"] == "avatar_type" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("avatar_type", sa.String(length=20), nullable=True, server_default="color"))
    if not any(column["name"] == "uploaded_image" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("uploaded_image", sa.Text(), nullable=True))
    if not any(column["name"] == "selected_color" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("selected_color", sa.String(length=50), nullable=True, server_default="bg-blue-500"))

    # Security & Access
    if not any(column["name"] == "mfa_enabled" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=True, server_default="true"))
    if not any(column["name"] == "approval_authority" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("approval_authority", sa.Boolean(), nullable=True, server_default="true"))
    if not any(column["name"] == "allowed_environments" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("allowed_environments", sa.String(length=500), nullable=True, server_default="dev,staging,prod"))
    if not any(column["name"] == "password_last_changed" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("password_last_changed", sa.DateTime(), nullable=True))
    if not any(column["name"] == "access_token" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("access_token", sa.String(length=255), nullable=True, unique=True))

    # User preferences
    if not any(column["name"] == "theme" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("theme", sa.String(length=20), nullable=True, server_default="Light"))
    if not any(column["name"] == "notifications" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("notifications", sa.String(length=20), nullable=True, server_default="All"))
    if not any(column["name"] == "timezone" for column in inspector.get_columns("users")):
        op.add_column("users", sa.Column("timezone", sa.String(length=50), nullable=True, server_default="UTC-8 (Pacific)"))


def downgrade() -> None:
    op.drop_column("users", "timezone")
    op.drop_column("users", "notifications")
    op.drop_column("users", "theme")
    op.drop_column("users", "access_token")
    op.drop_column("users", "password_last_changed")
    op.drop_column("users", "allowed_environments")
    op.drop_column("users", "approval_authority")
    op.drop_column("users", "mfa_enabled")
    op.drop_column("users", "selected_color")
    op.drop_column("users", "uploaded_image")
    op.drop_column("users", "avatar_type")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
