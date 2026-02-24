"""add resource kind

Revision ID: 20260224_000002
Revises: 20260218_000001
Create Date: 2026-02-24 00:00:02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260224_000002"
down_revision = "20260218_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resources",
        sa.Column("kind", sa.String(length=24), nullable=False, server_default="runtime"),
    )
    op.create_index("ix_resources_kind", "resources", ["kind"], unique=False)
    op.alter_column("resources", "kind", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_resources_kind", table_name="resources")
    op.drop_column("resources", "kind")
