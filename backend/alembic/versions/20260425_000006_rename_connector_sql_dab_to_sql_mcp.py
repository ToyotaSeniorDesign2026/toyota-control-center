"""rename connector sql-dab to sql-mcp in jobs table

Revision ID: 20260425_000006
Revises: 20260424_000005
Create Date: 2026-04-25 00:00:06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260425_000006"
down_revision = "20260424_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE jobs SET connector = 'sql-mcp' WHERE connector = 'sql-dab'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE jobs SET connector = 'sql-dab' WHERE connector = 'sql-mcp'")
    )
