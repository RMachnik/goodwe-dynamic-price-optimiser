#!/bin/bash
#
# Deployment script for monthly tracking & performance optimizations
# Run this on your local machine to deploy to remote server
#

set -e  # Exit on error

REMOTE_USER="rmachnik"
REMOTE_HOST="192.168.33.10"
REMOTE_PATH="/home/rmachnik/sources/goodwe-dynamic-price-optimiser"

echo "🚀 Deploying Monthly Tracking System"
echo "=================================="
echo ""

# Step 1: Commit and push changes locally
echo "📤 Step 1: Committing and pushing changes..."
git add src/daily_snapshot_manager.py src/log_web_server.py test/test_daily_snapshot_manager.py \
    docs/MONTHLY_TRACKING_IMPLEMENTATION.md docs/IMPLEMENTATION_SUMMARY.md docs/QUICK_REFERENCE.md \
    deploy_monthly_tracking.sh

git commit -m "Add monthly cost tracking with daily snapshots and performance optimizations" || echo "No changes to commit"
git push origin master

echo "✅ Changes pushed to git"
echo ""

# Step 2: Pull changes on remote server
echo "📥 Step 2: Pulling changes on remote server..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH} && git pull origin master"

echo "✅ Changes pulled"
echo ""

# Step 3: Create snapshots on remote server
echo "📸 Step 3: Creating daily snapshots..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH} && python3 src/daily_snapshot_manager.py create-missing 90"

echo "✅ Snapshots created"
echo ""

# Step 4: Run tests on remote server
echo "🧪 Step 4: Running tests..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ${REMOTE_PATH} && python3 test/test_daily_snapshot_manager.py"

echo "✅ Tests passed"
echo ""

# Step 5: Restart services
echo "🔄 Step 5: Restarting services..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo systemctl restart goodwe-master-coordinator"

echo "✅ Services restarted"
echo ""

# Step 6: Verify deployment
echo "✔️  Step 6: Verifying deployment..."
echo ""
echo "Checking service status..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "sudo systemctl status goodwe-master-coordinator --no-pager -l | head -15"
echo ""

echo "Testing API endpoints..."
echo ""
echo "1. Current month summary:"
curl -s http://192.168.33.10:8080/monthly-summary | python3 -m json.tool | head -20
echo ""

echo "2. Monthly comparison:"
curl -s http://192.168.33.10:8080/monthly-comparison | python3 -m json.tool | head -30
echo ""

echo "=================================="
echo "✅ Deployment Complete!"
echo ""
echo "📊 Dashboard: http://192.168.33.10:8080/"
echo "📖 Documentation: ${REMOTE_PATH}/docs/MONTHLY_TRACKING_IMPLEMENTATION.md"
echo ""
echo "💡 Next Steps:"
echo "1. Open http://192.168.33.10:8080/ to see the updated dashboard"
echo "2. Check that 'Cost & Savings' shows current month data"
echo "3. Set up daily snapshot cron job (see documentation)"
echo ""

