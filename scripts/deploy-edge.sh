#!/bin/bash
# =============================================================================
# deploy-edge.sh - Automated Edge Node Deployment to Raspberry Pi
# =============================================================================
# 
# This script deploys the edge node software to a Raspberry Pi, including:
# - Pre-deployment backup
# - Configuration updates for Hub API integration
# - Code deployment via git
# - Service restart
# - Health check with automatic rollback on failure
#
# Usage: ./scripts/deploy-edge.sh
#
# =============================================================================

set -e

# Configuration
RASP_USER="rmachnik"
RASP_HOST="192.168.33.10"
RASP_DIR="/home/rmachnik/sources/goodwe-dynamic-price-optimiser"
SSH_CMD="ssh ${RASP_USER}@${RASP_HOST}"

# Hub API Configuration (VPS)
HUB_API_URL="http://srv26.mikr.us:40316"
AMQP_BROKER="mws03.mikr.us"
AMQP_PORT="62071"
NODE_ID="rasp-01"
# AMQP password should be set via environment variable before running
AMQP_PASS="${AMQP_PASS:-}"  # Set AMQP_PASS env var before running, or script will prompt

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Step 1: Pre-flight Checks
# =============================================================================
preflight_checks() {
    log_info "Running pre-flight checks..."
    
    # Check SSH connectivity
    if ! $SSH_CMD "echo 'SSH connection OK'" &>/dev/null; then
        log_error "Cannot connect to Raspberry Pi at ${RASP_USER}@${RASP_HOST}"
        log_error "Make sure you can SSH to the Pi: ssh ${RASP_USER}@${RASP_HOST}"
        exit 1
    fi
    log_success "SSH connection verified"
    
    # Check if edge directory exists
    if ! $SSH_CMD "[ -d ${RASP_DIR} ]"; then
        log_error "Edge directory ${RASP_DIR} does not exist on Pi"
        exit 1
    fi
    log_success "Edge directory exists: ${RASP_DIR}"
    
    # Check sudo access
    if ! $SSH_CMD "sudo -n true 2>/dev/null"; then
        log_warning "Sudo access may require password. You may be prompted during deployment."
    else
        log_success "Sudo access verified (passwordless)"
    fi
    
    # Check current service status
    SERVICE_STATUS=$($SSH_CMD "systemctl is-active goodwe-coordinator 2>/dev/null || echo 'not-installed'")
    log_info "Current service status: ${SERVICE_STATUS}"
    
    # Check git status
    log_info "Checking git status on Pi..."
    $SSH_CMD "cd ${RASP_DIR} && git status --short && echo 'Branch:' && git branch --show-current"
}

# =============================================================================
# Step 2: Create Backup on Pi
# =============================================================================
create_backup() {
    log_info "Creating backup on Raspberry Pi..."
    
    local BACKUP_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    
    $SSH_CMD "
        set -e
        BACKUP_DIR=\"\$HOME/backups/pre-deploy-${BACKUP_TIMESTAMP}\"
        mkdir -p \"\$BACKUP_DIR\"
        
        cd ${RASP_DIR}
        
        # Backup current git commit
        if [ -d .git ]; then
            git log -1 --oneline > \"\$BACKUP_DIR/git-commit.txt\"
            git branch --show-current >> \"\$BACKUP_DIR/git-commit.txt\"
            echo 'Git state saved'
        fi
        
        # Backup configuration
        if [ -f config/master_coordinator_config.yaml ]; then
            cp config/master_coordinator_config.yaml \"\$BACKUP_DIR/\"
            echo 'Config backed up'
        fi
        
        # Backup .env
        if [ -f .env ]; then
            cp .env \"\$BACKUP_DIR/\"
            echo '.env backed up'
        fi
        
        # Backup database
        if [ -f data/goodwe_energy.db ]; then
            cp data/goodwe_energy.db \"\$BACKUP_DIR/\"
            echo 'Database backed up'
        fi
        
        # Record backup location
        echo \"\$BACKUP_DIR\" > ${RASP_DIR}/.last_backup
        
        echo 'Backup completed:' \"\$BACKUP_DIR\"
        ls -la \"\$BACKUP_DIR\"
    "
    
    log_success "Backup created on Pi"
}

