#!/bin/bash
# GoodWe Master Coordinator Management Script
# Usage: ./manage_services.sh [start|stop|restart|status|logs|enable|disable]

set -e

SERVICES=("goodwe-master-coordinator" "goodwe-ngrok")
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_DIR="/etc/systemd/system"

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
    local service=$1
    if ! systemctl list-unit-files | grep -q "^${service}.service"; then
        return 1
    fi
    return 0
}

start_services() {
    log "Starting GoodWe Services..."
    # Start app first, then ngrok
    for service in "${SERVICES[@]}"; do
        if check_service_exists "$service"; then
            log "Starting $service..."
            if sudo systemctl start "$service"; then
                success "$service started successfully"
            else
                error "Failed to start $service"
            fi
        else
            warning "Service $service not installed. Run install first."
        fi
    done
}

stop_services() {
    log "Stopping GoodWe Services..."
    # Stop in reverse order (ngrok first, then app)
    for (( i=${#SERVICES[@]}-1; i>=0; i-- )); do
        local service="${SERVICES[$i]}"
        if check_service_exists "$service"; then
            log "Stopping $service..."
            if sudo systemctl stop "$service"; then
                success "$service stopped"
            else
                warning "Failed to stop $service via systemctl"
            fi
        fi
    done
    
    # Additional cleanup for stuck processes
    log "Checking for stuck processes..."
    if pgrep -f "src/master_coordinator.py" > /dev/null; then
        log "Found stuck master_coordinator process, killing..."
        sudo pkill -f "src/master_coordinator.py" || true
    fi
    if pgrep -f "ngrok start" > /dev/null; then
        log "Found stuck ngrok process, killing..."
        sudo pkill -f "ngrok start" || true
    fi
    success "Cleanup complete"
}

restart_services() {
    log "Restarting GoodWe Services..."
    stop_services
    sleep 2
    start_services
}

show_status() {
    log "GoodWe Services Status:"
    echo
    for service in "${SERVICES[@]}"; do
        if check_service_exists "$service"; then
            echo -e "${BLUE}=== $service ===${NC}"
            sudo systemctl status "$service" --no-pager -l
            echo
        else
            warning "Service $service is not installed"
        fi
    done
}

show_logs() {
    local service_input=$1
    local lines=${2:-50}
    
    # If first argument is -f or a number, it's lines/flags, default to app service
    local target_service="goodwe-master-coordinator"
    if [[ "$service_input" == "goodwe-ngrok" ]]; then
        target_service="goodwe-ngrok"
        lines=${2:-50}
    elif [[ "$service_input" =~ ^[0-9]+$ ]] || [[ "$service_input" == "-f" ]]; then
        lines=$service_input
    fi

    if check_service_exists "$target_service"; then
        log "Showing logs for $target_service:"
        if [[ "$lines" == "-f" ]]; then
            sudo journalctl -u "$target_service" -f
        else
            sudo journalctl -u "$target_service" -n "$lines" --no-pager
        fi
    else
        error "Service $target_service not found"
    fi
}

enable_services() {
    log "Enabling services to start on boot..."
    for service in "${SERVICES[@]}"; do
        if check_service_exists "$service"; then
            sudo systemctl enable "$service"
            success "$service enabled"
        fi
    done
}

disable_services() {
    log "Disabling services from starting on boot..."
    for service in "${SERVICES[@]}"; do
        if check_service_exists "$service"; then
            sudo systemctl disable "$service"
            success "$service disabled"
        fi
    done
}

install_services() {
    log "Installing GoodWe services using symbolic links..."
    
    for service in "${SERVICES[@]}"; do
        local src="$PROJECT_DIR/systemd/$service.service"
        local dest="$SYSTEMD_DIR/$service.service"
        
        if [[ -f "$src" ]]; then
            log "Linking $service.service..."
            sudo ln -sf "$src" "$dest"
            success "Linked $service"
        else
            error "Service file not found: $src"
        fi
    done
    
    log "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    success "Systemd daemon reloaded"
}

show_help() {
    echo "GoodWe Services Management Script"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  install           Link systemd service files"
    echo "  start             Start all services"
    echo "  stop              Stop all services"
    echo "  restart           Restart all services"
    echo "  status            Show status of all services"
    echo "  logs [service] [lines/-f]  Show logs (default: coordinator, 50 lines)"
    echo "  enable            Enable services to start on boot"
    echo "  disable           Disable services from starting on boot"
    echo
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 logs goodwe-ngrok -f"
    echo "  $0 status"
}

check_root

case "${1:-help}" in
    install) install_services ;;
    start) start_services ;;
    stop) stop_services ;;
    restart) restart_services ;;
    status) show_status ;;
    logs) show_logs "$2" "$3" ;;
    enable) enable_services ;;
    disable) disable_services ;;
    help|--help|-h) show_help ;;
    *) error "Unknown command: $1"; show_help; exit 1 ;;
esac
