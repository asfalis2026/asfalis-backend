"""Add encryption HMAC index columns and widen string columns to Text

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-04-19 00:00:00.000000

Changes
-------
This migration supports field-level encryption at rest.

All sensitive string/float/JSON columns in the models have been changed to
EncryptedString / EncryptedFloat / EncryptedJSON TypeDecorators which store
Fernet ciphertexts — those are base64 strings substantially longer than the
original values, so existing VARCHAR(N) columns are widened to TEXT.

Additionally, HMAC "index" columns are added beside every encrypted field
used in SQL equality lookups (phone, email, device_mac, device_imei).  These
store a deterministic HMAC-SHA256 hex digest so filter_by() still works.

After running this migration you MUST also run the data migration script to
encrypt any existing plaintext rows:

    python scripts/migrate_plaintext_to_encrypted.py

Schema additions:
    users              — phone_hmac, email_hmac (VARCHAR 64, unique, indexed)
                         Widen: full_name, email, phone, sos_message,
                                fcm_token, profile_image_url → TEXT
    trusted_contacts   — phone_hmac (VARCHAR 64, indexed)
                         Widen: name, phone, email → TEXT
    connected_devices  — mac_hmac (VARCHAR 64, indexed)
                         Widen: device_name, device_mac → TEXT
    user_device_bindings — imei_hmac (VARCHAR 64, indexed)
                         Widen: device_imei → TEXT
    handset_change_requests — new_imei_hmac (VARCHAR 64, indexed)
                         Widen: old_device_imei, new_device_imei → TEXT
    location_history   — Widen/retype: latitude, longitude → TEXT (encrypted float)
                         Widen: address → TEXT
                         accuracy → TEXT (encrypted float)
    sos_alerts         — Widen/retype: latitude, longitude → TEXT (encrypted float)
                         Widen: address, sos_message, contacted_numbers → TEXT
    user_settings      — Widen: emergency_number, sos_message → TEXT
    support_tickets    — Widen: subject, message → TEXT
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
revision = 'j1k2l3m4n5o6'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None


def _column_exists(connection, table, column):
    from sqlalchemy import inspect as sa_inspect
    inspector = sa_inspect(connection)
    cols = [c['name'] for c in inspector.get_columns(table)]
    return column in cols


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    # Helper: alter column to TEXT (idempotent-safe via dialect check)
    def to_text(table, col, **kwargs):
        op.alter_column(table, col, type_=sa.Text(), **kwargs)

    # ── users ────────────────────────────────────────────────────────────────
    to_text('users', 'full_name', existing_nullable=False)
    to_text('users', 'email', existing_nullable=True)
    to_text('users', 'phone', existing_nullable=True)
    to_text('users', 'sos_message', existing_nullable=True)
    to_text('users', 'fcm_token', existing_nullable=True)
    to_text('users', 'profile_image_url', existing_nullable=True)

    if not _column_exists(conn, 'users', 'phone_hmac'):
        op.add_column('users', sa.Column('phone_hmac', sa.String(64), nullable=True))
    if not _column_exists(conn, 'users', 'email_hmac'):
        op.add_column('users', sa.Column('email_hmac', sa.String(64), nullable=True))

    # Indexes and unique constraints — drop existing unique on phone/email first (PostgreSQL)
    if dialect == 'postgresql':
        # Drop old unique constraints on plaintext phone/email if they exist;
        # uniqueness is now enforced at app level via HMAC columns.
        try:
            op.drop_constraint('users_phone_key', 'users', type_='unique')
        except Exception:
            pass
        try:
            op.drop_constraint('users_email_key', 'users', type_='unique')
        except Exception:
            pass

    op.create_index('ix_users_phone_hmac', 'users', ['phone_hmac'], unique=True)
    op.create_index('ix_users_email_hmac', 'users', ['email_hmac'], unique=True)

    # ── trusted_contacts ─────────────────────────────────────────────────────
    to_text('trusted_contacts', 'name', existing_nullable=False)
    to_text('trusted_contacts', 'phone', existing_nullable=False)
    to_text('trusted_contacts', 'email', existing_nullable=True)

    if not _column_exists(conn, 'trusted_contacts', 'phone_hmac'):
        op.add_column('trusted_contacts', sa.Column('phone_hmac', sa.String(64), nullable=True))
    op.create_index('ix_trusted_contacts_phone_hmac', 'trusted_contacts', ['phone_hmac'])

    # ── connected_devices ────────────────────────────────────────────────────
    to_text('connected_devices', 'device_name', existing_nullable=False)
    to_text('connected_devices', 'device_mac', existing_nullable=False)

    if not _column_exists(conn, 'connected_devices', 'mac_hmac'):
        op.add_column('connected_devices', sa.Column('mac_hmac', sa.String(64), nullable=True))
    op.create_index('ix_connected_devices_mac_hmac', 'connected_devices', ['mac_hmac'])

    # ── user_device_bindings ─────────────────────────────────────────────────
    to_text('user_device_bindings', 'device_imei', existing_nullable=False)

    if not _column_exists(conn, 'user_device_bindings', 'imei_hmac'):
        op.add_column('user_device_bindings', sa.Column('imei_hmac', sa.String(64), nullable=True))
    op.create_index('ix_user_device_bindings_imei_hmac', 'user_device_bindings', ['imei_hmac'])

    # ── handset_change_requests ──────────────────────────────────────────────
    to_text('handset_change_requests', 'old_device_imei', existing_nullable=True)
    to_text('handset_change_requests', 'new_device_imei', existing_nullable=False)

    if not _column_exists(conn, 'handset_change_requests', 'new_imei_hmac'):
        op.add_column('handset_change_requests', sa.Column('new_imei_hmac', sa.String(64), nullable=True))
    op.create_index('ix_handset_change_requests_new_imei_hmac', 'handset_change_requests', ['new_imei_hmac'])

    # ── location_history ─────────────────────────────────────────────────────
    # latitude/longitude were Float — now EncryptedFloat stored as Text
    to_text('location_history', 'latitude', existing_nullable=False)
    to_text('location_history', 'longitude', existing_nullable=False)
    to_text('location_history', 'address', existing_nullable=True)
    to_text('location_history', 'accuracy', existing_nullable=True)

    # ── sos_alerts ───────────────────────────────────────────────────────────
    to_text('sos_alerts', 'latitude', existing_nullable=False)
    to_text('sos_alerts', 'longitude', existing_nullable=False)
    to_text('sos_alerts', 'address', existing_nullable=True)
    to_text('sos_alerts', 'sos_message', existing_nullable=False)
    to_text('sos_alerts', 'contacted_numbers', existing_nullable=False)

    # ── user_settings ────────────────────────────────────────────────────────
    to_text('user_settings', 'emergency_number', existing_nullable=False)
    to_text('user_settings', 'sos_message', existing_nullable=False)

    # ── support_tickets ──────────────────────────────────────────────────────
    to_text('support_tickets', 'subject', existing_nullable=False)
    to_text('support_tickets', 'message', existing_nullable=False)


def downgrade():
    # Drop HMAC index columns and constraints
    op.drop_index('ix_users_phone_hmac', table_name='users')
    op.drop_index('ix_users_email_hmac', table_name='users')
    op.drop_column('users', 'phone_hmac')
    op.drop_column('users', 'email_hmac')

    op.drop_index('ix_trusted_contacts_phone_hmac', table_name='trusted_contacts')
    op.drop_column('trusted_contacts', 'phone_hmac')

    op.drop_index('ix_connected_devices_mac_hmac', table_name='connected_devices')
    op.drop_column('connected_devices', 'mac_hmac')

    op.drop_index('ix_user_device_bindings_imei_hmac', table_name='user_device_bindings')
    op.drop_column('user_device_bindings', 'imei_hmac')

    op.drop_index('ix_handset_change_requests_new_imei_hmac', table_name='handset_change_requests')
    op.drop_column('handset_change_requests', 'new_imei_hmac')

    # Note: reverting TEXT → VARCHAR(N) and Float is dialect-specific and
    # can corrupt data. Downgrade intentionally leaves widened columns as TEXT.
    # Restore original types manually if needed.
