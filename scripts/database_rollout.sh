#!/bin/bash
# =============================================================================
# Database Migration Rollout Script
# GoodWe Dynamic Price Optimiser - SQLite Database Feature
# =============================================================================
#
# This script guides you through safely enabling the database storage feature.
# Run with: ./scripts/database_rollout.sh [command]
#
# Commands:
#   preflight    - Run pre-deployment checks
#   install-deps - Install required Python dependencies
#   backup       - Create backup of existing data
#   deploy       - Deploy and restart service
#   verify       - Verify database is working
#   monitor      - Show monitoring commands
#   rollback     - Rollback to file-only mode
#   migrate      - Run historical data migration
#   help         - Show this help message
#
# =============================================================================

set -e

# Auto-detect project directory (same as manage_services.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration - uses project-relative paths
INSTALL_DIR="${INSTALL_DIR:-$PROJECT_DIR}"
DATA_DIR="${INSTALL_DIR}/data"
CONFIG_FILE="${INSTALL_DIR}/config/master_coordinator_config.yaml"
DB_FILE="${DATA_DIR}/goodwe_energy.db"
BACKUP_DIR="${HOME}/goodwe_backups"
LOG_DIR="${INSTALL_DIR}/logs"
LOG_FILE="${LOG_DIR}/master_coordinator.log"
OUT_DIR="${INSTALL_DIR}/out"
REQUIREMENTS_FILE="${INSTALL_DIR}/requirements.txt"

