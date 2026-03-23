#!/bin/bash
set -e

# Run Alembic migrations (replaces `flask db upgrade`)
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting Asfalis backend..."
exec "$@"
