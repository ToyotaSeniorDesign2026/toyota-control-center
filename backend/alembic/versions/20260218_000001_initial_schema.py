"""initial schema

Revision ID: 20260218_000001
Revises: 
Create Date: 2026-02-18 00:00:01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260218_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_domain", "users", ["domain"], unique=False)

    op.create_table(
        "resources",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("connector", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.String(length=64), nullable=False),
        sa.Column("owner_domain", sa.String(length=80), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("data_sensitivity", sa.String(length=32), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resources_name", "resources", ["name"], unique=False)
    op.create_index("ix_resources_type", "resources", ["type"], unique=False)
    op.create_index("ix_resources_owner_id", "resources", ["owner_id"], unique=False)
    op.create_index("ix_resources_owner_domain", "resources", ["owner_domain"], unique=False)
    op.create_index("ix_resources_environment", "resources", ["environment"], unique=False)
    op.create_index("ix_resources_status", "resources", ["status"], unique=False)
    op.create_index("ix_resources_data_sensitivity", "resources", ["data_sensitivity"], unique=False)

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval_id", sa.String(length=64), nullable=True),
        sa.Column("connector_run_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.Column("promotion_status", sa.String(length=40), nullable=True),
        sa.Column("git_ref", sa.String(length=255), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("workflow_run_id", sa.String(length=64), nullable=True),
        sa.Column("workflow_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_resource_id", "runs", ["resource_id"], unique=False)
    op.create_index("ix_runs_requested_by", "runs", ["requested_by"], unique=False)
    op.create_index("ix_runs_domain", "runs", ["domain"], unique=False)
    op.create_index("ix_runs_target_environment", "runs", ["target_environment"], unique=False)
    op.create_index("ix_runs_status", "runs", ["status"], unique=False)

    op.create_table(
        "run_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=2048), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_logs_run_id", "run_logs", ["run_id"], unique=False)
    op.create_index("ix_run_logs_timestamp", "run_logs", ["timestamp"], unique=False)
    op.create_index("ix_run_logs_level", "run_logs", ["level"], unique=False)

    op.create_table(
        "policy_evaluations",
        sa.Column("evaluation_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=40), nullable=False),
        sa.Column("overall_status", sa.String(length=40), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evaluated_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("evaluation_id"),
    )
    op.create_index("ix_policy_evaluations_run_id", "policy_evaluations", ["run_id"], unique=False)
    op.create_index("ix_policy_evaluations_overall_status", "policy_evaluations", ["overall_status"], unique=False)
    op.create_index("ix_policy_evaluations_risk_level", "policy_evaluations", ["risk_level"], unique=False)

    op.create_table(
        "policy_check_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("evaluation_id", sa.String(length=64), nullable=False),
        sa.Column("check_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.String(length=255), nullable=True),
        sa.Column("actual_value", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_check_results_evaluation_id", "policy_check_results", ["evaluation_id"], unique=False)
    op.create_index("ix_policy_check_results_result", "policy_check_results", ["result"], unique=False)
    op.create_index("ix_policy_check_results_severity", "policy_check_results", ["severity"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.String(length=64), nullable=True),
        sa.Column("risk_level", sa.String(length=24), nullable=False),
        sa.Column("comment", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("reviewed_at", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"], unique=False)
    op.create_index("ix_approvals_status", "approvals", ["status"], unique=False)
    op.create_index("ix_approvals_requested_by", "approvals", ["requested_by"], unique=False)
    op.create_index("ix_approvals_reviewer_id", "approvals", ["reviewer_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_events_received_at", "workflow_events", ["received_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workflow_events_received_at", table_name="workflow_events")
    op.drop_table("workflow_events")

    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_approvals_reviewer_id", table_name="approvals")
    op.drop_index("ix_approvals_requested_by", table_name="approvals")
    op.drop_index("ix_approvals_status", table_name="approvals")
    op.drop_index("ix_approvals_run_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_policy_check_results_severity", table_name="policy_check_results")
    op.drop_index("ix_policy_check_results_result", table_name="policy_check_results")
    op.drop_index("ix_policy_check_results_evaluation_id", table_name="policy_check_results")
    op.drop_table("policy_check_results")

    op.drop_index("ix_policy_evaluations_risk_level", table_name="policy_evaluations")
    op.drop_index("ix_policy_evaluations_overall_status", table_name="policy_evaluations")
    op.drop_index("ix_policy_evaluations_run_id", table_name="policy_evaluations")
    op.drop_table("policy_evaluations")

    op.drop_index("ix_run_logs_level", table_name="run_logs")
    op.drop_index("ix_run_logs_timestamp", table_name="run_logs")
    op.drop_index("ix_run_logs_run_id", table_name="run_logs")
    op.drop_table("run_logs")

    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_target_environment", table_name="runs")
    op.drop_index("ix_runs_domain", table_name="runs")
    op.drop_index("ix_runs_requested_by", table_name="runs")
    op.drop_index("ix_runs_resource_id", table_name="runs")
    op.drop_table("runs")

    op.drop_index("ix_resources_data_sensitivity", table_name="resources")
    op.drop_index("ix_resources_status", table_name="resources")
    op.drop_index("ix_resources_environment", table_name="resources")
    op.drop_index("ix_resources_owner_domain", table_name="resources")
    op.drop_index("ix_resources_owner_id", table_name="resources")
    op.drop_index("ix_resources_type", table_name="resources")
    op.drop_index("ix_resources_name", table_name="resources")
    op.drop_table("resources")

    op.drop_index("ix_users_domain", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
