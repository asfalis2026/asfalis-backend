#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
flask db upgrade

# Start the application
echo "Starting application..."
exec "$@"
