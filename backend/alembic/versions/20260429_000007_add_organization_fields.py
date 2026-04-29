"""Add organization and team information fields to users table.

Revision ID: 20260429_000007
Revises: 20260429_000006
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260429_000007"
down_revision = "20260429_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add organization and team fields to users table
    # These fields are managed by HR/admin and not user-editable
    
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Check if columns exist before adding
        inspector = sa.inspect(op.get_bind())
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        
        if 'job_title' not in existing_columns:
            batch_op.add_column(sa.Column('job_title', sa.String(120), nullable=True))
        
        if 'department' not in existing_columns:
            batch_op.add_column(sa.Column('department', sa.String(120), nullable=True))
        
        if 'team' not in existing_columns:
            batch_op.add_column(sa.Column('team', sa.String(120), nullable=True))
        
        if 'manager' not in existing_columns:
            batch_op.add_column(sa.Column('manager', sa.String(120), nullable=True))
        
        if 'employee_id' not in existing_columns:
            batch_op.add_column(sa.Column('employee_id', sa.String(40), nullable=True))
            batch_op.create_unique_constraint('uq_employee_id', ['employee_id'])


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Drop the unique constraint if it exists
        try:
            batch_op.drop_constraint('uq_employee_id', type_='unique')
        except Exception:
            pass
        
        # Drop columns if they exist
        inspector = sa.inspect(op.get_bind())
        existing_columns = [c['name'] for c in inspector.get_columns('users')]
        
        if 'employee_id' in existing_columns:
            batch_op.drop_column('employee_id')
        
        if 'manager' in existing_columns:
            batch_op.drop_column('manager')
        
        if 'team' in existing_columns:
            batch_op.drop_column('team')
        
        if 'department' in existing_columns:
            batch_op.drop_column('department')
        
        if 'job_title' in existing_columns:
            batch_op.drop_column('job_title')
