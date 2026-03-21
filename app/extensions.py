"""
Flask-SQLAlchemy compatibility proxy + Socket.IO server.

Provides:
  db         — thin proxy around ScopedSession so services can keep using
               db.session.add(), db.session.commit(), db.session.get() etc.
  sio        — python-socketio AsyncServer (replaces Flask-SocketIO)
  socketio   — alias for sio (backward compat with location_service.py)
"""

from app.database import ScopedSession
from sqlalchemy import text
import socketio as _socketio_lib

# ── Database proxy (Flask-SQLAlchemy style) ──────────────────────────────────

class _DBProxy:
    """
    Minimal proxy that delegates to the thread-local ScopedSession so all
    existing service/route code that uses `db.session.add(...)` continues
    to work without modification.
    """

    @property
    def session(self):
        return ScopedSession

    @staticmethod
    def text(t):
        return text(t)


db = _DBProxy()

# ── Socket.IO (async ASGI) ────────────────────────────────────────────────────

sio = _socketio_lib.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False,
)

# Backward-compat alias used by location_service.py
socketio = sio
