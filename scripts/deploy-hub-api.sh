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
    # read -p "   Continue? [y/N]: " -n 1 -r REPLY
    # echo ""
    # if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    #     echo "Deployment cancelled."
    #     exit 1
    # fi
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

# REMOVE local .env files to avoid overwriting production secrets on VPS
find "$DEPLOY_DIR" -name ".env" -type f -delete
echo "  ✓ Cleaned up local secrets from package"

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

# 2. Preparation on VPS
echo "🏗️  Preparing VPS for deployment..."
ssh -p 10358 root@srv26.mikr.us << 'PRESSH'
set -e
mkdir -p /home/goodwe/goodwe-cloud-hub/hub-api

# Backup production secrets if they exist
if [ -f /home/goodwe/goodwe-cloud-hub/hub-api/.env ]; then
    echo "  ✓ Backing up production .env..."
    cp /home/goodwe/goodwe-cloud-hub/hub-api/.env /home/goodwe/hub-api-env.bak
fi

# Create a backup of the current working state for easy rollback
if [ -d /home/goodwe/goodwe-cloud-hub/hub-api ]; then
    echo "  ✓ Creating rollback backup on VPS..."
    rm -rf /home/goodwe/goodwe-cloud-hub_backup
    cp -r /home/goodwe/goodwe-cloud-hub /home/goodwe/goodwe-cloud-hub_backup
fi

# Clean up remote directory (except for hidden files if needed, but here we want fresh code)
echo "  ✓ Cleaning up old files..."
# We keep the backup we just made obviously
find /home/goodwe/goodwe-cloud-hub -maxdepth 1 -not -name "goodwe-cloud-hub" -not -name "." -not -name "hub-api" -delete || true
rm -rf /home/goodwe/goodwe-cloud-hub/hub-api/*
PRESSH

echo "📤 Uploading package to VPS..."
scp -P 10358 -r "$DEPLOY_DIR"/* root@srv26.mikr.us:/home/goodwe/goodwe-cloud-hub/

echo "🏗️  Restoring secrets and setting permissions..."
ssh -p 10358 root@srv26.mikr.us << 'POSTSSH'
set -e
if [ -f /home/goodwe/hub-api-env.bak ]; then
    mv /home/goodwe/hub-api-env.bak /home/goodwe/goodwe-cloud-hub/hub-api/.env
    echo "  ✓ Restored production .env"
fi
chown -R goodwe:goodwe /home/goodwe/goodwe-cloud-hub
POSTSSH

echo "🏗️  Building and Starting on VPS..."
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

echo "  ✓ Starting new container..."
# Use up -d which handles restarts gracefully
docker-compose -f docker-compose.prod.yml up -d hub-api

echo "  ✓ Waiting for service to start (10s)..."
sleep 10

echo "  ✓ Checking health..."
if curl -f http://localhost:40314/health > /dev/null 2>&1; then
    echo "    ✅ API is healthy!"
    echo "    ✓ Deployment successful."
else
    echo "    ❌ Health check FAILED! ROLLING BACK..."
    if [ -d /home/goodwe/goodwe-cloud-hub_backup ]; then
        cd /home/goodwe
        rm -rf goodwe-cloud-hub
        mv goodwe-cloud-hub_backup goodwe-cloud-hub
        cd goodwe-cloud-hub
        echo "    ✓ Restored files from backup. Restarting previous version..."
        docker-compose -f docker-compose.prod.yml up -d hub-api
        echo "    ✅ Rollback complete. Previous version is running."
    else
        echo "    ❌ Error: No backup found to rollback to!"
    fi
    exit 1
fi

echo "✅ Hub API update complete!"
echo ""
echo "Container status:"
docker ps | grep goodwe-hub-api || echo "Warning: Container not found in ps list"
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
