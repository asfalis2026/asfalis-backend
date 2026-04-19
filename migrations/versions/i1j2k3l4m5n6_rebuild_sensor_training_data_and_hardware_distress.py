"""Add hardware_distress enum (sensor_training_data removed)

Revision ID: i1j2k3l4m5n6
Revises: h2i3j4k5l6m7
Create Date: 2026-04-06 00:00:00.000000

Changes
-------
1. Drop ``sensor_training_data`` and ``ml_models`` tables if they still
   exist (idempotent — safe even if manually deleted from the DB).

2. Add ``hardware_distress`` to the ``trigger_type_enum`` PostgreSQL enum
   used by ``sos_alerts.trigger_type``.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

# ---------------------------------------------------------------------------
revision = 'i1j2k3l4m5n6'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    inspector = sa_inspect(connection)
    return table_name in inspector.get_table_names()


def upgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name

    # ── 1. Drop ML tables if they still exist (idempotent) ──────────────────
    if _table_exists(connection, 'sensor_training_data'):
        op.drop_table('sensor_training_data')

    if _table_exists(connection, 'ml_models'):
        op.drop_table('ml_models')

    # ── 2. Add hardware_distress to trigger_type_enum ────────────────────────
    if dialect == 'postgresql':
        op.execute("COMMIT")
        op.execute("ALTER TYPE trigger_type_enum ADD VALUE IF NOT EXISTS 'hardware_distress'")
        op.execute("BEGIN")


def downgrade():
    # ML tables are intentionally not restored — they belong to a removed feature.
    # hardware_distress enum value cannot be removed from PostgreSQL without
    # dropping and recreating the entire type — left as-is (harmless when unused).
    pass
