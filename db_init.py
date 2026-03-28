"""
db_init.py — Bootstrap script for fresh database initialization.

On a brand-new database:
  1. Creates all tables from the SQLAlchemy models (create_all).
  2. Stamps the Alembic version table to the current head so that
     the existing "fix-up" migrations (which assume tables exist)
     are skipped on first run.

On an existing database (tables already present):
  - Falls through immediately; entrypoint.sh continues with
    `alembic upgrade head` as normal.
"""

import os
import sys

# ── Ensure /app is on the path (set by entrypoint.sh, but guard here too) ──
sys.path.insert(0, '/app')

from sqlalchemy import inspect as sa_inspect, create_engine, text
from alembic.config import Config
from alembic import command as alembic_command

# ── resolve DATABASE_URL (same logic as migrations/env.py) ──────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///Asfalis.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    inspector = sa_inspect(engine)
    existing_tables = inspector.get_table_names()

    # Check if the 'users' table (core anchor table) exists
    if 'users' not in existing_tables:
        print("[db_init] Fresh database detected — creating all tables via SQLAlchemy...")

        # Import all models so Base.metadata knows about them
        from app.database import Base  # noqa
        import app.models.user            # noqa
        import app.models.trusted_contact # noqa
        import app.models.sos_alert       # noqa
        import app.models.location        # noqa
        import app.models.device          # noqa
        import app.models.settings        # noqa
        import app.models.otp             # noqa
        import app.models.support         # noqa
        import app.models.sensor_data     # noqa
        import app.models.ml_model        # noqa
        import app.models.revoked_token   # noqa
        import app.models.device_security # noqa

        Base.metadata.create_all(engine)
        print("[db_init] Tables created.")

        # Stamp Alembic to the current head so it won't re-run history migrations
        alembic_cfg = Config("migrations/alembic.ini")
        alembic_command.stamp(alembic_cfg, "head")
        print("[db_init] Alembic stamped to head. Skipping historical migrations.")
    else:
        print("[db_init] Existing database detected — Alembic will handle any pending migrations.")
