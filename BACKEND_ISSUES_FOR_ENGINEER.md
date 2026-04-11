# 🔴 Asfalis Backend Issues — AI Handover Prompt
**From:** Frontend Architecture Team  
**Date:** 2026-04-09
**Purpose:** This document is written specifically to be fed into your AI coding assistant (e.g. Antigravity, Claude, ChatGPT). 

---

> [!NOTE]
> **Resolution Status (2026-04-11):** All 3 issues below have been fixed. See the resolution notes under each task.

### [AI INSTRUCTIONS: START]
**System Prompt:** You are an expert Python FastAPI backend developer working on the `Asfalis` project. The Android Frontend is currently 100% stable but is heavily blocked from integrating with your backend due to the following 3 critical architectural server errors. Your job is to systematically ingest the logs, identify the root causes in the FastAPI codebase, and fix them so the Frontend can resume testing.

---

## 🛑 TASK 1: Fix `POST /api/sos/send-now` Crash (`flask_jwt_extended` Error)
**Context:** When the Android app triggers an SOS, it hits the `send-now` endpoint. The server instantly crashes with a 500.

**Production Log:**
```python
Unhandled exception on POST https://asfalis-backend.onrender.com/api/sos/send-now
...
  File "/app/app/services/sos_service.py", line 153, in dispatch_sos
    from app.services.whatsapp_service import send_whatsapp_sync, _build_sos_body
  File "/app/app/services/whatsapp_service.py", line 1, in <module>
    from flask_jwt_extended import create_access_token, create_refresh_token
ModuleNotFoundError: No module named 'flask_jwt_extended'
```

**AI Fix Directive:** 
The application framework is FastAPI/Uvicorn, but `whatsapp_service.py` is attempting a Flask import (`flask_jwt_extended`). 
1. Open `whatsapp_service.py` and delete/replace this Flask import immediately.
2. If JWTs are needed for the WhatsApp dispatch, use the existing FastAPI JWT utilities natively configured in the backend's auth system. 

> [!NOTE]
> **✅ FIXED** — Removed the stale `from flask_jwt_extended import ...` line from `app/services/whatsapp_service.py` (line 1). That import was a dead copy-paste artifact from the Flask migration — no JWT tokens are created or needed in that file. The module now imports cleanly.

---

## 🛑 TASK 2: Fix Database Connection Leaks (`QueuePool` Exhaustion)
**Context:** Under load, or shortly after exceptions like Task 1 occur, the server drops all active queries and returns 503 Hibernate Wake errors. 

**Production Log:**
```python
Unhandled exception on POST... QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00
psycopg2.OperationalError: server closed the connection unexpectedly
```

**AI Fix Directive:** 
1. Database sessions requested from the SQLAlchemy `SessionLocal` generator are not being closed. 
2. Inspect the FastAPI `get_db()` dependency (likely in `database.py` or `dependencies.py`). Ensure it uses a `finally` block to return connections to the pool:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() # CRITICAL
```
3. Audit all background tasks (like `_expire_stale_countdowns()` in `sos_service.py`) and ensure any manual `db = SessionLocal()` instantiations also call `db.close()`.

> [!NOTE]
> **✅ FIXED** — Two changes in `app/database.py`:
> 1. Added pool tuning for production PostgreSQL: `pool_size=5`, `max_overflow=10`, `pool_recycle=280` (prevents Render's 300s idle-kill), `pool_timeout=20`, and a `statement_timeout=15000ms` connect arg so hung queries release connections quickly.
> 2. SQLite (dev/test) now uses `NullPool` to avoid multi-thread write conflicts.
>
> Also wrapped `_expire_stale_countdowns()` in `app/routes/sos.py` in a `try/except/rollback` guard so a failed bulk-update never leaves a dirty session in the pool.
>
> **Note**: The `get_db()` dependency and the per-request `ScopedSession.remove()` middleware were already correct — they did have the `finally` cleanup. The root cause was purely the pool misconfiguration + unguarded helper function.

---

## 🛑 TASK 3: Fix `POST /api/protection/collect` Schema (`422 Unprocessable Entity`)
**Context:** The Android Frontend is mathematically extracting 39 statistical features correctly based entirely on `labeled_windows.csv` and is attempting to send them to the backend to retrain the ML model. The frontend payload looks like this:
```json
{
  "sensor_type": "accelerometer",
  "x_mean": -0.46,
  "x_std": 0.465,
  "mag_iqr": 0.113,
  ... (and the rest of the 36 numerical variables matching the CSV row)
}
```

**Production Log:**
```json
{"success":false,"error":{"code":"VALIDATION_ERROR","message":"Validation failed for 'data': Field required"}}
```

**AI Fix Directive:**
The frontend sent the CSV columns as a flat JSON dictionary. But your FastAPI Pydantic schema is rejecting it because it strictly expects a field explicitly named `"data"` wrapping the 39 variables.
1. Inspect the Pydantic schema for `POST /api/protection/collect` (likely named `SensorTrainingRequest` or `CollectRequest`).
2. Does the backend want the Android app to nest all 39 variables inside a `{"data": { ... } }` object? 
3. **If Yes:** Stop here and tell the user "Yes, please wrap it in a 'data' array" so the frontend engineer can map it.
4. **If No:** Flatten your Pydantic schema to absorb the 39 fields natively at the root level, exactly as they are defined in `labeled_windows.csv`.

> [!NOTE]
> **✅ FIXED** — The `/collect` endpoint now accepts **both** payload formats without any changes needed on the Android side:
>
> **Format A (raw window)** — unchanged, backwards compatible:
> ```json
> { "sensor_type": "accelerometer", "label": 1, "window": [{"x": 0.1, "y": 9.8, "z": 0.2, "timestamp": ...}, ...] }
> ```
> **Format B (pre-extracted flat features)** — what Android is already sending:
> ```json
> { "sensor_type": "accelerometer", "label": 1, "x_mean": -0.46, "x_std": 0.465, ...(all 39 columns) }
> ```
> The backend auto-detects the format by checking if `x_mean` (or similar feature keys) are present at the root level. A new `FlatFeatureTrainingRequest` Pydantic model in `app/schemas/protection_schema.py` validates and maps the 39 fields directly to `SensorTrainingData` columns — no wrapping required.

---
### [AI INSTRUCTIONS: END]
Proceed sequentially and rewrite the necessary FastAPI endpoints. Provide the codebase patches back to the user.

