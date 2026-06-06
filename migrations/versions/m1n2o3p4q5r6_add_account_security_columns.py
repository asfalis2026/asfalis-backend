"""Add account security columns (failed_login_attempts, locked_until)

Revision ID: m1n2o3p4q5r6
Revises: l3m4n5o6p7q8
Create Date: 2026-06-06 00:00:00.000000

This migration adds account lockout columns to the users table for tracking
failed login attempts and temporary account locks.

Changes
-------
    users — failed_login_attempts (INTEGER, default=0)
            locked_until (TIMESTAMP, nullable)
"""
from alembic import op
import sqlalchemy as sa


revision = 'm1n2o3p4q5r6'
down_revision = 'l3m4n5o6p7q8'
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(connection)
    cols = [c['name'] for c in inspector.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()

    # Add failed_login_attempts column if it doesn't exist
    if not _column_exists(conn, 'users', 'failed_login_attempts'):
        op.add_column(
            'users',
            sa.Column('failed_login_attempts', sa.Integer(), nullable=True, server_default='0')
        )

    # Add locked_until column if it doesn't exist
    if not _column_exists(conn, 'users', 'locked_until'):
        op.add_column(
            'users',
            sa.Column('locked_until', sa.DateTime(), nullable=True)
        )


def downgrade():
    conn = op.get_bind()

    if _column_exists(conn, 'users', 'locked_until'):
        op.drop_column('users', 'locked_until')

    if _column_exists(conn, 'users', 'failed_login_attempts'):
        op.drop_column('users', 'failed_login_attempts')
