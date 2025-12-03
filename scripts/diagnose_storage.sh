#!/bin/bash
# =============================================================================
# Storage Diagnostics Script
# GoodWe Dynamic Price Optimiser - Database & Storage Health Check
# =============================================================================
#
# This script diagnoses storage issues on the Raspberry Pi or any deployment.
# Run with: ./scripts/diagnose_storage.sh
#
# Checks performed:
#   - Database file existence and size
#   - Table row counts (system_state, energy_data, coordinator_decisions)
#   - Latest timestamps from each table
#   - price_history.json existence
#   - WAL mode verification
#   - Service status via systemctl
#   - Recent log entries via journalctl
#   - Storage-related errors from logs
#
# =============================================================================

set -e

# Auto-detect project directory (same as database_rollout.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration - uses project-relative paths
INSTALL_DIR="${INSTALL_DIR:-$PROJECT_DIR}"
DATA_DIR="${INSTALL_DIR}/data"
DB_FILE="${DATA_DIR}/goodwe_energy.db"
PRICE_CACHE_FILE="${DATA_DIR}/price_history.json"
LOG_DIR="${INSTALL_DIR}/logs"
LOG_FILE="${LOG_DIR}/master_coordinator.log"
OUT_DIR="${INSTALL_DIR}/out"

# Service name
SERVICE="goodwe-master-coordinator"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
header() { echo -e "\n${CYAN}=== $1 ===${NC}"; }

# =============================================================================
# MAIN DIAGNOSTICS
# =============================================================================

echo "=============================================="
echo "  Storage Diagnostics"
echo "  GoodWe Dynamic Price Optimiser"
echo "=============================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Data directory: $DATA_DIR"
echo "Database file: $DB_FILE"
echo ""

# Track issues
issues_found=0

# -----------------------------------------------------------------------------
# 1. Database File Check
# -----------------------------------------------------------------------------
header "Database File"

if [ -f "$DB_FILE" ]; then
    success "Database file exists: $DB_FILE"
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo "   Size: $DB_SIZE"
    
    # Check for WAL files
    if [ -f "${DB_FILE}-wal" ]; then
        WAL_SIZE=$(du -h "${DB_FILE}-wal" | cut -f1)
        echo "   WAL file: ${WAL_SIZE}"
    fi
    if [ -f "${DB_FILE}-shm" ]; then
        SHM_SIZE=$(du -h "${DB_FILE}-shm" | cut -f1)
        echo "   SHM file: ${SHM_SIZE}"
    fi
else
    error "Database file NOT FOUND: $DB_FILE"
    ((issues_found++))
fi

# -----------------------------------------------------------------------------
# 2. Database Integrity & WAL Mode
# -----------------------------------------------------------------------------
header "Database Integrity"

if [ -f "$DB_FILE" ] && command -v sqlite3 &> /dev/null; then
    # Check integrity
    INTEGRITY=$(sqlite3 "$DB_FILE" 'PRAGMA integrity_check;' 2>/dev/null)
    if [ "$INTEGRITY" = "ok" ]; then
        success "Database integrity: OK"
    else
        error "Database integrity: FAILED"
        echo "   $INTEGRITY"
        ((issues_found++))
    fi
    
    # Check WAL mode
    JOURNAL_MODE=$(sqlite3 "$DB_FILE" 'PRAGMA journal_mode;' 2>/dev/null)
    if [ "$JOURNAL_MODE" = "wal" ]; then
        success "Journal mode: WAL (recommended)"
    else
        warn "Journal mode: $JOURNAL_MODE (expected: wal)"
    fi
else
    if ! command -v sqlite3 &> /dev/null; then
        warn "sqlite3 not installed - skipping integrity check"
    fi
fi

# -----------------------------------------------------------------------------
# 3. Table Row Counts
# -----------------------------------------------------------------------------
header "Table Row Counts"

if [ -f "$DB_FILE" ] && command -v sqlite3 &> /dev/null; then
    # Get row counts for key tables
    TABLES=("energy_data" "system_state" "coordinator_decisions" "charging_sessions" "battery_selling_sessions")
    
    for table in "${TABLES[@]}"; do
        COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "error")
        if [ "$COUNT" = "error" ]; then
            warn "$table: table not found or error"
        elif [ "$COUNT" -eq 0 ]; then
            error "$table: 0 rows (EMPTY)"
            ((issues_found++))
        else
            success "$table: $COUNT rows"
        fi
    done
