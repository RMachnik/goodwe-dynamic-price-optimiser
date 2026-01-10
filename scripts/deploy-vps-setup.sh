#!/bin/bash
set -e

# VPS Initial Setup Script
# Usage: ./deploy-vps-setup.sh

echo "🚀 Setting up VPS for GoodWe Cloud Hub..."

ssh -p 10358 root@srv26.mikr.us << 'ENDSSH'
set -e

echo "📦 Updating system..."
apt update && apt upgrade -y

echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

echo "🐙 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    apt install -y docker-compose-plugin docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

echo "🔧 Installing utilities..."
apt install -y git curl ufw fail2ban htop jq

echo "🔥 Configuring firewall..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (Nginx dashboard)
ufw allow 443/tcp   # HTTPS (future SSL)
ufw allow 10358/tcp # SSH custom port
# Note: Port 40314 for Hub API is already open on Mikrus VPS
echo "✅ Firewall configured"

echo "👤 Creating goodwe user..."
if ! id -u goodwe &> /dev/null; then
    useradd -m -s /bin/bash goodwe
    usermod -aG docker goodwe
    echo "✅ User 'goodwe' created"
else
    echo "✅ User 'goodwe' already exists"
fi

echo "📁 Creating application directories..."
su - goodwe -c "mkdir -p ~/goodwe-cloud-hub/hub-api"
su - goodwe -c "mkdir -p ~/goodwe-cloud-hub/dashboard"

echo "🌐 Installing Nginx..."
apt install -y nginx
systemctl enable nginx
echo "✅ Nginx installed"

echo "✅ VPS setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Set up managed PostgreSQL (Supabase/Neon)"
echo "   2. Set up managed MQTT broker (CloudAMQP/HiveMQ)"
echo "   3. Update hub-api/.env with connection strings"
echo "   4. Run: ./scripts/deploy-hub-api.sh"

ENDSSH

echo ""
echo "✅ VPS is ready for deployment!"