# =============================================================================
# Step 3: Update Environment Configuration
# =============================================================================
update_env_config() {
    log_info "Updating environment configuration for Hub API..."
    
    # Prompt for AMQP password if not set
    if [[ -z "$AMQP_PASS" ]]; then
        read -sp "Enter AMQP password for node '${NODE_ID}': " AMQP_PASS
        echo ""
        if [[ -z "$AMQP_PASS" ]]; then
            log_error "AMQP password is required. Set AMQP_PASS env var or enter when prompted."
            exit 1
        fi
    fi
    
    # Create .env file on Pi
    $SSH_CMD "cat > ${RASP_DIR}/.env" << ENVEOF
# GoodWe Edge Node Configuration
# Generated by deploy-edge.sh on $(date)

# Hub API (VPS)
HUB_API_URL=${HUB_API_URL}

# AMQP/RabbitMQ (Cloud Messaging)
AMQP_BROKER=${AMQP_BROKER}
AMQP_PORT=${AMQP_PORT}
NODE_ID=${NODE_ID}
AMQP_USER=node_${NODE_ID}
AMQP_PASS=${AMQP_PASS}

# Local API (for cloud reporter)
LOCAL_API=http://localhost:8080
ENVEOF
    
    log_success "Environment configuration updated"
    
    # Show config (mask password)
    log_info "Current .env configuration:"
    $SSH_CMD "cat ${RASP_DIR}/.env | sed 's/AMQP_PASS=.*/AMQP_PASS=*****/'"
}

# =============================================================================
# Step 4: Deploy Code via Git
# =============================================================================
deploy_code() {
    log_info "Deploying latest code to Raspberry Pi..."
    
    $SSH_CMD "
        set -e
        cd ${RASP_DIR}
        
        # Check if git repo exists
        if [ -d .git ]; then
            # Stash any local changes
            git stash -u 2>/dev/null || true
            
            # Fetch and pull latest
            git fetch origin
            
            # Get current branch
            BRANCH=\$(git branch --show-current)
            echo \"Current branch: \${BRANCH}\"
            
            # Pull latest changes
            git pull origin \${BRANCH}
            
            # Show what was updated
            echo 'Latest commit:'
            git log -1 --oneline
        else
            echo 'Warning: Not a git repository. Skipping code update.'
        fi
    "
    
    log_success "Code deployment complete"
}

# =============================================================================
# Step 5: Install/Update Dependencies
# =============================================================================
install_dependencies() {
    log_info "Checking and installing Python dependencies..."
    
    $SSH_CMD "
        set -e
        cd ${RASP_DIR}
        
        # Check if virtual environment exists
        if [ ! -d venv ]; then
            echo 'Creating virtual environment...'
            python3 -m venv venv
        fi
        
        # Activate and install requirements
        source venv/bin/activate
        
        # Upgrade pip first
        pip install --upgrade pip --quiet
        
        # Check for requirements changes
        if [ -f requirements.txt ]; then
            pip install -r requirements.txt --quiet
            echo 'Root dependencies installed/updated'
        fi
        
        # Install edge-specific requirements if they exist
        if [ -f edge/requirements.txt ]; then
            pip install -r edge/requirements.txt --quiet
            echo 'Edge dependencies installed'
        fi
        
        echo 'Python dependencies installed successfully'
    "
    
    log_success "Dependencies installed"
}

