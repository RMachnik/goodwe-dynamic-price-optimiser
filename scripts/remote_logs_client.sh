#!/bin/bash
# Remote Logs Client for GoodWe Master Coordinator
# Easy command-line access to remote logs

set -e

# Default server URL
DEFAULT_SERVER="http://localhost:8080"
SERVER_URL="${GOODWE_SERVER:-$DEFAULT_SERVER}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    echo "GoodWe Remote Logs Client"
    echo
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo
    echo "Commands:"
    echo "  status          Show system status"
    echo "  health          Check server health"
    echo "  logs [N]        Show last N log lines (default: 50)"
    echo "  errors          Show recent errors"
    echo "  warnings        Show recent warnings"
    echo "  files           List available log files"
    echo "  download FILE   Download log file"
    echo "  stream          Stream live logs"
    echo "  dashboard       Open dashboard in browser"
    echo
    echo "Options:"
    echo "  --server URL    Server URL (default: $DEFAULT_SERVER)"
    echo "  --file FILE     Log file (master, data, fast_charge)"
    echo "  --level LEVEL   Log level (ERROR, WARNING, INFO, DEBUG)"
    echo
    echo "Environment:"
    echo "  GOODWE_SERVER   Default server URL"
    echo
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 logs 100"
    echo "  $0 errors"
    echo "  $0 --server http://192.168.1.100:8080 logs"
    echo "  $0 --file data --level ERROR logs"
}

check_server() {
    if ! curl -s "$SERVER_URL/health" >/dev/null 2>&1; then
        echo -e "${RED}Error: Cannot connect to server at $SERVER_URL${NC}" >&2
        echo "Make sure the Master Coordinator is running and the web server is enabled." >&2
        exit 1
    fi
}

show_status() {
    echo -e "${BLUE}🔋 GoodWe Master Coordinator Status${NC}"
    echo "Server: $SERVER_URL"
    echo "=================================="
    
    # Health check
    HEALTH=$(curl -s "$SERVER_URL/health" | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "ERROR")
    echo -e "🏥 Health: ${GREEN}$HEALTH${NC}"
    
    # Coordinator status
    STATUS_DATA=$(curl -s "$SERVER_URL/status" 2>/dev/null || echo '{}')
    COORDINATOR_RUNNING=$(echo "$STATUS_DATA" | python -c "import sys, json; data=json.load(sys.stdin); print('Running' if data.get('coordinator_running') else 'Stopped')" 2>/dev/null || echo "Unknown")
    COORDINATOR_PID=$(echo "$STATUS_DATA" | python -c "import sys, json; data=json.load(sys.stdin); print(data.get('coordinator_pid', 'N/A'))" 2>/dev/null || echo "N/A")
    
    echo -e "🤖 Coordinator: ${GREEN}$COORDINATOR_RUNNING${NC}"
    if [ "$COORDINATOR_PID" != "N/A" ] && [ "$COORDINATOR_PID" != "None" ]; then
        echo "   PID: $COORDINATOR_PID"
    fi
    
    # Log files
    echo "📁 Log Files:"
    echo "$STATUS_DATA" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    log_files = data.get('log_files', {})
    for name, info in log_files.items():
        size = info.get('size', 0)
        modified = info.get('modified', 'Unknown')
        print(f'   {name}: {size} bytes (modified: {modified})')
except:
    print('   Unable to fetch log file information')
" 2>/dev/null || echo "   Unable to fetch log file information"
}

show_health() {
    echo -e "${BLUE}🏥 Server Health Check${NC}"
    echo "Server: $SERVER_URL"
    echo "=========================="
    
    curl -s "$SERVER_URL/health" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'Status: {data[\"status\"]}')
    print(f'Service: {data[\"service\"]}')
    print(f'Timestamp: {data[\"timestamp\"]}')
except Exception as e:
    print(f'Error parsing response: {e}')
" 2>/dev/null || echo "Error: Unable to fetch health status"
}

show_logs() {
    local lines=${1:-50}
    local file=${2:-master}
    local level=${3:-}
    
    echo -e "${BLUE}📋 Recent Logs${NC}"
    echo "Server: $SERVER_URL"
    echo "File: $file, Lines: $lines"
    if [ -n "$level" ]; then
        echo "Level: $level"
    fi
    echo "=========================="
    
    local url="$SERVER_URL/logs?file=$file&lines=$lines"
    if [ -n "$level" ]; then
        url="$url&level=$level"
    fi
    
    curl -s "$url" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f'Log file: {data[\"log_file\"]}')
    print(f'Total lines: {data[\"total_lines\"]}')
    print(f'Returned lines: {data[\"returned_lines\"]}')
    if data.get('level_filter'):
        print(f'Level filter: {data[\"level_filter\"]}')
    print()
    for line in data['lines']:
        print(line)
