# Enhanced Energy Management System for GoodWe Inverter

A comprehensive, intelligent energy management system that optimizes battery charging based on electricity prices, photovoltaic production, house consumption, and battery state for GoodWe inverters.

## 🚀 **Project Overview**

This system transforms your GoodWe inverter into an intelligent energy manager that:
- **Monitors** PV production, grid flow, battery status, and house consumption in real-time
- **Optimizes** battery charging based on electricity prices and multiple factors
- **Automates** charging decisions using a multi-factor decision engine
- **Tracks** energy patterns and provides comprehensive analytics
- **Saves** money by charging during low-price periods and optimizing energy usage

## 🏗️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GoodWe        │    │   Master        │    │   Multi-Factor  │
│   Inverter      │◄──►│   Coordinator   │◄──►│   Decision      │
│   (10 kWh)      │    │   (Central      │    │   Engine        │
│                 │    │   Orchestrator) │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PV System     │    │   Enhanced      │    │   Price-based   │
│   (5.47-6.87kW)│    │   Data          │    │   Optimization  │
│                 │    │   Collector     │    │   & Safety      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Master Coordinator Architecture**

The system is built around a **Master Coordinator** that orchestrates all components:

- **🎯 Central Control**: Single point of control for the entire energy management system
- **🔄 Data Orchestration**: Coordinates data collection from all sources
- **🧠 Decision Engine**: Multi-factor analysis and intelligent decision making
- **🛡️ Safety Management**: GoodWe Lynx-D compliant safety monitoring
- **⚡ Action Execution**: Automated charging control and system management

## 📁 **Project Structure**

```
goodwe-dynamic-price-optimiser/
├── src/                                    # Main source code
│   ├── master_coordinator.py              # 🎯 Master Coordinator (Main Service)
│   ├── enhanced_data_collector.py         # Enhanced data collection system
│   ├── fast_charge.py                     # Core inverter control library
│   ├── polish_electricity_analyzer.py     # Core price analysis library
│   └── automated_price_charging.py        # Core automated charging application
├── config/                                 # Configuration files
│   ├── master_coordinator_config.yaml     # 🎯 Master Coordinator Configuration
│   └── fast_charge_config.yaml            # Legacy configuration template
├── systemd/                                # Systemd service files
│   └── goodwe-master-coordinator.service  # 🎯 Single systemd service (orchestrates everything)
├── scripts/                                # Management and setup scripts
│   ├── ubuntu_setup.sh                    # 🚀 Automated Ubuntu setup
│   └── manage_services.sh                 # Service management script
├── examples/                               # Example scripts and usage
│   ├── example_usage.sh                   # Shell script examples
├── logs/                                   # Application logs
├── out/                                    # Script outputs and data
│   ├── energy_data/                        # Energy monitoring data
│   └── charging_schedule_*.json            # Price analysis outputs
├── test/                                   # Testing and investigation scripts
│   ├── inverter_test.py                   # Basic inverter connectivity test
│   ├── inverter_scan.py                   # Network discovery for inverters
│   ├── test_ips.py                        # IP range testing for inverters
│   ├── sensor_investigator.py             # Sensor discovery and investigation
│   └── test_structure.py                  # Project structure verification
├── docs/                                   # Documentation
│   ├── PROJECT_PLAN_Enhanced_Energy_Management.md
│   ├── README_fast_charging.md
│   ├── README_automated_charging.md
│   ├── README_MASTER_COORDINATOR.md
│   └── GOODWE_LYNX_D_SAFETY_COMPLIANCE.md
├── custom_components/                      # Home Assistant integration
│   └── goodwe/                            # GoodWe custom component
├── requirements.txt                        # Python dependencies
└── README.md                               # This file
```

## 🔧 **Installation & Setup**

### **Prerequisites**
- Python 3.8+
- GoodWe inverter (tested with GW10KN-ET)
- GoodWe Lynx-D battery system (LX-D5.0-10) - **Safety compliant**
- Network access to inverter (UDP port 8899 or TCP port 502)

### **Safety Compliance**
- ✅ **GoodWe Lynx-D Compliant**: Full safety compliance with Lynx-D specifications
- ✅ **VDE 2510-50 Standard**: Meets German battery safety standards
- ✅ **Voltage Range**: 320V - 480V (GoodWe Lynx-D specification)
- ✅ **Temperature Range**: 0°C - 53°C charging, -20°C - 53°C discharging
- ✅ **Emergency Protection**: Automatic safety stops and recovery
- 📋 **Safety Documentation**: See [GoodWe Lynx-D Safety Compliance](docs/GOODWE_LYNX_D_SAFETY_COMPLIANCE.md)