# =============================================================================
# Step 5a: Install Systemd Service (if not exists)
# =============================================================================
install_systemd_service() {
    log_info "Checking systemd service configuration..."
    
    local SERVICE_EXISTS=$($SSH_CMD "[ -f /etc/systemd/system/goodwe-coordinator.service ] && echo 'yes' || echo 'no'")
    
    if [[ "$SERVICE_EXISTS" == "no" ]]; then
        log_warning "Systemd service not found. Installing..."
        
        # Create systemd service file
        $SSH_CMD "sudo tee /etc/systemd/system/goodwe-coordinator.service > /dev/null" << SERVICEEOF
[Unit]
Description=GoodWe Energy Coordinator
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${RASP_USER}
WorkingDirectory=${RASP_DIR}
Environment=PATH=${RASP_DIR}/venv/bin:/usr/bin:/bin
EnvironmentFile=${RASP_DIR}/.env
ExecStart=${RASP_DIR}/venv/bin/python -m src.master_coordinator
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF
        
        $SSH_CMD "sudo systemctl daemon-reload && sudo systemctl enable goodwe-coordinator"
        log_success "Systemd service installed and enabled"
    else
        log_success "Systemd service already exists"
        # Update service file anyway to ensure it's current
        log_info "Updating systemd service file..."
        $SSH_CMD "sudo tee /etc/systemd/system/goodwe-coordinator.service > /dev/null" << SERVICEEOF
[Unit]
Description=GoodWe Energy Coordinator
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${RASP_USER}
WorkingDirectory=${RASP_DIR}
Environment=PATH=${RASP_DIR}/venv/bin:/usr/bin:/bin
EnvironmentFile=${RASP_DIR}/.env
ExecStart=${RASP_DIR}/venv/bin/python -m src.master_coordinator
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF
        $SSH_CMD "sudo systemctl daemon-reload"
    fi
}

# =============================================================================
# Step 6: Restart Services
# =============================================================================
restart_services() {
    log_info "Restarting Edge Node services..."
    
    $SSH_CMD "
        set -e
        
        # Reload systemd in case service file was updated
        sudo systemctl daemon-reload
        
        # Restart the main coordinator service
        if systemctl is-active --quiet goodwe-coordinator; then
            echo 'Restarting goodwe-coordinator...'
            sudo systemctl restart goodwe-coordinator
        else
            echo 'Starting goodwe-coordinator...'
            sudo systemctl start goodwe-coordinator
        fi
        
        # Give it time to start
        sleep 5
        
        # Show status
        sudo systemctl status goodwe-coordinator --no-pager || true
    "
    
    log_success "Services restarted"
}

# =============================================================================
# Step 7: Health Check
# =============================================================================
health_check() {
    log_info "Running health checks..."
    
    # Give service more time to stabilize
    sleep 3
    
    # Check 1: Service is running
    local SERVICE_STATUS=$($SSH_CMD "systemctl is-active goodwe-coordinator 2>/dev/null || echo 'failed'")
    if [[ "$SERVICE_STATUS" != "active" ]]; then
        log_error "Service is not running: ${SERVICE_STATUS}"
        log_info "Showing recent logs:"
        $SSH_CMD "journalctl -u goodwe-coordinator --since '2 minutes ago' --no-pager | tail -30" || true
        return 1
    fi
    log_success "Service is active"
    
    # Check 2: Web server is responding (give it time)
    sleep 5
    local WEB_STATUS=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/health 2>/dev/null || echo '000'")
    if [[ "$WEB_STATUS" != "200" ]]; then
        log_warning "Web server returned status: ${WEB_STATUS} (may still be starting)"
    else
        log_success "Web server is responding (HTTP 200)"
    fi
    
    # Check 3: No critical errors in recent logs
    local CRITICAL_ERRORS=$($SSH_CMD "journalctl -u goodwe-coordinator --since '1 minute ago' --no-pager 2>/dev/null | grep -c 'CRITICAL\|FATAL\|Error' || echo '0'")
    if [[ "$CRITICAL_ERRORS" != "0" ]]; then
        log_warning "Found ${CRITICAL_ERRORS} potential errors in logs"
        $SSH_CMD "journalctl -u goodwe-coordinator --since '1 minute ago' --no-pager | grep -i 'error\|critical\|fatal' | tail -5" || true
    fi
    
    log_success "Health checks passed"
    return 0
}

