#!/bin/bash
# Setup script for remote log access
# This script configures the web server for remote log monitoring

set -e

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

check_dependencies() {
    log "Checking dependencies..."
    
    # Check if virtual environment exists
    if [[ ! -d "$PROJECT_DIR/venv" ]]; then
        error "Virtual environment not found. Please run the main setup first."
        exit 1
    fi
    
    # Check if required packages are installed
    source "$PROJECT_DIR/venv/bin/activate"
    
    if ! python -c "import flask" 2>/dev/null; then
        warning "Flask not found, installing..."
        pip install flask flask-cors psutil
    fi
    
    if ! python -c "import flask_cors" 2>/dev/null; then
        warning "Flask-CORS not found, installing..."
        pip install flask-cors
    fi
    
    if ! python -c "import psutil" 2>/dev/null; then
        warning "psutil not found, installing..."
        pip install psutil
    fi
    
    success "Dependencies check completed"
}

configure_firewall() {
    log "Configuring firewall for web server access..."
    
    # Check if ufw is available
    if command -v ufw >/dev/null 2>&1; then
        # Get current IP address
        CURRENT_IP=$(hostname -I | awk '{print $1}')
        
        echo "Current server IP: $CURRENT_IP"
        echo "Web server will be accessible on: http://$CURRENT_IP:8080"
        
        read -p "Do you want to allow access to port 8080? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo ufw allow 8080
            success "Firewall rule added for port 8080"
        else
            warning "Firewall not configured. You may need to manually allow port 8080."
        fi
    else
        warning "UFW not found. Please manually configure your firewall to allow port 8080."
    fi
}

test_web_server() {
    log "Testing web server functionality..."
    
    # Start web server in background
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    log "Starting test web server on port 8082..."
    python src/log_web_server.py --port 8082 &
    SERVER_PID=$!
    
    # Wait for server to start
    sleep 3
    
    # Test endpoints
    if python scripts/test_log_server.py http://localhost:8082; then
        success "Web server test completed successfully"
    else
        error "Web server test failed"
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    
    # Stop test server
    kill $SERVER_PID 2>/dev/null || true
    sleep 2
}

show_access_info() {
    log "Remote log access setup completed!"
    echo
    echo "=========================================="
    echo "🌐 REMOTE LOG ACCESS INFORMATION"
    echo "=========================================="
    echo
    
    # Get server IP
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo "📡 Web Dashboard:"
    echo "   Local:  http://localhost:8080"
    echo "   Remote: http://$SERVER_IP:8080"
    echo
    
    echo "🔗 API Endpoints:"
    echo "   Health:  http://$SERVER_IP:8080/health"
    echo "   Status:  http://$SERVER_IP:8080/status"
    echo "   Logs:    http://$SERVER_IP:8080/logs"
    echo "   Files:   http://$SERVER_IP:8080/logs/files"
    echo
    
    echo "📱 Usage Examples:"
    echo "   # View recent logs"
    echo "   curl \"http://$SERVER_IP:8080/logs?lines=50\""
    echo
    echo "   # Filter by error level"
    echo "   curl \"http://$SERVER_IP:8080/logs?level=ERROR\""
    echo
    echo "   # Check system status"
    echo "   curl \"http://$SERVER_IP:8080/status\""
    echo
    echo "   # Download log file"
    echo "   curl \"http://$SERVER_IP:8080/logs/download/master_coordinator.log\" -o master.log"
    echo
    
    echo "🚀 Next Steps:"
    echo "   1. Start the Master Coordinator: ./scripts/manage_services.sh start"
    echo "   2. Open web browser: http://$SERVER_IP:8080"
    echo "   3. Monitor logs in real-time"
    echo
    
    echo "🔒 Security Notes:"
    echo "   - Web server has no authentication (add for production)"
    echo "   - Consider using HTTPS for remote access"
    echo "   - Firewall rules applied for port 8080"
    echo
}

create_monitoring_script() {
    log "Creating monitoring script..."
    
    cat > "$PROJECT_DIR/scripts/monitor_remote.sh" << 'EOF'
#!/bin/bash
# Remote monitoring script for GoodWe Master Coordinator

SERVER_URL="${1:-http://localhost:8080}"

echo "🔋 GoodWe Master Coordinator Remote Monitor"
echo "Server: $SERVER_URL"
echo "=========================================="

# Check health
echo "🏥 Health Check:"
HEALTH=$(curl -s "$SERVER_URL/health" | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "ERROR")
echo "   Status: $HEALTH"

# Check coordinator status
echo "🤖 Coordinator Status:"
STATUS=$(curl -s "$SERVER_URL/status" | python -c "import sys, json; data=json.load(sys.stdin); print('Running' if data.get('coordinator_running') else 'Stopped')" 2>/dev/null || echo "UNKNOWN")
echo "   Coordinator: $STATUS"

# Show recent errors
echo "❌ Recent Errors:"
ERRORS=$(curl -s "$SERVER_URL/logs?level=ERROR&lines=5" | python -c "import sys, json; data=json.load(sys.stdin); print('\n'.join(data['lines']))" 2>/dev/null || echo "No errors or unable to fetch")
if [ "$ERRORS" != "No errors or unable to fetch" ] && [ -n "$ERRORS" ]; then
    echo "$ERRORS"
else
    echo "   No recent errors found"
fi

echo "=========================================="
echo "🌐 Dashboard: $SERVER_URL"
EOF

    chmod +x "$PROJECT_DIR/scripts/monitor_remote.sh"
    success "Monitoring script created: scripts/monitor_remote.sh"
}

main() {
    echo "🔋 GoodWe Master Coordinator - Remote Log Access Setup"
    echo "======================================================"
    echo
    
    check_dependencies
    configure_firewall
    test_web_server
    create_monitoring_script
    show_access_info
    
    success "Remote log access setup completed successfully!"
}

# Run main function
main "$@"