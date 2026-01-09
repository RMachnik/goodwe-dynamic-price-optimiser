#!/bin/sh
set -e

echo "🐘 [INIT] Running database migrations..."
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
