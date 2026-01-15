#!/bin/sh
set -e

echo "🐘 [INIT] Running database migrations..."

# 1. Wait for database/Verify connectivity (if postgres)
# This is a basic check to see if we can even talk to the DB before running alembic
if [ -n "$DATABASE_URL" ]; then
    echo "📡 Verifying database connectivity..."
    # Placeholder for a real health check (e.g. pg_isready if available)
    # For now, we rely on alembic failing fast, but we log the attempt
fi

# Check if migrations dir exists
if [ ! -d "/app/migrations" ]; then
    echo "❌ [ERROR] Migrations directory NOT FOUND at /app/migrations"
    ls -R /app
    exit 1
fi

alembic upgrade head
echo "✅ [INIT] Migrations complete!"

echo "🚀 [INIT] Starting Hub API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
