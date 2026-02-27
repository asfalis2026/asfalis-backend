"""Add revoked_tokens table for JWT blocklist

Stores JTIs of refresh tokens that have been consumed (rotation) or
explicitly invalidated (logout). Prevents refresh-token reuse attacks and
ensures logged-out sessions cannot be resumed.

Revision ID: b7f3a9e12c45
Revises: 6ae25ed0c87d
Create Date: 2026-02-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f3a9e12c45'
down_revision = '6ae25ed0c87d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(length=36), nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti')
    )
    op.create_index(
        op.f('ix_revoked_tokens_jti'),
        'revoked_tokens',
        ['jti'],
        unique=True
    )


def downgrade():
    op.drop_index(op.f('ix_revoked_tokens_jti'), table_name='revoked_tokens')
    op.drop_table('revoked_tokens')
