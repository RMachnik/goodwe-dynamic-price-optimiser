#!/bin/bash
set -e

# Raspberry Pi Backup Script
# Usage: ./backup-rasp.sh

echo "🔐 Connecting to Raspberry Pi..."
BACKUP_DIR="goodwe-backup-$(date +%Y%m%d-%H%M%S)"

# Create backup on Raspberry Pi
ssh rmachnik@192.168.33.10 << 'ENDSSH'
set -e

BACKUP_DIR="backups/pre-cloud-deployment-$(date +%Y%m%d)"
mkdir -p ~/$BACKUP_DIR
cd ~/$BACKUP_DIR

echo "📦 Backing up application data..."

# 0. Stop the service for consistent backup
echo "  ⏸️ Stopping goodwe-coordinator service..."
if systemctl is-active --quiet goodwe-coordinator 2>/dev/null; then
    sudo systemctl stop goodwe-coordinator
    echo "  ✓ Service stopped"
    SERVICE_WAS_RUNNING=true
else
    echo "  ℹ Service was not running"
    SERVICE_WAS_RUNNING=false
fi

# Wait for any pending writes
sleep 2

# 1. Export SQLite database (if exists)
if [ -f ~/sources/goodwe-dynamic-price-optimiser/data/telemetry.db ]; then
    echo "  ✓ Exporting SQLite database..."
    sqlite3 ~/sources/goodwe-dynamic-price-optimiser/data/telemetry.db ".backup telemetry-backup.db"
else
    echo "  ℹ No database found to backup"
fi

# 2. Backup configuration files
echo "  ✓ Backing up config files..."
if [ -f ~/sources/goodwe-dynamic-price-optimiser/config/config.yaml ]; then
    cp ~/sources/goodwe-dynamic-price-optimiser/config/config.yaml ./config.yaml.backup
fi

if [ -d ~/sources/goodwe-dynamic-price-optimiser/config ]; then
    cp -r ~/sources/goodwe-dynamic-price-optimiser/config ./config-backup/
fi

if [ -f ~/sources/goodwe-dynamic-price-optimiser/.env ]; then
    cp ~/sources/goodwe-dynamic-price-optimiser/.env ./env.backup
fi

# Backup entire data directory
if [ -d ~/sources/goodwe-dynamic-price-optimiser/data ]; then
    echo "  ✓ Backing up data directory..."
    cp -r ~/sources/goodwe-dynamic-price-optimiser/data ./data-backup/
fi

# 3. Record current git commit
echo "  ✓ Recording git commit..."
cd ~/sources/goodwe-dynamic-price-optimiser
git log -1 --oneline > ~/$BACKUP_DIR/git-commit.txt
echo "Current branch: $(git branch --show-current)" >> ~/$BACKUP_DIR/git-commit.txt
git status >> ~/$BACKUP_DIR/git-status.txt

# 4. Backup systemd service (if exists)
if [ -f /etc/systemd/system/goodwe-coordinator.service ]; then
    echo "  ✓ Backing up systemd service..."
    sudo cp /etc/systemd/system/goodwe-coordinator.service ~/$BACKUP_DIR/ 2>/dev/null || true
fi

# 5. Document current state
echo "  ✓ Documenting system state..."
systemctl status goodwe-coordinator --no-pager > ~/$BACKUP_DIR/service-status.txt 2>&1 || echo "Service not found" > ~/$BACKUP_DIR/service-status.txt
pip freeze > ~/$BACKUP_DIR/requirements-current.txt 2>/dev/null || true

# 6. Create a manifest
cat > ~/$BACKUP_DIR/MANIFEST.txt << EOF
=== GoodWe Raspberry Pi Backup ===
Date: $(date)
Hostname: $(hostname)
User: $(whoami)
Python: $(python3 --version 2>&1)
Working Directory: ~/sources/goodwe-dynamic-price-optimiser

Files in this backup:
$(ls -lh)

Git Status:
$(cat git-status.txt)

Last Commit:
$(cat git-commit.txt)
EOF

# 7. Restart the service if it was running
if [ "$SERVICE_WAS_RUNNING" = true ]; then
    echo "  ▶️ Restarting goodwe-coordinator service..."
    sudo systemctl start goodwe-coordinator
    sleep 2
    if systemctl is-active --quiet goodwe-coordinator; then
        echo "  ✓ Service restarted successfully"
    else
        echo "  ⚠️ Warning: Service failed to restart!"
    fi
fi

echo "✅ Backup complete on Raspberry Pi!"
echo "   Location: ~/$BACKUP_DIR"
ls -lh ~/$BACKUP_DIR

ENDSSH

# Copy backup to local machine
echo "📥 Downloading backup to local machine..."
BACKUP_DIR_NAME="backups/pre-cloud-deployment-$(date +%Y%m%d)"
scp -r rmachnik@192.168.33.10:~/$BACKUP_DIR_NAME ~/Desktop/

echo "✅ Backup complete!"
echo "   Local backup saved to: ~/Desktop/$BACKUP_DIR_NAME"
echo ""
echo "📋 Backup contents:"
ls -lh ~/Desktop/$BACKUP_DIR_NAME

echo ""
echo "🎯 Next steps:"
echo "   1. Review backup: ~/Desktop/$BACKUP_DIR_NAME"
echo "   2. Run: ./scripts/deploy-vps-setup.sh (if first time)"
echo "   3. Run: ./scripts/deploy-hub-api.sh"
