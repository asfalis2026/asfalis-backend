"""schema_cleanup_phone_only

Revision ID: c7d8e9f0a1b2
Revises: 915e0b05243e
Create Date: 2026-02-27 00:00:00.000000

This migration:
  1. Wipes all existing data (fresh start for phone-only auth)
  2. Drops the `email` column from `otp_records`
  3. Recreates `otp_purpose_enum` without the obsolete `email_verification` value
  4. Recreates `auth_provider_enum` without the obsolete `email` value
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7d8e9f0a1b2'
down_revision = '915e0b05243e'
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------ #
    # 1. Wipe all data — fresh start (phone-only auth era)
    # ------------------------------------------------------------------ #
    # Cascade handles: trusted_contacts, sos_alerts, location_history,
    # user_settings, connected_devices, support_tickets
    op.execute("TRUNCATE TABLE users CASCADE")
    # Tables without FK to users
    op.execute("TRUNCATE TABLE otp_records")
    op.execute("TRUNCATE TABLE revoked_tokens")
    op.execute("TRUNCATE TABLE ml_models")
    op.execute("TRUNCATE TABLE sensor_training_data")

    # ------------------------------------------------------------------ #
    # 2. Drop obsolete `email` column from otp_records
    # ------------------------------------------------------------------ #
    with op.batch_alter_table('otp_records', schema=None) as batch_op:
        batch_op.drop_column('email')

    # ------------------------------------------------------------------ #
    # 3. Recreate otp_purpose_enum without `email_verification`
    #    PostgreSQL does not support DROP VALUE from an enum; must recreate.
    # ------------------------------------------------------------------ #
    op.execute(
        "CREATE TYPE otp_purpose_enum_new AS ENUM "
        "('login', 'verify', 'reset_password', 'phone_verification')"
    )
    op.execute(
        "ALTER TABLE otp_records "
        "ALTER COLUMN purpose TYPE otp_purpose_enum_new "
        "USING purpose::text::otp_purpose_enum_new"
    )
    op.execute("DROP TYPE otp_purpose_enum")
    op.execute("ALTER TYPE otp_purpose_enum_new RENAME TO otp_purpose_enum")

    # ------------------------------------------------------------------ #
    # 4. Recreate auth_provider_enum without `email`
    # ------------------------------------------------------------------ #
    op.execute(
        "CREATE TYPE auth_provider_enum_new AS ENUM ('phone', 'google')"
    )
    op.execute(
        "ALTER TABLE users "
        "ALTER COLUMN auth_provider TYPE auth_provider_enum_new "
        "USING auth_provider::text::auth_provider_enum_new"
    )
    op.execute("DROP TYPE auth_provider_enum")
    op.execute("ALTER TYPE auth_provider_enum_new RENAME TO auth_provider_enum")


def downgrade():
    # Enum restoration and data recovery are not supported in this migration.
    pass
