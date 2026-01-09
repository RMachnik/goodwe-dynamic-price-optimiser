#!/bin/bash
# Deploy Time Series Data Source Display Fix
# This script deploys the fix for the Time Series tab showing "Mock Data" incorrectly

set -e

# Configuration
REMOTE_HOST="${REMOTE_HOST:-rafal@192.168.33.10}"
REMOTE_PATH="${REMOTE_PATH:-/opt/goodwe-dynamic-price-optimiser}"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log "Deploying Time Series Data Source Display Fix..."

# Step 1: Copy the fixed file
log "Copying updated log_web_server.py to remote server..."
scp "$LOCAL_PATH/src/log_web_server.py" "$REMOTE_HOST:$REMOTE_PATH/src/"
success "File copied successfully"

# Step 2: Restart the master coordinator service
log "Restarting master coordinator service..."
ssh "$REMOTE_HOST" "cd $REMOTE_PATH && sudo systemctl restart goodwe-master-coordinator.service"
success "Service restarted successfully"

# Step 3: Wait for service to start
log "Waiting for service to start (5 seconds)..."
sleep 5

# Step 4: Check service status
log "Checking service status..."
ssh "$REMOTE_HOST" "sudo systemctl status goodwe-master-coordinator.service --no-pager -l | head -20"

# Step 5: Verify the fix
log "Verifying the fix..."
echo
log "Testing /historical-data endpoint..."
DATA_SOURCE=$(curl -s http://192.168.33.10:8080/historical-data | python3 -c "import sys, json; print(json.load(sys.stdin).get('data_source', 'unknown'))" 2>/dev/null || echo "failed")
echo "  API data_source: $DATA_SOURCE"

log "Testing web dashboard JavaScript..."
JS_CHECK=$(curl -s http://192.168.33.10:8080/ | grep "data.data_source === 'real_inverter'" | wc -l)
if [ "$JS_CHECK" -gt 0 ]; then
    success "JavaScript code is correctly checking for 'real_inverter'"
else
    warning "JavaScript code may not be updated yet (cache issue?)"
fi

echo
success "Deployment completed!"
echo
log "Please refresh your browser (Ctrl+Shift+R or Cmd+Shift+R) to clear cache"
log "The Time Series tab should now show 'Real Data' instead of 'Mock Data'"





