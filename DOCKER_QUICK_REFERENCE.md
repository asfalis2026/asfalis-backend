# Asfalis Backend - Docker Quick Reference

## ⚡ TL;DR - Get Running in 30 Seconds

```bash
# 1. Setup environment
cp requirements.txt .env  # Create .env from template (see DOCKER_SETUP.md)

# 2. Build and run
docker-compose build
docker-compose up

# 3. Visit
# API:      http://localhost:5000
# Swagger:  http://localhost:5000/docs
# ReDoc:    http://localhost:5000/redoc
```

---

## 🚀 Common Tasks

### Start Development Server
```bash
docker-compose up                    # Start
docker-compose up -d                 # Start in background
docker-compose logs -f               # View logs
docker-compose down                  # Stop
```

### Database Migrations
```bash
docker-compose exec web alembic upgrade head      # Run migrations
docker-compose exec web alembic history           # View history
docker-compose exec web alembic current           # Check version
```

### Testing
```bash
docker-compose exec web python -m pytest
docker-compose exec web python -m pytest -v       # Verbose
docker-compose exec web python -m pytest tests/   # Specific folder
```

### Shell Access
```bash
docker-compose exec web bash                      # Enter container shell
docker-compose exec web python3                   # Open Python REPL
docker-compose exec web pip list                  # List packages
```

### View Logs
```bash
docker-compose logs                   # All services, last 100 lines
docker-compose logs -f                # Follow logs in real-time
docker-compose logs web               # Specific service only
docker-compose logs --tail=50         # Last 50 lines
```

---

## 📦 Direct Docker Commands (Without Compose)

### Build Image
```bash
docker build -t asfalis-backend:latest .
```

### Run Container
```bash
# Basic
docker run -p 5000:8000 asfalis-backend:latest

# With env file
docker run -p 5000:8000 --env-file .env asfalis-backend:latest

# Interactive (shell)
docker run -it -p 5000:8000 --env-file .env asfalis-backend:latest /bin/bash

# Background (detached)
docker run -d -p 5000:8000 --env-file .env --name asfalis asfalis-backend:latest
```

### Manage Container
```bash
docker ps                           # List running containers
docker ps -a                        # List all containers
docker logs <container_id>          # View logs
docker logs -f <container_id>       # Follow logs
docker exec -it <container_id> bash # Enter running container
docker stop <container_id>          # Stop container
docker start <container_id>         # Start stopped container
docker rm <container_id>            # Delete container
```

---

## 🔧 Environment Setup

### Create .env File

```bash
# Development
DEBUG=true
SECRET_KEY=dev-secret-key
JWT_SECRET_KEY=dev-jwt-secret
DATABASE_URL=sqlite:///Asfalis.db
LOG_LEVEL=DEBUG

# Production (Render/Cloud)
DEBUG=false
SECRET_KEY=<strong-random-key>
JWT_SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://user:pwd@db:5432/asfalis
FIREBASE_CREDENTIALS_JSON='{"type":"service_account","..."}'
TWILIO_ACCOUNT_SID=<your-sid>
TWILIO_AUTH_TOKEN=<your-token>
```

**Generate secure keys:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🐛 Troubleshooting

### Port Already in Use
```bash
# Check what's using port 5000/8000
lsof -i :5000

# Stop Docker containers
docker-compose down

# Or kill process
kill -9 <PID>
```

### Container Exits Immediately
```bash
# Check logs
docker-compose logs web

# Rebuild without cache
docker-compose build --no-cache
docker-compose up
```

### Database Connection Error
```bash
# Verify DATABASE_URL
echo $DATABASE_URL

# For SQLite
docker-compose exec web sqlite3 Asfalis.db ".tables"

# For PostgreSQL
docker-compose exec web psql postgresql://user:pwd@host/db -c "\dt"
```

### Migration Fails
```bash
# Reset and re-run
docker-compose exec web alembic stamp head
docker-compose exec web alembic upgrade head

# Or manually reset database
docker-compose down -v  # Remove all volumes
docker-compose up       # Fresh start
```

### Can't Access API
```bash
# Check if service is running
docker-compose ps

# Verify port mapping
docker port <container_id>

# Test locally in container
docker-compose exec web curl http://localhost:8000/health
```

---

## 📊 Docker Compose Services

### Current Configuration
```yaml
web:
  - Image: Built from ./Dockerfile
  - Port: 5000 → 8000 (host → container)
  - Environment: Loaded from .env file
  - DNS: 8.8.8.8, 8.8.4.4 (for corporate networks)
```

### Add PostgreSQL (Optional)
Edit `docker-compose.yml`:
```yaml
services:
  web:
    # ... existing config
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/asfalis_db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: asfalis_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Then upgrade:
```bash
docker-compose up -d
docker-compose exec web alembic upgrade head
```

---

## 📈 Production Deployment

### Render.com
- Push to GitHub → Auto-deployed
- Includes PostgreSQL database
- See `render.yaml` for config

### AWS EC2 + Docker
```bash
# On EC2 instance
git clone <repo>
cd asfalis-backend
docker-compose up -d
# Setup nginx reverse proxy on port 80
```

### Google Cloud Run
```bash
gcloud run deploy asfalis \
  --source . \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=...
```

---

## ✅ Health Checks

```bash
# API is running
curl http://localhost:5000/health

# Swagger docs
open http://localhost:5000/docs

# Database connected
docker-compose exec web python3 -c "from app.database import engine; print(engine.execute('SELECT 1'))"

# All services
docker-compose ps
```

---

## 📚 Logs Patterns

```bash
# Real-time debugging
docker-compose logs -f web | grep ERROR

# Find specific error
docker-compose logs web | grep "migration"

# Count log entries
docker-compose logs web | wc -l

# Export logs
docker-compose logs web > app-logs.txt
```

---

## 🧹 Cleanup

```bash
# Stop all services
docker-compose down

# Remove containers and volumes (CAREFUL - data loss!)
docker-compose down -v

# Remove unused images
docker image prune

# Remove all unused resources (images, containers, networks, volumes)
docker system prune -a --volumes

# Check disk usage
docker system df
```

---

## 📱 API Testing

### Using curl
```bash
# Health check
curl http://localhost:5000/health

# Register user
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@123"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test@123"}'
```

### Using Python
```python
import requests

base_url = "http://localhost:5000"

# Health check
response = requests.get(f"{base_url}/health")
print(response.json())

# Register
response = requests.post(
    f"{base_url}/api/auth/register",
    json={"email": "test@example.com", "password": "Test@123"}
)
print(response.json())
```

### Using Postman
1. Import from `postman/collections/`
2. Set environment to local (`http://localhost:5000`)
3. Run requests in sequence

---

## 🔐 Security Reminders

⚠️ **Never commit:**
- `.env` file with real credentials
- `firebase-credentials.json`
- `*.key` files

✅ **DO commit:**
- `.env.example` (template without secrets)
- `docker-compose.yml`
- `Dockerfile`
- `requirements.txt`

---

## 📞 Need Help?

1. Check logs: `docker-compose logs web`
2. See full docs: `DOCKER_SETUP.md`
3. Check code: `app/main.py`, `app/config.py`
4. Read FastAPI: https://fastapi.tiangolo.com
5. Read Docker: https://docs.docker.com

---

**Quick Links:**
- [Full Docker Documentation](DOCKER_SETUP.md)
- [API Documentation](http://localhost:5000/docs)
- [Health Status](http://localhost:5000/health)
