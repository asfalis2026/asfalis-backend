"""Add 'failed' status to sos_status_enum

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-06-06 00:00:00.000000

Background
----------
The SOS alert system needs to track when a WhatsApp message fails to send
(e.g., Twilio daily limit exhausted). This adds a 'failed' status to the
sos_status_enum so the Android app can display a red "FAILED" badge.

Fix
---
Add 'failed' value to the sos_status_enum type using PostgreSQL-safe DDL.
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = 'k2l3m4n5o6p7'
down_revision = 'j1k2l3m4n5o6'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # SQLite stores enums as plain VARCHAR — no DDL change is required.
    if connection.dialect.name != 'postgresql':
        return

    # Check whether 'failed' is already present in the enum type.
    result = connection.execute(
        sa.text(
            "SELECT 1 FROM pg_enum "
            "WHERE enumtypid = 'sos_status_enum'::regtype "
            "AND enumlabel = 'failed'"
        )
    ).fetchone()

    if result is not None:
        # Already present — nothing to do.
        return

    # 'failed' is missing.
    # ALTER TYPE ADD VALUE cannot run inside a transaction on PostgreSQL < 12.
    # Drop to the raw psycopg2 DBAPI connection and use autocommit mode.
    raw_conn = connection.connection.dbapi_connection  # SQLAlchemy 2.x

    original_autocommit = raw_conn.autocommit
    try:
        raw_conn.autocommit = True
        with raw_conn.cursor() as cur:
            cur.execute("ALTER TYPE sos_status_enum ADD VALUE 'failed'")
    finally:
        # Always restore the original isolation / autocommit state.
        raw_conn.autocommit = original_autocommit


def downgrade():
    # PostgreSQL does not support removing individual values from an enum type
    # without dropping and recreating the entire type.
    pass
