#!/bin/bash
# Startup script for Render — runs migrations then starts the server
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting PulseMetrics API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
