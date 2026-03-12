"""Ensure iot_button is in trigger_type_enum (PostgreSQL-safe re-apply)

Revision ID: g1h2i3j4k5l6
Revises: c1d2e3f4g5h6
Create Date: 2026-03-12 00:00:00.000000

Background
----------
The earlier migration c1d2e3f4g5h6 ran::

    ALTER TYPE trigger_type_enum ADD VALUE IF NOT EXISTS 'iot_button'

inside Alembic's default transaction block.  On **PostgreSQL < 12** this DDL
statement cannot execute inside an open transaction and is silently skipped
(or raises an error that causes the migration to be rolled back).  When the
enum value is absent, every ``POST /api/sos/trigger`` call with
``trigger_type="iot_button"`` fails at the DB commit step, no SOSAlert row is
created, and the alert never appears in history.

Fix
---
This migration detects whether ``'iot_button'`` is already present in the
enum.  If it is not, it drops to the raw psycopg2 DBAPI connection, switches
it to autocommit mode, executes the ``ALTER TYPE`` statement, then restores
the original isolation level.  This approach is safe on **all** PostgreSQL
versions (9.3 +) and is a no-op on SQLite (which stores enums as VARCHAR).
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision = 'g1h2i3j4k5l6'
down_revision = 'c1d2e3f4g5h6'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    # SQLite stores enums as plain VARCHAR — no DDL change is required.
    if connection.dialect.name != 'postgresql':
        return

    # Check whether 'iot_button' is already present in the enum type.
    result = connection.execute(
        sa.text(
            "SELECT 1 FROM pg_enum "
            "WHERE enumtypid = 'trigger_type_enum'::regtype "
            "AND enumlabel = 'iot_button'"
        )
    ).fetchone()

    if result is not None:
        # Already present — nothing to do.
        return

    # 'iot_button' is missing.
    # ALTER TYPE ADD VALUE cannot run inside a transaction on PostgreSQL < 12.
    # Drop to the raw psycopg2 DBAPI connection and use autocommit mode.
    raw_conn = connection.connection.dbapi_connection  # SQLAlchemy 2.x

    original_autocommit = raw_conn.autocommit
    try:
        raw_conn.autocommit = True
        with raw_conn.cursor() as cur:
            cur.execute("ALTER TYPE trigger_type_enum ADD VALUE 'iot_button'")
    finally:
        # Always restore the original isolation / autocommit state so that
        # Alembic's own version-tracking INSERT can still run correctly.
        raw_conn.autocommit = original_autocommit


def downgrade():
    # PostgreSQL does not support removing individual values from an enum type
    # without dropping and recreating the entire type (which requires
    # temporarily changing the column type on every table that uses it).
    # Since 'iot_button' is harmless when unused, the downgrade is a no-op.
    pass
