"""Add scheduled_at field for future runs.

Revision ID: 20260429_000011
Revises: 20260429_000010
Create Date: 2026-04-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_000011"
down_revision = "20260429_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add scheduled_at column to runs table
    op.add_column(
        "runs",
        sa.Column("scheduled_at", sa.String(64), nullable=True),
    )
    # Add index for faster queries
    op.create_index("ix_runs_scheduled_at", "runs", ["scheduled_at"])


def downgrade() -> None:
    op.drop_index("ix_runs_scheduled_at", table_name="runs")
    op.drop_column("runs", "scheduled_at")
