"""add contact verification

Revision ID: e3f4g5h6i7j8
Revises: d1e2f3a4b5c6
Create Date: 2026-03-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e3f4g5h6i7j8'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    # Add verification fields to trusted_contacts
    with op.batch_alter_table('trusted_contacts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('verified_at', sa.DateTime(), nullable=True))

    # Update otp_purpose_enum to include trusted_contact_verification
    # Note: This is for SQLite. For PostgreSQL, you'd use ALTER TYPE
    with op.batch_alter_table('otp_records', schema=None) as batch_op:
        batch_op.alter_column('purpose',
                              existing_type=sa.Enum('login', 'verify', 'reset_password', 'phone_verification', name='otp_purpose_enum'),
                              type_=sa.Enum('login', 'verify', 'reset_password', 'phone_verification', 'trusted_contact_verification', name='otp_purpose_enum'),
                              existing_nullable=False)


def downgrade():
    # Remove verification fields from trusted_contacts
    with op.batch_alter_table('trusted_contacts', schema=None) as batch_op:
        batch_op.drop_column('verified_at')
        batch_op.drop_column('is_verified')

    # Revert otp_purpose_enum
    with op.batch_alter_table('otp_records', schema=None) as batch_op:
        batch_op.alter_column('purpose',
                              existing_type=sa.Enum('login', 'verify', 'reset_password', 'phone_verification', 'trusted_contact_verification', name='otp_purpose_enum'),
                              type_=sa.Enum('login', 'verify', 'reset_password', 'phone_verification', name='otp_purpose_enum'),
                              existing_nullable=False)
