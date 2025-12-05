#!/bin/bash
# GoodWe Master Coordinator Management Script
# Usage: ./manage_services.sh [start|stop|restart|status|logs|enable|disable]

set -e

SERVICE="goodwe-master-coordinator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo privileges."
        exit 1
    fi
}

check_service_exists() {
    if ! systemctl list-unit-files | grep -q "^${SERVICE}.service"; then
        error "Service ${SERVICE} not found. Make sure systemd service is installed."
        return 1
    fi
}

start_services() {
    log "Starting GoodWe Master Coordinator..."
    if check_service_exists; then
        if sudo systemctl start "$SERVICE"; then
            success "$SERVICE started successfully"
        else
            error "Failed to start $SERVICE"
        fi
    fi
}

stop_services() {
    log "Stopping GoodWe Master Coordinator..."
    if check_service_exists; then
        if sudo systemctl stop "$SERVICE"; then
            success "$SERVICE stopped via systemctl"
        else
            warning "Failed to stop $SERVICE via systemctl, attempting manual cleanup..."
        fi
        
        # Additional cleanup for stuck processes
        log "Checking for stuck processes..."
        
        # Kill master coordinator if still running
        if pgrep -f "src/master_coordinator.py" > /dev/null; then
            log "Found stuck master_coordinator process, killing..."
            sudo pkill -f "src/master_coordinator.py" || true
            sleep 1
        fi
        
        # Kill web server if running standalone or stuck
        if pgrep -f "src/log_web_server.py" > /dev/null; then
             log "Found stuck log_web_server process, killing..."
             sudo pkill -f "src/log_web_server.py" || true
             sleep 1
        fi
        
        success "Cleanup complete"
    fi
}

restart_services() {
    log "Restarting GoodWe Master Coordinator..."
    if check_service_exists; then
        if sudo systemctl restart "$SERVICE"; then
            success "$SERVICE restarted successfully"
        else
            error "Failed to restart $SERVICE"
        fi
    fi
}

show_status() {
    log "GoodWe Master Coordinator Status:"
    echo
    if check_service_exists; then
        echo -e "${BLUE}=== $SERVICE ===${NC}"
        sudo systemctl status "$SERVICE" --no-pager -l
        echo
    fi
}

show_logs() {
    local lines=${1:-100}
    if check_service_exists; then
        log "Showing logs for $SERVICE (last $lines lines):"
        sudo journalctl -u "$SERVICE" -n "$lines" --no-pager -f
    else
        error "Service $SERVICE not found"
    fi
}

enable_services() {
    log "Enabling GoodWe Master Coordinator to start on boot..."
    if check_service_exists; then
        if sudo systemctl enable "$SERVICE"; then
            success "$SERVICE enabled successfully"
        else
            error "Failed to enable $SERVICE"
        fi
    fi
}

disable_services() {
    log "Disabling GoodWe Master Coordinator from starting on boot..."
    if check_service_exists; then
        if sudo systemctl disable "$SERVICE"; then
            success "$SERVICE disabled successfully"
        else
            error "Failed to disable $SERVICE"
        fi
    fi
}

install_services() {
    log "Installing GoodWe Master Coordinator systemd service..."
    
    # Check if service file exists
    if [[ ! -f "$PROJECT_DIR/systemd/goodwe-master-coordinator.service" ]]; then
        error "Master coordinator service file not found at $PROJECT_DIR/systemd/goodwe-master-coordinator.service"
        exit 1
    fi
    
    # Copy service file
    log "Installing goodwe-master-coordinator.service..."
    sudo cp "$PROJECT_DIR/systemd/goodwe-master-coordinator.service" "/etc/systemd/system/"
    success "Master coordinator service installed"
    
    # Reload systemd
    log "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    success "Systemd daemon reloaded"
    
    log "Service installed successfully. Use 'enable' to start it on boot."
}

show_help() {
    echo "GoodWe Master Coordinator Management Script"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  install     Install systemd service file"
    echo "  start       Start the master coordinator"
    echo "  stop        Stop the master coordinator"
    echo "  restart     Restart the master coordinator"
    echo "  status      Show status of the master coordinator"
    echo "  logs [lines] Show logs (default: 100 lines, use -f for follow)"
    echo "  enable      Enable master coordinator to start on boot"
    echo "  disable     Disable master coordinator from starting on boot"
    echo "  help        Show this help message"
    echo
    echo "Examples:"
    echo "  $0 install"
    echo "  $0 start"
    echo "  $0 logs 50"
    echo "  $0 logs -f"
    echo "  $0 status"
}

# Main script logic
check_root

case "${1:-help}" in
    install)
        install_services
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    enable)
        enable_services
        ;;
    disable)
        disable_services
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
