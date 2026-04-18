"""
Alembic env.py — rewritten without Flask/Flask-Migrate dependency.

Reads DATABASE_URL from environment directly and uses app.database.Base.metadata
for autogenerate support.
"""

import os
import logging
from logging.config import fileConfig
from dotenv import load_dotenv

from alembic import context
from sqlalchemy import engine_from_config, pool

load_dotenv()

# Alembic Config object
alembic_config = context.config

# Set up Python logging from alembic.ini
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

logger = logging.getLogger('alembic.env')

# ── Database URL ──────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///Asfalis.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

alembic_config.set_main_option('sqlalchemy.url', DATABASE_URL)

# ── Import all models so Alembic can detect schema changes ────────────────────
from app.database import Base  # noqa: E402

import app.models.user          # noqa: F401
import app.models.trusted_contact  # noqa: F401
import app.models.sos_alert     # noqa: F401
import app.models.location      # noqa: F401
import app.models.device        # noqa: F401
import app.models.settings      # noqa: F401
import app.models.otp           # noqa: F401
import app.models.support       # noqa: F401

import app.models.revoked_token # noqa: F401
import app.models.device_security  # noqa: F401

target_metadata = Base.metadata


# ── Migration runners ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
