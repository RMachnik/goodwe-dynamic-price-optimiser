#!/bin/bash
set -e

# Raspberry Pi Restore Script
# Usage: ./restore-rasp.sh [backup-directory]
# Example: ./restore-rasp.sh ~/Desktop/backups/pre-cloud-deployment-20260110

echo "🔄 Raspberry Pi Restore Utility"
echo ""

# Get backup directory
BACKUP_DIR="${1:-}"

if [ -z "$BACKUP_DIR" ]; then
    echo "Available backups on Desktop:"
    ls -d ~/Desktop/backups/pre-cloud-deployment-* 2>/dev/null || echo "No backups found in ~/Desktop/backups/"
    echo ""
    read -p "Enter backup directory path: " BACKUP_DIR
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Backup directory not found: $BACKUP_DIR"
    exit 1
fi

echo "📦 Backup to restore: $BACKUP_DIR"
echo ""
echo "Contents:"
ls -lh "$BACKUP_DIR"
echo ""

# Display manifest if exists
if [ -f "$BACKUP_DIR/MANIFEST.txt" ]; then
    echo "📋 Backup Manifest:"
    cat "$BACKUP_DIR/MANIFEST.txt"
    echo ""
fi

# Show git commit info
if [ -f "$BACKUP_DIR/git-commit.txt" ]; then
    echo "📌 Git state at backup time:"
    cat "$BACKUP_DIR/git-commit.txt"
    echo ""
fi

read -p "⚠️ This will restore the Pi to this backup state. Continue? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "🚀 Starting restore process..."

# Upload backup to Pi
echo "📤 Uploading backup to Raspberry Pi..."
scp -r "$BACKUP_DIR" rmachnik@192.168.33.10:~/restore-temp/

# Execute restore on Pi
ssh rmachnik@192.168.33.10 << 'ENDSSH'
set -e

RESTORE_DIR=~/restore-temp
APP_DIR=~/sources/goodwe-dynamic-price-optimiser

# Handle nested directory structure from scp
if [ -f "$RESTORE_DIR/MANIFEST.txt" ]; then
    echo "📦 Restoring from: $RESTORE_DIR"
else
    # Find the actual backup directory (scp may create nested structure)
    ACTUAL_DIR=$(find ~/restore-temp -maxdepth 2 -name "MANIFEST.txt" -exec dirname {} \; 2>/dev/null | head -1)
    if [ -n "$ACTUAL_DIR" ]; then
        RESTORE_DIR="$ACTUAL_DIR"
        echo "📦 Restoring from: $RESTORE_DIR"
    else
        echo "❌ Could not find backup files in restore-temp"
        exit 1
    fi
fi

# 1. Stop the service
echo "  ⏸️ Stopping goodwe-coordinator service..."
if systemctl is-active --quiet goodwe-coordinator 2>/dev/null; then
    sudo systemctl stop goodwe-coordinator
    echo "  ✓ Service stopped"
fi

# 2. Restore git state
if [ -f "$RESTORE_DIR/git-commit.txt" ]; then
    COMMIT_HASH=$(head -1 "$RESTORE_DIR/git-commit.txt" | cut -d' ' -f1)
    echo "  ✓ Restoring to git commit: $COMMIT_HASH"
    cd "$APP_DIR"
    git fetch origin 2>/dev/null || true
    git checkout "$COMMIT_HASH" 2>/dev/null || echo "  ⚠️ Could not checkout exact commit, skipping..."
fi

# 3. Restore config files
echo "  ✓ Restoring configuration files..."
if [ -d "$RESTORE_DIR/config-backup" ]; then
    cp -r "$RESTORE_DIR/config-backup/"* "$APP_DIR/config/" 2>/dev/null || true
elif [ -f "$RESTORE_DIR/config.yaml.backup" ]; then
    cp "$RESTORE_DIR/config.yaml.backup" "$APP_DIR/config/config.yaml"
fi

if [ -f "$RESTORE_DIR/env.backup" ]; then
    cp "$RESTORE_DIR/env.backup" "$APP_DIR/.env"
fi

# 4. Restore database
echo "  ✓ Restoring database..."
if [ -f "$RESTORE_DIR/telemetry-backup.db" ]; then
    mkdir -p "$APP_DIR/data"
    cp "$RESTORE_DIR/telemetry-backup.db" "$APP_DIR/data/telemetry.db"
elif [ -d "$RESTORE_DIR/data-backup" ]; then
    mkdir -p "$APP_DIR/data"
    cp -r "$RESTORE_DIR/data-backup/"* "$APP_DIR/data/" 2>/dev/null || true
fi

# 5. Restore systemd service if it was backed up
if [ -f "$RESTORE_DIR/goodwe-coordinator.service" ]; then
    echo "  ✓ Restoring systemd service file..."
    sudo cp "$RESTORE_DIR/goodwe-coordinator.service" /etc/systemd/system/
    sudo systemctl daemon-reload
fi

# 6. Restart service
echo "  ▶️ Starting goodwe-coordinator service..."
sudo systemctl start goodwe-coordinator 2>/dev/null || echo "  ⚠️ Could not start service"

# Wait and check status
sleep 3
if systemctl is-active --quiet goodwe-coordinator 2>/dev/null; then
    echo "  ✓ Service running!"
else
    echo "  ⚠️ Service not running. Check logs with: journalctl -u goodwe-coordinator -n 50"
fi

# 7. Cleanup
rm -rf ~/restore-temp

echo ""
echo "✅ Restore complete!"
echo ""
echo "📋 Current status:"
systemctl status goodwe-coordinator --no-pager 2>/dev/null || echo "Service status unavailable"

ENDSSH

echo ""
echo "✅ Raspberry Pi restored from backup!"
echo ""
echo "🔍 Verify by running:"
echo "   ssh rmachnik@192.168.33.10 'systemctl status goodwe-coordinator'"
echo ""
echo "📋 Check logs:"
echo "   ssh rmachnik@192.168.33.10 'journalctl -u goodwe-coordinator -n 20'"
