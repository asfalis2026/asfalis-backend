"""Add message_sids column to sos_alerts table

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-06-06 00:00:00.000000

Background
----------
The SOS alert system needs to track Twilio Message SIDs so that when Twilio
sends status callbacks (webhooks), we can map them back to the specific
SOSAlert record to update its delivery status.

Fix
---
Add nullable JSON column 'message_sids' to store phone -> sid mappings.
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = 'l3m4n5o6p7q8'
down_revision = 'k2l3m4n5o6p7'
branch_labels = None
depends_on = None


def upgrade():
    # Add the message_sids column - nullable so it works with existing rows
    op.add_column('sos_alerts', sa.Column('message_sids', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('sos_alerts', 'message_sids')
