"""add_profile_fields

Revision ID: 20260429_000008
Revises: 20260429_000007
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_000008"
down_revision = "20260429_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add phone, location, and bio columns to users table
    op.add_column(
        "users",
        sa.Column("phone", sa.String(20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("location", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("bio", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Drop the columns
    op.drop_column("users", "bio")
    op.drop_column("users", "location")
    op.drop_column("users", "phone")
