"""add_email_to_users_fix_schema

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-02-27 00:00:01.000000

The public.users table is missing the email column (it exists only in
auth.users, the Supabase-internal table). SQLAlchemy includes every
model column in SELECT queries, causing a ProgrammingError on every
user lookup. This migration adds the column back.
"""
from alembic import op
import sqlalchemy as sa


revision = 'd1e2f3a4b5c6'
down_revision = 'c7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('email', sa.String(255), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email')
