"""initial_phone_auth

Revision ID: 915e0b05243e
Revises: 
Create Date: 2026-02-27 21:33:24.755647

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '915e0b05243e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    # Add phone_verification to otp_purpose_enum (PostgreSQL-only)
    if bind.dialect.name == 'postgresql':
        op.execute("ALTER TYPE otp_purpose_enum ADD VALUE IF NOT EXISTS 'phone_verification'")

    # Drop the unique constraint on revoked_tokens.jti — only if the table exists
    # (this migration was originally written against an existing database)
    if 'revoked_tokens' in existing_tables:
        with op.batch_alter_table('revoked_tokens', schema=None) as batch_op:
            batch_op.drop_constraint(batch_op.f('revoked_tokens_jti_key'), type_='unique')


def downgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    existing_tables = inspector.get_table_names()

    if 'revoked_tokens' in existing_tables:
        with op.batch_alter_table('revoked_tokens', schema=None) as batch_op:
            batch_op.create_unique_constraint(batch_op.f('revoked_tokens_jti_key'), ['jti'])

    # Note: PostgreSQL does not support removing enum values; phone_verification will remain.
