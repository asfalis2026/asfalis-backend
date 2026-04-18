"""Rebuild sensor_training_data (window features) and add hardware_distress enum

Revision ID: i1j2k3l4m5n6
Revises: h2i3j4k5l6m7
Create Date: 2026-04-06 00:00:00.000000

Changes
-------
1. Drop the old ``sensor_training_data`` table (per-reading schema) and
   recreate it with the new window-level 39-feature schema matching
   ``labeled_windows.csv``.

2. Add ``hardware_distress`` to the ``trigger_type_enum`` PostgreSQL enum
   used by ``sos_alerts.trigger_type``.

PostgreSQL notes
----------------
- Adding an enum value requires autocommit mode on PostgreSQL < 12.
- Dropping and recreating a table with a FK to ``sos_alerts`` requires the
  FK to ``sos_alert_id`` in the new table to be added *after* the table
  exists (handled below).
- SQLite stores enums as VARCHAR — no DDL changes are needed for (2).
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
revision = 'i1j2k3l4m5n6'
down_revision = 'h2i3j4k5l6m7'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name

    # ── 1. Rebuild sensor_training_data ─────────────────────────────────────
    op.drop_table('sensor_training_data')

    op.create_table(
        'sensor_training_data',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('user_id',     sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('dataset_name',       sa.String(100), nullable=True),
        sa.Column('motion_description', sa.Text(),      nullable=True),
        sa.Column('danger_label',       sa.Integer(),   nullable=False),

        # X-axis
        sa.Column('x_mean',   sa.Float(), nullable=False),
        sa.Column('x_std',    sa.Float(), nullable=False),
        sa.Column('x_min',    sa.Float(), nullable=False),
        sa.Column('x_max',    sa.Float(), nullable=False),
        sa.Column('x_range',  sa.Float(), nullable=False),
        sa.Column('x_median', sa.Float(), nullable=False),
        sa.Column('x_iqr',    sa.Float(), nullable=False),
        sa.Column('x_rms',    sa.Float(), nullable=False),

        # Y-axis
        sa.Column('y_mean',   sa.Float(), nullable=False),
        sa.Column('y_std',    sa.Float(), nullable=False),
        sa.Column('y_min',    sa.Float(), nullable=False),
        sa.Column('y_max',    sa.Float(), nullable=False),
        sa.Column('y_range',  sa.Float(), nullable=False),
        sa.Column('y_median', sa.Float(), nullable=False),
        sa.Column('y_iqr',    sa.Float(), nullable=False),
        sa.Column('y_rms',    sa.Float(), nullable=False),

        # Z-axis
        sa.Column('z_mean',   sa.Float(), nullable=False),
        sa.Column('z_std',    sa.Float(), nullable=False),
        sa.Column('z_min',    sa.Float(), nullable=False),
        sa.Column('z_max',    sa.Float(), nullable=False),
        sa.Column('z_range',  sa.Float(), nullable=False),
        sa.Column('z_median', sa.Float(), nullable=False),
        sa.Column('z_iqr',    sa.Float(), nullable=False),
        sa.Column('z_rms',    sa.Float(), nullable=False),

        # Magnitude
        sa.Column('mag_mean',   sa.Float(), nullable=False),
        sa.Column('mag_std',    sa.Float(), nullable=False),
        sa.Column('mag_min',    sa.Float(), nullable=False),
        sa.Column('mag_max',    sa.Float(), nullable=False),
        sa.Column('mag_range',  sa.Float(), nullable=False),
        sa.Column('mag_median', sa.Float(), nullable=False),
        sa.Column('mag_iqr',    sa.Float(), nullable=False),
        sa.Column('mag_rms',    sa.Float(), nullable=False),

        # Cross-correlations
        sa.Column('xy_corr', sa.Float(), nullable=False),
        sa.Column('xz_corr', sa.Float(), nullable=False),
        sa.Column('yz_corr', sa.Float(), nullable=False),

        # Bookkeeping
        sa.Column('sos_alert_id', sa.String(36), sa.ForeignKey('sos_alerts.id'), nullable=True),
        sa.Column('is_verified',  sa.Boolean(), default=False),
        sa.Column('created_at',   sa.DateTime(), server_default=sa.func.now()),
    )

    # ── 2. Add hardware_distress to trigger_type_enum ────────────────────────
    if dialect == 'postgresql':
        op.execute("COMMIT")
        op.execute("ALTER TYPE trigger_type_enum ADD VALUE IF NOT EXISTS 'hardware_distress'")
        op.execute("BEGIN")


def downgrade():
    # Recreate the old per-reading sensor_training_data schema
    op.drop_table('sensor_training_data')

    op.create_table(
        'sensor_training_data',
        sa.Column('id',          sa.String(36), primary_key=True),
        sa.Column('user_id',     sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('timestamp',   sa.BigInteger(), nullable=False),
        sa.Column('x',           sa.Float(),   nullable=False),
        sa.Column('y',           sa.Float(),   nullable=False),
        sa.Column('z',           sa.Float(),   nullable=False),
        sa.Column('sensor_type', sa.String(20), nullable=False),
        sa.Column('label',       sa.Integer(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('created_at',  sa.DateTime(), server_default=sa.func.now()),
    )
    # hardware_distress enum value cannot be removed from PostgreSQL without
    # dropping and recreating the entire type — left as-is (harmless when unused).
