"""add run execution status summary table

Revision ID: 20260226_000003
Revises: 20260224_000002
Create Date: 2026-02-26 00:00:03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260226_000003"
down_revision = "20260224_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("run_execution_status"):
        op.create_table(
            "run_execution_status",
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("risk_level", sa.String(length=24), nullable=False),
            sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
            sa.Column("last_log_at", sa.String(length=64), nullable=True),
            sa.Column("log_count", sa.Integer(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("run_id"),
        )
        op.alter_column("run_execution_status", "requires_approval", server_default=None)
        op.alter_column("run_execution_status", "log_count", server_default=None)

    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_run_execution_status_status ON run_execution_status (status)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_run_execution_status_risk_level ON run_execution_status (risk_level)"))
    bind.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_run_execution_status_updated_at ON run_execution_status (updated_at)"))

    bind.execute(
        sa.text(
            """
            INSERT INTO run_execution_status (run_id, status, risk_level, requires_approval, updated_at, last_log_at, log_count)
            SELECT
              r.id AS run_id,
              r.status AS status,
              r.risk_level AS risk_level,
              r.requires_approval AS requires_approval,
              r.updated_at AS updated_at,
              l.last_log_at AS last_log_at,
              COALESCE(l.log_count, 0) AS log_count
            FROM runs r
            LEFT JOIN (
              SELECT run_id, MAX(timestamp) AS last_log_at, COUNT(*) AS log_count
              FROM run_logs
              GROUP BY run_id
            ) l ON l.run_id = r.id
            ON CONFLICT (run_id) DO UPDATE SET
              status = EXCLUDED.status,
              risk_level = EXCLUDED.risk_level,
              requires_approval = EXCLUDED.requires_approval,
              updated_at = EXCLUDED.updated_at,
              last_log_at = EXCLUDED.last_log_at,
              log_count = EXCLUDED.log_count
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_run_execution_status_updated_at", table_name="run_execution_status")
    op.drop_index("ix_run_execution_status_risk_level", table_name="run_execution_status")
    op.drop_index("ix_run_execution_status_status", table_name="run_execution_status")
    op.drop_table("run_execution_status")
