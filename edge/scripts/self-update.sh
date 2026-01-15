#!/bin/bash
# GoodWe Dynamic Price Optimiser - Enhanced Edge Self-Update Script
# Performs a safe update with health checks and automatic rollback.

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 Starting self-update at $(date)"
echo "Current directory: $PWD"

# 0. Backup current local data (Safety First)
backup_local_data() {
    local backup_dir="backups/auto_pre_update_$(date +%Y%m%d_%H%M%S)"
    echo "💾 Creating automated pre-update backup: $backup_dir"
    mkdir -p "$backup_dir"
    
    # Store config
    if [ -d "config" ]; then cp -r config "$backup_dir/"; fi
    if [ -f ".env" ]; then cp .env "$backup_dir/"; fi
    
    # Store database (if sqlite)
    if [ -f "data/telemetry.db" ]; then
        if command -v sqlite3 >/dev/null 2>&1; then
            sqlite3 data/telemetry.db ".backup $backup_dir/telemetry.db"
        else
            cp data/telemetry.db "$backup_dir/"
        fi
    fi
    echo "✅ Backup saved to $backup_dir"
}

# 1. Save current state
OLD_COMMIT=$(git rev-parse HEAD)
echo "💾 Current commit: $OLD_COMMIT"
backup_local_data

# 1. Cleanup local python state (prevents issues with stale bytecode)
find . -name "__pycache__" -type d -exec rm -rf {} +

# 2. Update Code
echo "📥 Fetching latest code..."
git fetch

# Identify current branch (usually main or master)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📍 Resetting to origin/$CURRENT_BRANCH..."
git reset --hard "origin/$CURRENT_BRANCH"

# 3. Check for requirement changes
if ! git diff --quiet $OLD_COMMIT HEAD -- requirements.txt; then
    echo "📦 Requirements changed. Updating dependencies..."
    if [ -f "venv/bin/pip" ]; then
        ./venv/bin/pip install -r requirements.txt
    else
        pip3 install -r requirements.txt || echo "⚠️ Pip install failed, continuing..."
    fi
fi

# 4. Syntax Validation (Prevents Bricking)
echo "🔍 Running syntax check on Python files..."
SYNTAX_ERRORS=""
for pyfile in $(find ./src -name "*.py" -type f); do
    if ! python3 -m py_compile "$pyfile" 2>&1; then
        SYNTAX_ERRORS="$SYNTAX_ERRORS\n$pyfile"
    fi
done

if [ -n "$SYNTAX_ERRORS" ]; then
    echo "❌ Syntax errors detected in the following files:$SYNTAX_ERRORS"
    echo "⚠️ Rolling back to $OLD_COMMIT..."
    git reset --hard "$OLD_COMMIT"
    exit 1
fi

echo "✅ Syntax check passed."

# 5. Restart Services
echo "♻️ Restarting GoodWe services..."
if [ -f "./scripts/manage_services.sh" ]; then
    bash ./scripts/manage_services.sh restart
else
    sudo systemctl restart goodwe-coordinator.service || { echo "❌ Failed to restart coordinator"; exit 1; }
    sudo systemctl restart goodwe-reporter.service || true
    sudo systemctl restart goodwe-log-server.service || true
fi

# 6. Post-deployment Health Check
echo "🩺 Verifying deployment health..."
sleep 15 # Wait for services to initialize

HEALTH_URL="http://localhost:8080/health"
if command -v curl >/dev/null 2>&1; then
    if curl --silent --fail "$HEALTH_URL" | grep -q "healthy"; then
        echo "✅ Health check passed: Service is healthy."
    else
        echo "❌ Health check FAILED! Service not responding correctly."
        echo "⚠️ ROLLING BACK to $OLD_COMMIT..."
        git reset --hard "$OLD_COMMIT"
        sudo systemctl restart goodwe-coordinator.service
        exit 1
    fi
else
    echo "⚠️ curl not found, skipping health check."
fi

echo "✅ Self-update complete at $(date)"
