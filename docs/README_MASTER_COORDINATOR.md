# Master Coordinator for GoodWe Enhanced Energy Management System

The Master Coordinator is the central orchestrator that manages all components of your intelligent energy management system. It replaces the need to run multiple individual services and provides unified control over the entire system.

## 🏗️ **Architecture Overview**

```
┌─────────────────────────────────────────────────────────────┐
│                    MASTER COORDINATOR                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Data          │  │   Decision      │  │   Action     │ │
│  │   Collection    │  │   Engine        │  │   Executor   │ │
│  │   Manager       │  │   Manager       │  │   Manager    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Enhanced      │  │   Multi-Factor  │  │   Fast Charge   │
│   Data          │  │   Decision      │  │   Controller    │
│   Collector     │  │   Engine        │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Price         │  │   Battery       │  │   Grid Flow     │
│   Analyzer      │  │   Manager       │  │   Optimizer     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## 🚀 **Key Features**

### **Unified Management**
- **Single Service**: One systemd service manages everything
- **Centralized Logging**: All logs in one place with proper rotation
- **Health Monitoring**: Continuous system health checks
- **Emergency Controls**: Automatic safety stops and alerts

### **Intelligent Decision Making**
- **Multi-Factor Analysis**: Considers price, battery, PV, and consumption
- **Weighted Scoring**: 40% price, 25% battery, 20% PV, 15% consumption
- **Dynamic Decisions**: Makes charging decisions every 15 minutes
- **Confidence Scoring**: Provides decision confidence levels

### **Comprehensive Data Collection**
- **Real-time Monitoring**: PV production, grid flow, battery status
- **Historical Analysis**: 24-hour data retention for pattern analysis
- **Performance Metrics**: System efficiency and utilization tracking
- **Data Storage**: Organized storage in JSON format

### **Safety & Reliability**
- **Emergency Stops**: Automatic shutdown on dangerous conditions
- **Auto-Recovery**: Automatic reconnection and error handling
- **Graceful Shutdown**: Proper cleanup on service stop
- **Resource Limits**: CPU and memory limits for stability

## 📋 **System Requirements**

- **Python**: 3.8 or higher
- **Dependencies**: All requirements from `requirements.txt`
- **System**: Ubuntu 20.04+ with systemd
- **Network**: Access to inverter and internet for price data
- **Storage**: ~1GB for logs and data (30-day retention)

## 🔧 **Installation & Setup**

### **1. Quick Setup (Recommended)**
```bash
# Run the automated setup script
cd /path/to/goodwe-dynamic-price-optimiser
./scripts/ubuntu_setup.sh
```

### **2. Manual Setup**
```bash
# Install systemd service
sudo cp systemd/goodwe-master-coordinator.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable goodwe-master-coordinator
sudo systemctl start goodwe-master-coordinator
```

### **3. Configuration**
Edit the configuration file:
```bash
sudo nano /opt/goodwe-dynamic-price-optimiser/config/master_coordinator_config.yaml
```

**Important Settings to Configure:**
- `inverter.ip_address`: Your inverter's IP address
- `coordinator.decision_interval_minutes`: How often to make decisions (default: 15)
- `charging.max_power`: Maximum charging power in Watts
- `battery_management.capacity_kwh`: Your battery capacity

## 🎮 **Service Management**

### **Using the Management Script**
```bash
cd /opt/goodwe-dynamic-price-optimiser

# Start the service
./scripts/manage_services.sh start

# Stop the service
./scripts/manage_services.sh stop

# Restart the service
./scripts/manage_services.sh restart

# Check status
./scripts/manage_services.sh status

# View logs
./scripts/manage_services.sh logs

# Enable auto-start on boot
./scripts/manage_services.sh enable
```

### **Using systemctl Directly**
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

# Enable auto-start
sudo systemctl enable goodwe-master-coordinator
```

## 📊 **Monitoring & Status**

### **Real-time Status**
```bash
# Check current status
python3 src/master_coordinator.py --status
```

**Status Information:**
- System state (monitoring, charging, optimizing, error)
- Uptime and last decision time
- Current data from all sensors
- Performance metrics
- Decision count and history

### **Log Monitoring**
```bash
# View live logs
sudo journalctl -u goodwe-master-coordinator -f

# View recent logs
sudo journalctl -u goodwe-master-coordinator -n 100

# View logs from today
sudo journalctl -u goodwe-master-coordinator --since today
```

### **Data Files**
- **System State**: `/opt/goodwe-dynamic-price-optimiser/out/system_state/`
- **Energy Data**: `/opt/goodwe-dynamic-price-optimiser/out/energy_data/`
- **Charging Schedules**: `/opt/goodwe-dynamic-price-optimiser/out/charging_schedules/`
- **Logs**: `/opt/goodwe-dynamic-price-optimiser/logs/`

## 🧠 **Decision Engine**

### **Multi-Factor Analysis**
The coordinator uses a weighted scoring system:

1. **Price Factor (40%)**: Electricity market prices
   - 0-200 PLN/MWh = 100 points (excellent)
   - 200-400 PLN/MWh = 80 points (good)
   - 400-600 PLN/MWh = 40 points (fair)
   - 600+ PLN/MWh = 0 points (poor)

2. **Battery Factor (25%)**: Battery state of charge
   - 0-20% = 100 points (critical - charge immediately)
   - 20-40% = 80 points (low - charge during low/medium prices)
   - 40-70% = 40 points (medium - charge during low prices only)
   - 70-90% = 10 points (high - charge during very low prices only)
   - 90-100% = 0 points (full - no charging needed)

