# Ubuntu Server Setup Playbook for GoodWe Services

This guide will help you set up the GoodWe Dynamic Price Optimizer services on your Ubuntu server using systemd.

## Prerequisites

- Ubuntu 20.04 LTS or newer
- Python 3.8 or newer
- sudo privileges
- Internet connection

## Step 1: Initial Server Setup

### 1.1 Update the system
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install required packages
```bash
sudo apt install -y python3 python3-pip python3-venv git curl wget
```

### 1.3 Create application user (optional but recommended)
```bash
sudo useradd -m -s /bin/bash goodwe
sudo usermod -aG sudo goodwe
```

## Step 2: Deploy the Application

### 2.1 Clone or upload your project
```bash
# If using git
sudo git clone https://github.com/your-username/goodwe-dynamic-price-optimiser.git /opt/goodwe-dynamic-price-optimiser

# Or if uploading files
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser
# Upload your files to /opt/goodwe-dynamic-price-optimiser/
```

### 2.2 Set proper permissions
```bash
sudo chown -R ubuntu:ubuntu /opt/goodwe-dynamic-price-optimiser
sudo chmod +x /opt/goodwe-dynamic-price-optimiser/scripts/manage_services.sh
```

### 2.3 Create necessary directories
```bash
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser/logs
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser/out
sudo chown -R ubuntu:ubuntu /opt/goodwe-dynamic-price-optimiser/logs
sudo chown -R ubuntu:ubuntu /opt/goodwe-dynamic-price-optimiser/out
```

## Step 3: Python Environment Setup

### 3.1 Create virtual environment
```bash
cd /opt/goodwe-dynamic-price-optimiser
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Test the installation
```bash
cd src
python3 fast_charge.py --help
python3 automated_price_charging.py --help
```

## Step 4: Configure Services

### 4.1 Update service files for your environment
Edit the systemd service file if needed:
```bash
sudo nano /opt/goodwe-dynamic-price-optimiser/systemd/goodwe-master-coordinator.service
```

**Important**: The service file is already configured to use the virtual environment:
```ini
ExecStart=/opt/goodwe-dynamic-price-optimiser/venv/bin/python /opt/goodwe-dynamic-price-optimiser/src/master_coordinator.py --non-interactive
```

### 4.2 Install systemd services
```bash
cd /opt/goodwe-dynamic-price-optimiser
./scripts/manage_services.sh install
```

## Step 5: Configure Your Application

### 5.1 Create configuration file
```bash
sudo cp /opt/goodwe-dynamic-price-optimiser/config/fast_charge_config.yaml /opt/goodwe-dynamic-price-optimiser/config/fast_charge_config.yaml.backup
sudo nano /opt/goodwe-dynamic-price-optimiser/config/fast_charge_config.yaml
```

### 5.2 Update configuration with your settings
```yaml
inverter:
  ip_address: "192.168.1.100"  # Your inverter IP
  port: 8899
  timeout: 10

charging:
  max_power: 5000  # Watts
  safety_voltage_min: 45.0
  safety_voltage_max: 58.0
  safety_current_max: 32.0

logging:
  level: "INFO"
  file: "/opt/goodwe-dynamic-price-optimiser/logs/fast_charge.log"
```

## Step 6: Start and Test Services

### 6.1 Enable services to start on boot
```bash
./scripts/manage_services.sh enable
```

### 6.2 Start services
```bash
./scripts/manage_services.sh start
```

### 6.3 Check service status
```bash
./scripts/manage_services.sh status
```

### 6.4 View logs
```bash
# View all logs
./scripts/manage_services.sh logs

# View specific service logs
./scripts/manage_services.sh logs goodwe-fast-charge
```

## Step 7: Firewall Configuration (if needed)

### 7.1 Allow necessary ports
```bash
# If using UFW
sudo ufw allow 8899/tcp  # GoodWe inverter port
sudo ufw allow 22/tcp    # SSH
sudo ufw enable
```

## Step 8: Monitoring and Maintenance

### 8.1 Service management commands
```bash
# Start all services
./scripts/manage_services.sh start

# Stop all services
./scripts/manage_services.sh stop

# Restart all services
./scripts/manage_services.sh restart

# Check status
./scripts/manage_services.sh status

# View logs
./scripts/manage_services.sh logs

# Disable auto-start on boot
./scripts/manage_services.sh disable
```

### 8.2 Manual service control
```bash
# Individual service control
sudo systemctl start goodwe-fast-charge
sudo systemctl stop goodwe-fast-charge
sudo systemctl restart goodwe-fast-charge
sudo systemctl status goodwe-fast-charge

# View logs for specific service
sudo journalctl -u goodwe-fast-charge -f
```

### 8.3 Log rotation setup
```bash
sudo nano /etc/logrotate.d/goodwe
```

Add:
```
/opt/goodwe-dynamic-price-optimiser/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
}
```

## Troubleshooting

### Common Issues

1. **Service fails to start**
   ```bash
   sudo journalctl -u goodwe-fast-charge -n 50
   ```

2. **Permission denied**
   ```bash
   sudo chown -R ubuntu:ubuntu /opt/goodwe-dynamic-price-optimiser
   ```

3. **Python module not found**
   ```bash
   # Check if virtual environment is activated in service
   sudo systemctl edit goodwe-fast-charge
   # Add:
   [Service]
   Environment=PATH=/opt/goodwe-dynamic-price-optimiser/venv/bin
   ```

4. **Configuration file not found**
   ```bash
   # Check file paths in service files
   sudo systemctl cat goodwe-fast-charge
   ```

### Log Locations

- **System logs**: `sudo journalctl -u service-name`
- **Application logs**: `/opt/goodwe-dynamic-price-optimiser/logs/`
- **Service status**: `systemctl status service-name`

## Security Considerations

1. **Run services as non-root user** (already configured)
2. **Use systemd security features** (already configured)
3. **Regular updates**: `sudo apt update && sudo apt upgrade`
4. **Monitor logs regularly**
5. **Backup configuration files**

## Backup and Recovery

### Backup
```bash
# Backup configuration
sudo tar -czf goodwe-backup-$(date +%Y%m%d).tar.gz /opt/goodwe-dynamic-price-optimiser/config/

# Backup logs
sudo tar -czf goodwe-logs-$(date +%Y%m%d).tar.gz /opt/goodwe-dynamic-price-optimiser/logs/
```

### Recovery
```bash
# Restore from backup
sudo tar -xzf goodwe-backup-YYYYMMDD.tar.gz -C /
sudo systemctl daemon-reload
sudo systemctl restart goodwe-fast-charge
```

## Next Steps

1. **Monitor the services** for the first few days
2. **Set up log monitoring** (optional)
3. **Configure alerts** (optional)
4. **Schedule regular backups**
5. **Update documentation** with your specific configuration

## Support

If you encounter issues:
1. Check the logs: `./scripts/manage_services.sh logs`
2. Verify configuration files
3. Test Python scripts manually
4. Check system resources: `htop`, `df -h`
