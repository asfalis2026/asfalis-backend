# 🔗 Asfalis Backend — Integration Guide
### Docker · Render · Cron-Job · Postman

> This guide walks through the full integration lifecycle of the Asfalis backend:
> deploying via **Docker on Render**, keeping the free-tier service alive with **cron-job.org**,
> and testing all endpoints using **Postman**.

---

## 📋 Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Docker — Build & Run Locally](#2-docker--build--run-locally)
3. [Render — Deploy to Production](#3-render--deploy-to-production)
4. [Cron-Job — Keep Service Alive](#4-cron-job--keep-service-alive)
5. [Postman — API Testing](#5-postman--api-testing)
6. [Environment Variables Reference](#6-environment-variables-reference)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Asfalis Backend                         │
│                                                             │
│   ┌──────────┐    push     ┌───────────────────────────┐   │
│   │  GitHub  │ ──────────► │   Render (Web Service)    │   │
│   └──────────┘             │   Docker / Python runtime │   │
│                            │   Port: $PORT (auto)      │   │
│                            └────────────┬──────────────┘   │
│                                         │                   │
│              ┌──────────────────────────┤                   │
│              │                          │                   │
│   ┌──────────▼──────┐      ┌────────────▼────────────┐     │
│   │  Asfalis-db     │      │  cron-job.org           │     │
│   │  PostgreSQL     │      │  Pings /health every    │     │
│   │  (Render Free) │      │  14 minutes             │     │
│   └─────────────────┘      └─────────────────────────┘     │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │  Postman                                            │   │
│   │  Tests all API endpoints against Production URL    │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Docker — Build & Run Locally

### Project Files at a Glance

| File | Purpose |
|---|---|
| `Dockerfile` | Defines the container image (Python 3.12-slim) |
| `docker-compose.yml` | Orchestrates local development containers |
| `entrypoint.sh` | Bootstraps DB, runs migrations, starts server |
| `.env` | Local environment variables (never commit!) |

### `Dockerfile` Explained

```dockerfile
FROM python:3.12-slim          # Lightweight Python image

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt   # Install deps

COPY . .

EXPOSE 8000                    # Container listens on port 8000

COPY entrypoint.sh .
RUN sed -i 's/\r//' entrypoint.sh && chmod +x entrypoint.sh  # Fix CRLF

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "wsgi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### `entrypoint.sh` Explained

```bash
#!/bin/bash
set -e
export PYTHONPATH=/app

# Step 1: Bootstrap database (create tables if fresh DB)
python db_init.py

# Step 2: Apply any pending Alembic migrations
alembic -c migrations/alembic.ini upgrade head

# Step 3: Hand off to CMD (uvicorn)
exec "$@"
```

> **Key**: `exec "$@"` passes control to the `CMD` directive, allowing
> Docker signals (SIGTERM etc.) to be properly forwarded to uvicorn.

### Build & Run Locally

```bash
# 1. Build the image
docker build -t asfalis-backend .

# 2. Run with docker-compose (uses .env automatically)
docker-compose up --build

# 3. Verify the service is up
curl http://localhost:8000/health
```

### Common Local Docker Commands

```bash
# Stop all containers
docker-compose down

# Remove containers + volumes (fresh DB)
docker-compose down -v

# Tail logs
docker-compose logs -f web

# Run a one-off command inside the container
docker exec -it <container_id> bash

# Rebuild without cache
docker-compose build --no-cache
```

---

## 3. Render — Deploy to Production

Asfalis uses **Render's native Python runtime** (defined in `render.yaml`).
You can alternatively switch to Docker runtime — both approaches are documented below.

### Option A: Native Python Runtime (Current Setup via `render.yaml`)

Render auto-detects `render.yaml` in the repository root and provisions services.

```yaml
# render.yaml (current configuration)
services:
  - type: web
    name: Asfalis-backend
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: alembic upgrade head && uvicorn wsgi:app --host 0.0.0.0 --port $PORT --workers 1
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
        sync: false         # Set manually in Render dashboard
      - key: TWILIO_ACCOUNT_SID
        sync: false
      - key: TWILIO_AUTH_TOKEN
        sync: false
      - key: TWILIO_PHONE_NUMBER
        sync: false
      - key: TWILIO_VERIFY_SERVICE_SID
        sync: false

databases:
  - name: Asfalis-db
    databaseName: Asfalis
    user: Asfalis_user
    plan: free
    region: singapore
```

### Option B: Docker Runtime on Render

To use the `Dockerfile` instead of the native runtime, update `render.yaml`:

```yaml
services:
  - type: web
    name: Asfalis-backend
    runtime: docker              # ← Change this
    dockerfilePath: ./Dockerfile  # ← Point to your Dockerfile
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: Asfalis-db
          property: connectionString
      # ... same env vars as above
```

### Deploying to Render

#### Step 1 — Connect Repository
1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Render detects `render.yaml` automatically

#### Step 2 — Set Secret Environment Variables
Navigate to **Dashboard → Asfalis-backend → Environment** and manually set:

| Variable | Description |
|---|---|
| `FIREBASE_CREDENTIALS_JSON` | Full JSON string of your Firebase service account key |
| `TWILIO_ACCOUNT_SID` | From Twilio console |
| `TWILIO_AUTH_TOKEN` | From Twilio console |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number (+E.164 format) |
| `TWILIO_VERIFY_SERVICE_SID` | Twilio Verify Service SID |
| `ENCRYPTION_KEY` | Fernet key for field-level encryption (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) |

#### Step 3 — Trigger Deploy
```bash
# Push to main branch triggers auto-deploy
git push origin main

# Or manually trigger via Render dashboard → "Manual Deploy"
```

#### Step 4 — Verify Deployment
```
GET https://asfalis-backend.onrender.com/health
```
Expected response:
```json
{ "status": "healthy" }
```

### Render Free Tier Limitations

> ⚠️ **Free tier services spin down after 15 minutes of inactivity.**
> They take ~30–60 seconds to cold-start on the next request.
> Use **cron-job.org** (Section 4) to prevent this.

| Limit | Free Tier |
|---|---|
| Instances | 1 |
| RAM | 512 MB |
| CPU | Shared |
| Bandwidth | 100 GB/month |
| DB Storage | 1 GB |
| DB Connections | Limited |

---

## 4. Cron-Job — Keep Service Alive

**cron-job.org** is a free service that pings your Render endpoint on a schedule,
preventing the free-tier cold-start problem.

### Setup on cron-job.org

#### Step 1 — Create Account
Go to [cron-job.org](https://cron-job.org) and sign up for a free account.

#### Step 2 — Create New Cron Job

Click **Create Cronjob** and fill in:

| Field | Value |
|---|---|
| **Title** | `Asfalis Backend Keep-Alive` |
| **URL** | `https://asfalis-backend.onrender.com/health` |
| **Schedule** | Every **14 minutes** (see schedule config below) |
| **Request Method** | `GET` |
| **Request Timeout** | `30` seconds |
| **Enable notifications** | On failure only (recommended) |

#### Step 3 — Schedule Configuration

In the **Schedule** section, select **"Every N minutes"** and set to `14`.

Or use the advanced schedule editor:
```
# Cron expression: every 14 minutes
*/14 * * * *
```

> **Why 14 minutes?** Render spins down services after 15 minutes of inactivity.
> Pinging every 14 minutes keeps it consistently warm.

#### Step 4 — Add Request Headers (Optional but Recommended)

Add a custom header to identify keep-alive pings in your logs:

| Header | Value |
|---|---|
| `X-Ping-Source` | `cron-job-keepalive` |
| `User-Agent` | `CronJob/1.0 AsfalisKeepAlive` |

#### Step 5 — Save and Enable

Click **Create** and ensure the job shows **Status: Enabled**.

### Verifying the Cron Job Works

After 15–20 minutes, check the **Execution History** tab in cron-job.org dashboard:

```
✅ 200 OK  — Service is alive and responding
❌ 4xx/5xx — Check Render logs for errors
⏱️ Timeout — Service was cold-starting; check if 30s timeout is enough
```

### Adding a `/health` Endpoint (If Not Present)

Ensure your Flask app has a health endpoint. Add to your routes if missing:

```python
# app/routes/health.py
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Lightweight endpoint for keep-alive pings."""
    return jsonify({
        "status": "healthy",
        "service": "asfalis-backend"
    }), 200
```

Register it in your app factory:
```python
# In your app/__init__.py or main app file
from app.routes.health import health_bp
app.register_blueprint(health_bp)
```

---

## 5. Postman — API Testing

### Environments Setup

Postman **Environments** let you switch between local and production without editing requests.

#### Create Two Environments

**Environment 1: Local**
| Variable | Initial Value | Current Value |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | `http://localhost:8000` |
| `ACCESS_TOKEN` | _(empty)_ | _(auto-set by login script)_ |
| `REFRESH_TOKEN` | _(empty)_ | _(auto-set)_ |

**Environment 2: Production**
| Variable | Initial Value | Current Value |
|---|---|---|
| `BASE_URL` | `https://asfalis-backend.onrender.com` | `https://asfalis-backend.onrender.com` |
| `ACCESS_TOKEN` | _(empty)_ | _(auto-set by login script)_ |
| `REFRESH_TOKEN` | _(empty)_ | _(auto-set)_ |

### Collection Structure

```
📁 Asfalis Backend
├── 📁 Auth
│   ├── POST  Register User
│   ├── POST  Login
│   ├── POST  Refresh Token
│   └── POST  Logout
├── 📁 User
│   ├── GET   Get Profile
│   └── PATCH Update Profile
├── 📁 Contacts
│   ├── GET   List Contacts
│   ├── POST  Add Contact (Step 1 — Search)
│   └── POST  Add Contact (Step 2 — Confirm)
├── 📁 SOS
│   ├── POST  Trigger SOS
│   └── GET   SOS History
├── 📁 Notifications
│   └── POST  Send Test Notification
└── 🔆 Health Check
    └── GET   /health
```

### Authentication Flow

#### Pre-request Script (Collection Level)

Add this to the **Collection → Pre-request Scripts** tab to auto-attach tokens:

```javascript
// Auto-attach Authorization header if token exists
const token = pm.environment.get("ACCESS_TOKEN");
if (token) {
    pm.request.headers.add({
        key: "Authorization",
        value: `Bearer ${token}`
    });
}
```

#### Login Request — Auto-capture Token

In the **POST /auth/login** request's **Tests** tab:

```javascript
if (pm.response.code === 200) {
    const jsonData = pm.response.json();

    // Store tokens in environment
    pm.environment.set("ACCESS_TOKEN", jsonData.access_token);
    pm.environment.set("REFRESH_TOKEN", jsonData.refresh_token);

    console.log("✅ Tokens captured and stored in environment");
} else {
    console.error("❌ Login failed:", pm.response.status);
}
```

### Common Request Templates

#### Health Check
```
GET {{BASE_URL}}/health
```

#### Register User (Phone)
```
POST {{BASE_URL}}/api/auth/register/phone
Content-Type: application/json

{
  "full_name": "Test User",
  "phone_number": "+6591234567",
  "country": "Singapore",
  "password": "SecurePass123!"
}
```

#### Login (Phone)
```
POST {{BASE_URL}}/api/auth/login/phone
Content-Type: application/json

{
  "phone_number": "+6591234567",
  "password": "SecurePass123!"
}
```

#### Protected Endpoint (Token Auto-attached)
```
GET {{BASE_URL}}/api/user/profile
Authorization: Bearer {{ACCESS_TOKEN}}
```

### Running Collection Tests

#### Via Postman GUI (Collection Runner)

1. Click the **▶ Run** button on the collection
2. Select **Environment**: `Local` or `Production`
3. Set **Iterations**: 1 (or more for load testing)
4. Click **Run Asfalis Backend**

#### Via Newman (CLI)

Newman is Postman's command-line runner for CI/CD pipelines.

```bash
# Install Newman
npm install -g newman

# Export your collection from Postman:
# Collection → ⋯ → Export → Collection v2.1

# Run against local
newman run ./postman/Asfalis_Backend.postman_collection.json \
  --environment ./postman/Local.postman_environment.json \
  --reporters cli,json \
  --reporter-json-export ./postman/results/local_run.json

# Run against production
newman run ./postman/Asfalis_Backend.postman_collection.json \
  --environment ./postman/Production.postman_environment.json \
  --reporters cli,html \
  --reporter-html-export ./postman/results/production_report.html
```

#### Integrate Newman in GitHub Actions

```yaml
# .github/workflows/postman-tests.yml
name: API Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'   # Runs daily at 6 AM UTC

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Newman
        run: npm install -g newman newman-reporter-htmlextra

      - name: Run Postman Collection
        run: |
          newman run postman/Asfalis_Backend.postman_collection.json \
            --env-var "BASE_URL=${{ secrets.RENDER_BASE_URL }}" \
            --env-var "ACCESS_TOKEN=" \
            --reporters cli,htmlextra \
            --reporter-htmlextra-export results/report.html

      - name: Upload Test Report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: newman-report
          path: results/report.html
```

---

## 6. Environment Variables Reference

### Full `.env` Template

```bash
# ─── Application ───────────────────────────────────────────
ENVIRONMENT=development           # development | production
SECRET_KEY=your-flask-secret-key
JWT_SECRET_KEY=your-jwt-secret

# ─── Database ──────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@host:5432/Asfalis

# ─── Encryption ────────────────────────────────────────────
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your-fernet-key-here

# ─── Firebase (Push Notifications) ─────────────────────────
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"..."}

# ─── Twilio (SMS / OTP) ────────────────────────────────────
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### How Render Injects Environment Variables

```
render.yaml (sync: false)  →  Set manually in Render Dashboard
render.yaml (generateValue: true)  →  Render auto-generates a random value
render.yaml (fromDatabase)  →  Render injects the DB connection string automatically
```

---

## 7. Troubleshooting

### Docker Issues

| Problem | Cause | Fix |
|---|---|---|
| `exec ./entrypoint.sh: no such file or directory` | CRLF line endings on Windows | The `sed -i 's/\r//'` in Dockerfile fixes this automatically |
| Container exits immediately | entrypoint.sh error | Run `docker-compose logs web` to see the error |
| DB connection refused | DB not ready | Add a `wait-for-it.sh` or retry logic in entrypoint.sh |
| Port already in use | Another process on 8000 | Change host port: `"8001:8000"` in docker-compose.yml |

### Render Issues

| Problem | Cause | Fix |
|---|---|---|
| Cold start timeouts | Free tier spin-down | Set up cron-job.org (Section 4) |
| Build fails | Missing dependency | Add to `requirements.txt` and redeploy |
| `DATABASE_URL` not set | Env var missing | Check Render → Environment tab |
| Migrations fail on deploy | DB not ready | Add retry logic or use the `entrypoint.sh` DB init approach |

### Cron-Job Issues

| Problem | Cause | Fix |
|---|---|---|
| Still getting cold starts | Schedule too infrequent | Reduce to every 10–12 minutes |
| 404 responses | Wrong URL or `/health` not registered | Verify endpoint exists in app |
| Job disabled automatically | Too many consecutive failures | Check Render logs; re-enable job |

### Postman Issues

| Problem | Cause | Fix |
|---|---|---|
| `ACCESS_TOKEN` not set | Login request failed | Run the Login request first |
| 401 Unauthorized | Token expired | Re-run Login to refresh token |
| SSL errors against production | Certificate issue | Ensure HTTPS URL is correct |
| 503 from Render | Cold start in progress | Wait 30–60s and retry |

---

## 🔄 Full Workflow Summary

```
1. 📝 Code Changes
       │
       ▼
2. 🐳 Test Locally with Docker
   docker-compose up --build
   → Postman (Local environment) to verify
       │
       ▼
3. 🚀 Push to GitHub → Triggers Render Auto-Deploy
   git push origin main
       │
       ▼
4. ⏳ Render Builds & Deploys
   buildCommand: pip install -r requirements.txt
   startCommand: alembic upgrade head && uvicorn wsgi:app ...
       │
       ▼
5. ✅ Verify Production
   → Postman (Production environment) to run smoke tests
   → Check GET https://asfalis-backend.onrender.com/health
       │
       ▼
6. 🕐 Cron-Job Keeps Service Warm
   cron-job.org pings /health every 14 minutes
   → No more cold starts for active users
```

---

*Last updated: 2026-03-29 | Asfalis Backend v1.0*