3. **PV Factor (20%)**: Solar production
   - High production (3kW+) = 0 points (use solar)
   - Medium production (1-3kW) = 30 points
   - Low production (0.1-1kW) = 60 points
   - No production = 100 points (charge from grid)

4. **Consumption Factor (15%)**: House consumption
   - High consumption (3kW+) = 100 points (charge to support)
   - Medium consumption (1-3kW) = 60 points
   - Low consumption (0.1-1kW) = 30 points
   - Very low consumption = 0 points

### **Decision Logic**
- **Total Score ≥ 70**: Start charging (if not already charging)
- **Total Score ≤ 30**: Stop charging (if currently charging)
- **30 < Score < 70**: Continue current state
- **Battery ≤ 20%**: Emergency charge (regardless of score)

## ⚠️ **Safety Features**

### **Emergency Stop Conditions**
The system automatically stops all operations if:
- Battery temperature > 60°C
- Battery voltage < 45V or > 58V
- Grid voltage < 200V or > 250V
- System errors or communication failures

### **Health Monitoring**
- Continuous inverter connectivity checks
- Automatic reconnection on communication loss
- Performance metrics tracking
- Resource usage monitoring

### **Graceful Shutdown**
- Stops charging before shutdown
- Saves current system state
- Proper cleanup of resources
- Logs shutdown reason

## 🔧 **Configuration Options**

### **Decision Intervals**
```yaml
coordinator:
  decision_interval_minutes: 15        # How often to make decisions
  health_check_interval_minutes: 5     # How often to check system health
  data_collection_interval_seconds: 60 # How often to collect data
```

### **Charging Thresholds**
```yaml
coordinator:
  charging_thresholds:
    start_charging_score: 70    # Start charging if total score >= this
    stop_charging_score: 30     # Stop charging if total score <= this
    continue_charging_min: 30   # Continue charging if score >= this
    continue_charging_max: 70   # Continue charging if score <= this
```

### **Safety Limits**
```yaml
charging:
  max_power: 5000              # Maximum charging power in Watts
  safety_voltage_min: 45.0     # Minimum safe battery voltage
  safety_voltage_max: 58.0     # Maximum safe battery voltage
  safety_current_max: 32.0     # Maximum safe charging current
  safety_temp_max: 60.0        # Maximum safe battery temperature
```

## 🐛 **Troubleshooting**

### **Common Issues**

1. **Service won't start**
   ```bash
   # Check logs for errors
   sudo journalctl -u goodwe-master-coordinator -n 50
   
   # Check configuration
   python3 src/master_coordinator.py --status
   ```

2. **Inverter connection failed**
   ```bash
   # Test inverter connectivity
   python3 test/inverter_test.py
   
   # Check network connectivity
   ping 192.168.1.100  # Replace with your inverter IP
   ```

3. **No price data**
   ```bash
   # Test internet connectivity
   curl -I https://api.raporty.pse.pl/api/csdac-pln
   
   # Check DNS resolution
   nslookup api.raporty.pse.pl
   ```

4. **High resource usage**
   ```bash
   # Check system resources
   htop
   
   # Check service resource limits
   systemctl show goodwe-master-coordinator --property=MemoryMax,CPUQuota
   ```

### **Debug Mode**
```bash
# Run in debug mode
python3 src/master_coordinator.py --test

# Enable verbose logging
# Edit config file and set debug.enabled: true
```

## 📈 **Performance Monitoring**

### **Key Metrics**
- **Decision Accuracy**: How often decisions lead to cost savings
- **System Uptime**: Service availability percentage
- **Data Collection Rate**: Successful data collection percentage
- **Charging Efficiency**: Energy charged vs. energy wasted
- **Cost Savings**: Money saved through intelligent charging

### **Monitoring Commands**
```bash
# View performance metrics
python3 src/master_coordinator.py --status

# Check system resources
htop
df -h

# View service metrics
systemctl status goodwe-master-coordinator
```

## 🔄 **Updates & Maintenance**

### **Updating the Service**
```bash
# Stop service
sudo systemctl stop goodwe-master-coordinator

# Update code
git pull origin main

# Restart service
sudo systemctl start goodwe-master-coordinator
```

### **Configuration Changes**
```bash
# Edit configuration
sudo nano /opt/goodwe-dynamic-price-optimiser/config/master_coordinator_config.yaml

# Restart service to apply changes
sudo systemctl restart goodwe-master-coordinator
```

### **Log Rotation**
Logs are automatically rotated daily and kept for 7 days. Manual cleanup:
```bash
# Clean old logs
sudo journalctl --vacuum-time=7d

# Clean application logs
find /opt/goodwe-dynamic-price-optimiser/logs -name "*.log.*" -mtime +7 -delete
```

## 🆘 **Support**

### **Getting Help**
1. Check the logs: `sudo journalctl -u goodwe-master-coordinator -f`
2. Verify configuration: `python3 src/master_coordinator.py --status`
3. Test components individually
4. Check system resources and connectivity

### **Useful Commands**
```bash
# Full system status
./scripts/manage_services.sh status

# View all logs
./scripts/manage_services.sh logs

# Test single decision cycle
python3 src/master_coordinator.py --test

# Emergency stop (if needed)
sudo systemctl stop goodwe-master-coordinator
```

---

**The Master Coordinator provides a complete, intelligent energy management solution that runs continuously in the background, making optimal charging decisions based on multiple factors while ensuring safety and reliability.**
