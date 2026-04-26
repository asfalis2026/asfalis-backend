"""
FastAPI application factory — replaces Flask's app/__init__.py create_app().

Mounts:
  - CORSMiddleware
  - SlowAPI rate limiting
  - DB session cleanup middleware
  - Socket.IO ASGI app at /socket.io/
  - All 9 APIRouters under /api/
  - /health endpoint
  - Global HTTP exception handler that wraps errors in Asfalis JSON format
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import socketio

from app.config import Config
from app.database import ScopedSession, engine, Base

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Keepalive ping (prevents Render free-tier spin-down) ─────────────────────
async def _keepalive_ping():
    """Ping own /health every 30 s to prevent Render free-tier idle shutdown."""
    await asyncio.sleep(15)  # let the server finish starting up first
    service_url = os.environ.get("RENDER_EXTERNAL_URL")  # injected automatically by Render
    if not service_url:
        return  # not running on Render — no-op locally
    url = f"{service_url}/health"
    logger.info(f"Keepalive ping active → {url}")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.get(url, timeout=10)
            except Exception:
                pass  # network hiccup — just retry next cycle
            await asyncio.sleep(30)


# ── Lifespan: startup / shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Create tables on startup (Alembic handles production migrations)."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified.")
    except Exception as e:
        logger.warning(f"DB create_all skipped: {e}")
    asyncio.create_task(_keepalive_ping())  # keeps Render free-tier awake
    yield
    ScopedSession.remove()
    logger.info("Application shutdown.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Asfalis Women Safety API",
    description=(
        "## Asfalis Personal Safety Backend\n\n"
        "Backend API for the Asfalis Android safety application. "
        "All endpoints are prefixed with `/api/`.\n\n"
        "---\n\n"
        "### 🔐 Authentication\n"
        "Most endpoints require a **Bearer Token** in the `Authorization` header. "
        "Obtain tokens via `POST /api/auth/login/phone` or `POST /api/auth/verify-phone-otp`.\n\n"
        "---\n\n"
        "### 🚨 SOS Flows\n\n"
        "**Flow 1 — Manual SOS** (`trigger_type: 'manual' | 'iot_button'`)\n"
        "1. App calls `POST /sos/trigger` → countdown starts\n"
        "2. If not cancelled → app calls `POST /sos/send-now` → WhatsApp sent\n"
        "3. Cancel during countdown → 'I am Safe' WhatsApp sent to contacts\n\n"
        "**Flow 2 — Auto SOS** (`trigger_type: 'auto_fall' | 'auto_shake'`)\n"
        "1. App detects magnitude spike → calls `POST /protection/predict` (or `/sensor-data`)\n"
        "2. Backend predicts DANGER based on magnitude → starts countdown + sends FCM push\n"
        "3. If not cancelled → app calls `POST /sos/send-now`\n"
        "4. Cancel → cancels countdown, no WhatsApp sent\n\n"
        "**Flow 3 — Hardware Auto Distress** (`trigger_type: 'hardware_distress'`)\n"
        "1. App detects bracelet disconnect / out-of-radius → waits 10s for reconnect\n"
        "2. No reconnect → app calls `POST /sos/trigger` with `hardware_distress`\n"
        "3. Backend starts 10s countdown → app calls `POST /sos/send-now` if not cancelled\n"
        "4. Cancel → countdown cancelled, no WhatsApp message (app handles reconnect)\n"
    ),
    version="2.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB session cleanup middleware ─────────────────────────────────────────────
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    from app.database import _session_id
    import uuid
    # Set a unique session ID for this request context BEFORE running the route.
    # The synchronous route in the threadpool will inherit this ContextVar.
    token = _session_id.set(str(uuid.uuid4()))
    try:
        response = await call_next(request)
        return response
    finally:
        # Now remove() will target the exact session used by the route.
        ScopedSession.remove()
        # Reset the ContextVar to prevent cross-request leakage in the event loop.
        _session_id.reset(token)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": {"code": "INTERNAL_SERVER_ERROR",
                                              "message": "An unexpected error occurred."}},
    )

from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    # Wrap FastAPI HTTPExceptions in Asfalis JSON format
    detail = exc.detail
    if isinstance(detail, dict):
        content = {"success": False, "error": detail}
    else:
        content = {"success": False, "error": {"code": "HTTP_ERROR", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=content)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Wrap FastAPI validation errors in Asfalis JSON format."""
    # Extract first error for a cleaner response
    errors = exc.errors()
    msg = "Invalid request properties."
    if errors:
        first = errors[0]
        # loc[0] is often 'body', loc[1] is the field name
        field = first.get('loc', ['?'])[-1]
        raw_msg = first.get('msg', 'Validation error')
        msg = f"Validation failed for '{field}': {raw_msg}"

    return JSONResponse(
        status_code=422,
        content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": msg}}
    )


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {"status": "healthy", "service": "Asfalis-backend", "database": db_status}


# ── Socket.IO ASGI mount ──────────────────────────────────────────────────────
from app.extensions import sio
from app.sockets import location_socket  # register socket event handlers

socketio_app = socketio.ASGIApp(sio, other_asgi_app=app)

# ── Register all routers ──────────────────────────────────────────────────────
from app import models as _all_models  # ensure all models are registered for Base.metadata.create_all()
from app.routes import auth, user, contacts, sos, protection, location, settings, device, support

app.include_router(auth.router,        prefix="/api/auth",       tags=["Auth"])
app.include_router(user.router,        prefix="/api/user",       tags=["User"])
app.include_router(contacts.router,    prefix="/api/contacts",  tags=["Contacts"])
app.include_router(sos.router,         prefix="/api/sos",        tags=["SOS"])
app.include_router(protection.router,  prefix="/api/protection", tags=["Protection"])
app.include_router(location.router,    prefix="/api/location",   tags=["Location"])
app.include_router(settings.router,    prefix="/api/settings",   tags=["Settings"])
app.include_router(device.router,      prefix="/api/device",     tags=["Device"])
app.include_router(support.router,     prefix="/api/support",    tags=["Support"])

