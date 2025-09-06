#!/bin/bash
# Ubuntu Docker Setup Script for GoodWe Dynamic Price Optimiser
# Run this script on your Ubuntu server to automatically set up Docker deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    error "This script should not be run as root. Please run as a regular user with sudo privileges."
    exit 1
fi

# Check if sudo is available
if ! sudo -n true 2>/dev/null; then
    error "This script requires sudo privileges. Please run with a user that has sudo access."
    exit 1
fi

log "Starting Ubuntu Docker setup for GoodWe Dynamic Price Optimiser..."

# Step 1: Update system
log "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 2: Install Docker and required packages
log "Installing Docker and required packages..."

# Install Docker
log "Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
log "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install other required packages
log "Installing other required packages..."
sudo apt install -y python3 python3-pip python3-venv git curl wget jq

# Step 3: Create application directory
log "Setting up application directory..."
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser
sudo chown -R $USER:$USER /opt/goodwe-dynamic-price-optimiser

# Step 4: Clone repository
log "Cloning repository..."
cd /opt/goodwe-dynamic-price-optimiser
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git .

# Step 5: Create data directories
log "Creating data directories..."
mkdir -p data logs out config

# Step 6: Create configuration file
log "Creating configuration file..."
if [ ! -f config/master_coordinator_config.yaml ]; then
    cp config/master_coordinator_config.yaml.example config/master_coordinator_config.yaml
    log "Configuration file created. Please edit it with your inverter details:"
    log "nano /opt/goodwe-dynamic-price-optimiser/config/master_coordinator_config.yaml"
fi

# Step 7: Build Docker image
log "Building Docker image..."
./scripts/docker_manage.sh build

# Step 8: Create Docker management script
log "Creating Docker management script..."
sudo cp scripts/docker_manage.sh /usr/local/bin/goodwe-docker
sudo chmod +x /usr/local/bin/goodwe-docker

# Step 9: Create systemd service for Docker container
log "Creating systemd service for Docker container..."
sudo tee /etc/systemd/system/goodwe-docker.service > /dev/null <<EOF
[Unit]
Description=GoodWe Dynamic Price Optimiser Docker Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/goodwe-dynamic-price-optimiser
ExecStart=/usr/local/bin/goodwe-docker start
ExecStop=/usr/local/bin/goodwe-docker stop
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Enable and start service
log "Enabling and starting Docker service..."
sudo systemctl daemon-reload
sudo systemctl enable goodwe-docker
sudo systemctl start goodwe-docker

# Step 11: Show status
log "Checking service status..."
sudo systemctl status goodwe-docker --no-pager

# Step 12: Clean up
log "Cleaning up..."
rm -f get-docker.sh

success "Docker setup completed successfully!"
echo ""
echo "🐳 Docker Management Commands:"
echo "  goodwe-docker start     # Start the container"
echo "  goodwe-docker stop      # Stop the container"
echo "  goodwe-docker status    # Check container status"
echo "  goodwe-docker logs      # View container logs"
echo "  goodwe-docker restart   # Restart the container"
echo ""
echo "📁 Configuration:"
echo "  nano /opt/goodwe-dynamic-price-optimiser/config/master_coordinator_config.yaml"
echo ""
echo "📊 Service Management:"
echo "  sudo systemctl start goodwe-docker"
echo "  sudo systemctl stop goodwe-docker"
echo "  sudo systemctl status goodwe-docker"
echo ""
echo "📋 Container will automatically start on system boot!"
echo "📋 Container runs independently of SSH sessions!"
echo ""
echo "⚠️  IMPORTANT: You need to log out and log back in for Docker group changes to take effect."
echo "   After logging back in, you can run: goodwe-docker status"