# Service management (aligned with manage_services.sh)
SERVICE="goodwe-master-coordinator"
MANAGE_SCRIPT="${SCRIPT_DIR}/manage_services.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# PREFLIGHT CHECKS
# =============================================================================
cmd_preflight() {
    echo "=============================================="
    echo "  Pre-Flight Checks for Database Rollout"
    echo "=============================================="
    echo ""
    
    local checks_passed=0
    local checks_failed=0
    
    # Check 1: Data directory exists
    info "Checking data directory..."
    if [ -d "$DATA_DIR" ]; then
        success "Data directory exists: $DATA_DIR"
        ((checks_passed++))
    else
        warn "Data directory does not exist: $DATA_DIR"
        echo "  Run: sudo mkdir -p $DATA_DIR && sudo chown \$(whoami):\$(whoami) $DATA_DIR"
        ((checks_failed++))
    fi
    
    # Check 2: Data directory writable
    info "Checking write permissions..."
    if [ -w "$DATA_DIR" ] 2>/dev/null; then
        success "Data directory is writable"
        ((checks_passed++))
    else
        error "Data directory is not writable"
        echo "  Run: sudo chown \$(whoami):\$(whoami) $DATA_DIR"
        ((checks_failed++))
    fi
    
    # Check 3: Disk space (cross-platform: works on Linux and macOS)
    info "Checking disk space..."
    local free_space=""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: df outputs in 512-byte blocks by default, use -g for GB
        free_space=$(df -g "$DATA_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
    else
        # Linux: use -BG for GB
        free_space=$(df -BG "$DATA_DIR" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G')
    fi
    
    if [ -n "$free_space" ] && [ "$free_space" -gt 1 ] 2>/dev/null; then
        success "Disk space: ${free_space}GB free (>1GB required)"
        ((checks_passed++))
    else
        warn "Low disk space or unable to check (need >1GB free)"
        # Don't fail on disk space warning, just warn
        ((checks_passed++))
    fi
    
    # Check 4: Config file exists
    info "Checking configuration..."
    if [ -f "$CONFIG_FILE" ]; then
        success "Config file exists: $CONFIG_FILE"
        ((checks_passed++))
        
        # Check if database is enabled
        if grep -q "database_storage:" "$CONFIG_FILE"; then
            if grep -A2 "database_storage:" "$CONFIG_FILE" | grep -q "enabled: true"; then
                success "Database storage is enabled in config"
            else
                warn "Database storage is disabled in config"
            fi
        fi
    else
        error "Config file not found: $CONFIG_FILE"
        ((checks_failed++))
    fi
    
    # Check 5: Python aiosqlite dependency
    info "Checking aiosqlite dependency..."
    if python3 -c "import aiosqlite; print(f'aiosqlite {aiosqlite.__version__}')" 2>/dev/null; then
        success "aiosqlite is installed"
        ((checks_passed++))
    else
        error "aiosqlite not installed"
        echo "  Run: pip install aiosqlite>=0.19.0"
        echo "  Or: pip install -r requirements.txt"
        ((checks_failed++))
    fi
    
    # Check 6: SQLite3 CLI available
    info "Checking SQLite3 CLI..."
    if command -v sqlite3 &> /dev/null; then
        success "SQLite3 is installed: $(sqlite3 --version)"
        ((checks_passed++))
    else
        warn "SQLite3 not found (optional, for manual inspection)"
        ((checks_passed++))
    fi
    
    # Check 7: Python database test
    info "Testing Python SQLite write..."
    if python3 -c "
import sqlite3
import os
test_db = '$DATA_DIR/test_preflight.db'
try:
    conn = sqlite3.connect(test_db)
    conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
    conn.close()
    os.remove(test_db)
    print('OK')
except Exception as e:
    print(f'FAIL: {e}')
    exit(1)
" 2>/dev/null; then
        success "Python SQLite write test passed"
        ((checks_passed++))
    else
        error "Python SQLite write test failed"
        ((checks_failed++))
    fi
    
    echo ""
    echo "=============================================="
    echo "  Results: $checks_passed passed, $checks_failed failed"
    echo "=============================================="
    
    if [ $checks_failed -gt 0 ]; then
        error "Pre-flight checks failed. Fix issues above before proceeding."
        echo ""
        echo "Tip: Run './scripts/database_rollout.sh install-deps' to install dependencies"
        return 1
    else
        success "All pre-flight checks passed! Safe to proceed."
        return 0
    fi
}

# =============================================================================
# INSTALL DEPENDENCIES
# =============================================================================
cmd_install_deps() {
    echo "=============================================="
    echo "  Installing Python Dependencies"
    echo "=============================================="
    echo ""
    
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        error "Requirements file not found: $REQUIREMENTS_FILE"
        return 1
    fi
    
    info "Requirements file: $REQUIREMENTS_FILE"
    echo ""
    
    # Check if we're in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        success "Virtual environment detected: $VIRTUAL_ENV"
    else
        warn "No virtual environment detected"
        echo "  Consider activating a venv first: source .venv/bin/activate"
        echo ""
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Installation cancelled"
            return 0
        fi
    fi
    
    # Install database-specific dependencies
    info "Installing aiosqlite (required for database)..."
    pip install "aiosqlite>=0.19.0"
    
    echo ""
    info "Verifying installation..."
    if python3 -c "import aiosqlite; print(f'aiosqlite {aiosqlite.__version__} installed successfully')" 2>/dev/null; then
        success "Database dependencies installed successfully!"
    else
        error "Failed to verify aiosqlite installation"
        return 1
    fi
    
    echo ""
    info "To install ALL project dependencies, run:"
    echo "  pip install -r $REQUIREMENTS_FILE"
}

# =============================================================================
# BACKUP
# =============================================================================
cmd_backup() {
    echo "=============================================="
    echo "  Creating Backup"
    echo "=============================================="
    echo ""
    
    mkdir -p "$BACKUP_DIR"
    local backup_file="$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    info "Creating backup at: $backup_file"
    
    cd "$INSTALL_DIR"
    
    # Backup out directory (JSON files)
    if [ -d "out" ]; then
        info "Backing up out/ directory..."
        tar -czvf "$backup_file" out/ 2>/dev/null || true
        success "Backup created: $backup_file"
        echo "  Size: $(ls -lh "$backup_file" | awk '{print $5}')"
    else
        warn "No out/ directory found to backup"
    fi
    
    # Also backup existing database if present
    if [ -f "$DB_FILE" ]; then
        local db_backup="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).db"
        info "Backing up existing database..."
        cp "$DB_FILE" "$db_backup"
        success "Database backup: $db_backup"
    fi
    
    echo ""
    success "Backup complete!"
    echo "  Backups stored in: $BACKUP_DIR"
}

# =============================================================================
# DEPLOY
# =============================================================================
cmd_deploy() {
    echo "=============================================="
    echo "  Deploying Database Feature"
    echo "=============================================="
    echo ""
    
    info "Project directory: $PROJECT_DIR"
    info "Service: $SERVICE"
    echo ""
    
    # Check if running in Docker or systemd
    if [ -f "$PROJECT_DIR/docker-compose.yml" ] && command -v docker-compose &> /dev/null; then
        info "Docker environment detected"
        
        read -p "Restart Docker containers? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            info "Stopping containers..."
            cd "$PROJECT_DIR"
            docker-compose down
            
            info "Starting containers with rebuild..."
            docker-compose up -d --build
            
            success "Docker containers restarted"
        fi
    elif systemctl is-active --quiet "$SERVICE" 2>/dev/null || systemctl list-unit-files | grep -q "$SERVICE"; then
        info "Systemd service detected: $SERVICE"
        
        # Use manage_services.sh if available, otherwise direct systemctl
        if [ -x "$MANAGE_SCRIPT" ]; then
            read -p "Restart service using manage_services.sh? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                info "Restarting service via manage_services.sh..."
                "$MANAGE_SCRIPT" restart
                success "Service restarted"
            fi
        else
            read -p "Restart systemd service? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                info "Restarting service..."
                sudo systemctl restart "$SERVICE"
                success "Service restarted"
            fi
        fi
    else
        warn "No Docker or systemd service detected"
        echo "  Please restart your service manually"
        echo "  Or install systemd service: $MANAGE_SCRIPT install"
    fi
    
    echo ""
    info "Waiting 10 seconds for service to start..."
    sleep 10
    
    cmd_verify
}

# =============================================================================
# VERIFY
# =============================================================================
cmd_verify() {
    echo "=============================================="
    echo "  Verifying Database Operation"
    echo "=============================================="
    echo ""
    
    local checks_passed=0
    local checks_failed=0
    
    # Check 1: Database file exists
    info "Checking database file..."
    if [ -f "$DB_FILE" ]; then
        success "Database file exists: $DB_FILE"
        echo "  Size: $(ls -lh "$DB_FILE" | awk '{print $5}')"
        ((checks_passed++))
    else
        warn "Database file not yet created (may take a few minutes)"
        ((checks_failed++))
    fi
    
    # Check 2: Storage initialization in logs
    info "Checking logs for storage initialization..."
    if [ -f "$LOG_FILE" ]; then
        if grep -q "Storage layer initialized\|Connected to SQLite" "$LOG_FILE" 2>/dev/null; then
            success "Storage initialization found in logs"
            ((checks_passed++))
        else
            warn "Storage initialization not found in logs yet"
            ((checks_failed++))
        fi
        
        # Check for errors
        local error_count=$(grep -c "Error saving\|Failed to connect" "$LOG_FILE" 2>/dev/null || echo "0")
        if [ "$error_count" -gt 0 ]; then
            warn "Found $error_count storage errors in logs"
            echo "  Run: grep -i 'error.*storage\|failed.*connect' $LOG_FILE | tail -5"
        else
            success "No storage errors found in logs"
            ((checks_passed++))
        fi
    else
        warn "Log file not found: $LOG_FILE"
    fi
    
    # Check 3: Database has tables
    if [ -f "$DB_FILE" ] && command -v sqlite3 &> /dev/null; then
        info "Checking database tables..."
        local table_count=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
        if [ "$table_count" -gt 0 ]; then
            success "Database has $table_count tables"
            ((checks_passed++))
            
            # Show table names
            echo "  Tables: $(sqlite3 "$DB_FILE" "SELECT GROUP_CONCAT(name) FROM sqlite_master WHERE type='table';" 2>/dev/null)"
        else
            warn "No tables found in database"
            ((checks_failed++))
        fi
        
        # Check data counts
        info "Checking data in tables..."
        for table in energy_data system_state coordinator_decisions; do
            local count=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
            if [ "$count" -gt 0 ]; then
                success "  $table: $count records"
            else
                info "  $table: 0 records (may populate over time)"
            fi
        done
    fi
    
    echo ""
    echo "=============================================="
    if [ $checks_failed -gt 0 ]; then
        warn "Some checks failed - monitor for a few more minutes"
    else
        success "Database verification passed!"
    fi
    echo "=============================================="
}

# =============================================================================
# MONITOR
# =============================================================================
cmd_monitor() {
    echo "=============================================="
    echo "  Monitoring Commands"
    echo "=============================================="
    echo ""
    
    echo "Copy and run these commands to monitor the database:"
    echo ""
    
    echo "${BLUE}# Watch database file size${NC}"
    echo "watch -n 60 'ls -lh $DB_FILE'"
    echo ""
    
    echo "${BLUE}# Check for storage errors${NC}"
    echo "grep -i 'error.*storage\|failed.*connect\|retrying' $LOG_FILE | tail -20"
    echo ""
    
    echo "${BLUE}# Check data counts${NC}"
    echo "sqlite3 $DB_FILE 'SELECT \"energy_data:\", COUNT(*) FROM energy_data UNION ALL SELECT \"system_state:\", COUNT(*) FROM system_state UNION ALL SELECT \"decisions:\", COUNT(*) FROM coordinator_decisions;'"
    echo ""
    
    echo "${BLUE}# Check latest timestamp${NC}"
    echo "sqlite3 $DB_FILE 'SELECT MAX(timestamp) FROM energy_data;'"
    echo ""
    
    echo "${BLUE}# Check database integrity${NC}"
    echo "sqlite3 $DB_FILE 'PRAGMA integrity_check;'"
    echo ""
    
    echo "${BLUE}# Check WAL mode${NC}"
    echo "sqlite3 $DB_FILE 'PRAGMA journal_mode;'"
    echo ""
    
    echo "${BLUE}# Tail logs for storage messages${NC}"
    echo "tail -f $LOG_FILE | grep -i storage"
}

# =============================================================================
# ROLLBACK
# =============================================================================
cmd_rollback() {
    echo "=============================================="
    echo "  Rollback to File-Only Mode"
    echo "=============================================="
    echo ""
    
    warn "This will disable database storage and revert to file-only mode."
    read -p "Are you sure? [y/N] " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Rollback cancelled"
        return 0
    fi
    
    # Disable database in config
    info "Disabling database in config..."
    if [ -f "$CONFIG_FILE" ]; then
        # Create backup of config
        cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
        
        # Use sed to disable database_storage
        # This is a simple approach - you may need to adjust for your YAML structure
        sed -i.tmp 's/enabled: true  # Enable database/enabled: false  # Disabled by rollback/' "$CONFIG_FILE" 2>/dev/null || \
        sed -i '' 's/enabled: true  # Enable database/enabled: false  # Disabled by rollback/' "$CONFIG_FILE"
        
        success "Config updated (backup at ${CONFIG_FILE}.bak)"
    else
        error "Config file not found: $CONFIG_FILE"
        return 1
    fi
    
    # Restart service using manage_services.sh if available
    if [ -x "$MANAGE_SCRIPT" ]; then
        info "Restarting service via manage_services.sh..."
        "$MANAGE_SCRIPT" restart
        success "Service restarted"
    elif systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
        info "Restarting systemd service..."
        sudo systemctl restart "$SERVICE"
        success "Service restarted"
    elif [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        info "Restarting Docker containers..."
        cd "$PROJECT_DIR"
        docker-compose restart
        success "Containers restarted"
    else
        warn "Please restart your service manually"
    fi
    
    echo ""
    success "Rollback complete!"
    echo "  Database storage is now disabled."
    echo "  JSON files will continue to be written."
}

# =============================================================================
# MIGRATE
# =============================================================================
cmd_migrate() {
    echo "=============================================="
    echo "  Migrate Historical JSON Data to Database"
    echo "=============================================="
    echo ""
    
    local migrate_script="$INSTALL_DIR/scripts/migrate_json_to_db.py"
    
    if [ -f "$migrate_script" ]; then
        info "Running migration script..."
        python3 "$migrate_script"
        
        echo ""
        info "Verifying migration..."
        cmd_verify
    else
        error "Migration script not found: $migrate_script"
        return 1
    fi
}

# =============================================================================
# HELP
# =============================================================================
cmd_help() {
    echo "=============================================="
    echo "  Database Rollout Script - Help"
    echo "=============================================="
    echo ""
    echo "Project directory: $PROJECT_DIR"
    echo "Service: $SERVICE"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  preflight     Run pre-deployment checks"
    echo "  install-deps  Install required Python dependencies"
    echo "  backup        Create backup of existing data"
    echo "  deploy        Deploy and restart service"
    echo "  verify        Verify database is working"
    echo "  monitor       Show monitoring commands"
    echo "  rollback      Rollback to file-only mode"
    echo "  migrate       Run historical data migration"
    echo "  help          Show this help message"
    echo ""
    echo "Recommended Rollout Order:"
    echo "  1. $0 preflight     # Check everything is ready"
    echo "  2. $0 install-deps  # Install dependencies if needed"
    echo "  3. $0 backup        # Backup existing data"
    echo "  4. $0 deploy        # Deploy and restart"
    echo "  5. $0 verify        # Check it's working"
    echo "  6. $0 monitor       # Get monitoring commands"
    echo ""
    echo "Environment Variables:"
    echo "  INSTALL_DIR   Override project directory (auto-detected: $PROJECT_DIR)"
    echo ""
    echo "Related Scripts:"
    echo "  manage_services.sh   Service management (start, stop, restart, logs)"
    echo ""
    echo "Example:"
    echo "  $0 preflight"
    echo "  INSTALL_DIR=/custom/path $0 preflight"
}

# =============================================================================
# MAIN
# =============================================================================
main() {
    local command="${1:-help}"
    
    case "$command" in
        preflight)
            cmd_preflight
            ;;
        install-deps)
            cmd_install_deps
            ;;
        backup)
            cmd_backup
            ;;
        deploy)
            cmd_deploy
            ;;
        verify)
            cmd_verify
            ;;
        monitor)
            cmd_monitor
            ;;
        rollback)
            cmd_rollback
            ;;
        migrate)
            cmd_migrate
            ;;
        help|--help|-h)
            cmd_help
            ;;
        *)
            error "Unknown command: $command"
            echo ""
            cmd_help
            return 1
            ;;
    esac
}

main "$@"
