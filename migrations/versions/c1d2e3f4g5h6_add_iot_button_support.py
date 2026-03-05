"""add_iot_button_support

Revision ID: c1d2e3f4g5h6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-05 12:00:00.000000

Adds two changes for the ESP32 wearable IoT integration:

1. ``connected_devices.last_button_press_at`` (DateTime, nullable)
   Stores the UTC timestamp of the most recent hardware button press so the
   backend can detect a "double-tap" (two presses within 1.5 s → cancel SOS).

2. Extends the ``trigger_type_enum`` Postgres enum to include the new value
   ``'iot_button'``, which is emitted when an SOS is fired via the wearable.
   On SQLite (development) the enum is stored as a VARCHAR so no ALTER is needed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4g5h6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None

# Helper: detect whether we're running against PostgreSQL
def _is_postgresql():
    bind = op.get_bind()
    return bind.dialect.name == 'postgresql'


def upgrade():
    # ------------------------------------------------------------------ #
    # 1. Add last_button_press_at to connected_devices
    # ------------------------------------------------------------------ #
    op.add_column(
        'connected_devices',
        sa.Column('last_button_press_at', sa.DateTime(), nullable=True)
    )

    # ------------------------------------------------------------------ #
    # 2. Add 'iot_button' to the trigger_type_enum (PostgreSQL only)
    #    SQLite stores enums as plain VARCHAR — no DDL change required.
    # ------------------------------------------------------------------ #
    if _is_postgresql():
        op.execute("ALTER TYPE trigger_type_enum ADD VALUE IF NOT EXISTS 'iot_button'")


def downgrade():
    # Remove the column added above
    op.drop_column('connected_devices', 'last_button_press_at')

    # NOTE: PostgreSQL does not support removing values from an enum type
    # without recreating it.  Downgrade leaves 'iot_button' in the enum but
    # the application simply won't emit that value, so rows are unaffected.
