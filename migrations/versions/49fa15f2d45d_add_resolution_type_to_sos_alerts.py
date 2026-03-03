"""add_resolution_type_to_sos_alerts

Revision ID: 49fa15f2d45d
Revises: e3f4g5h6i7j8
Create Date: 2026-03-03 07:58:10.412635

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '49fa15f2d45d'
down_revision = 'e3f4g5h6i7j8'
branch_labels = None
depends_on = None


def upgrade():
    # Add resolution_type column to sos_alerts table
    op.add_column('sos_alerts', sa.Column('resolution_type', sa.String(length=50), nullable=True))


def downgrade():
    # Remove resolution_type column
    op.drop_column('sos_alerts', 'resolution_type')
