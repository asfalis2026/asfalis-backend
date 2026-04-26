"""
SQLAlchemy engine, session, and declarative Base for the FastAPI application.

This module is the single source of truth for the database connection.
All models import Base from here; all services/routes use the db proxy
in extensions.py (which wraps ScopedSession).
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session, DeclarativeBase
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///Asfalis.db')

# Render (and some older tooling) uses postgres:// — SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

if _IS_SQLITE:
    # SQLite: NullPool creates a fresh connection per session — no pool to ping.
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
else:
    # PostgreSQL (Supabase / Production):
    # - Using port 6543 (Transaction Pooler):
    #   We MUST use NullPool because the Supabase pooler handles the actual
    #   connection pooling. SQLAlchemy's local QueuePool conflicts with it,
    #   causing "SSL connection has been closed unexpectedly" errors.
    # - pool_pre_ping: validate before use (still good practice)
    # - sslmode=require: enforced for Supabase pooler connections.
    # - connect_timeout: prevent hanging on initial handshake.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args={
            "sslmode": "require",
            "connect_timeout": 10
        },
    )

from contextvars import ContextVar
import uuid

# ContextVar-based scope function — ensures each request gets a unique session,
# even when FastAPI switches threads or uses a threadpool.
_session_id = ContextVar("session_id", default=None)

def _get_session_id():
    # If no ID exists in context, create one. The middleware in main.py
    # will initialize this for every HTTP request.
    sid = _session_id.get()
    if sid is None:
        sid = str(uuid.uuid4())
        _session_id.set(sid)
    return sid

_SessionFactory = sessionmaker(bind=engine, autoflush=True, autocommit=False)

# Scoped session using our ContextVar scope — isolation per request.
ScopedSession = scoped_session(_SessionFactory, scopefunc=_get_session_id)



class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── Flask-SQLAlchemy compat ──────────────────────────────────────────────────
# Adds a Model.query = ScopedSession.query_property() on every model class
# so legacy code like TrustedContact.query.filter_by(...).first() still works.
Base.query = ScopedSession.query_property()  # type: ignore[attr-defined]


# ── FastAPI dependency ───────────────────────────────────────────────────────
def get_db():
    """
    FastAPI dependency that yields the thread-local scoped session.

    The middleware in main.py calls ScopedSession.remove() after every request
    so connections are returned to the pool automatically.  This function can
    optionally be injected into route functions that want an explicit session
    reference, but most routes use the global db proxy from extensions.py.
    """
    try:
        yield ScopedSession
    finally:
        ScopedSession.remove()
