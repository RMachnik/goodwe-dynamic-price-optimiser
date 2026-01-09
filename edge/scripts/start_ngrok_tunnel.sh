#!/bin/bash
# Start ngrok tunnel for GoodWe Master Coordinator Web UI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}🔗 GoodWe Master Coordinator - ngrok Tunnel Setup${NC}"
echo "=================================================="

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}❌ ngrok is not installed. Please install it first:${NC}"
    echo "   brew install ngrok/ngrok/ngrok"
    exit 1
fi

# Check if web server is running
if ! lsof -i :8080 &> /dev/null; then
    echo -e "${YELLOW}⚠️  Web server is not running on port 8080${NC}"
    echo -e "${BLUE}💡 Starting Master Coordinator with web server...${NC}"
    
    # Start the master coordinator in background
    cd "$PROJECT_ROOT"
    python src/master_coordinator.py &
    COORDINATOR_PID=$!
    
    # Wait for web server to start
    echo -e "${BLUE}⏳ Waiting for web server to start...${NC}"
    for i in {1..30}; do
        if lsof -i :8080 &> /dev/null; then
            echo -e "${GREEN}✅ Web server is running on port 8080${NC}"
            break
        fi
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ Web server failed to start within 30 seconds${NC}"
            kill $COORDINATOR_PID 2>/dev/null || true
            exit 1
        fi
    done
else
    echo -e "${GREEN}✅ Web server is already running on port 8080${NC}"
fi

# Check if ngrok authtoken is set
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo -e "${YELLOW}⚠️  NGROK_AUTHTOKEN environment variable is not set${NC}"
    echo -e "${BLUE}💡 To get your authtoken:${NC}"
    echo "   1. Sign up at https://ngrok.com/"
    echo "   2. Go to https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   3. Copy your authtoken"
    echo "   4. Run: export NGROK_AUTHTOKEN=your_token_here"
    echo ""
    echo -e "${BLUE}🔄 Starting ngrok without authtoken (limited features)...${NC}"
fi

# Start ngrok tunnel
echo -e "${BLUE}🚀 Starting ngrok tunnel...${NC}"
echo -e "${YELLOW}📝 Note: Press Ctrl+C to stop the tunnel${NC}"
echo ""

cd "$PROJECT_ROOT"

# Use the free tunnel configuration
ngrok start goodwe-web-ui-free --config ngrok.yml

# Cleanup function
cleanup() {
    echo -e "\n${BLUE}🛑 Stopping ngrok tunnel...${NC}"
    if [ ! -z "$COORDINATOR_PID" ]; then
        echo -e "${BLUE}🛑 Stopping Master Coordinator...${NC}"
        kill $COORDINATOR_PID 2>/dev/null || true
    fi
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM
