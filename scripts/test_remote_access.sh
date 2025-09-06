#!/bin/bash
# Test script for remote log access functionality
# This script tests all remote access features and provides setup instructions

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

get_server_ip() {
    hostname -I | awk '{print $1}'
}

test_web_server() {
    local server_url="$1"
    local port="${2:-8080}"
    
    log "Testing web server at $server_url:$port"
    
    # Test health endpoint
    if curl -s --connect-timeout 5 "$server_url:$port/health" >/dev/null 2>&1; then
        success "✅ Health endpoint accessible"
    else
        error "❌ Health endpoint not accessible"
        return 1
    fi
    
    # Test status endpoint
    if curl -s --connect-timeout 5 "$server_url:$port/status" >/dev/null 2>&1; then
        success "✅ Status endpoint accessible"
    else
        error "❌ Status endpoint not accessible"
        return 1
    fi
    
    # Test logs endpoint
    if curl -s --connect-timeout 5 "$server_url:$port/logs?lines=5" >/dev/null 2>&1; then
        success "✅ Logs endpoint accessible"
    else
        error "❌ Logs endpoint not accessible"
        return 1
    fi
    
    # Test dashboard
    if curl -s --connect-timeout 5 "$server_url:$port/" >/dev/null 2>&1; then
        success "✅ Dashboard accessible"
    else
        error "❌ Dashboard not accessible"
        return 1
    fi
    
    return 0
}

test_remote_client() {
    local server_url="$1"
    
    log "Testing remote logs client"
    
    if ./scripts/remote_logs_client.sh --server "$server_url" health >/dev/null 2>&1; then
        success "✅ Remote logs client working"
    else
        error "❌ Remote logs client failed"
        return 1
    fi
    
    return 0
}

show_access_info() {
    local server_ip=$(get_server_ip)
    local port="${1:-8080}"
    
    echo
    echo "🌐 REMOTE ACCESS INFORMATION"
    echo "============================"
    echo
    echo "📡 Web Dashboard:"
    echo "   Local:  http://localhost:$port"
    echo "   Remote: http://$server_ip:$port"
    echo
    echo "🔗 API Endpoints:"
    echo "   Health:  http://$server_ip:$port/health"
    echo "   Status:  http://$server_ip:$port/status"
    echo "   Logs:    http://$server_ip:$port/logs"
    echo "   Files:   http://$server_ip:$port/logs/files"
    echo
    echo "📱 Command Line Access:"
    echo "   # Check status"
    echo "   ./scripts/remote_logs_client.sh --server http://$server_ip:$port status"
    echo
    echo "   # View logs"
    echo "   ./scripts/remote_logs_client.sh --server http://$server_ip:$port logs 50"
    echo
    echo "   # Show errors"
    echo "   ./scripts/remote_logs_client.sh --server http://$server_ip:$port errors"
    echo
    echo "   # Stream live logs"
    echo "   ./scripts/remote_logs_client.sh --server http://$server_ip:$port stream"
    echo
    echo "🔧 Direct API Examples:"
    echo "   # Health check"
    echo "   curl http://$server_ip:$port/health"
    echo
    echo "   # Get recent logs"
    echo "   curl \"http://$server_ip:$port/logs?lines=50\""
    echo
    echo "   # Download log file"
    echo "   curl \"http://$server_ip:$port/logs/download/master_coordinator.log\" -o master.log"
    echo
}

show_firewall_instructions() {
    local server_ip=$(get_server_ip)
    local port="${1:-8080}"
    
    echo
    echo "🔒 FIREWALL CONFIGURATION"
    echo "========================="
    echo
    echo "To allow remote access, configure your firewall:"
    echo
    echo "📋 UFW (Ubuntu/Debian):"
    echo "   sudo ufw allow $port/tcp"
    echo "   sudo ufw status"
    echo
    echo "📋 iptables (Generic Linux):"
    echo "   sudo iptables -A INPUT -p tcp --dport $port -j ACCEPT"
    echo "   sudo iptables-save > /etc/iptables/rules.v4"
    echo
    echo "📋 firewalld (CentOS/RHEL):"
    echo "   sudo firewall-cmd --permanent --add-port=$port/tcp"
    echo "   sudo firewall-cmd --reload"
    echo
    echo "🔐 Security Recommendations:"
    echo "   1. Allow only specific IP ranges:"
    echo "      sudo ufw allow from 192.168.1.0/24 to any port $port"
    echo
    echo "   2. Use VPN for remote access"
    echo "   3. Add authentication to the web server"
    echo "   4. Use HTTPS with SSL certificates"
    echo
    echo "⚠️  Current Status:"
    echo "   - Web server is running and accessible locally"
    echo "   - Remote access depends on firewall configuration"
    echo "   - No authentication is currently implemented"
    echo
}

test_connectivity() {
    local server_ip=$(get_server_ip)
    local port="${1:-8080}"
    
    log "Testing connectivity to $server_ip:$port"
    
    # Test local access
    if test_web_server "localhost" "$port"; then
        success "✅ Local access working"
    else
        error "❌ Local access failed"
        return 1
    fi
    
    # Test remote access (same machine, different IP)
    if test_web_server "$server_ip" "$port"; then
        success "✅ Remote access working"
    else
        warning "⚠️  Remote access failed (may be firewall blocking)"
    fi
    
    return 0
}

run_comprehensive_test() {
    local server_ip=$(get_server_ip)
    local port="${1:-8080}"
    
    echo "🔋 GoodWe Master Coordinator - Remote Access Test"
    echo "================================================="
    echo
    
    log "Server IP: $server_ip"
    log "Port: $port"
    echo
    
    # Test web server functionality
    if test_connectivity "$port"; then
        success "Web server is working correctly!"
    else
        error "Web server has issues"
        exit 1
    fi
    
    echo
    
    # Test remote client
    if test_remote_client "http://$server_ip:$port"; then
        success "Remote logs client is working!"
    else
        error "Remote logs client has issues"
    fi
    
    echo
    
    # Show access information
    show_access_info "$port"
    
    # Show firewall instructions
    show_firewall_instructions "$port"
    
    success "Remote access test completed!"
}

usage() {
    echo "GoodWe Master Coordinator - Remote Access Test"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  test [PORT]        Run comprehensive test (default: 8080)"
    echo "  info [PORT]        Show access information"
    echo "  firewall [PORT]    Show firewall configuration instructions"
    echo "  help               Show this help message"
    echo
    echo "Examples:"
    echo "  $0 test            # Test with default port 8080"
    echo "  $0 test 8080       # Test with port 8080"
    echo "  $0 info            # Show access information"
    echo "  $0 firewall        # Show firewall instructions"
}

main() {
    case "${1:-test}" in
        test)
            run_comprehensive_test "$2"
            ;;
        info)
            show_access_info "$2"
            ;;
        firewall)
            show_firewall_instructions "$2"
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