# =============================================================================
# Step 8: Rollback (if needed)
# =============================================================================
rollback() {
    log_error "Initiating rollback..."
    
    $SSH_CMD "
        set -e
        cd ${RASP_DIR}
        
        # Get last backup location
        if [ -f .last_backup ]; then
            BACKUP_DIR=\$(cat .last_backup)
            echo \"Restoring from backup: \$BACKUP_DIR\"
            
            # Stop service
            sudo systemctl stop goodwe-coordinator 2>/dev/null || true
            
            # Restore git commit
            if [ -f \"\$BACKUP_DIR/git-commit.txt\" ]; then
                COMMIT=\$(head -1 \"\$BACKUP_DIR/git-commit.txt\" | awk '{print \$1}')
                echo \"Restoring to commit: \$COMMIT\"
                git checkout \$COMMIT 2>/dev/null || true
            fi
            
            # Restore config
            if [ -f \"\$BACKUP_DIR/master_coordinator_config.yaml\" ]; then
                cp \"\$BACKUP_DIR/master_coordinator_config.yaml\" config/
                echo 'Config restored'
            fi
            
            # Restore .env
            if [ -f \"\$BACKUP_DIR/.env\" ]; then
                cp \"\$BACKUP_DIR/.env\" ./
                echo '.env restored'
            fi
            
            # Restore database
            if [ -f \"\$BACKUP_DIR/goodwe_energy.db\" ]; then
                cp \"\$BACKUP_DIR/goodwe_energy.db\" data/
                echo 'Database restored'
            fi
            
            # Restart service
            sudo systemctl start goodwe-coordinator
            
            echo 'Rollback complete!'
        else
            echo 'No backup found to restore from'
        fi
    "
    
    log_warning "Rollback completed. Please check the Pi manually."
}

# =============================================================================
# Main Execution
# =============================================================================
main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║           Edge Node Deployment to Raspberry Pi                ║"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    echo "║  Target: ${RASP_USER}@${RASP_HOST}                             "
    echo "║  Directory: ${RASP_DIR}                                        "
    echo "║  Hub API: ${HUB_API_URL}                                       "
    echo "║  AMQP: ${AMQP_BROKER}:${AMQP_PORT}                             "
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
    
    read -p "Proceed with deployment? (y/n): " CONFIRM
    if [[ "$CONFIRM" != "y" ]]; then
        log_warning "Deployment cancelled"
        exit 0
    fi
    
    # Execute deployment steps
    preflight_checks
    create_backup
    update_env_config
    deploy_code
    install_dependencies
    install_systemd_service
    restart_services
    
    # Health check with rollback on failure
    if ! health_check; then
        log_error "Health check failed!"
        read -p "Rollback to previous version? (y/n): " DO_ROLLBACK
        if [[ "$DO_ROLLBACK" == "y" ]]; then
            rollback
        fi
        exit 1
    fi
    
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                 ✅ DEPLOYMENT SUCCESSFUL!                     ║"
    echo "╠═══════════════════════════════════════════════════════════════╣"
    echo "║  Edge Node is now connected to:                               "
    echo "║  - Hub API: ${HUB_API_URL}                                    "
    echo "║  - AMQP: ${AMQP_BROKER}:${AMQP_PORT}                          "
    echo "║                                                               "
    echo "║  Next Steps:                                                  "
    echo "║  1. Check dashboard: http://srv26.mikr.us:40317              "
    echo "║  2. Verify telemetry: ssh ${RASP_USER}@${RASP_HOST}          "
    echo "║     journalctl -u goodwe-coordinator -f                       "
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
}

# Run main function
main "$@"
