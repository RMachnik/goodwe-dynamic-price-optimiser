# Systemd Service Installation Guide

This guide explains how to install and configure the GoodWe Master Coordinator as a systemd service.

## 🔍 **Check Systemd Status**

First, verify that systemd is installed and running:

```bash
# Check systemd version
systemctl --version

# Check if systemd is running
systemctl status
```

## 📋 **Manual Installation Steps**

### **1. Install the Service File**

```bash
# Copy the service file to systemd directory
sudo cp systemd/goodwe-master-coordinator.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload
```

### **2. Verify Installation**

```bash
# Check if service is recognized
systemctl list-unit-files | grep goodwe

# Check service status
systemctl status goodwe-master-coordinator
```

### **3. Enable and Start Service**

```bash
# Enable service to start on boot
sudo systemctl enable goodwe-master-coordinator

# Start the service
sudo systemctl start goodwe-master-coordinator

# Check status
sudo systemctl status goodwe-master-coordinator
```

## 🛠️ **Alternative: User Service (No Sudo Required)**

If you don't have sudo access, you can run the service as a user service:

### **1. Create User Service Directory**

```bash
mkdir -p ~/.config/systemd/user
```

### **2. Create User Service File**

```bash
# Copy and modify the service file for user mode
cp systemd/goodwe-master-coordinator.service ~/.config/systemd/user/
```

### **3. Edit User Service File**

```bash
nano ~/.config/systemd/user/goodwe-master-coordinator.service
```

Remove or comment out these lines (they require root privileges):
```ini
# NoNewPrivileges=true
# PrivateTmp=true
# ProtectSystem=strict
# ProtectHome=true
# ReadWritePaths=/opt/goodwe-dynamic-price-optimiser/logs
# ReadWritePaths=/opt/goodwe-dynamic-price-optimiser/out
# ReadWritePaths=/opt/goodwe-dynamic-price-optimiser/config
# IPAddressAllow=localhost
# IPAddressAllow=10.0.0.0/8
# IPAddressAllow=172.16.0.0/12
# IPAddressAllow=192.168.0.0/16
# LimitNOFILE=65536
# MemoryMax=512M
# CPUQuota=50%
```

Update the paths to match your current directory:
```ini
WorkingDirectory=/home/rmachnik/sources/goodwe-dynamic-price-optimiser/src
ExecStart=/home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/bin/python /home/rmachnik/sources/goodwe-dynamic-price-optimiser/src/master_coordinator.py --non-interactive
Environment=PYTHONPATH=/home/rmachnik/sources/goodwe-dynamic-price-optimiser/src
Environment=HOME=/home/rmachnik
```

### **4. Enable and Start User Service**

```bash
# Reload user systemd
systemctl --user daemon-reload

# Enable user service
systemctl --user enable goodwe-master-coordinator

# Start user service
systemctl --user start goodwe-master-coordinator

# Check status
systemctl --user status goodwe-master-coordinator
```

## 🔧 **Service Management Commands**

### **System Service (with sudo)**
```bash
# Start service
sudo systemctl start goodwe-master-coordinator

# Stop service
sudo systemctl stop goodwe-master-coordinator

# Restart service
sudo systemctl restart goodwe-master-coordinator

# Check status
sudo systemctl status goodwe-master-coordinator

# View logs
sudo journalctl -u goodwe-master-coordinator -f

# Disable service
sudo systemctl disable goodwe-master-coordinator
```

### **User Service (no sudo)**
```bash
# Start service
systemctl --user start goodwe-master-coordinator

# Stop service
systemctl --user stop goodwe-master-coordinator

# Restart service
systemctl --user restart goodwe-master-coordinator

# Check status
systemctl --user status goodwe-master-coordinator

# View logs
journalctl --user -u goodwe-master-coordinator -f

# Disable service
systemctl --user disable goodwe-master-coordinator
```

## 🐛 **Troubleshooting**

### **Service Won't Start**
```bash
# Check service status
systemctl status goodwe-master-coordinator

# Check logs
journalctl -u goodwe-master-coordinator -n 50

# Check if paths exist
ls -la /home/rmachnik/sources/goodwe-dynamic-price-optimiser/venv/bin/python
ls -la /home/rmachnik/sources/goodwe-dynamic-price-optimiser/src/master_coordinator.py
```

### **Permission Issues**
```bash
# Check file permissions
ls -la systemd/goodwe-master-coordinator.service

# Make sure service file is readable
chmod 644 systemd/goodwe-master-coordinator.service
```

### **Path Issues**
```bash
# Verify current directory
pwd

# Check if virtual environment exists
ls -la venv/bin/python

# Check if master coordinator exists
ls -la src/master_coordinator.py
```

## 🚀 **Quick Setup Script**

Create a quick setup script:

```bash
#!/bin/bash
# quick_setup.sh

echo "Setting up GoodWe Master Coordinator service..."

# Check if we have sudo access
if sudo -n true 2>/dev/null; then
    echo "Installing as system service..."
    sudo cp systemd/goodwe-master-coordinator.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable goodwe-master-coordinator
    sudo systemctl start goodwe-master-coordinator
    echo "Service installed and started!"
    sudo systemctl status goodwe-master-coordinator
else
    echo "Installing as user service..."
    mkdir -p ~/.config/systemd/user
    cp systemd/goodwe-master-coordinator.service ~/.config/systemd/user/
    # Edit the service file to remove root-only options
    sed -i 's/^NoNewPrivileges/#NoNewPrivileges/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^PrivateTmp/#PrivateTmp/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^ProtectSystem/#ProtectSystem/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^ProtectHome/#ProtectHome/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^ReadWritePaths/#ReadWritePaths/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^IPAddressAllow/#IPAddressAllow/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^LimitNOFILE/#LimitNOFILE/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^MemoryMax/#MemoryMax/' ~/.config/systemd/user/goodwe-master-coordinator.service
    sed -i 's/^CPUQuota/#CPUQuota/' ~/.config/systemd/user/goodwe-master-coordinator.service
    
    systemctl --user daemon-reload
    systemctl --user enable goodwe-master-coordinator
    systemctl --user start goodwe-master-coordinator
    echo "User service installed and started!"
    systemctl --user status goodwe-master-coordinator
fi
```

## 📝 **Notes**

- **System Service**: Requires sudo access, runs as root, starts on boot
- **User Service**: No sudo required, runs as user, starts when user logs in
- **Web Server**: Both modes support the web server on port 8080
- **Logs**: Use `journalctl` to view service logs
- **Configuration**: Edit `config/master_coordinator_config.yaml` for settings