# RAKSHA Backend - Run Guide

This guide provides step-by-step instructions to set up and run the Raksha backend server, including all necessary services (Database, Redis, Celery).

## 1. Prerequisites

Ensure you have the following installed on your system:
- **Python 3.10+**
- **pip** (Python package manager)

## 2. Environment Setup

### 2.1 Virtual Environment
It's recommended to use a virtual environment to manage dependencies.

```bash
# Verify you are in the project root (where requirements.txt is located)
# cd women_safety_backend (if needed)

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2.2 Install Dependencies
```bash
pip install -r requirements.txt
```

### 2.3 Configuration
Ensure your `.env` file is set up with valid keys. 
Refer to `ENV_SETUP_GUIDE.md` for detailed instructions on getting API keys for Twilio, Firebase, and Google Maps.

## 3. Database Initialization

### 3. Database Initialization

Since you are using **PostgreSQL (Supabase)**, ensure your `.env` contains the correct `DATABASE_URL`.

Run the following commands to apply migrations to your remote database:

```bash
# Apply migrations to Supabase/PostgreSQL
flask db upgrade
```

> **Note:** Do NOT run `flask db init` if the `migrations/` folder already exists.

## 4. Running the Services

Since we have configured the backend to run in "eager mode" for local development, **you do NOT need to run Redis or Celery separately.**

### Start the Backend Server

Simply run this command in your terminal:

```bash
# Make sure venv is activated
source venv/bin/activate

# Run Flask (Development Mode)
flask run --host=0.0.0.0 --port=5000
```

That's it! The server handles SMS, Push Notifications, and Database operations synchronously.

## 5. Verification

- **API Health Check**: Visit `http://localhost:5000/health`
- **Socket.IO**: Connect a client to `http://localhost:5000`.

## 6. Running with Docker (Optional)

If you prefer to run the entire backend using Docker, follow these steps:

1. **Install Docker**: Ensure Docker Desktop is installed and running.
2. **Setup .env**: Ensure your `.env` file is present in the root directory.
3. **Run Command**:
   ```bash
   docker-compose up --build
   ```
4. **Access**: The server will be available at `http://localhost:5000`.
5. **Background Mode**: To run in the background, use `docker-compose up -d`.

## Troubleshooting

### Port 5000 Already in Use (macOS)
On macOS, `ControlCenter` (AirPlay Receiver) often uses port 5000. To fix this:

1. **Option A: Disable AirPlay Receiver**
   - Go to **System Settings** -> **General** -> **AirDrop & Handoff**
   - Turn off **AirPlay Receiver**

2. **Option B: Kill the conflicting process**
   ```bash
   lsof -i :5000  # Find the PID
   kill -9 <PID>  # Kill the process
   ```

3. **Option C: Run on a different port**
   ```bash
   flask run --host=0.0.0.0 --port=5001
   ```

### Missing Keys
- Check `.env` file for typos.
