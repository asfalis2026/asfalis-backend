#!/bin/bash
set -e
export PYTHONPATH=/app

# Run database migrations
echo "Running database migrations..."
alembic -c migrations/alembic.ini upgrade head || echo "Migration completed or skipped"

# Start the application
echo "Starting Asfalis backend..."
exec "$@"
