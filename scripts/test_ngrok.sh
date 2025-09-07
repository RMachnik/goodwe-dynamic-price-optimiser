#!/bin/bash
# Test script for ngrok tunnel

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing ngrok tunnel for GoodWe Web UI${NC}"
echo "=============================================="

# Check if web server is running
if ! lsof -i :8080 &> /dev/null; then
    echo -e "${RED}❌ Web server is not running on port 8080${NC}"
    echo -e "${BLUE}💡 Please start the web server first:${NC}"
    echo "   python src/log_web_server.py --host 0.0.0.0 --port 8080"
    exit 1
fi

echo -e "${GREEN}✅ Web server is running on port 8080${NC}"

# Test web server health
echo -e "${BLUE}🔍 Testing web server health endpoint...${NC}"
if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "${GREEN}✅ Web server is responding${NC}"
else
    echo -e "${RED}❌ Web server is not responding${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Starting ngrok tunnel...${NC}"
echo -e "${YELLOW}📝 This will create a public URL for your web UI${NC}"
echo -e "${YELLOW}📝 Press Ctrl+C to stop the tunnel${NC}"
echo ""

# Start ngrok with our configuration
ngrok start goodwe-web-ui-free --config ngrok.yml
