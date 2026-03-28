#!/bin/bash
set -e
export PYTHONPATH=/app

# Bootstrap: create tables on fresh DB, stamp Alembic head to skip history
echo "Initializing database..."
python db_init.py

# Run any pending Alembic migrations
echo "Running database migrations..."
alembic -c migrations/alembic.ini upgrade head

# Start the application
echo "Starting Asfalis backend..."
exec "$@"
