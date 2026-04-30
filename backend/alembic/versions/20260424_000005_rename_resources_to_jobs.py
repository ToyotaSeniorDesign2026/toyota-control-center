"""rename resources table to jobs and resource_id to job_id

Revision ID: 20260424_000005
Revises: 20260328_000004
Create Date: 2026-04-24 00:00:05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260424_000005"
down_revision = "20260328_000004"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    result = op.get_bind().execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=:t"),
        {"t": name},
    )
    return result.fetchone() is not None


def _column_exists(table: str, column: str) -> bool:
    result = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def _index_exists(name: str) -> bool:
    result = op.get_bind().execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # 1. Rename resources → jobs
    #    create_all() may have already created an empty "jobs" table from the new
    #    Job model.  If so, drop it before renaming the real "resources" table.
    # ---------------------------------------------------------------------------
    if _table_exists("resources"):
        if _table_exists("jobs"):
            # Drop the auto-created empty shell so the rename can proceed
            op.execute("DROP TABLE jobs")
        op.rename_table("resources", "jobs")

    # Rename indexes on the jobs table (previously resources)
    for old, new in [
        ("ix_resources_name", "ix_jobs_name"),
        ("ix_resources_kind", "ix_jobs_kind"),
        ("ix_resources_type", "ix_jobs_type"),
        ("ix_resources_owner_id", "ix_jobs_owner_id"),
        ("ix_resources_owner_domain", "ix_jobs_owner_domain"),
        ("ix_resources_environment", "ix_jobs_environment"),
        ("ix_resources_status", "ix_jobs_status"),
        ("ix_resources_data_sensitivity", "ix_jobs_data_sensitivity"),
    ]:
        if _index_exists(old):
            op.execute(f"ALTER INDEX {old} RENAME TO {new}")

    # ---------------------------------------------------------------------------
    # 2. Rename resource_id → job_id in runs
    # ---------------------------------------------------------------------------
    if _column_exists("runs", "resource_id"):
        op.alter_column("runs", "resource_id", new_column_name="job_id")

    if _index_exists("ix_runs_resource_id"):
        op.execute("ALTER INDEX ix_runs_resource_id RENAME TO ix_runs_job_id")

    # ---------------------------------------------------------------------------
    # 3. Create connectors table (idempotent)
    # ---------------------------------------------------------------------------
    if not _table_exists("connectors"):
        op.create_table(
            "connectors",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("connector_type", sa.String(length=80), nullable=False),
            sa.Column("owner_id", sa.String(length=64), nullable=False),
            sa.Column("owner_domain", sa.String(length=80), nullable=False),
            sa.Column("environment", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.String(length=64), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_connectors_name", "connectors", ["name"], unique=False)
        op.create_index("ix_connectors_connector_type", "connectors", ["connector_type"], unique=False)
        op.create_index("ix_connectors_owner_id", "connectors", ["owner_id"], unique=False)
        op.create_index("ix_connectors_owner_domain", "connectors", ["owner_domain"], unique=False)
        op.create_index("ix_connectors_environment", "connectors", ["environment"], unique=False)
        op.create_index("ix_connectors_status", "connectors", ["status"], unique=False)


def downgrade() -> None:
    if _table_exists("connectors"):
        op.drop_index("ix_connectors_status", table_name="connectors")
        op.drop_index("ix_connectors_environment", table_name="connectors")
        op.drop_index("ix_connectors_owner_domain", table_name="connectors")
        op.drop_index("ix_connectors_owner_id", table_name="connectors")
        op.drop_index("ix_connectors_connector_type", table_name="connectors")
        op.drop_index("ix_connectors_name", table_name="connectors")
        op.drop_table("connectors")

    if _column_exists("runs", "job_id"):
        if _index_exists("ix_runs_job_id"):
            op.execute("ALTER INDEX ix_runs_job_id RENAME TO ix_runs_resource_id")
        op.alter_column("runs", "job_id", new_column_name="resource_id")

    if _table_exists("jobs"):
        for old, new in [
            ("ix_jobs_data_sensitivity", "ix_resources_data_sensitivity"),
            ("ix_jobs_status", "ix_resources_status"),
            ("ix_jobs_environment", "ix_resources_environment"),
            ("ix_jobs_owner_domain", "ix_resources_owner_domain"),
            ("ix_jobs_owner_id", "ix_resources_owner_id"),
            ("ix_jobs_type", "ix_resources_type"),
            ("ix_jobs_kind", "ix_resources_kind"),
            ("ix_jobs_name", "ix_resources_name"),
        ]:
            if _index_exists(old):
                op.execute(f"ALTER INDEX {old} RENAME TO {new}")
        op.rename_table("jobs", "resources")
