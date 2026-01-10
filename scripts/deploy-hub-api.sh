#!/bin/bash
set -e

# Hub API Deployment Script
# Usage: ./deploy-hub-api.sh [branch-name]
# Example: ./deploy-hub-api.sh feature/cloud-migration

# Detect current branch
CURRENT_BRANCH=$(git branch --show-current)
DEPLOY_BRANCH="${1:-$CURRENT_BRANCH}"

echo "🚀 Deploying Hub API to VPS..."
echo "   Branch: $DEPLOY_BRANCH"
echo ""

# Warn if deploying from feature branch
if [[ "$DEPLOY_BRANCH" != "main" && "$DEPLOY_BRANCH" != "master" ]]; then
    echo "⚠️  WARNING: Deploying from feature branch '$DEPLOY_BRANCH'"
    echo "   This is fine for testing, but production should use 'main' or 'master'"
    read -p "   Continue? [y/N]: " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 0
    fi
fi

# Check if secrets are configured on VPS
echo "📋 Checking if secrets are configured on VPS..."
if ! ssh -p 10358 root@srv26.mikr.us 'test -f /home/goodwe/goodwe-cloud-hub/hub-api/.env'; then
    echo "❌ Error: Secrets not configured on VPS!"
    echo ""
    echo "Run this first:"
    echo "  ./scripts/manage-secrets.sh vps"
    exit 1
fi
echo "✅ Secrets found on VPS"

echo "📦 Preparing deployment files..."

# Create a temporary deployment package
DEPLOY_DIR=$(mktemp -d)
echo "  Using temp dir: $DEPLOY_DIR"

# Copy necessary files
cp -r hub-api "$DEPLOY_DIR/"
cp docker-compose.yml "$DEPLOY_DIR/"

# Write branch information to deployment
echo "$DEPLOY_BRANCH" > "$DEPLOY_DIR/DEPLOY_BRANCH.txt"
echo "Deployed: $(date)" >> "$DEPLOY_DIR/DEPLOY_BRANCH.txt"

# Create production docker-compose override
cat > "$DEPLOY_DIR/docker-compose.prod.yml" << 'EOF'
version: '3.3'

services:
  hub-api:
    build:
      context: ./hub-api
      dockerfile: Dockerfile
    container_name: goodwe-hub-api
    restart: unless-stopped
    ports:
      - "40314:8000"
    env_file:
      - ./hub-api/.env
    # Note: Using Dockerfile CMD (start.sh) which runs migrations then uvicorn
EOF

echo "📤 Uploading to VPS..."
scp -P 10358 -r "$DEPLOY_DIR"/* root@srv26.mikr.us:/home/goodwe/goodwe-cloud-hub/

echo "🐳 Deploying on VPS..."
ssh -p 10358 root@srv26.mikr.us << 'ENDSSH'
set -e

cd /home/goodwe/goodwe-cloud-hub

# Display deployed branch info
if [ -f DEPLOY_BRANCH.txt ]; then
    echo "📋 Deployment Info:"
    cat DEPLOY_BRANCH.txt
fi

echo "  ✓ Building Docker image..."
docker-compose -f docker-compose.prod.yml build hub-api

echo "  ✓ Stopping old container (if exists)..."
docker-compose -f docker-compose.prod.yml down || true

echo "  ✓ Starting new container..."
docker-compose -f docker-compose.prod.yml up -d hub-api

echo "  ✓ Waiting for service to start..."
sleep 5

echo "  ✓ Checking health..."
if curl -f http://localhost:40314/health > /dev/null 2>&1; then
    echo "    ✅ API is healthy!"
else
    echo "    ⚠️  Health check failed, checking logs..."
    docker logs goodwe-hub-api --tail 50
    exit 1
fi

echo "✅ Hub API deployed successfully!"
echo ""
echo "Container status:"
docker ps | grep goodwe-hub-api

ENDSSH

# Cleanup
rm -rf "$DEPLOY_DIR"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🔍 Verify deployment:"
echo "   curl http://srv26.mikr.us:40314/health"
echo ""
echo "📋 View logs:"
echo "   ssh -p 10358 root@srv26.mikr.us 'docker logs goodwe-hub-api -f'"
echo ""
echo "🎯 Next step:"
echo "   Set up Nginx reverse proxy with SSL"
echo "   Run: ./scripts/setup-nginx.sh"