except Exception as e:
    print(f'Error parsing logs: {e}')
" 2>/dev/null || echo "Error: Unable to fetch logs"
}

show_errors() {
    echo -e "${RED}❌ Recent Errors${NC}"
    show_logs 20 master ERROR
}

show_warnings() {
    echo -e "${YELLOW}⚠️  Recent Warnings${NC}"
    show_logs 20 master WARNING
}

list_files() {
    echo -e "${BLUE}📁 Available Log Files${NC}"
    echo "Server: $SERVER_URL"
    echo "======================"
    
    curl -s "$SERVER_URL/logs/files" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    files = data.get('log_files', [])
    for file_info in files:
        name = file_info['name']
        size = file_info['size']
        modified = file_info['modified']
        print(f'{name}: {size} bytes')
        print(f'  Modified: {modified}')
        print()
except Exception as e:
    print(f'Error parsing file list: {e}')
" 2>/dev/null || echo "Error: Unable to fetch file list"
}

download_file() {
    local file="$1"
    if [ -z "$file" ]; then
        echo -e "${RED}Error: Please specify a file to download${NC}" >&2
        echo "Available files:" >&2
        list_files >&2
        exit 1
    fi
    
    echo -e "${BLUE}📥 Downloading $file${NC}"
    curl -s "$SERVER_URL/logs/download/$file" -o "$file" || {
        echo -e "${RED}Error: Failed to download $file${NC}" >&2
        exit 1
    }
    echo -e "${GREEN}Downloaded: $file${NC}"
}

stream_logs() {
    local file=${1:-master}
    local level=${2:-}
    
    echo -e "${BLUE}📡 Streaming Live Logs${NC}"
    echo "Server: $SERVER_URL"
    echo "File: $file"
    if [ -n "$level" ]; then
        echo "Level: $level"
    fi
    echo "Press Ctrl+C to stop"
    echo "=========================="
    
    local url="$SERVER_URL/logs?file=$file&follow=true"
    if [ -n "$level" ]; then
        url="$url&level=$level"
    fi
    
    curl -N -s "$url" | while IFS= read -r line; do
        if [[ $line == data:* ]]; then
            # Parse Server-Sent Events
            data="${line#data: }"
            echo "$data" | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('type') == 'log':
        print(data['line'])
    elif data.get('type') == 'error':
        print(f'Error: {data[\"message\"]}')
except:
    pass
" 2>/dev/null
        fi
    done
}

open_dashboard() {
    echo -e "${BLUE}🌐 Opening Dashboard${NC}"
    echo "URL: $SERVER_URL"
    
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$SERVER_URL"
    elif command -v open >/dev/null 2>&1; then
        open "$SERVER_URL"
    else
        echo "Please open your browser and navigate to: $SERVER_URL"
    fi
}

# Parse command line arguments
COMMAND=""
LINES=50
FILE="master"
LEVEL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --server)
            SERVER_URL="$2"
            shift 2
            ;;
        --file)
            FILE="$2"
            shift 2
            ;;
        --level)
            LEVEL="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        status|health|logs|errors|warnings|files|download|stream|dashboard)
            COMMAND="$1"
            shift
            ;;
        [0-9]*)
            LINES="$1"
            shift
            ;;
        *)
            if [ -z "$COMMAND" ]; then
                COMMAND="$1"
            else
                echo -e "${RED}Unknown option: $1${NC}" >&2
                usage
                exit 1
            fi
            shift
            ;;
    esac
done

# Set default command
if [ -z "$COMMAND" ]; then
    COMMAND="status"
fi

# Check server connection
check_server

# Execute command
case $COMMAND in
    status)
        show_status
        ;;
    health)
        show_health
        ;;
    logs)
        show_logs "$LINES" "$FILE" "$LEVEL"
        ;;
    errors)
        show_errors
        ;;
    warnings)
        show_warnings
        ;;
    files)
        list_files
        ;;
    download)
        download_file "$1"
        ;;
    stream)
        stream_logs "$FILE" "$LEVEL"
        ;;
    dashboard)
        open_dashboard
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}" >&2
        usage
        exit 1
        ;;
esac