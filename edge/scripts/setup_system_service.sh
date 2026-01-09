#!/bin/bash
# Setup script for GoodWe Master Coordinator as a system systemd service
# This script requires sudo privileges

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="goodwe-master-coordinator"
SYSTEMD_SERVICE_DIR="/etc/systemd/system"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo privileges."
        exit 1
    fi
}

check_dependencies() {
    log "Checking dependencies..."
    
    # Check if virtual environment exists
    if [[ ! -d "$PROJECT_DIR/venv" ]]; then
        error "Virtual environment not found at $PROJECT_DIR/venv"
        echo "Please run the main setup first to create the virtual environment"
        exit 1
    fi
    
    # Check if master coordinator exists
    if [[ ! -f "$PROJECT_DIR/src/master_coordinator.py" ]]; then
        error "Master coordinator not found at $PROJECT_DIR/src/master_coordinator.py"
        exit 1
    fi
    
    # Check if user exists
    if ! id "$USER" >/dev/null 2>&1; then
        error "User $USER not found"
        exit 1
    fi
    
    success "Dependencies check completed"
}

stop_user_service() {
    log "Stopping existing user service..."
    
    if systemctl --user is-active "$SERVICE_NAME" >/dev/null 2>&1; then
        systemctl --user stop "$SERVICE_NAME"
        success "User service stopped"
    else
        log "User service was not running"
    fi
    
    if systemctl --user is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        systemctl --user disable "$SERVICE_NAME"
        success "User service disabled"
    else
        log "User service was not enabled"
    fi
}

create_system_service_file() {
    log "Creating system service file..."
    
    sudo tee "$SYSTEMD_SERVICE_DIR/$SERVICE_NAME.service" > /dev/null << EOF
[Unit]
Description=GoodWe Master Coordinator Service
Documentation=https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/src/master_coordinator.py --non-interactive
ExecStop=/bin/kill -TERM \$MAINPID
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal
SyslogIdentifier=goodwe-master-coordinator

# Environment variables
Environment=PYTHONPATH=$PROJECT_DIR/src
Environment=PYTHONUNBUFFERED=1
Environment=HOME=$HOME

# Security restrictions
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_DIR/logs
ReadWritePaths=$PROJECT_DIR/out
ReadWritePaths=$PROJECT_DIR/config
IPAddressAllow=localhost
IPAddressAllow=10.0.0.0/8
IPAddressAllow=172.16.0.0/12
IPAddressAllow=192.168.0.0/16
LimitNOFILE=65536
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
    
    success "System service file created"
}

reload_systemd() {
    log "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    success "Systemd daemon reloaded"
}

enable_system_service() {
    log "Enabling system service to start on boot..."
    
    if sudo systemctl enable "$SERVICE_NAME"; then
        success "System service enabled"
    else
        error "Failed to enable system service"
        exit 1
    fi
}

start_system_service() {
    log "Starting system service..."
    
    if sudo systemctl start "$SERVICE_NAME"; then
        success "System service started"
    else
        error "Failed to start system service"
        echo "Check logs with: sudo journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

check_service_status() {
    log "Checking service status..."
    
    if sudo systemctl is-active "$SERVICE_NAME" >/dev/null 2>&1; then
        success "Service is running"
    else
        warning "Service is not running"
        echo "Check status with: sudo systemctl status $SERVICE_NAME"
    fi
}

test_web_server() {
    log "Testing web server..."
    
    # Wait a moment for the service to start
    sleep 3
    
    if curl -s http://localhost:8080/health >/dev/null 2>&1; then
        success "Web server is accessible"
    else
        warning "Web server is not accessible yet (may need more time to start)"
        echo "Try: curl http://localhost:8080/health"
    fi
}

show_service_info() {
    echo
    echo "🔋 GoodWe Master Coordinator System Service"
    echo "============================================="
    echo
    echo "📁 Service file: $SYSTEMD_SERVICE_DIR/$SERVICE_NAME.service"
    echo "🌐 Web server: http://localhost:8080"
    echo "👤 Running as user: $USER"
    echo "📂 Working directory: $PROJECT_DIR"
    echo
    echo "🔧 Management Commands:"
    echo "   Start:   sudo systemctl start $SERVICE_NAME"
    echo "   Stop:    sudo systemctl stop $SERVICE_NAME"
    echo "   Restart: sudo systemctl restart $SERVICE_NAME"
    echo "   Status:  sudo systemctl status $SERVICE_NAME"
    echo "   Logs:    sudo journalctl -u $SERVICE_NAME -f"
    echo
    echo "📊 Current Status:"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
    echo
    echo "🌐 Web Dashboard:"
    echo "   http://localhost:8080"
    echo
    echo "📱 Remote Access:"
    echo "   ./scripts/remote_logs_client.sh status"
    echo
}

main() {
    echo "🔋 GoodWe Master Coordinator - System Service Setup"
    echo "=================================================="
    echo
    echo "This will convert your user service to a system service that:"
    echo "  ✅ Survives SSH disconnections"
    echo "  ✅ Starts automatically on boot"
    echo "  ✅ Runs independently of your login session"
    echo
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r
    
    check_root
    check_dependencies
    stop_user_service
    create_system_service_file
    reload_systemd
    enable_system_service
    start_system_service
    check_service_status
    test_web_server
    show_service_info
    
    success "System service setup completed successfully!"
    echo
    echo "🎯 Next Steps:"
    echo "   1. Check web dashboard: http://localhost:8080"
    echo "   2. Test remote access: ./scripts/remote_logs_client.sh status"
    echo "   3. Configure firewall: ./scripts/configure_firewall.sh open"
    echo
    echo "🔒 Security Note:"
    echo "   The service now runs as a system service but still executes as user '$USER'"
    echo "   This provides the benefits of system service management while maintaining security."
    echo
}

main "$@"