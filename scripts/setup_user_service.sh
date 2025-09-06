#!/bin/bash
# Setup script for GoodWe Master Coordinator as a user systemd service
# This script works without sudo privileges

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
USER_SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="goodwe-master-coordinator"

check_dependencies() {
    log "Checking dependencies..."
    
    # Check if systemd user services are supported
    if ! systemctl --user --version >/dev/null 2>&1; then
        error "Systemd user services are not supported on this system"
        exit 1
    fi
    
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
    
    success "Dependencies check completed"
}

create_user_service_directory() {
    log "Creating user systemd service directory..."
    
    if [[ ! -d "$USER_SERVICE_DIR" ]]; then
        mkdir -p "$USER_SERVICE_DIR"
        success "Created user service directory: $USER_SERVICE_DIR"
    else
        log "User service directory already exists: $USER_SERVICE_DIR"
    fi
}

install_user_service() {
    log "Installing user systemd service..."
    
    # Copy the user service file
    if [[ -f "$PROJECT_DIR/systemd/goodwe-master-coordinator-user.service" ]]; then
        cp "$PROJECT_DIR/systemd/goodwe-master-coordinator-user.service" "$USER_SERVICE_DIR/$SERVICE_NAME.service"
        success "User service file installed"
    else
        error "User service file not found: $PROJECT_DIR/systemd/goodwe-master-coordinator-user.service"
        exit 1
    fi
    
    # Reload systemd user daemon
    log "Reloading systemd user daemon..."
    systemctl --user daemon-reload
    success "Systemd user daemon reloaded"
}

enable_user_service() {
    log "Enabling user service to start on login..."
    
    if systemctl --user enable "$SERVICE_NAME"; then
        success "User service enabled"
    else
        error "Failed to enable user service"
        exit 1
    fi
}

start_user_service() {
    log "Starting user service..."
    
    if systemctl --user start "$SERVICE_NAME"; then
        success "User service started"
    else
        error "Failed to start user service"
        echo "Check logs with: journalctl --user -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

check_service_status() {
    log "Checking service status..."
    
    if systemctl --user is-active "$SERVICE_NAME" >/dev/null 2>&1; then
        success "Service is running"
    else
        warning "Service is not running"
        echo "Check status with: systemctl --user status $SERVICE_NAME"
    fi
}

show_service_info() {
    echo
    echo "🔋 GoodWe Master Coordinator User Service"
    echo "=========================================="
    echo
    echo "📁 Service file: $USER_SERVICE_DIR/$SERVICE_NAME.service"
    echo "🌐 Web server: http://localhost:8080"
    echo
    echo "🔧 Management Commands:"
    echo "   Start:   systemctl --user start $SERVICE_NAME"
    echo "   Stop:    systemctl --user stop $SERVICE_NAME"
    echo "   Restart: systemctl --user restart $SERVICE_NAME"
    echo "   Status:  systemctl --user status $SERVICE_NAME"
    echo "   Logs:    journalctl --user -u $SERVICE_NAME -f"
    echo
    echo "📊 Current Status:"
    systemctl --user status "$SERVICE_NAME" --no-pager -l || true
    echo
    echo "🌐 Web Dashboard:"
    echo "   http://localhost:8080"
    echo
    echo "📱 Remote Access:"
    echo "   ./scripts/remote_logs_client.sh status"
    echo
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

main() {
    echo "🔋 GoodWe Master Coordinator - User Service Setup"
    echo "================================================="
    echo
    
    check_dependencies
    create_user_service_directory
    install_user_service
    enable_user_service
    start_user_service
    check_service_status
    test_web_server
    show_service_info
    
    success "User service setup completed successfully!"
    echo
    echo "🎯 Next Steps:"
    echo "   1. Check web dashboard: http://localhost:8080"
    echo "   2. Test remote access: ./scripts/remote_logs_client.sh status"
    echo "   3. Configure firewall: ./scripts/configure_firewall.sh open"
    echo
}

main "$@"