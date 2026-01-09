#!/bin/bash
# Ubuntu Server Quick Setup Script for GoodWe Services
# Run this script on your Ubuntu server to automatically set up the services

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

log "Starting Ubuntu server setup for GoodWe services..."

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

# Step 4: Copy application files
log "Copying application files..."
if [[ -d "." ]]; then
    cp -r . /opt/goodwe-dynamic-price-optimiser/
else
    error "Please run this script from the project directory"
    exit 1
fi

# Step 5: Create necessary directories
log "Creating necessary directories..."
mkdir -p /opt/goodwe-dynamic-price-optimiser/logs
mkdir -p /opt/goodwe-dynamic-price-optimiser/out

# Step 6: Set up Python environment
log "Setting up Python virtual environment..."
cd /opt/goodwe-dynamic-price-optimiser
python3 -m venv venv
source venv/bin/activate

# Step 7: Install Python dependencies
log "Installing Python dependencies..."
pip install --upgrade pip
if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt
else
    warning "requirements.txt not found, installing basic dependencies..."
    pip install goodwe==0.4.8 PyYAML requests
fi

# Step 8: Update and install master coordinator systemd service
log "Setting up master coordinator systemd service..."
if [[ -f "systemd/goodwe-master-coordinator.service" ]]; then
    # Replace python3 with venv python path
    sed -i 's|/usr/bin/python3|/opt/goodwe-dynamic-price-optimiser/venv/bin/python|g' systemd/goodwe-master-coordinator.service
    # Update working directory to project root
    sed -i 's|WorkingDirectory=.*|WorkingDirectory=/opt/goodwe-dynamic-price-optimiser|g' systemd/goodwe-master-coordinator.service
    success "Updated master coordinator service file"
    
    # Install the service
    sudo cp systemd/goodwe-master-coordinator.service /etc/systemd/system/
    sudo systemctl daemon-reload
    success "Master coordinator systemd service installed"
else
    error "Master coordinator service file not found!"
    exit 1
fi

# Step 9: Set up service management
log "Setting up service management..."
chmod +x scripts/manage_services.sh

# Step 10: Create default configuration if it doesn't exist
log "Setting up configuration..."
if [[ ! -f "config/master_coordinator_config.yaml" ]]; then
    warning "Master coordinator configuration not found. Please ensure config/master_coordinator_config.yaml exists."
    warning "You can copy it from the project repository or create it manually."
fi

# Ensure the configuration has the correct inverter IP
if [[ -f "config/master_coordinator_config.yaml" ]]; then
    log "Updating configuration with current settings..."
    # Update inverter IP if it's still the default
    sed -i 's/ip_address: "192.168.1.100"/ip_address: "192.168.68.51"/g' config/master_coordinator_config.yaml
    success "Configuration updated"
fi

# Step 11: Set up log rotation
log "Setting up log rotation..."
sudo tee /etc/logrotate.d/goodwe > /dev/null << 'EOF'
/opt/goodwe-dynamic-price-optimiser/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Step 12: Final setup
log "Finalizing setup..."
sudo systemctl daemon-reload

success "Setup completed successfully!"
echo
echo "Next steps:"
echo "1. Edit configuration: sudo nano /opt/goodwe-dynamic-price-optimiser/config/master_coordinator_config.yaml"
echo "2. Test the master coordinator: cd /opt/goodwe-dynamic-price-optimiser && source venv/bin/activate && python3 src/master_coordinator.py --test"
echo "3. Start the service: sudo systemctl start goodwe-master-coordinator"
echo "4. Check status: sudo systemctl status goodwe-master-coordinator"
echo "5. View logs: sudo journalctl -u goodwe-master-coordinator -f"
echo "6. Enable auto-start: sudo systemctl enable goodwe-master-coordinator"
echo
echo "Master Coordinator Management Commands:"
echo "  sudo systemctl start goodwe-master-coordinator     # Start the service"
echo "  sudo systemctl stop goodwe-master-coordinator      # Stop the service"
echo "  sudo systemctl restart goodwe-master-coordinator   # Restart the service"
echo "  sudo systemctl status goodwe-master-coordinator    # Check status"
echo "  sudo journalctl -u goodwe-master-coordinator -f    # View live logs"
echo "  sudo journalctl -u goodwe-master-coordinator --since today  # View today's logs"
echo
echo "Manual Testing Commands:"
echo "  cd /opt/goodwe-dynamic-price-optimiser"
echo "  source venv/bin/activate"
echo "  python3 src/master_coordinator.py --help           # Show help"
echo "  python3 src/master_coordinator.py --status         # Show current status"
echo "  python3 src/master_coordinator.py --test           # Run test mode"
echo
success "GoodWe Master Coordinator is ready to use!"
