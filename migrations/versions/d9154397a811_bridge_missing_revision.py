"""bridge missing revision

Revision ID: d9154397a811
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04 00:00:00.000000

NOTE: This is a bridge/placeholder migration created because the production
database already has revision 'd9154397a811' stamped in its alembic_version
table, but the corresponding migration file was missing from the repository.

The database schema is already correct. This file simply reconciles the
revision history so that `flask db upgrade` resolves cleanly (no-op).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd9154397a811'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Database schema is already up to date.
    # This migration is a no-op bridge to reconcile the missing revision.
    pass


def downgrade():
    pass
