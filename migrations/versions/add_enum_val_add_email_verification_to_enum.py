"""Add email_verification to enum

Revision ID: add_enum_val
Revises: 4f716fa5f13c
Create Date: 2026-02-12 11:49:19.125997

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_enum_val'
down_revision = '4f716fa5f13c'
branch_labels = None
depends_on = None


def upgrade():
    # Helper to add value to enum if not exists
    # Requires running outside a transaction block for some PG versions
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE otp_purpose_enum ADD VALUE IF NOT EXISTS 'email_verification'")


def downgrade():
    pass