else
    warn "Cannot check table row counts (sqlite3 not available or DB missing)"
fi

# -----------------------------------------------------------------------------
# 4. Latest Timestamps
# -----------------------------------------------------------------------------
header "Latest Timestamps"

if [ -f "$DB_FILE" ] && command -v sqlite3 &> /dev/null; then
    # Get latest timestamp from key tables
    echo "Most recent records:"
    
    LATEST_ENERGY=$(sqlite3 "$DB_FILE" "SELECT MAX(timestamp) FROM energy_data;" 2>/dev/null || echo "N/A")
    echo "   energy_data:          $LATEST_ENERGY"
    
    LATEST_STATE=$(sqlite3 "$DB_FILE" "SELECT MAX(timestamp) FROM system_state;" 2>/dev/null || echo "N/A")
    echo "   system_state:         $LATEST_STATE"
    
    LATEST_DECISION=$(sqlite3 "$DB_FILE" "SELECT MAX(timestamp) FROM coordinator_decisions;" 2>/dev/null || echo "N/A")
    echo "   coordinator_decisions: $LATEST_DECISION"
    
    # Check if data is stale (more than 10 minutes old)
    if [ "$LATEST_STATE" != "N/A" ] && [ -n "$LATEST_STATE" ]; then
        # Try to parse and check age (best effort)
        CURRENT_TIME=$(date +%s)
        # This is a simple check - may not work for all timestamp formats
        if command -v python3 &> /dev/null; then
            AGE_SECONDS=$(python3 -c "
from datetime import datetime
try:
    ts = '$LATEST_STATE'.replace('T', ' ').split('.')[0]
    dt = datetime.fromisoformat(ts)
    age = (datetime.now() - dt).total_seconds()
    print(int(age))
except:
    print(-1)
" 2>/dev/null)
            if [ "$AGE_SECONDS" -gt 600 ] 2>/dev/null; then
                warn "system_state data is stale (${AGE_SECONDS}s old, >10min)"
            elif [ "$AGE_SECONDS" -ge 0 ] 2>/dev/null; then
                success "system_state data is fresh (${AGE_SECONDS}s old)"
            fi
        fi
    fi
else
    warn "Cannot check timestamps (sqlite3 not available or DB missing)"
fi

# -----------------------------------------------------------------------------
# 5. Price History Cache
# -----------------------------------------------------------------------------
header "Price History Cache"

if [ -f "$PRICE_CACHE_FILE" ]; then
    success "price_history.json exists"
    CACHE_SIZE=$(du -h "$PRICE_CACHE_FILE" | cut -f1)
    echo "   Size: $CACHE_SIZE"
    
    # Count entries if jq is available
    if command -v jq &> /dev/null; then
        ENTRY_COUNT=$(jq 'length' "$PRICE_CACHE_FILE" 2>/dev/null || echo "error")
        if [ "$ENTRY_COUNT" != "error" ]; then
            echo "   Entries: $ENTRY_COUNT"
        fi
    elif command -v python3 &> /dev/null; then
        ENTRY_COUNT=$(python3 -c "import json; print(len(json.load(open('$PRICE_CACHE_FILE'))))" 2>/dev/null || echo "error")
        if [ "$ENTRY_COUNT" != "error" ]; then
            echo "   Entries: $ENTRY_COUNT"
        fi
    fi
else
    warn "price_history.json NOT FOUND: $PRICE_CACHE_FILE"
    echo "   This file is created when adaptive thresholds collect price data"
fi

# -----------------------------------------------------------------------------
# 6. Coordinator State Files
# -----------------------------------------------------------------------------
header "Coordinator State Files"

STATE_FILES=$(ls -1 "$OUT_DIR"/coordinator_state_*.json 2>/dev/null | wc -l)
if [ "$STATE_FILES" -gt 0 ]; then
    success "Found $STATE_FILES coordinator state file(s)"
    LATEST_STATE_FILE=$(ls -t "$OUT_DIR"/coordinator_state_*.json 2>/dev/null | head -1)
    if [ -n "$LATEST_STATE_FILE" ]; then
        echo "   Latest: $(basename "$LATEST_STATE_FILE")"
        FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$LATEST_STATE_FILE" 2>/dev/null || stat -f %m "$LATEST_STATE_FILE" 2>/dev/null) ))
        echo "   Age: ${FILE_AGE}s"
    fi
else
    warn "No coordinator state files found in $OUT_DIR"
fi

# -----------------------------------------------------------------------------
# 7. Service Status
# -----------------------------------------------------------------------------
header "Service Status"

if command -v systemctl &> /dev/null; then
    if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
        success "Service $SERVICE is running"
        # Get PID and uptime
        PID=$(systemctl show "$SERVICE" --property=MainPID --value 2>/dev/null)
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            echo "   PID: $PID"
        fi
    else
        error "Service $SERVICE is NOT running"
        ((issues_found++))
        echo "   Start with: sudo systemctl start $SERVICE"
    fi
else
    warn "systemctl not available - cannot check service status"
fi

# -----------------------------------------------------------------------------
# 8. Recent Log Entries
# -----------------------------------------------------------------------------
header "Recent Log Entries (last 10)"

if command -v journalctl &> /dev/null; then
    echo ""
    sudo journalctl -u "$SERVICE" -n 10 --no-pager 2>/dev/null || warn "Cannot read journalctl (may need sudo)"
else
    if [ -f "$LOG_FILE" ]; then
        echo ""
        tail -10 "$LOG_FILE" 2>/dev/null || warn "Cannot read log file"
    else
        warn "No log file found at $LOG_FILE"
    fi
fi

# -----------------------------------------------------------------------------
# 9. Storage-Related Errors
# -----------------------------------------------------------------------------
header "Storage-Related Errors (last 24h)"

ERROR_COUNT=0
if command -v journalctl &> /dev/null; then
    ERROR_COUNT=$(sudo journalctl -u "$SERVICE" --since "24 hours ago" --no-pager 2>/dev/null | grep -iE "storage.*error|failed.*save|database.*error|sqlite.*error" | wc -l)
elif [ -f "$LOG_FILE" ]; then
    ERROR_COUNT=$(grep -iE "storage.*error|failed.*save|database.*error|sqlite.*error" "$LOG_FILE" 2>/dev/null | tail -100 | wc -l)
fi

if [ "$ERROR_COUNT" -eq 0 ]; then
    success "No storage errors found in last 24h"
else
    warn "Found $ERROR_COUNT storage-related errors"
    echo ""
    echo "Recent storage errors:"
    if command -v journalctl &> /dev/null; then
        sudo journalctl -u "$SERVICE" --since "24 hours ago" --no-pager 2>/dev/null | grep -iE "storage.*error|failed.*save|database.*error|sqlite.*error" | tail -5
    elif [ -f "$LOG_FILE" ]; then
        grep -iE "storage.*error|failed.*save|database.*error|sqlite.*error" "$LOG_FILE" 2>/dev/null | tail -5
    fi
fi

# -----------------------------------------------------------------------------
# 10. Mock Data Warnings
# -----------------------------------------------------------------------------
header "Mock Data Warnings (indicates storage read issues)"

MOCK_WARNINGS=0
if command -v journalctl &> /dev/null; then
    MOCK_WARNINGS=$(sudo journalctl -u "$SERVICE" --since "1 hour ago" --no-pager 2>/dev/null | grep -c "No real inverter data available" || echo 0)
elif [ -f "$LOG_FILE" ]; then
    MOCK_WARNINGS=$(grep -c "No real inverter data available" "$LOG_FILE" 2>/dev/null | tail -100 || echo 0)
fi

if [ "$MOCK_WARNINGS" -eq 0 ]; then
    success "No mock data warnings in last hour"
else
    warn "Found $MOCK_WARNINGS 'mock data' warnings in last hour"
    echo "   This indicates LogWebServer cannot read real data from storage"
fi

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
header "Summary"

if [ "$issues_found" -eq 0 ]; then
    success "All checks passed! Storage appears healthy."
else
    error "Found $issues_found issue(s) that need attention"
    echo ""
    echo "Recommended actions:"
    echo "  1. If system_state is empty: wait 5 min after service restart"
    echo "  2. If service not running: sudo systemctl start $SERVICE"
    echo "  3. If database missing: check config/master_coordinator_config.yaml"
    echo "  4. For persistent issues: check logs with 'sudo journalctl -u $SERVICE -f'"
fi

echo ""
echo "=============================================="
echo "  Diagnostics Complete"
echo "=============================================="