### **Quick Start**

#### **Option 1: Automated Setup (Recommended for Ubuntu)**
```bash
# Clone and run automated setup
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
cd goodwe-dynamic-price-optimiser
chmod +x scripts/ubuntu_setup.sh
./scripts/ubuntu_setup.sh
```

#### **Option 2: Manual Setup**
1. **Clone the repository**
   ```bash
   git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
   cd goodwe-dynamic-price-optimiser
   ```

2. **Set up Python virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure the Master Coordinator**
   ```bash
   # Edit the master coordinator configuration
   nano config/master_coordinator_config.yaml
   # Update inverter IP address and other settings
   ```

4. **Test the Master Coordinator**
   ```bash
   # Test mode (single decision cycle)
   python src/master_coordinator.py --test
   
   # Show current status
   python src/master_coordinator.py --status
   
   # Start the coordinator
   python src/master_coordinator.py
   ```

### **Production Deployment (Ubuntu Server)**

#### **Using Systemd Service (Recommended)**
```bash
# Install the service
sudo cp systemd/goodwe-master-coordinator.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start the service
sudo systemctl start goodwe-master-coordinator

# Enable auto-start on boot
sudo systemctl enable goodwe-master-coordinator

# Check status
sudo systemctl status goodwe-master-coordinator

# View logs
sudo journalctl -u goodwe-master-coordinator -f
```

#### **Service Management**
```bash
# Using the management script (single service)
./scripts/manage_services.sh start     # Start the master coordinator
./scripts/manage_services.sh stop      # Stop the master coordinator
./scripts/manage_services.sh restart   # Restart the master coordinator
./scripts/manage_services.sh status    # Check status
./scripts/manage_services.sh logs      # View logs (last 100 lines)
./scripts/manage_services.sh logs -f   # Follow logs in real-time
./scripts/manage_services.sh enable    # Enable auto-start on boot
./scripts/manage_services.sh disable   # Disable auto-start on boot
```

## 🎯 **Master Coordinator Features**

### **Intelligent Decision Making**
- **📊 Multi-Factor Analysis**: Considers electricity prices, PV production, battery state, and consumption
- **⏰ Real-Time Monitoring**: Continuous data collection and analysis
- **🔄 Adaptive Learning**: Improves decisions based on historical patterns
- **🛡️ Safety First**: GoodWe Lynx-D compliant safety monitoring

### **Current Date & Time Handling**
- **📅 Automatic Date Detection**: Always uses current date for price analysis
- **🕐 Real-Time Updates**: Fetches latest electricity prices for today
- **⏱️ Precise Timing**: 15-minute interval price analysis
- **🌍 Timezone Aware**: Handles local time correctly

### **System Monitoring**
- **📈 Performance Metrics**: Tracks charging efficiency and savings
- **📊 Data Analytics**: Comprehensive energy usage analysis
- **🔍 Health Checks**: Continuous system health monitoring
- **📝 Detailed Logging**: Complete audit trail of all decisions

## 📊 **Usage Examples**

### **Testing the Master Coordinator**
```bash
# Test mode (single decision cycle)
python src/master_coordinator.py --test

# Show current status
python src/master_coordinator.py --status

# Start the coordinator
python src/master_coordinator.py
```

### **Individual Component Testing**
```bash
# Test inverter connectivity
python test/inverter_test.py

# Test data collection
python src/enhanced_data_collector.py --single

# Test price analysis
python src/polish_electricity_analyzer.py --date $(date +%Y-%m-%d)

# Test fast charging
python src/fast_charge.py --status
```

## 🔧 **Configuration**

### **Master Coordinator Configuration**
The main configuration file is `config/master_coordinator_config.yaml`:

```yaml
# Inverter Configuration
inverter:
  ip_address: "192.168.68.51"  # Your inverter IP
  port: 8899
  family: "ET"  # Inverter family
  comm_addr: 0xf7

# Charging Configuration
charging:
  max_power: 5000  # Maximum charging power in Watts
  safety_voltage_min: 320.0  # GoodWe Lynx-D minimum voltage
  safety_voltage_max: 480.0  # GoodWe Lynx-D maximum voltage

# Coordinator Settings
coordinator:
  decision_interval_minutes: 15  # How often to make decisions
  health_check_interval_minutes: 5  # Health check frequency
  emergency_stop_conditions:
    battery_temp_max: 53.0  # GoodWe Lynx-D max temperature
    battery_voltage_min: 320.0  # GoodWe Lynx-D min voltage
    battery_voltage_max: 480.0  # GoodWe Lynx-D max voltage
```

## 📚 **Documentation**

