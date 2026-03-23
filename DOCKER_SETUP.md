# Asfalis Backend - Docker Setup & Deployment Guide

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Environment Configuration](#environment-configuration)
5. [Docker Architecture](#docker-architecture)
6. [Running with Docker](#running-with-docker)
7. [Database Setup & Migrations](#database-setup--migrations)
8. [API Endpoints](#api-endpoints)
9. [Socket.IO & Real-Time Features](#socketio--real-time-features)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)

---

## Project Overview

**Asfalis** is a comprehensive women safety application backend built with modern technologies:

- **Framework**: FastAPI (ASGI - async Python web framework)
- **Real-Time**: Socket.IO for WebSocket connections
- **Database**: PostgreSQL (with SQLAlchemy ORM)
- **Authentication**: JWT-based with OTP support
- **Notifications**: Firebase Cloud Messaging (FCM), Twilio SMS/WhatsApp
- **ML/Analytics**: TensorFlow, scikit-learn, XGBoost for safety predictions
- **Containerization**: Docker & Docker Compose

### Key Features
- **Authentication**: User registration, login, OTP verification
- **SOS Alerts**: Emergency alerts with countdown and cooldown
- **Location Tracking**: Real-time location sharing via WebSockets
- **Trusted Contacts**: Store and notify emergency contacts
- **Device Management**: Device IMEI binding and security
- **Protection Services**: Device security monitoring
- **User Settings**: Customizable preferences
- **Support**: In-app support system

### Tech Stack
```
FastAPI + Uvicorn (ASGI server)
     ↓
Socket.IO (Real-time)
     ↓
SQLAlchemy + Alembic (Database ORM & Migrations)
     ↓
PostgreSQL / SQLite (Database)
     ↓
Docker + Docker Compose (Containerization)
```

---

## Prerequisites

### System Requirements
- **Docker**: v20.10 or later
- **Docker Compose**: v1.29 or later
- **Python**: 3.12 (for local development)
- **Git**: For version control

### Installation Guides
- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
- [Docker for Linux](https://docs.docker.com/engine/install/)

### Verify Installation
```bash
docker --version
docker-compose --version
```

---

## Quick Start

### 1️⃣ Setup Environment Variables
Create a `.env` file in the project root (copy from template below):

```bash
# Copy the template
cp .env.example .env  # If template exists
# Or create manually
```

### 2️⃣ Build and Run with Docker Compose
```bash
# Build the Docker image
docker-compose build

# Start the container
docker-compose up

# Start in background mode
docker-compose up -d
```

### 3️⃣ Run Database Migrations
```bash
# Migrations run automatically via entrypoint.sh
# But you can also run manually:
docker-compose exec web alembic upgrade head
```

### 4️⃣ Access the Application
- **API**: http://localhost:5000 (from docker-compose.yml port mapping)
- **API Docs (Swagger)**: http://localhost:5000/docs
- **API Docs (ReDoc)**: http://localhost:5000/redoc
- **Health Check**: http://localhost:5000/health

### 5️⃣ Stop the Container
```bash
docker-compose down
```

---

## Environment Configuration

### Environment Variables Template

Create a `.env` file with these variables:

```env
# ═══════════════════════════════════════════════════════════════
# DATABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
DATABASE_URL=postgresql://user:password@db:5432/asfalis_db
# Or for SQLite (development only):
# DATABASE_URL=sqlite:///Asfalis.db

# ═══════════════════════════════════════════════════════════════
# APPLICATION SETTINGS
# ═══════════════════════════════════════════════════════════════
DEBUG=false
SECRET_KEY=your-secret-key-change-in-production
LOG_LEVEL=INFO

# ═══════════════════════════════════════════════════════════════
# JWT AUTHENTICATION
# ═══════════════════════════════════════════════════════════════
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRES=900              # 15 minutes (seconds)
JWT_REFRESH_TOKEN_EXPIRES=2592000         # 30 days (seconds)
JWT_SOS_TOKEN_EXPIRES_DAYS=30             # SOS token validity

# ═══════════════════════════════════════════════════════════════
# OTP CONFIGURATION (One-Time Password)
# ═══════════════════════════════════════════════════════════════
OTP_EXPIRY_SECONDS=300                    # 5 minutes
MAX_OTP_ATTEMPTS=5                        # Max failed attempts

# ═══════════════════════════════════════════════════════════════
# TWILIO SMS CONFIGURATION (Account 1)
# ═══════════════════════════════════════════════════════════════
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890           # Sender phone number
TWILIO_VERIFY_SERVICE_SID=your_service_sid

# ═══════════════════════════════════════════════════════════════
# TWILIO WhatsApp CONFIGURATION (Account 2)
# ═══════════════════════════════════════════════════════════════
TWILIO_WA_ACCOUNT_SID=your_whatsapp_account_sid
TWILIO_WA_AUTH_TOKEN=your_whatsapp_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
TWILIO_SANDBOX_CODE=join <sandbox-code>

# ═══════════════════════════════════════════════════════════════
# FIREBASE CLOUD MESSAGING (FCM)
# ═══════════════════════════════════════════════════════════════
# Option 1: Path to credentials JSON file
FIREBASE_CREDENTIALS_PATH=/app/firebase-credentials.json

# Option 2: Full credentials JSON as environment variable (recommended for Docker)
FIREBASE_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","...":""}'

# ═══════════════════════════════════════════════════════════════
# SOS CONFIGURATION
# ═══════════════════════════════════════════════════════════════
SOS_COOLDOWN_SECONDS=20                   # Min time between SOS triggers
SOS_COUNTDOWN_SECONDS=10                  # Countdown before alert dispatch
MAX_TRUSTED_CONTACTS=5                    # Max emergency contacts

# ═══════════════════════════════════════════════════════════════
# DEVICE SECURITY
# ═══════════════════════════════════════════════════════════════
IMEI_BINDING_ENABLED=false                # Enforce device IMEI binding
IOT_DOUBLE_TAP_WINDOW_SECONDS=1.5         # IoT button double-tap window

# ═══════════════════════════════════════════════════════════════
# RATE LIMITING
# ═══════════════════════════════════════════════════════════════
RATELIMIT_STORAGE_URI=memory://           # In-memory storage (dev only)
# For production: RATELIMIT_STORAGE_URI=redis://redis:6379

# ═══════════════════════════════════════════════════════════════
# APPLICATION PORT
# ═══════════════════════════════════════════════════════════════
PORT=8000
```

### Getting Sensitive Credentials

#### Twilio SMS Setup
1. Create account at [twilio.com](https://www.twilio.com)
2. Navigate to **Console Dashboard**
3. Copy: **Account SID**, **Auth Token**
4. Buy a phone number or use trial (get **Phone Number**)
5. Create Verify Service (get **Service SID**)

#### Firebase Setup
1. Create project at [Firebase Console](https://console.firebase.google.com)
2. Go to **Project Settings** → **Service Accounts**
3. Click **Generate New Private Key** → Download JSON file
4. Copy entire JSON content to `FIREBASE_CREDENTIALS_JSON` env var

#### Database URL Format
```
PostgreSQL: postgresql://username:password@host:port/database
SQLite:     sqlite:///path/to/database.db
```

---

## Docker Architecture

### Dockerfile Structure

```dockerfile
FROM python:3.12-slim
├─ WORKDIR /app
├─ COPY requirements.txt .
├─ RUN pip install --no-cache-dir -r requirements.txt
├─ COPY . .
├─ EXPOSE 8000
├─ COPY entrypoint.sh .
├─ RUN chmod +x entrypoint.sh
├─ ENTRYPOINT ["./entrypoint.sh"]
└─ CMD ["uvicorn", "wsgi:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Key Points:**
- **Base Image**: `python:3.12-slim` (lightweight, 160MB vs 880MB with default Python)
- **Working Directory**: `/app` (inside container)
- **Entrypoint**: `entrypoint.sh` runs migrations on startup
- **Exposure**: Port 8000 (uvicorn default)
- **No Cache**: `--no-cache-dir` reduces image size

### Docker Compose Configuration

The `docker-compose.yml` defines:

| Service | Image | Ports | Environment |
|---------|-------|-------|-------------|
| web | Local build | 5000→5000 | `.env` file |

**DNS Configuration**: Google DNS (8.8.8.8, 8.8.4.4) for corporate networks

---

## Running with Docker

### Build the Image

```bash
# Build with default tag
docker build -t asfalis-backend:latest .

# Build with version tag
docker build -t asfalis-backend:v2.0.0 .

# View image info
docker images asfalis-backend
```

### Run Container Directly (without Compose)

```bash
# Basic run (SQLite database)
docker run -p 8000:8000 asfalis-backend:latest

# With environment variables
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pwd@db:5432/asfalis \
  -e DEBUG=true \
  -e SECRET_KEY=your-secret \
  asfalis-backend:latest

# With .env file
docker run -p 8000:8000 --env-file .env asfalis-backend:latest

# Interactive mode (for debugging)
docker run -it -p 8000:8000 --env-file .env asfalis-backend:latest /bin/bash

# Detached mode (background)
docker run -d -p 8000:8000 --env-file .env --name asfalis asfalis-backend:latest

# View logs
docker logs asfalis
docker logs -f asfalis  # Follow logs

# Stop container
docker stop asfalis
docker rm asfalis      # Remove after stopping
```

### Run with Docker Compose

```bash
# Build image from Dockerfile
docker-compose build

# Start services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs
docker-compose logs -f web  # Follow logs

# Check running services
docker-compose ps

# Execute command in running container
docker-compose exec web bash
docker-compose exec web python -m pytest

# Stop services
docker-compose down

# Remove containers and volumes
docker-compose down -v
```

### Common Docker Commands

```bash
# List running containers
docker ps

# List all containers (including stopped)
docker ps -a

# View container logs
docker logs <container_id>

# Execute command in container
docker exec -it <container_id> bash

# Copy file from container
docker cp <container_id>:/app/file.txt ./file.txt

# Remove image
docker rmi asfalis-backend:latest

# Remove all unused images
docker image prune

# Get resource usage
docker stats
```

---

## Database Setup & Migrations

### Database Initialization

Migrations **automatically run** when the container starts via `entrypoint.sh`:

```bash
#!/bin/bash
set -e
echo "Running database migrations..."
alembic upgrade head
echo "Starting Asfalis backend..."
exec "$@"
```

### Manual Migration Commands

```bash
# Run pending migrations
docker-compose exec web alembic upgrade head

# View migration history
docker-compose exec web alembic history

# Downgrade to previous version
docker-compose exec web alembic downgrade -1

# Create new migration
docker-compose exec web alembic revision --autogenerate -m "description"

# Check current database version
docker-compose exec web alembic current
```

### Migration Files

Migrations are stored in `migrations/versions/`:
- Each file has an auto-generated version ID
- SQLAlchemy models automatically tracked
- Alembic compares models to database schema

### Database from Scratch

If migrations fail or database is corrupted:

```bash
# Using PostgreSQL
docker-compose exec web dropdb -U user asfalis_db
docker-compose exec web createdb -U user asfalis_db
docker-compose exec web alembic upgrade head

# Using SQLite
docker-compose exec web rm Asfalis.db
docker-compose exec web alembic upgrade head
```

### Backup Database

```bash
# PostgreSQL dump
docker exec <container_id> pg_dump -U user asfalis_db > backup.sql

# Restore from backup
docker exec -i <container_id> psql -U user asfalis_db < backup.sql
```

---

## API Endpoints

### Base URL
- **Development**: `http://localhost:8000` (or 5000 from docker-compose)
- **Production**: `https://your-domain.com`

### API Documentation
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI Schema**: `/openapi.json`

### Route Structure

| Prefix | Module | Purpose |
|--------|--------|---------|
| `/api/auth` | `routes/auth.py` | Registration, login, OTP verification |
| `/api/user` | `routes/user.py` | User profile, account management |
| `/api/contacts` | `routes/contacts.py` | Trusted emergency contacts |
| `/api/sos` | `routes/sos.py` | SOS alert triggers and history |
| `/api/protection` | `routes/protection.py` | Device protection services |
| `/api/location` | `routes/location.py` | Location data and tracking |
| `/api/settings` | `routes/settings.py` | User preferences and settings |
| `/api/device` | `routes/device.py` | Device registration and management |
| `/api/support` | `routes/support.py` | Support tickets and help |

### Core Endpoints

#### Health Check
```
GET /health
Response: {"status": "ok"}
```

#### Authentication
```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/verify-otp
POST /api/auth/refresh-token
```

#### SOS Alert
```
POST /api/sos/trigger
GET /api/sos/history
GET /api/sos/status
```

#### Real-Time Location
```
POST /api/location/update
GET /api/location/current  
GET /api/location/history
```

#### Trusted Contacts
```
POST /api/contacts/add
DELETE /api/contacts/{contact_id}
GET /api/contacts
```

---

## Socket.IO & Real-Time Features

### Architecture

Socket.IO is mounted as ASGI middleware in `wsgi.py`:

```python
from app.main import socketio_app as app  # Socket.IO wraps FastAPI

# Routes:
# - /socket.io/* → handled by Socket.IO
# - /api/* → handled by FastAPI
```

### WebSocket Endpoints

**Location Tracking** (`/socket.io`):
```javascript
// Client side (JavaScript)
const socket = io('http://localhost:8000');

// Emit location update
socket.emit('location_update', {
  latitude: 28.6139,
  longitude: 77.2090,
  accuracy: 10,
  timestamp: '2026-03-22T10:30:00Z'
});

// Listen for other users' location updates
socket.on('location_received', (data) => {
  console.log('Updated location:', data);
});
```

**Connection States**:
- `connect` - Client connected to server
- `disconnect` - Client disconnected
- `location_update` - Real-time location broadcast
- `location_received` - Receive updates from other clients

### Features Using Socket.IO
- Real-time location sharing with trusted contacts
- Live SOS alert notifications
- Device status updates
- Chat/messaging (if implemented)

---

## Deployment

### 1. Local Development with Docker

**Setup:**
```bash
# Create .env with development values
cat > .env << EOF
DEBUG=true
SECRET_KEY=dev-secret-key
JWT_SECRET_KEY=dev-jwt-secret
DATABASE_URL=sqlite:///Asfalis.db
LOG_LEVEL=DEBUG
EOF

# Run
docker-compose up

# Access at http://localhost:5000
```

### 2. Render.com Deployment (Cloud)

The project includes `render.yaml` for automated deployment:

```bash
# Push to GitHub
git push origin main

# Render automatically:
# 1. Detects push
# 2. Builds Docker image
# 3. Installs dependencies from requirements.txt
# 4. Runs migrations: alembic upgrade head
# 5. Starts app: uvicorn wsgi:app --host 0.0.0.0 --port $PORT
# 6. PostgreSQL database created in Singapore region
```

**Required Environment Variables on Render:**
- `DATABASE_URL` (auto-set from PostgreSQL)
- `SECRET_KEY` (auto-generated)
- `JWT_SECRET_KEY` (auto-generated)
- `FIREBASE_CREDENTIALS_JSON`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, etc.

**Render Dashboard:**
1. Connect GitHub repository
2. Create new Web Service
3. Environment variables automatically populated
4. Service deployed at: `https://asfalis-backend.onrender.com`

### 3. AWS Elastic Container Service (ECS)

**Steps:**
1. Push image to ECR (Elastic Container Registry)
2. Create ECS Task Definition
3. Create ECS Service
4. Configure Load Balancer
5. Link RDS PostgreSQL database

```bash
# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag asfalis-backend:latest <account>.dkr.ecr.<region>.amazonaws.com/asfalis:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/asfalis:latest
```

### 4. Google Cloud Run

```bash
# Build and deploy
gcloud run deploy asfalis-backend \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://...,SECRET_KEY=...
```

### 5. Manual Server Deployment (VPS/EC2)

```bash
# On server:
1. Install Docker & Docker Compose
2. Clone repository
3. Create .env file
4. docker-compose up -d
5. Configure reverse proxy (nginx)
6. Setup SSL certificate (Let's Encrypt)
7. Configure firewall
```

---

## Troubleshooting

### Container Issues

#### Container exits immediately
```bash
# Check logs
docker-compose logs web

# Common causes:
# 1. Port already in use
docker ps  # View running containers
# Stop conflicting container or change port in docker-compose.yml

# 2. Missing environment variables
# Add missing vars to .env file

# 3. Database connection error
# Verify DATABASE_URL in .env
```

#### Can't connect to database
```bash
# Test PostgreSQL connection
docker-compose exec web psql postgresql://user:pwd@db:5432/asfalis

# Or for SQLite
docker-compose exec web sqlite3 Asfalis.db ".tables"

# Check DATABASE_URL format
echo $DATABASE_URL
```

#### Migration errors
```bash
# Check migration history
docker-compose exec web alembic history

# View current version
docker-compose exec web alembic current

# Manually run migrations with verbose output
docker-compose exec web alembic upgrade head --sql
```

### Application Issues

#### Port already in use
```bash
# Find process using port 5000/8000
lsof -i :5000
netstat -tulpn | grep 5000

# Change port in docker-compose.yml
# Or kill existing process:
kill -9 <PID>
```

#### High memory usage
```bash
# Check resource usage
docker stats

# Reduce workers in uvicorn command
# Current: --workers 1 (fine for testing)
# Production: --workers 4 (or CPU count)

# Restart with limits
docker run -m 512m -p 8000:8000 asfalis-backend:latest
```

#### Permission denied errors
```bash
# Ensure entrypoint.sh is executable
chmod +x entrypoint.sh

# Rebuild image
docker-compose build --no-cache
docker-compose up
```

### Database Issues

#### Database locked (SQLite)
```bash
# SQLite doesn't handle concurrent access well
# For development only; use PostgreSQL for production

# Remove and recreate
rm Asfalis.db
docker-compose exec web alembic upgrade head
```

#### Migration conflicts
```bash
# If migrations are out of sync:
docker-compose exec web alembic stamp head
docker-compose exec web alembic upgrade head
```

### Debugging

#### Interactive debugging
```bash
# Enter container shell
docker-compose exec web bash

# Run Python REPL
python3
>>> from app.main import app
>>> print(app.title)

# Check environment variables
env | grep DATABASE

# View dependencies
pip list
pip show fastapi
```

#### Enable verbose logging
```bash
# In .env
LOG_LEVEL=DEBUG

# Or start with
docker run -e LOG_LEVEL=DEBUG -e DEBUG=true ...
```

#### Test API endpoints
```bash
# Basic health check
curl http://localhost:5000/health

# With authentication
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"secure123"}'
```

---

## Performance Optimization

### Image Size Optimization
```bash
# Current: python:3.12-slim (~160MB)
# Alternative: python:3.12-alpine (~50MB) - but slower/unstable

# Check image size
docker images asfalis-backend
```

### Multi-Stage Build (Optional)

```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim as builder
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "wsgi:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Uvicorn Settings
```bash
# Current (testing): --workers 1
# Production: --workers 4 (or auto = CPU count)
# Add: --worker-class uvicorn.workers.UvicornWorker

# Full production command:
uvicorn wsgi:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --loop uvloop \
  --http httptools
```

---

## Security Best Practices

### 1. Environment Variables
✅ Use `.env` file (NOT in git)
✅ Change all secret keys in production
✅ Use strong passwords (>20 characters)
✅ Rotate keys periodically

### 2. Database Security
✅ Use strong database password
✅ Only expose database within Docker network
✅ Enable SSL for database connections
✅ Regular backups

### 3. Docker Security
✅ Use specific image versions (not `latest`)
✅ Scan images for vulnerabilities: `docker scan asfalis-backend`
✅ Run container as non-root user (optional)
✅ Set resource limits: `-m 512m --cpus 1`

### 4. API Security
✅ Enable HTTPS in production
✅ Set CORS properly (not `*`)
✅ Implement rate limiting (already done)
✅ Validate all inputs (Pydantic handles this)
✅ Use secure JWT secrets

### 5. Firebase Credentials
⚠️ Never commit `firebase-credentials.json`
✅ Use environment variable `FIREBASE_CREDENTIALS_JSON`
✅ Regenerate keys if accidentally exposed

---

## Useful Commands Reference

```bash
# ─── BUILD ──────────────────────────────────────────────────
docker build -t asfalis-backend:latest .
docker-compose build
docker-compose build --no-cache

# ─── RUN ─────────────────────────────────────────────────────
docker-compose up
docker-compose up -d
docker run -p 8000:8000 --env-file .env asfalis-backend:latest

# ─── MANAGE ─────────────────────────────────────────────────
docker-compose ps
docker-compose logs -f
docker-compose stop
docker-compose down
docker-compose down -v  # Remove volumes too

# ─── DEBUG ──────────────────────────────────────────────────
docker-compose exec web bash
docker-compose exec web python -m pytest
docker logs <container_id> -f

# ─── MIGRATIONS ──────────────────────────────────────────────
docker-compose exec web alembic upgrade head
docker-compose exec web alembic history
docker-compose exec web alembic current

# ─── CLEAN UP ────────────────────────────────────────────────
docker system prune
docker image prune
docker volume prune
```

---

## Support & Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **Docker Docs**: https://docs.docker.com
- **Socket.IO Python**: https://python-socketio.readthedocs.io
- **SQLAlchemy**: https://docs.sqlalchemy.org
- **Alembic Migrations**: https://alembic.sqlalchemy.org

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-03-22 | Initial Docker documentation |

---

**Last Updated**: March 22, 2026
**Maintained By**: Asfalis Development Team
