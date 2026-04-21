#!/bin/bash
set -e
export PYTHONPATH=/app

# Start the application
echo "Starting Asfalis backend..."
exec "$@"
