#!/bin/bash
# Firewall configuration script for GoodWe Master Coordinator
# This script configures UFW to allow remote access to the web server

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

check_ufw() {
    if ! command -v ufw >/dev/null 2>&1; then
        error "UFW (Uncomplicated Firewall) is not installed."
        echo "Please install it with: sudo apt install ufw"
        exit 1
    fi
}

get_server_ip() {
    # Get the primary IP address
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo "$SERVER_IP"
}

configure_firewall() {
    local port=${1:-8080}
    local server_ip=$(get_server_ip)
    
    log "Configuring firewall for GoodWe Master Coordinator"
    log "Server IP: $server_ip"
    log "Web server port: $port"
    
    # Check if UFW is active
    if ! sudo ufw status | grep -q "Status: active"; then
        warning "UFW is not active. Enabling UFW..."
        sudo ufw --force enable
    fi
    
    # Allow SSH (important!)
    if ! sudo ufw status | grep -q "22/tcp"; then
        log "Allowing SSH access..."
        sudo ufw allow 22/tcp
    fi
    
    # Allow web server port
    log "Allowing access to port $port..."
    sudo ufw allow $port/tcp
    
    # Show current status
    log "Current firewall status:"
    sudo ufw status numbered
    
    success "Firewall configured successfully!"
    echo
    echo "🌐 Remote Access Information:"
    echo "   Local:  http://localhost:$port"
    echo "   Remote: http://$server_ip:$port"
    echo
    echo "🔒 Firewall Rules:"
    echo "   - SSH (port 22): Allowed"
    echo "   - Web Server (port $port): Allowed"
    echo
    echo "⚠️  Security Notes:"
    echo "   - Web server has no authentication"
    echo "   - Consider restricting access to specific IP ranges"
    echo "   - Use HTTPS for production deployments"
}

restrict_to_local_network() {
    local port=${1:-8080}
    local server_ip=$(get_server_ip)
    
    log "Configuring firewall for local network access only"
    
    # Get local network range
    local_network=$(echo $server_ip | sed 's/\.[0-9]*$/.0\/24/')
    log "Local network: $local_network"
    
    # Remove general port rule if it exists
    sudo ufw delete allow $port/tcp 2>/dev/null || true
    
    # Allow only local network
    sudo ufw allow from $local_network to any port $port
    
    success "Firewall configured for local network access only!"
    echo
    echo "🌐 Access Information:"
    echo "   Local Network: $local_network"
    echo "   Web Server: http://$server_ip:$port"
    echo
    echo "🔒 Security:"
    echo "   - Only devices on $local_network can access the web server"
    echo "   - External access is blocked"
}

show_status() {
    log "Current firewall status:"
    sudo ufw status verbose
    echo
    log "Network interfaces:"
    ip addr show | grep -E "inet [0-9]" | grep -v "127.0.0.1"
    echo
    local server_ip=$(get_server_ip)
    log "Server IP: $server_ip"
}

usage() {
    echo "GoodWe Master Coordinator Firewall Configuration"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  open [PORT]        Allow access to web server port (default: 8080)"
    echo "  local [PORT]       Allow access only from local network"
    echo "  status             Show current firewall status"
    echo "  help               Show this help message"
    echo
    echo "Examples:"
    echo "  $0 open            # Allow access to port 8080"
    echo "  $0 open 8080       # Allow access to port 8080"
    echo "  $0 local 8080      # Allow access only from local network"
    echo "  $0 status          # Show firewall status"
}

main() {
    check_ufw
    
    case "${1:-help}" in
        open)
            configure_firewall "$2"
            ;;
        local)
            restrict_to_local_network "$2"
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"