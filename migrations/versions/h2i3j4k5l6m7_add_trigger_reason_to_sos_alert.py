"""add trigger_reason to sos_alerts

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-12

Adds a nullable text column trigger_reason to sos_alerts.
Populated for auto-SOS alerts with the short human-readable reason
(e.g. "Unusual fall detected") that is included in the WhatsApp
message body by _build_sos_body() in whatsapp_service.
Manual and IoT-button alerts leave this NULL — the trigger label
alone (from TRIGGER_TYPE_LABELS) is sufficient context.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = 'h2i3j4k5l6m7'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'sos_alerts',
        sa.Column('trigger_reason', sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column('sos_alerts', 'trigger_reason')