### **📋 Project Planning**
- **[PROJECT_PLAN_Enhanced_Energy_Management.md](docs/PROJECT_PLAN_Enhanced_Energy_Management.md)** - Comprehensive project plan with tasks, timelines, and progress tracking

### **🎯 Master Coordinator**
- **[README_MASTER_COORDINATOR.md](docs/README_MASTER_COORDINATOR.md)** - Master Coordinator documentation and usage

### **🛡️ Safety Compliance**
- **[GOODWE_LYNX_D_SAFETY_COMPLIANCE.md](docs/GOODWE_LYNX_D_SAFETY_COMPLIANCE.md)** - GoodWe Lynx-D safety compliance documentation

### **🔌 Fast Charging Control**
- **[README_fast_charge.md](docs/README_fast_charge.md)** - Basic GoodWe inverter fast charging control

### **⚡ Automated Price-Based Charging**
- **[README_automated_charging.md](docs/README_automated_charging.md)** - Intelligent charging based on electricity prices

### **🧪 Testing & Investigation**
- **Test Scripts** in `test/` directory for connectivity and sensor investigation

## 🎯 **Current Status**

### **✅ Master Coordinator - COMPLETED**
- **🎯 Central Orchestration**: Single point of control for entire energy management system
- **📊 Multi-Factor Decision Engine**: Intelligent analysis of prices, PV, battery, and consumption
- **🛡️ Safety Compliance**: Full GoodWe Lynx-D safety monitoring and emergency controls
- **⚡ Automated Charging**: Price-based optimization with safety-first approach
- **📅 Current Date Handling**: Real-time price analysis for today's electricity market
- **🔄 System Health**: Continuous monitoring and automatic recovery

### **✅ Enhanced Data Collection - COMPLETED**
- Real-time monitoring of PV production, grid flow, battery status
- Comprehensive data collection every 60 seconds
- Data storage and historical tracking
- Beautiful real-time dashboard

## 🖥️ **Command-Line Usage**

### **🎯 Master Coordinator (Main Service)**
```bash
# Test mode (single decision cycle)
python src/master_coordinator.py --test

# Show current status
python src/master_coordinator.py --status

# Start the coordinator
python src/master_coordinator.py

# Start in non-interactive mode (for systemd)
python src/master_coordinator.py --non-interactive
```

### **📊 Individual Components**
```bash
# Enhanced Data Collector
python src/enhanced_data_collector.py --single      # Collect one data point
python src/enhanced_data_collector.py --status      # Show current status

# Price Analysis
python src/polish_electricity_analyzer.py --date $(date +%Y-%m-%d)

# Fast Charging Control
python src/fast_charge.py --status
python src/fast_charge.py --start --monitor
```

### **📈 Polish Electricity Analyzer**
```bash
# Analyze today's prices (default)
python src/polish_electricity_analyzer.py

# Custom analysis
python src/polish_electricity_analyzer.py --date $(date +%Y-%m-%d)
python src/polish_electricity_analyzer.py --duration 6.0 --windows 5
python src/polish_electricity_analyzer.py --quiet --output my_schedule.json
```

## 🎯 **Key Features**

### **📅 Current Date & Time Handling**
- **✅ Automatic Date Detection**: Always uses current date for price analysis
- **✅ Real-Time Price Updates**: Fetches latest electricity prices for today
- **✅ Precise Timing**: 15-minute interval price analysis
- **✅ Timezone Aware**: Handles local time correctly

### **🛡️ Safety Compliance**
- **✅ GoodWe Lynx-D Compliant**: Full safety compliance with Lynx-D specifications
- **✅ VDE 2510-50 Standard**: Meets German battery safety standards
- **✅ Emergency Protection**: Automatic safety stops and recovery
- **✅ Voltage Range**: 320V - 480V (GoodWe Lynx-D specification)
- **✅ Temperature Range**: 0°C - 53°C charging, -20°C - 53°C discharging

### **📊 Multi-Factor Decision Engine**
- **✅ Price Analysis**: Real-time electricity market price monitoring
- **✅ PV Production**: Solar generation tracking and optimization
- **✅ Battery Management**: State of charge and health monitoring
- **✅ Consumption Patterns**: House energy usage analysis
- **✅ Safety First**: All decisions prioritize safety over optimization

## 🚀 **Getting Started**

1. **Quick Setup**: Use the automated Ubuntu setup script
2. **Manual Setup**: Follow the manual installation steps
3. **Test**: Run the master coordinator in test mode
4. **Deploy**: Set up as a systemd service for production use

## 📞 **Support**

For questions, issues, or contributions, please refer to the documentation in the `docs/` directory or create an issue in the repository.

---

**🎯 The Master Coordinator is now fully operational and ready for production use!**
