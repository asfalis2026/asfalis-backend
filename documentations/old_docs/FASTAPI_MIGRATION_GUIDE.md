# Flask → FastAPI Migration Guide
### Asfalis Backend — Complete Step-by-Step Playbook

> **Scope:** Full migration keeping the same PostgreSQL schema, Alembic migrations, SQLAlchemy models, ML model, Twilio SMS/WhatsApp services, and Firebase FCM service untouched.  
> **Estimated effort:** ~2–3 weeks for a single developer.  
> **Zero downtime strategy:** Run old Flask app on the existing Render service until FastAPI passes all tests, then swap.

---

## Table of Contents

1. [What Changes / What Stays](#1-what-changes--what-stays)
2. [New Project Structure](#2-new-project-structure)
3. [Dependencies](#3-dependencies)
4. [Configuration (Pydantic Settings)](#4-configuration-pydantic-settings)
5. [Database Layer — Zero Changes](#5-database-layer--zero-changes)
6. [App Entry Point](#6-app-entry-point)
7. [JWT Authentication](#7-jwt-authentication)
8. [Pydantic Schemas (replacing Marshmallow)](#8-pydantic-schemas-replacing-marshmallow)
9. [Route-by-Route Migration](#9-route-by-route-migration)
   - [9.1 Auth](#91-auth-routes)
   - [9.2 SOS](#92-sos-routes)
   - [9.3 Protection (ML / Auto SOS)](#93-protection-routes)
   - [9.4 Contacts](#94-contacts-routes)
   - [9.5 Location](#95-location-routes)
   - [9.6 Settings, User, Device, Support](#96-settings-user-device-support-routes)
10. [WebSocket — Location Socket](#10-websocket--location-socket)
11. [Rate Limiting](#11-rate-limiting)
12. [Services — No Changes Required](#12-services--no-changes-required)
13. [ML Model — No Changes Required](#13-ml-model--no-changes-required)
14. [Utilities Migration](#14-utilities-migration)
15. [Deployment Updates](#15-deployment-updates)
16. [Testing](#16-testing)
17. [Migration Checklist](#17-migration-checklist)

---

## 1. What Changes / What Stays

### ✅ Stays Exactly the Same (zero edits needed)
| Component | Reason |
|---|---|
| `DATABASE_URL` in `.env` | Same PostgreSQL connection string |
| All `app/models/*.py` | SQLAlchemy models are framework-agnostic |
| All `migrations/` (Alembic) | Alembic doesn't depend on Flask |
| `app/services/fcm_service.py` | Pure Firebase Admin SDK |
| `app/services/sms_service.py` | Pure Twilio SDK |
| `app/services/whatsapp_service.py` | Pure Twilio SDK |
| `app/services/sos_service.py` | Uses SQLAlchemy directly |
| `app/services/location_service.py` | Uses SQLAlchemy directly |
| `app/services/protection_service.py` | Uses scikit-learn + SQLAlchemy |
| `app/utils/timezone_utils.py` | Pure Python |
| `app/utils/validators.py` | Pure Python |
| `app/utils/otp.py` | Pure Python + SQLAlchemy |
| `scripts/` | Standalone scripts |
| ML model binary in DB | Same `MLModel` SQLAlchemy model |

### 🔄 Must Be Rewritten
| Flask Component | FastAPI Replacement |
|---|---|
| `app/__init__.py` (factory) | `main.py` (FastAPI app instance) |
| `app/config.py` (plain class) | `app/config.py` (Pydantic `BaseSettings`) |
| `app/extensions.py` | Removed — no global extension objects needed |
| `Flask-JWT-Extended` | `python-jose` + custom `Depends()` |
| `Flask-SocketIO` | `python-socketio` (ASGI mode) |
| `Flask-Limiter` | `slowapi` |
| `Flask-CORS` | `fastapi.middleware.cors.CORSMiddleware` |
| `Flask-Migrate` | Alembic CLI directly (Flask-Migrate was just a CLI wrapper) |
| Marshmallow schemas | Pydantic v2 models |
| Route blueprints → decorators | FastAPI `APIRouter` |
| `app/utils/decorators.py` | FastAPI `Depends()` functions |
| `wsgi.py` | `main.py` (ASGI, run with `uvicorn`) |
| `gunicorn` | `uvicorn` (or `gunicorn + uvicorn worker`) |

---

## 2. New Project Structure

Keep everything under `app/` but replace the Flask plumbing:

```
asfalis-backend/              # (same root)
├── main.py                   # NEW — replaces wsgi.py
├── app/
│   ├── config.py             # REWRITE — Pydantic BaseSettings
│   ├── database.py           # NEW — SQLAlchemy engine + session
│   ├── dependencies.py       # NEW — shared FastAPI Depends (auth, db, etc.)
│   ├── models/               # UNCHANGED
│   ├── routers/              # RENAMED from routes/
│   │   ├── auth.py
│   │   ├── sos.py
│   │   ├── contacts.py
│   │   ├── location.py
│   │   ├── protection.py
│   │   ├── settings.py
│   │   ├── user.py
│   │   ├── device.py
│   │   └── support.py
│   ├── schemas/              # REWRITE — Pydantic instead of Marshmallow
│   │   ├── auth_schema.py
│   │   ├── sos_schema.py
│   │   ├── contact_schema.py
│   │   ├── protection_schema.py
│   │   ├── settings_schema.py
│   │   └── user_schema.py
│   ├── services/             # UNCHANGED
│   ├── sockets/              # REWRITE — python-socketio ASGI
│   │   └── location_socket.py
│   └── utils/                # MOSTLY UNCHANGED
│       ├── timezone_utils.py
│       ├── validators.py
│       └── otp.py
├── migrations/               # UNCHANGED
├── requirements.txt          # REWRITE
├── Dockerfile                # MINOR EDIT
└── render.yaml               # MINOR EDIT
```

---

## 3. Dependencies

Replace `requirements.txt` entirely:

```txt
# Core
fastapi==0.115.0
uvicorn[standard]==0.30.0

# Database (same as before — zero schema changes)
SQLAlchemy==2.0.38
psycopg2-binary==2.9.11
alembic==1.13.1

# Authentication
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.2.1

# Validation (replaces Marshmallow)
pydantic==2.7.0
pydantic-settings==2.3.0

# WebSocket (replaces Flask-SocketIO)
python-socketio==5.11.3

# Rate Limiting (replaces Flask-Limiter)
slowapi==0.1.9

# Services — no version changes needed
twilio==9.4.6
firebase-admin==6.6.0
resend==2.0.0

# ML (unchanged)
numpy>=1.24.0
scikit-learn>=1.3.0
joblib>=1.3.0
pandas>=2.0.0

# Utilities
python-dotenv==1.0.1
pytz==2024.1

# Testing
pytest==8.0.0
httpx==0.27.0           # replaces flask test client
pytest-asyncio==0.23.0
```

Install:
```bash
pip install -r requirements.txt
```

---

## 4. Configuration (Pydantic Settings)

**Replace** `app/config.py` entirely. The `.env` file stays **100% identical**.

```python
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import timedelta
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Flask → FastAPI: SECRET_KEY becomes app secret
    SECRET_KEY: str = "dev-secret-key"
    DATABASE_URL: str = "sqlite:///Asfalis.db"

    # JWT
    JWT_SECRET_KEY: str = "jwt-secret-key"
    JWT_ACCESS_TOKEN_EXPIRES: int = 900        # seconds
    JWT_REFRESH_TOKEN_EXPIRES: int = 2592000   # seconds
    JWT_SOS_TOKEN_EXPIRES_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # OTP
    OTP_EXPIRY_SECONDS: int = 300
    MAX_OTP_ATTEMPTS: int = 5

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # Twilio WhatsApp
    TWILIO_WA_ACCOUNT_SID: str = ""
    TWILIO_WA_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    TWILIO_SANDBOX_CODE: str = ""

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""

    # App behaviour
    MAX_TRUSTED_CONTACTS: int = 5
    SOS_COOLDOWN_SECONDS: int = 20
    SOS_COUNTDOWN_SECONDS: int = 10
    IMEI_BINDING_ENABLED: bool = False
    IOT_DOUBLE_TAP_WINDOW_SECONDS: float = 1.5

    # Resend (Email)
    RESEND_API_KEY: str = ""

@lru_cache
def get_settings() -> Settings:
    return Settings()

# Singleton used by services that don't have DI (e.g. fcm_service.py)
# This keeps fcm_service.py and other services UNCHANGED.
Config = get_settings()
```

> **Why this works:** `fcm_service.py` does `from app.config import Config` and reads `Config.FIREBASE_CREDENTIALS_PATH`. The singleton `Config = get_settings()` at the bottom satisfies this import with zero changes to the service files.

---

## 5. Database Layer — Zero Changes

All SQLAlchemy models stay byte-for-byte identical. You only need a new **session factory** file.

```python
# app/database.py  (NEW FILE)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

settings = get_settings()

# Use same DATABASE_URL from .env
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,         # detect stale connections
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """FastAPI dependency — yields a DB session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Alembic — Stays the Same

`migrations/` is completely untouched. The only change: you no longer run `flask db upgrade`. Instead:

```bash
# Before: flask db upgrade
# After:
alembic upgrade head

# Before: flask db migrate -m "message"
# After:
alembic revision --autogenerate -m "message"
```

Update `migrations/env.py` to remove Flask dependency:

```python
# migrations/env.py  — replace the Flask-specific section at the top
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv
import os

load_dotenv()

# Import ALL models so Alembic can detect them
from app.models import *  # noqa — triggers all model imports
from app.extensions_compat import db  # see Step 6

config = context.config
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata  # same as before
```

---

## 6. App Entry Point

### Compatibility shim for services (keeps service files unchanged)

The services import `from app.extensions import db`. Create a thin compatibility module:

```python
# app/extensions_compat.py  (NEW FILE)
"""
Compatibility shim so existing services/models can keep doing:
    from app.extensions import db
without any changes.
"""
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Fake 'db' object that exposes .metadata and .Model
# SQLAlchemy 2.x models use Base directly, but old models use db.Model
class _FakeDB:
    Model = Base
    metadata = Base.metadata

db = _FakeDB()
```

> **Note:** If your models already use `db.Column`, `db.Model` from Flask-SQLAlchemy, the cleanest approach is to swap to pure SQLAlchemy declarative base instead. See **Step 5a** below.

### Step 5a — Update models to pure SQLAlchemy (one-time find/replace)

In each model file, replace the imports:

```python
# OLD (Flask-SQLAlchemy)
from app.extensions import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), ...)

# NEW (pure SQLAlchemy 2.x — same schema, just different import)
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float, LargeBinary
from sqlalchemy.orm import relationship
from app.database import Base   # shared declarative base
import uuid
from datetime import datetime

class User(Base):
    __tablename__ = 'users'
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # ... rest of columns unchanged
```

Run this find-replace across all files in `app/models/`:

| Find | Replace |
|---|---|
| `from app.extensions import db` | `from sqlalchemy import Column, String, Boolean, DateTime, Enum, Float, LargeBinary; from app.database import Base` |
| `db.Model` | `Base` |
| `db.Column(` | `Column(` |
| `db.String(` | `String(` |
| `db.Boolean(` | `Boolean(` |
| `db.DateTime(` | `DateTime(` |
| `db.Float(` | `Float(` |
| `db.LargeBinary(` | `LargeBinary(` |
| `db.relationship(` | `relationship(` |
| `db.session` | `# inject session via Depends(get_db) in routes` |

### Main Application File

```python
# main.py  (replaces wsgi.py)
from dotenv import load_dotenv
load_dotenv()

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import get_settings
from app.routers import auth, user, contacts, sos, location, settings, device, support, protection

settings_obj = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Asfalis FastAPI starting up")
    yield
    # Shutdown
    logging.info("Asfalis FastAPI shutting down")

app = FastAPI(
    title="Asfalis Safety API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS (replaces Flask-CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (replaces Flask-Limiter)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register routers (same URL prefixes)
app.include_router(auth.router,       prefix="/api/auth")
app.include_router(user.router,       prefix="/api/user")
app.include_router(contacts.router,   prefix="/api/contacts")
app.include_router(sos.router,        prefix="/api/sos")
app.include_router(location.router,   prefix="/api/location")
app.include_router(settings.router,   prefix="/api/settings")
app.include_router(device.router,     prefix="/api/device")
app.include_router(support.router,    prefix="/api/support")
app.include_router(protection.router, prefix="/api/protection")

@app.get("/health")
def health():
    return {"status": "ok"}

# Mount Socket.IO app (replaces Flask-SocketIO)
import socketio as sio_module
from app.sockets.location_socket import sio
socket_app = sio_module.ASGIApp(sio, other_asgi_app=app)

# Use socket_app as the ASGI entrypoint in uvicorn/gunicorn
```

---

## 7. JWT Authentication

### Dependency functions (replaces `@jwt_required()`)

```python
# app/dependencies.py  (NEW FILE)
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer()

class TokenError(HTTPException):
    pass

def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_EXPIRED", "message": "Your session has expired. Please refresh your token."}
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_INVALID", "message": "Invalid or malformed token. Please log in again."}
        )

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    """Replaces @jwt_required() + get_jwt_identity()."""
    payload = _decode_token(credentials.credentials)

    # Check revoked refresh tokens (same RevokedToken model)
    if payload.get("type") == "refresh":
        from app.models.revoked_token import RevokedToken
        jti = payload.get("jti")
        if db.query(RevokedToken).filter_by(jti=jti).first():
            raise HTTPException(
                status_code=401,
                detail={"code": "REFRESH_TOKEN_REUSED", "message": "Token has been revoked."}
            )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token subject."})
    return user_id

def get_current_user_id_from_sos_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """SOS token validation — same logic, just checks token_purpose claim."""
    payload = _decode_token(credentials.credentials)
    # sos_token has additional_claims={"token_purpose": "sos"}
    # We accept both regular access tokens and sos tokens for /sos/trigger
    return payload.get("sub")

def create_access_token(user_id: str, expires_delta=None, additional_claims=None) -> str:
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    expire_seconds = expires_delta or settings.JWT_ACCESS_TOKEN_EXPIRES
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expire_seconds),
        "type": "access",
        **(additional_claims or {})
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    import uuid
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=settings.JWT_REFRESH_TOKEN_EXPIRES),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```

---

## 8. Pydantic Schemas (replacing Marshmallow)

Marshmallow `Schema` → Pydantic `BaseModel`. The field names and validation rules stay identical.

```python
# app/schemas/auth_schema.py
import re
from pydantic import BaseModel, field_validator
from typing import Optional

E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')

def _validate_e164(v: str) -> str:
    if not E164_RE.match(v):
        raise ValueError("Phone number must be in E.164 format (e.g. +919876543210).")
    return v

class PhoneRegisterSchema(BaseModel):
    full_name: str
    phone_number: str
    country: str
    password: str

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v): return _validate_e164(v)

    @field_validator('full_name')
    @classmethod
    def validate_name(cls, v):
        if len(v) < 2: raise ValueError("full_name must be at least 2 characters")
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8: raise ValueError("password must be at least 8 characters")
        return v

class PhoneLoginSchema(BaseModel):
    phone_number: str
    password: str
    device_imei: Optional[str] = None
    confirm_handover: bool = False

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v): return _validate_e164(v)

class VerifyPhoneOTPSchema(BaseModel):
    phone_number: str
    otp_code: str

    @field_validator('otp_code')
    @classmethod
    def validate_otp(cls, v):
        if len(v) != 6: raise ValueError("otp_code must be exactly 6 characters")
        return v

class ResendOTPSchema(BaseModel):
    phone_number: str

class ForgotPasswordSchema(BaseModel):
    phone_number: str

class ResetPasswordSchema(BaseModel):
    phone_number: str
    otp_code: str
    new_password: str

class RefreshTokenSchema(BaseModel):
    refresh_token: str

# app/schemas/sos_schema.py
class SOSTriggerSchema(BaseModel):
    latitude: float = 0.0
    longitude: float = 0.0
    trigger_type: str = "manual"

class SOSActionSchema(BaseModel):
    alert_id: str

class SOSFeedbackSchema(BaseModel):
    alert_id: str
    feedback: str  # "false_alarm" | "confirmed_danger"
```

---

## 9. Route-by-Route Migration

### 9.1 Auth Routes

**Pattern:** `Blueprint` → `APIRouter`, `@jwt_required()` → `Depends(get_current_user_id)`, `request.json` → Pydantic body parameter, `jsonify(...)` → `dict` return (FastAPI auto-serializes).

```python
# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.dependencies import get_current_user_id, create_access_token, create_refresh_token
from app.schemas.auth_schema import PhoneRegisterSchema, PhoneLoginSchema, VerifyPhoneOTPSchema, ResendOTPSchema
from app.models.user import User
from app.models.settings import UserSettings
from app.models.revoked_token import RevokedToken
from app.config import get_settings

settings_obj = get_settings()
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# ── Register ──────────────────────────────────────────────────────────
@router.post("/register")
@limiter.limit("5/minute")  # replaces @limiter.limit on Flask route
async def register(request: Request, body: PhoneRegisterSchema, db: Session = Depends(get_db)):
    # Same logic as Flask auth.py register() — just swap:
    #   User.query.filter_by(...) → db.query(User).filter_by(...)
    #   db.session.add(user)     → db.add(user)
    #   db.session.commit()      → db.commit()
    #   return jsonify(...)      → return {"status": "success", "data": {...}}
    existing = db.query(User).filter_by(phone=body.phone_number).first()
    if existing:
        raise HTTPException(status_code=409, detail={"code": "PHONE_EXISTS", "message": "Phone already registered."})
    # ... rest of logic identical
    return {"status": "success", "message": "OTP sent to your phone."}

# ── Login ─────────────────────────────────────────────────────────────
@router.post("/login")
async def login(body: PhoneLoginSchema, db: Session = Depends(get_db)):
    # Same logic — copy from Flask version, replace db.session → db
    ...

# ── Verify OTP ────────────────────────────────────────────────────────
@router.post("/verify-otp")
async def verify_otp(body: VerifyPhoneOTPSchema, db: Session = Depends(get_db)):
    ...

# ── Me ────────────────────────────────────────────────────────────────
@router.get("/me")
async def me(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter_by(id=current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found."})
    return {"status": "success", "data": user.to_dict()}

# ── Logout ────────────────────────────────────────────────────────────
@router.post("/logout")
async def logout(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    # Revoke refresh token — same RevokedToken model
    ...
    return {"status": "success", "message": "Logged out."}

# ── Refresh ───────────────────────────────────────────────────────────
@router.post("/refresh")
async def refresh_token(
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    new_access = create_access_token(current_user_id)
    return {"status": "success", "data": {"access_token": new_access}}
```

> **SQLAlchemy session swap table** — apply everywhere:

| Flask-SQLAlchemy | FastAPI + SQLAlchemy (db from `Depends(get_db)`) |
|---|---|
| `User.query.get(id)` | `db.get(User, id)` |
| `User.query.filter_by(phone=x).first()` | `db.query(User).filter_by(phone=x).first()` |
| `User.query.all()` | `db.query(User).all()` |
| `db.session.add(obj)` | `db.add(obj)` |
| `db.session.commit()` | `db.commit()` |
| `db.session.delete(obj)` | `db.delete(obj)` |
| `db.session.refresh(obj)` | `db.refresh(obj)` |

---

### 9.2 SOS Routes

```python
# app/routers/sos.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.sos_schema import SOSTriggerSchema, SOSActionSchema
from app.services.sos_service import trigger_sos, dispatch_sos, cancel_sos, mark_user_safe
from app.models.trusted_contact import TrustedContact
from app.models.user import User
from app.config import get_settings
from app.utils.timezone_utils import format_datetime_for_response, get_timezone_for_country

settings_obj = get_settings()
router = APIRouter()

def _serialize_sos_alert(alert, user_country):
    tz_zone = get_timezone_for_country(user_country).zone if user_country else 'UTC'
    return {
        'alert_id': alert.id,
        'trigger_type': alert.trigger_type,
        'address': alert.address,
        'status': alert.status,
        'triggered_at': format_datetime_for_response(alert.triggered_at, user_country),
        'sent_at': format_datetime_for_response(alert.sent_at, user_country),
        'resolved_at': format_datetime_for_response(alert.resolved_at, user_country),
        'resolution_type': alert.resolution_type,
        'timezone': tz_zone,
    }

@router.post("/trigger", status_code=201)
async def trigger(
    body: SOSTriggerSchema,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    contact_count = db.query(TrustedContact).filter_by(user_id=current_user_id).count()
    if contact_count == 0:
        raise HTTPException(status_code=400, detail={"code": "NO_CONTACTS", "message": "Add at least one emergency contact first."})

    # sos_service.py is UNCHANGED — it uses its own db session internally.
    # Pass the same parameters as before.
    alert, msg = trigger_sos(current_user_id, body.latitude, body.longitude, body.trigger_type)
    if not alert:
        raise HTTPException(status_code=400, detail={"code": "ERROR", "message": msg})

    user = db.get(User, current_user_id)
    payload = _serialize_sos_alert(alert, user.country if user else None)
    payload['countdown_seconds'] = settings_obj.SOS_COUNTDOWN_SECONDS
    payload['contacts_to_notify'] = contact_count
    return {"success": True, "data": payload, "message": msg}

@router.post("/send-now")
async def send_now(
    body: SOSActionSchema,
    current_user_id: str = Depends(get_current_user_id),
):
    success, msg, delivery_report = dispatch_sos(body.alert_id, current_user_id)
    if not success:
        raise HTTPException(status_code=400, detail={"code": "ERROR", "message": msg})
    return {"success": True, "message": msg, "delivery_report": delivery_report}

@router.post("/cancel")
async def cancel(
    body: SOSActionSchema,
    current_user_id: str = Depends(get_current_user_id),
):
    success, msg = cancel_sos(body.alert_id, current_user_id)
    if not success:
        raise HTTPException(status_code=400, detail={"code": "ERROR", "message": msg})
    return {"success": True, "message": msg}

@router.post("/safe")
async def safe(
    body: SOSActionSchema,
    current_user_id: str = Depends(get_current_user_id),
):
    success, msg, contacts_notified = mark_user_safe(body.alert_id, current_user_id)
    if not success:
        raise HTTPException(status_code=400, detail={"code": "ERROR", "message": msg})
    return {"success": True, "message": msg, "contacts_notified": contacts_notified}
```

---

### 9.3 Protection Routes

The `protection_service.py` is **unchanged** (pure Python + SQLAlchemy). Only the route layer changes.

```python
# app/routers/protection.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.protection_schema import ToggleProtectionSchema, SensorDataSchema, SensorWindowSchema
from app.services.protection_service import (
    toggle_protection, get_protection_status,
    analyze_sensor_data, predict_from_window, submit_sos_feedback
)

router = APIRouter()

@router.post("/toggle")
async def toggle(
    body: ToggleProtectionSchema,
    current_user_id: str = Depends(get_current_user_id),
):
    success, msg = toggle_protection(current_user_id, body.is_active)
    status = get_protection_status(current_user_id)
    return {"success": True, "data": status, "message": msg}

@router.get("/status")
async def status(current_user_id: str = Depends(get_current_user_id)):
    return {"success": True, "data": get_protection_status(current_user_id)}

@router.post("/sensor-data")
async def sensor_data(
    body: SensorDataSchema,
    background_tasks: BackgroundTasks,    # <-- FastAPI bonus: run ML in background
    current_user_id: str = Depends(get_current_user_id),
):
    # analyze_sensor_data is CPU-bound — run in thread pool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        analyze_sensor_data,
        current_user_id, body.sensor_type, body.data, body.sensitivity
    )
    return {"success": True, "data": result}

@router.post("/predict")
async def predict(
    body: SensorWindowSchema,
    current_user_id: str = Depends(get_current_user_id),
):
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, predict_from_window,
        current_user_id, body.window, body.sensor_type,
        body.location, body.latitude, body.longitude
    )
    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result)
    return result

@router.post("/feedback")
async def feedback(
    body: dict,
    current_user_id: str = Depends(get_current_user_id),
):
    success, msg = submit_sos_feedback(current_user_id, body.get('alert_id'), body.get('feedback'))
    if not success:
        raise HTTPException(status_code=400, detail={"code": "ERROR", "message": msg})
    return {"success": True, "message": msg}
```

> **Key improvement over Flask:** `run_in_executor` runs the scikit-learn prediction in a thread pool without blocking the event loop. In Flask, ML inference blocked the entire Gunicorn thread.

---

### 9.4 Contacts Routes

```python
# app/routers/contacts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user_id

router = APIRouter()

# Follow same pattern as auth.py:
# - Replace Blueprint → APIRouter
# - Replace @jwt_required() → Depends(get_current_user_id)
# - Replace request.json → Pydantic body param
# - Replace User.query.* → db.query(User).*
# - Replace jsonify() → return dict
```

---

### 9.5 Location Routes

```python
# app/routers/location.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user_id
from app.services.location_service import update_location

router = APIRouter()

@router.post("/update")
async def update(
    body: dict,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # location_service.py is UNCHANGED
    result = update_location(
        current_user_id,
        body.get('latitude'), body.get('longitude'),
        body.get('accuracy'), body.get('altitude'),
    )
    return {"success": True, "data": result}
```

---

### 9.6 Settings, User, Device, Support Routes

Apply the same mechanical replacement for the remaining 4 routers:

```python
# app/routers/settings.py  |  user.py  |  device.py  |  support.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user_id

router = APIRouter()

# All endpoints: same URL paths, same business logic.
# Only the plumbing changes (see pattern above).
```

---

## 10. WebSocket — Location Socket

`Flask-SocketIO` → `python-socketio` in **ASGI mode**. The event names, room logic, and JWT decode all stay the same.

```python
# app/sockets/location_socket.py  (REWRITE — same logic, ASGI mount)
import socketio
from jose import jwt, JWTError
from app.config import get_settings
from app.services.location_service import update_location
from app.database import SessionLocal
from app.models.trusted_contact import TrustedContact
from app.models.user import User

settings_obj = get_settings()

# Create AsyncServer (ASGI-compatible) — replaces Flask-SocketIO
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
)

def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings_obj.JWT_SECRET_KEY, algorithms=[settings_obj.JWT_ALGORITHM])
    except JWTError:
        return None

@sio.event(namespace='/location')
async def connect(sid, environ, auth):
    """Replaces @socketio.on('connect', namespace='/location')"""
    # Token comes from query string: ?token=xxx
    from urllib.parse import parse_qs
    qs = environ.get('QUERY_STRING', '')
    token = parse_qs(qs).get('token', [None])[0]

    if not token:
        return False

    payload = _decode_token(token)
    if not payload:
        return False

    user_id = payload.get('sub')
    await sio.enter_room(sid, f"user_{user_id}", namespace='/location')
    await sio.emit('status', {'msg': 'Connected to location stream'}, to=sid, namespace='/location')
    # Save user_id in session for later events
    async with sio.session(sid, namespace='/location') as session:
        session['user_id'] = user_id

@sio.event(namespace='/location')
async def join_tracking(sid, data):
    """Replaces @socketio.on('join_tracking', namespace='/location')"""
    async with sio.session(sid, namespace='/location') as session:
        requester_id = session.get('user_id')

    if not requester_id or 'target_user_id' not in data:
        await sio.emit('error', {'msg': 'Missing token or target_user_id'}, to=sid, namespace='/location')
        return

    target_user_id = data['target_user_id']
    db = SessionLocal()
    try:
        if requester_id == target_user_id:
            await sio.enter_room(sid, f"tracking_{target_user_id}", namespace='/location')
            await sio.emit('joined', {'room': f"tracking_{target_user_id}"}, to=sid, namespace='/location')
            return

        requester = db.get(User, requester_id)
        if not requester:
            await sio.emit('error', {'msg': 'Requester not found'}, to=sid, namespace='/location')
            return

        contact = db.query(TrustedContact).filter_by(
            user_id=target_user_id, phone=requester.phone
        ).first()

        if contact:
            await sio.enter_room(sid, f"tracking_{target_user_id}", namespace='/location')
            await sio.emit('joined', {'room': f"tracking_{target_user_id}"}, to=sid, namespace='/location')
        else:
            await sio.emit('error', {'msg': 'Unauthorized: not a trusted contact'}, to=sid, namespace='/location')
    finally:
        db.close()

@sio.event(namespace='/location')
async def update_location_event(sid, data):
    """Receive location from device and broadcast to tracking room."""
    async with sio.session(sid, namespace='/location') as session:
        user_id = session.get('user_id')
    if not user_id:
        return
    # Emit to anyone tracking this user
    await sio.emit(
        'location_update',
        {'user_id': user_id, **data},
        room=f"tracking_{user_id}",
        namespace='/location',
    )

@sio.event(namespace='/location')
async def disconnect(sid):
    pass
```

Mount in `main.py` (already shown in Step 6):
```python
# At the bottom of main.py
import socketio as sio_module
from app.sockets.location_socket import sio
socket_app = sio_module.ASGIApp(sio, other_asgi_app=app)
# Run uvicorn with: uvicorn main:socket_app --host 0.0.0.0 --port 5000
```

---

## 11. Rate Limiting

`Flask-Limiter` → `slowapi` (same API surface, same decorator syntax).

```python
# In any router file:
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)

@router.post("/register")
@limiter.limit("5/minute")         # identical to Flask-Limiter syntax
async def register(request: Request, body: PhoneRegisterSchema, ...):
    ...
```

---

## 12. Services — No Changes Required

The following files require **zero edits**. They are pure Python + third-party SDKs with no Flask imports:

| File | Why it works unchanged |
|---|---|
| `app/services/fcm_service.py` | Uses `firebase_admin` SDK + `threading`. Imports `Config` — satisfied by `Config = get_settings()` singleton in `config.py`. |
| `app/services/sms_service.py` | Uses `twilio` SDK only |
| `app/services/whatsapp_service.py` | Uses `twilio` SDK only |
| `app/services/location_service.py` | Uses SQLAlchemy — opens its own session |
| `app/services/sos_service.py` | Same as above |
| `app/services/protection_service.py` | Same as above + scikit-learn |

**One exception:** Any service that calls `from flask import current_app` to read config must be updated:

```python
# OLD (in sos_service.py)
from flask import current_app
cooldown = current_app.config.get('SOS_COOLDOWN_SECONDS', 20)

# NEW
from app.config import get_settings
cooldown = get_settings().SOS_COOLDOWN_SECONDS
```

---

## 13. ML Model — No Changes Required

`app/models/ml_model.py` is a SQLAlchemy model — zero changes. The training scripts in `scripts/` are standalone and don't need changes. The ML inference in `protection_service.py` uses `joblib` and `scikit-learn` directly — no Flask dependency.

The only change is running predictions via `run_in_executor` (already shown in Step 9.3) to avoid blocking the async event loop.

---

## 14. Utilities Migration

### `app/utils/timezone_utils.py` — No changes
### `app/utils/validators.py` — No changes

### `app/utils/otp.py`
If it uses `db.session`, update to accept a `db: Session` parameter:

```python
# OLD
def store_otp(phone, code):
    from app.extensions import db
    ...
    db.session.add(otp)
    db.session.commit()

# NEW — accept db as param (pass from route via Depends)
def store_otp(phone: str, code: str, db: Session):
    ...
    db.add(otp)
    db.commit()
```

### `app/utils/decorators.py` — Replace with `Depends()`

```python
# OLD Flask decorator
@validate_schema(MySchema)
def my_route():
    ...

# NEW — Pydantic body parameter does this automatically
@router.post("/endpoint")
async def my_route(body: MySchema):  # validation is automatic
    ...
```

The `decorators.py` file is no longer needed.

---

## 15. Deployment Updates

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
# Changed: gunicorn with uvicorn worker instead of sync worker
CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000", "main:socket_app"]
```

### entrypoint.sh

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head      # replaces: flask db upgrade

echo "Starting application..."
exec "$@"
```

### render.yaml

```yaml
services:
  - type: web
    name: Asfalis-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    # Changed: alembic instead of flask db, uvicorn worker
    startCommand: alembic upgrade head && gunicorn -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT main:socket_app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: Asfalis-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: FIREBASE_CREDENTIALS_JSON
        sync: false
      - key: TWILIO_ACCOUNT_SID
        sync: false
      - key: TWILIO_AUTH_TOKEN
        sync: false
      - key: TWILIO_PHONE_NUMBER
        sync: false
      - key: TWILIO_WA_ACCOUNT_SID
        sync: false
      - key: TWILIO_WA_AUTH_TOKEN
        sync: false
      - key: RESEND_API_KEY
        sync: false
```

### Local development

```bash
# OLD
flask run --port 5001

# NEW
uvicorn main:socket_app --reload --port 5001
```

---

## 16. Testing

Replace `flask test client` with `httpx.AsyncClient`.

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app   # not socket_app — test HTTP only
from app.database import get_db, Base

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest_asyncio.fixture
async def client(db):
    def override_get_db():
        try: yield db
        finally: pass

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

```python
# tests/test_auth.py
import pytest

@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={
        "full_name": "Test User",
        "phone_number": "+919999999999",
        "country": "India",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
```

Run tests:
```bash
pytest tests/ -v
```

---

## 17. Migration Checklist

Work through these in order. Check off each item before moving to the next.

### Phase 1 — Foundation
- [ ] Create new virtualenv, install new `requirements.txt`
- [ ] Rewrite `app/config.py` → Pydantic `BaseSettings`
- [ ] Create `app/database.py` (SQLAlchemy engine + `get_db`)
- [ ] Update all `app/models/*.py` to pure SQLAlchemy (remove `db.Column` → `Column`, `db.Model` → `Base`)
- [ ] Update `migrations/env.py` to remove Flask imports
- [ ] Verify `alembic upgrade head` works (run against dev DB)

### Phase 2 — Core Auth
- [ ] Create `app/dependencies.py` (JWT `Depends` functions)
- [ ] Rewrite `app/schemas/auth_schema.py` → Pydantic
- [ ] Create `main.py` with bare FastAPI app + middleware
- [ ] Migrate `app/routers/auth.py`
- [ ] Test: register, login, verify-otp, me, logout, refresh

### Phase 3 — SOS & Protection (most critical)
- [ ] Rewrite `app/schemas/sos_schema.py` → Pydantic
- [ ] Migrate `app/routers/sos.py`
- [ ] Fix `current_app.config` references in `sos_service.py` → `get_settings()`
- [ ] Rewrite `app/schemas/protection_schema.py` → Pydantic
- [ ] Migrate `app/routers/protection.py` (add `run_in_executor` for ML)
- [ ] Test: trigger, send-now, cancel, safe, predict, feedback

### Phase 4 — Remaining Routes
- [ ] Migrate `app/routers/contacts.py`
- [ ] Migrate `app/routers/location.py`
- [ ] Migrate `app/routers/settings.py`
- [ ] Migrate `app/routers/user.py`
- [ ] Migrate `app/routers/device.py`
- [ ] Migrate `app/routers/support.py`

### Phase 5 — WebSocket
- [ ] Rewrite `app/sockets/location_socket.py` → `python-socketio` ASGI
- [ ] Mount `socket_app` in `main.py`
- [ ] Test: connect with token, join_tracking, location_update broadcast

### Phase 6 — Deploy
- [ ] Update `entrypoint.sh` (alembic instead of flask db)
- [ ] Update `Dockerfile` (uvicorn worker)
- [ ] Update `render.yaml` (alembic + uvicorn worker)
- [ ] Update `conftest.py` and all test files
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Deploy to new Render service (keep old service live until verified)
- [ ] Swap DNS / Render service

---

## Quick Reference: Key Equivalents

| Flask | FastAPI |
|---|---|
| `Blueprint('name', __name__)` | `APIRouter()` |
| `@bp.route('/path', methods=['POST'])` | `@router.post('/path')` |
| `@jwt_required()` | `current_user_id: str = Depends(get_current_user_id)` |
| `get_jwt_identity()` | `current_user_id` (parameter above) |
| `request.json` | Pydantic model parameter |
| `jsonify(success=True, data=x)` | `return {"success": True, "data": x}` |
| `return jsonify(...), 400` | `raise HTTPException(status_code=400, detail=...)` |
| `User.query.get(id)` | `db.get(User, id)` |
| `User.query.filter_by(x=y).first()` | `db.query(User).filter_by(x=y).first()` |
| `db.session.add(obj)` | `db.add(obj)` |
| `db.session.commit()` | `db.commit()` |
| `current_app.config.get('KEY')` | `get_settings().KEY` |
| `flask run` | `uvicorn main:socket_app --reload` |
| `flask db upgrade` | `alembic upgrade head` |
| `flask db migrate` | `alembic revision --autogenerate` |
| Auto docs: manual (POSTMAN_GUIDE.md) | Auto at `/docs` (Swagger UI) |
