"""add run execution config persistence fields

Revision ID: 20260328_000004
Revises: 20260226_000003
Create Date: 2026-03-28 00:00:04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_000004"
down_revision = "20260226_000003"
branch_labels = None
depends_on = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "runs", "trigger_source"):
        op.add_column("runs", sa.Column("trigger_source", sa.String(length=32), nullable=True))
    if not _has_column(inspector, "runs", "execution_backend"):
        op.add_column("runs", sa.Column("execution_backend", sa.String(length=32), nullable=True))
    if not _has_column(inspector, "runs", "execution_mode"):
        op.add_column("runs", sa.Column("execution_mode", sa.String(length=32), nullable=True))
    if not _has_column(inspector, "runs", "submitted_config_json"):
        op.add_column("runs", sa.Column("submitted_config_json", sa.JSON(), nullable=True))
    if not _has_column(inspector, "runs", "resolved_job_spec_json"):
        op.add_column("runs", sa.Column("resolved_job_spec_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "resolved_job_spec_json")
    op.drop_column("runs", "submitted_config_json")
    op.drop_column("runs", "execution_mode")
    op.drop_column("runs", "execution_backend")
    op.drop_column("runs", "trigger_source")
