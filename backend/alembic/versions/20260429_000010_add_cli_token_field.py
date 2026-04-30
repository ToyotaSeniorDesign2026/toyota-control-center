"""Add CLI token field to users table.

Revision ID: 20260429_000010
Revises: 20260429_000009
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_000010"
down_revision = "20260429_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add CLI token field to users table for CLI authentication
    with op.batch_alter_table("users", schema=None) as batch_op:
        # Check if column exists before adding
        inspector = sa.inspect(op.get_bind())
        existing_columns = [c["name"] for c in inspector.get_columns("users")]
        
        if "cli_token" not in existing_columns:
            batch_op.add_column(sa.Column("cli_token", sa.String(255), nullable=True))
            batch_op.create_unique_constraint("uq_cli_token", ["cli_token"])


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        # Drop the unique constraint if it exists
        try:
            batch_op.drop_constraint("uq_cli_token", type_="unique")
        except Exception:
            pass
        
        # Drop column if it exists
        inspector = sa.inspect(op.get_bind())
        existing_columns = [c["name"] for c in inspector.get_columns("users")]
        
        if "cli_token" in existing_columns:
            batch_op.drop_column("cli_token")
