"""Add language preference to user_settings

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-06-12 00:00:00.000000

This migration adds a language preference column to the user_settings table.
Supported languages: 'en' (English), 'hin' (Hindi), 'ben' (Bengali)
Default value is 'en'.

Changes
-------
    user_settings — language (ENUM, default='en')
"""
from alembic import op
import sqlalchemy as sa


revision = 'n2o3p4q5r6s7'
down_revision = 'm1n2o3p4q5r6'
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(connection)
    cols = [c['name'] for c in inspector.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()

    # Add language column if it doesn't exist
    if not _column_exists(conn, 'user_settings', 'language'):
        op.add_column(
            'user_settings',
            sa.Column(
                'language',
                sa.Enum('en', 'hin', 'ben', name='language_enum'),
                nullable=False,
                server_default='en'
            )
        )


def downgrade():
    conn = op.get_bind()

    if _column_exists(conn, 'user_settings', 'language'):
        op.drop_column('user_settings', 'language')

    # Drop enum type if it exists
    conn.execute(sa.text("DROP TYPE IF EXISTS language_enum"))
