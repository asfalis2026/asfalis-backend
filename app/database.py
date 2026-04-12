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
    # PostgreSQL (Render / production):
    # - pool_size=5      : keep 5 persistent connections (matches Render free tier)
    # - max_overflow=10  : allow 10 burst connections under load
    # - pool_recycle=280 : recycle before Render's 300s idle timeout kills them
    # - pool_timeout=20  : raise instead of hanging 30s when pool is exhausted
    # - pool_pre_ping    : validate connection before use (catches dead sockets)
    # - statement_timeout: kill hung PG queries after 15s so they release the connection
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=280,
        pool_timeout=20,
        connect_args={"options": "-c statement_timeout=15000"},  # 15s PG statement timeout
    )

_SessionFactory = sessionmaker(bind=engine, autoflush=True, autocommit=False)

# Thread-local scoped session — each request/thread gets its own isolated session.
# This mirrors Flask-SQLAlchemy's behaviour so services need no changes.
ScopedSession = scoped_session(_SessionFactory)



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
