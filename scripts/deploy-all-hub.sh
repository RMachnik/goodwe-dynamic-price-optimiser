#!/bin/bash
set -e

# GoodWe Cloud Hub - Unified Orchestrator
# This script performs the full deployment of the Hub API to a VPS.
# Designed for direct IP-based access (No Domain/SSL required).

echo "🚀 Starting Full Hub Provisioning..."
echo ""

# 1. VPS Setup
echo "🏗️  Phase 1: Initial VPS Setup..."
./scripts/deploy-vps-setup.sh

# 2. Secret Management
echo ""
echo "🔐 Phase 2: Configuring Production Secrets..."
./scripts/manage-secrets.sh vps

# 3. RabbitMQ Configuration
echo ""
echo "🐰 Phase 3: Configuring RabbitMQ..."
./scripts/configure-rabbitmq.sh

# 4. Hub API Deployment
echo ""
echo "🚢 Phase 4: Deploying Hub API..."
./scripts/deploy-hub-api.sh

# 5. IP-Based Nginx Setup
echo ""
echo "🌐 Phase 5: Setting up IP-Based Access..."
# Inline Nginx setup for simplicity in this orchestrator
ssh -p 10358 root@srv26.mikr.us << 'ENDSSH'
set -e
echo "🔧 Configuring Nginx for Direct IP Access..."
cat > /etc/nginx/sites-available/goodwe-api << 'EOF'
server {
    listen 8001;
    server_name _; 

    location / {
        proxy_pass http://localhost:40314;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
ln -sf /etc/nginx/sites-available/goodwe-api /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo "✅ Nginx configured for IP on port 8001"
ENDSSH

echo ""
echo "🎉 DEPLOYMENT COMPLETE!"
echo "------------------------------------------------"
echo "API Access: http://<vps-ip>:8001/health"
echo "Dashboard:  http://<vps-ip>:8001/dashboard (once built)"
echo "------------------------------------------------"
