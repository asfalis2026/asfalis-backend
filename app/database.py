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

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///Asfalis.db')

# Render (and some older tooling) uses postgres:// — SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    # pool_pre_ping keeps connections fresh after DB restarts
    pool_pre_ping=True,
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
