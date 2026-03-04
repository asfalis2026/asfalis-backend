"""add_auto_sos_enabled_to_user_settings

Revision ID: f1a2b3c4d5e6
Revises: 49fa15f2d45d, d9154397a811
Create Date: 2026-03-05 00:00:00.000000

Merges the two existing branch heads (49fa15f2d45d and d9154397a811) and
adds the ``auto_sos_enabled`` flag to ``user_settings``.

When True the frontend is expected to stream accelerometer / gyroscope
readings to ``POST /protection/predict`` whenever the device-side magnitude
exceeds the user-configured threshold.  The backend then runs the ML model
and triggers an SOS countdown if danger is predicted.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = ('49fa15f2d45d', 'd9154397a811')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'user_settings',
        sa.Column(
            'auto_sos_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
    )


def downgrade():
    op.drop_column('user_settings', 'auto_sos_enabled')
