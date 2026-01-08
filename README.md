# GoodWe Dynamic Price Optimiser

A comprehensive, intelligent energy management system that optimizes battery charging based on electricity prices, photovoltaic production, house consumption, and battery state. **Now with support for multiple inverter brands through vendor-agnostic abstraction layer!**

## 🚀 **Project Overview**

This system transforms your GoodWe inverter into an intelligent energy manager that:
- **✅ VALIDATED**: Monitors PV production, grid flow, battery status, house consumption, and per-phase currents in real-time
- **✅ EFFICIENT**: Optimizes battery charging based on Polish electricity market prices (95-98% accuracy)
- **✅ RELIABLE**: Automates charging decisions using validated CSDAC-PLN API (100% uptime)
- **✅ SMART**: Implements intelligent charging strategy with weather-aware PV forecasting and consumption analysis (1500W PV overproduction threshold)
- **✅ INTELLIGENT**: Considers consumption patterns and price optimization opportunities
- **✅ INTEGRATED**: Polish electricity pricing with SC component and G13s seasonal distribution tariff (supports G11, G12, G12as, G12w, G13s, G14dynamic)
- **✅ WEATHER-ENHANCED**: Real-time weather data from IMGW + Open-Meteo for accurate PV forecasting
- **✅ NIGHT CHARGING**: Smart night charging for high price day preparation with battery discharge optimization
- **✅ MULTI-SESSION**: Multiple daily charging sessions for maximum cost optimization
- **✅ ADVANCED OPTIMIZATION**: Smart critical charging rules prevent expensive charging and enable proactive charging
- **✅ COST-EFFECTIVE**: Real-world tested optimization rules save up to 70% on charging costs
- **✅ BATTERY SELLING**: Conservative battery energy selling generates ~260 PLN/year additional revenue
- **✅ PRICE FORECASTS**: PSE price forecasts enable earlier and more accurate charging decisions (180-360 PLN/year savings)
- **✅ PROVEN**: Saves money by charging during optimal price windows and avoiding grid charging during PV overproduction

**For historical development details and technical history, see [Project History](docs/archive/PROJECT_HISTORY.md).**

## ☁️ **Multi-Tenant Cloud Hub (Vision)**

We are currently expanding the system into a **Hub-and-Spoke** architecture:
- **Central Cloud Hub**: A centralized management console to monitor multiple edge nodes (Raspberry Pi), manage configurations, and push automated code updates.
- **Smart Edge Nodes**: Local Raspberry Pi instances continue to handle real-time inverter logic, ensuring **offline resilience** and local security.
- **Unified Dashboard**: Aggregated data from all tenants visible in one place on a central VPS.

See [Cloud Architecture Plan](docs/archive/PROJECT_HISTORY.md) (Planning stage).

## 🔌 **Supported Inverters**

### Currently Supported
- **GoodWe**: ET, ES, DT families (all models) ✅
  - Full feature support: charging, discharging, data collection, operation modes
  - Tested with GoodWe ET series inverters
  - Uses [goodwe](https://pypi.org/project/goodwe/) Python library

### Coming Soon
- **Fronius**: Symo, Primo, Gen24 series 🔜
- **SMA**: Sunny Boy, Sunny Tripower series 🔜
- **Huawei**: SUN2000 series 🔜
- **Solax**: X1, X3 series 🔜

**Want to add support for your inverter?** See [Adding New Inverter Guide](docs/ADDING_NEW_INVERTER.md)

## 🏗️ **Architecture**

The system uses **Port and Adapter Pattern** (Hexagonal Architecture) to separate business logic from hardware integration:

```
Energy Algorithm → InverterPort Interface → Vendor Adapter → Inverter Hardware
```

This architecture enables:
- ✅ Support for multiple inverter brands
- ✅ Easy testing with mock adapters
- ✅ Clean separation of concerns
- ✅ Vendor-independent optimization algorithm

See [Inverter Abstraction Documentation](docs/INVERTER_ABSTRACTION.md) for details.

**For detailed implementation strategy, technical specifications, and current progress, see the [Project Plan](docs/PROJECT_PLAN_Enhanced_Energy_Management.md).**

## 📊 **Database Storage**

The system uses SQLite with automatic schema migrations for persistent storage. For complete details on the database implementation:

- **[Database Migration Plan](docs/DATABASE_MIGRATION_PLAN.md)**: Complete migration strategy and current status
- **[Database Performance Optimization](docs/DATABASE_PERFORMANCE_OPTIMIZATION.md)**: Indexes, batch operations, and performance tuning

**Key Features:**
- **Automatic Schema Migrations**: Database upgrades automatically on startup
- **Composite Indexes**: Optimized queries for common access patterns
- **Batch Operations**: Efficient bulk inserts for high-frequency data
- **Data Retention**: Configurable cleanup of old data

### 🔧 **Database Schema Migrations**

The system includes an automatic schema migration mechanism that ensures database compatibility across versions.

**How it works:**
1. On application startup, `SQLiteStorage` checks the current schema version in the `schema_version` table
2. If the database version is lower than `SCHEMA_VERSION` in `src/database/schema.py`, pending migrations are applied
3. Each migration is recorded in `schema_version` with a timestamp and description

**Adding a new migration:**

1. **Increment `SCHEMA_VERSION`** in `src/database/schema.py`:
   ```python
   SCHEMA_VERSION = 3  # Was 2, now 3
   ```

2. **Add migration entry** to `MIGRATIONS` list in `src/database/schema.py`:
   ```python
   MIGRATIONS = [
       (1, "Initial schema", []),
       (2, "Add price snapshot fields", []),
       # New migration:
       (3, "Add new_column to energy_data", [
           "ALTER TABLE energy_data ADD COLUMN new_column REAL DEFAULT 0;",
       ]),
   ]
   ```

3. **Run tests** to verify migration works:
   ```bash
   python -m pytest test/test_database_infrastructure.py::TestMigrations -v
   ```

**Key files:**
- `src/database/schema.py` - Schema definitions, version, and migrations
- `src/database/sqlite_storage.py` - Migration execution logic (`_run_migrations()`)
- `test/test_database_infrastructure.py` - Migration tests (`TestMigrations` class)

**Important notes:**
- Migrations are idempotent - running them multiple times is safe
- Always test migrations on a copy of production data before deploying
- Schema version is tracked in the `schema_version` table
- Use `IF NOT EXISTS` and `IF EXISTS` clauses for safety

## 🌟 **Latest Updates (January 2026)**

### **Raspberry Pi & VPS Integration** 🚀
- **Systemd Service Suite**: Fully integrated suite of services (`master-coordinator`, `ngrok`, `vps-tunnel`) managed via a single script.
- **Reverse SSH Tunneling**: Securely expose your local dashboard to the internet via Mikrus VPS without third-party services like Ngrok.
- **Robust Path Handling**: Services now use dynamic path detection, making them easier to install on different systems.
- **Multi-Tenant Planning**: Researching Hub-and-Spoke architecture for central management of multiple edge nodes.

> [!NOTE]
> Detailed historical updates have been moved to [HISTORY.md](HISTORY.md).

## 🏗️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GoodWe        │    │   Master        │    │   Multi-Factor  │
│   Inverter      │◄──►│   Coordinator   │◄──►│   Decision      │
│   (20 kWh)      │    │   (Central      │    │   Engine        │
│                 │    │   Orchestrator) │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PV System     │    │   Enhanced      │    │   Price-based   │
│   (5.47-6.87kW)│    │   Data          │    │   Optimization  │
│                 │    │   Collector     │    │   & Safety      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Weather APIs  │    │   Weather       │    │   Weather-      │
│   IMGW +        │◄──►│   Data          │◄──►│   Enhanced      │
│   Open-Meteo    │    │   Collector     │    │   PV Forecast   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Master Coordinator Architecture**

The system is built around a **Master Coordinator** that orchestrates all components:

- **🎯 Central Control**: Single point of control for the entire energy management system
- **🔄 Data Orchestration**: Coordinates data collection from all sources
- **🧠 Decision Engine**: Multi-factor analysis and intelligent decision making
- **🛡️ Safety Management**: GoodWe Lynx-D compliant safety monitoring
- **⚡ Action Execution**: Automated charging control and system management

**Detailed architecture and component descriptions available in the [Project Plan](docs/PROJECT_PLAN_Enhanced_Energy_Management.md).**

## 🧠 **Smart Charging Strategy**

The system now implements an **Enhanced Smart Charging Strategy** that considers multiple factors:

### **Decision Factors:**
- **🔋 Battery Level**: Critical (20%), Low (30%), Medium (50%) thresholds
- **☀️ PV Overproduction**: Avoids grid charging when PV > consumption + 500W
- **💰 Price Optimization**: Waits for 30%+ price savings opportunities
- **🏠 Consumption Patterns**: Predicts future consumption needs
- **⚡ Grid Usage**: Considers current grid import/export status
- **🌙 Night Charging**: Charges at night during low prices for high price day preparation
- **🔋 Battery Discharge**: Discharges battery during high price periods when PV insufficient
- **🔄 Multi-Session**: Multiple daily charging sessions for optimal cost savings

### **Decision Logic:**
```
🚨 CRITICAL (Always Charge): Battery < 20%
🌙 NIGHT CHARGING (High Priority): Charge at night if tomorrow has poor PV + high prices
🔄 MULTI-SESSION (High Priority): Execute multiple daily charging sessions automatically
🟢 HIGH (PV Overproduction): No grid charging when PV overproduction detected
🔴 HIGH (Low Battery + High Consumption): Charge when battery < 30% + high grid usage
⚡ BATTERY DISCHARGE (High Price): Discharge battery during high price periods
🟡 MEDIUM (Price Analysis): Wait for 30%+ price savings
🟠 LOW (Consumption Pattern): Consider charging based on expected consumption
```

### **Benefits:**
- **💡 Cost Savings**: Wait for 50-70% cheaper electricity prices
- **☀️ PV Optimization**: Use solar overproduction instead of expensive grid power
- **⏰ Smart Timing**: Charge when consumption is high or prices are low
- **🌙 Night Arbitrage**: Buy cheap electricity at night, avoid expensive daytime rates
- **⚡ Peak Shaving**: Discharge battery during high price periods for maximum savings
- **🔄 Multi-Session Optimization**: Multiple daily charging sessions for maximum cost efficiency
- **🛡️ Safety First**: Always charge when battery is critically low

## 📁 **Project Structure**

```
goodwe-dynamic-price-optimiser/
├── src/                                    # Main source code
│   ├── master_coordinator.py              # 🎯 Master Coordinator (Main Service)
│   ├── enhanced_data_collector.py         # Enhanced data collection system
│   ├── fast_charge.py                     # Core inverter control library
│   ├── tariff_pricing.py                  # Tariff-aware price calculation
│   └── automated_price_charging.py        # Core automated charging application
├── config/                                 # Configuration files
│   └── master_coordinator_config.yaml     # 🎯 Master Coordinator Configuration
├── systemd/                                # Systemd service files
│   └── goodwe-master-coordinator.service  # 🎯 Single systemd service (orchestrates everything)
├── docker-compose.yml                      # 🐳 Docker Compose configuration
├── docker-compose.simple.yml               # 🐳 Simple Docker Compose for development
├── docker-compose.prod.yml                 # 🐳 Production Docker Compose
├── Dockerfile                              # 🐳 Docker image definition
├── Dockerfile.simple                       # 🐳 Simple Dockerfile for faster builds
├── docker-entrypoint.sh                    # 🐳 Docker entrypoint script
├── .dockerignore                           # 🐳 Docker ignore file
├── scripts/                                # Management and setup scripts
│   ├── ubuntu_setup.sh                    # 🚀 Automated Ubuntu setup
│   ├── manage_services.sh                 # Service management script
│   ├── docker_manage.sh                   # 🐳 Docker management script
│   └── docker_run.sh                      # 🐳 Docker run script
├── run_demo.sh                            # 🚀 Demo script for testing
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
│   ├── GOODWE_LYNX_D_SAFETY_COMPLIANCE.md
│   └── DOCKER_DEPLOYMENT.md                # 🐳 Comprehensive Docker guide
├── requirements.txt                        # Python dependencies
└── README.md                               # This file
```

## 🐳 **Docker Deployment**

For comprehensive Docker setup, configuration, and troubleshooting, see [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md).

**Quick Docker Start:**
```bash
# Simple setup (recommended for development)
docker compose -f docker-compose.simple.yml up --build

# Or use the management script
./scripts/docker_manage.sh build
./scripts/docker_manage.sh start
```

## 🔧 **Installation & Setup**

### **Prerequisites**
- Python 3.8+
- GoodWe inverter (tested with GW10KN-ET)
- GoodWe Lynx-D battery system (2x LX-D5.0-10 = 20 kWh) - **Safety compliant**
- Network access to inverter (UDP port 8899 or TCP port 502)

### **Safety Compliance**
- ✅ **GoodWe Lynx-D Compliant**: Full safety compliance with Lynx-D specifications
- ✅ **VDE 2510-50 Standard**: Meets German battery safety standards
- ✅ **Voltage Range**: 320V - 480V (GoodWe Lynx-D specification)
- ✅ **Temperature Range**: 0°C - 53°C charging, -20°C - 53°C discharging
- ✅ **Emergency Protection**: Automatic safety stops and recovery
- 📋 **Safety Documentation**: See [GoodWe Lynx-D Safety Compliance](docs/GOODWE_LYNX_D_SAFETY_COMPLIANCE.md)

### **Quick Start**

### **Option 1: Raspberry Pi (Systemd) - RECOMMENDED**
The system is optimized to run as a persistent service on Linux/Raspberry Pi.

1. **Install services**:
   ```bash
   chmod +x scripts/manage_services.sh
   ./scripts/manage_services.sh install
   ```

2. **Configure**:
   ```bash
   nano config/master_coordinator_config.yaml
   ```

3. **Start everything**:
   ```bash
   ./scripts/manage_services.sh start
   ```

4. **Monitor logs**:
   ```bash
   ./scripts/manage_services.sh logs -f
   ```

### **Option 2: VPS SSH Tunnel (External Access)**
Expose your dashboard securely without third-party services:
1. Configure `goodwe-vps-tunnel.service` with your VPS details.
2. Link the service: `./scripts/manage_services.sh install`.
3. Start the tunnel: `./scripts/manage_services.sh start`.
4. Access via `http://your-vps-ip:30358`.

### **Option 3: Ngrok Tunnel**
Use Ngrok for quick public access:
1. Configure `ngrok.yml` with your auth token and domain.
2. Start the service: `./scripts/manage_services.sh start_service goodwe-ngrok`.

### **Option 4: Docker Setup**
For those who prefer containerization:
```bash
docker compose -f docker-compose.simple.yml up -d
```
See [Docker Deployment Guide](docs/DOCKER_DEPLOYMENT.md).

## 🎯 **Master Coordinator Features**

### **Advanced Optimization Rules**
- **🎯 Smart Critical Charging**: Emergency (5% SOC) vs Critical (10% SOC) with price awareness
- **💰 Rule 1**: At 10% SOC with high price (>0.8 PLN/kWh), always wait for price drop
- **⚡ Rule 2**: Proactive charging when PV is poor + battery <80% + price ≤0.7 PLN/kWh + weather poor
- **🔥 Rule 3**: Super low price charging (≤0.3 PLN/kWh) - always charge fully from grid regardless of PV
- **💸 Cost Savings**: Real-world tested rules save up to 70% on charging costs
- **🚫 Prevents Expensive Charging**: Avoids charging at high prices when better prices are available soon
- **📊 Proactive Management**: Charges when conditions are favorable, not just when battery is low
- **⚡ Super Low Price Strategy**: Capture super cheap grid electricity to sell PV at high prices later

### **Intelligent Decision Making**
- **📊 Multi-Factor Analysis**: Considers electricity prices, PV production, battery state, and consumption
- **⚡ PV vs Consumption Analysis**: Avoids grid charging during PV overproduction, triggers urgent charging during PV deficit
- **🎯 Smart Overproduction Detection**: Prevents unnecessary grid charging when PV > consumption + 500W
- **🚨 Deficit Response**: Automatically starts charging when PV insufficient for consumption
- **🌤️ Weather-Aware PV Forecasting**: Uses weather data to predict PV production trends and optimize charging timing
- **⏰ Smart Timing Logic**: Decides whether to wait for PV improvement or charge from grid immediately
- **📈 Trend Analysis**: Analyzes PV production trends (increasing/decreasing/stable) for optimal decision making
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

### **Enhanced Dashboard**
The system includes a comprehensive web dashboard for monitoring and analysis. See the [Enhanced Dashboard Documentation](docs/ENHANCED_DASHBOARD.md) for detailed information.

```bash
# Start the enhanced dashboard
python src/log_web_server.py --port 8080

# Access the dashboard
open http://localhost:8080
```

**Key Features:**
- **Time Series Tab**: NEW - Interactive dual-axis chart showing:
  - Battery SOC percentage over time (left Y-axis, 0-100%)
  - PV production in kW over time (right Y-axis, 0-max)
  - 24-hour historical data with 1-minute resolution
  - Real-time data updates every 30 seconds
  - Interactive tooltips and zoom capabilities
  - Data summary with SOC range and PV peak statistics
- **Decision Intelligence**: Real-time charging decision monitoring and analysis
- **Performance Metrics**: Cost savings, efficiency scoring, and system health
- **Interactive Analytics**: Charts and visualizations for data analysis
- **System Monitoring**: Real-time status, logs, and health indicators
- **Dark Mode Support**: Toggle between light and dark themes with persistent preference

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

# Test master coordinator
python src/master_coordinator.py

# Test fast charging
python src/fast_charge.py --status
```

### **CI/Test Maintenance Notes**
- **Home Assistant workflow disabled**: This repository is no longer linked to Home Assistant; `.github/workflows/hassfest.yaml` is disabled
- **Test fixtures centralized**: Database fixtures (`temp_db`, `storage_config`, `storage`) in `test/conftest.py`
- **Test status**: 533 passed, 2 skipped (verified locally)

## 🔧 **Configuration**

### **Electricity Tariff Configuration**

The system supports multiple Polish electricity tariffs with accurate distribution pricing:

#### **Available Tariffs:**
- **G11**: Single-zone (static distribution)
- **G12**: Two-zone (time-based distribution, 07:00-22:00 peak)
- **G12w**: Two-zone with wider night hours (time-based, 06:00-22:00 peak)
- **G12as**: Two-zone with volume-based pricing (time-based, 07:00-13:00 peak)
- **G14dynamic**: Dynamic tariff based on grid load (kompas-based)

#### **Price Calculation Formula:**
```
Final Price = Market Price (CSDAC) + SC Component + Distribution Price
```

- **Market Price**: Variable (from PSE CSDAC API)
- **SC Component**: Fixed at 0.0892 PLN/kWh for all tariffs
- **Distribution Price**: Variable by tariff type

#### **Configure Your Tariff:**

Edit `config/master_coordinator_config.yaml`:

```yaml
electricity_tariff:
  tariff_type: "g12"  # Options: g11, g12, g12as, g12w, g13, g14dynamic
  sc_component_pln_kwh: 0.0892
```

Tip: For simple two-zone distribution with dynamic energy price (CSDAC), choose `g12`. See detailed tariff notes in `docs/TARIFF_CONFIGURATION.md`.

#### **G14dynamic Special Requirements:**

**⚠️ G14dynamic requires PSE Peak Hours (Kompas Energetyczny) to be enabled:**

```yaml
pse_peak_hours:
  enabled: true  # REQUIRED for G14dynamic
```

Without PSE Peak Hours, the system cannot determine the dynamic distribution price and will fail to start.

#### **Distribution Prices by Tariff:**

| Tariff | Type | Distribution Price | Notes |
|--------|------|-------------------|-------|
| **G12w** | Time-based | 0.3566 PLN/kWh (peak)<br>0.0749 PLN/kWh (off-peak) | Peak: 06:00-22:00<br>Off-peak: 22:00-06:00 |
| **G14dynamic** | Kompas-based | 0.0145 PLN/kWh (green)<br>0.0578 PLN/kWh (yellow)<br>0.4339 PLN/kWh (orange)<br>2.8931 PLN/kWh (red) | Varies by grid load status |
| **G11** | Static | 0.3125 PLN/kWh | Same price 24/7 |

See [TARIFF_CONFIGURATION.md](docs/TARIFF_CONFIGURATION.md) for detailed documentation.

### **Master Coordinator Configuration**
The main configuration file is `config/master_coordinator_config.yaml`:

```yaml
# Inverter Configuration
inverter:
  ip_address: "192.168.33.15"  # Your inverter IP
  port: 8899
  family: "ET"  # Inverter family
  comm_addr: 0xf7

# Charging Configuration
charging:
  max_power: 10000  # Maximum charging power in Watts
  safety_voltage_min: 320.0  # GoodWe Lynx-D minimum voltage
  safety_voltage_max: 480.0  # GoodWe Lynx-D maximum voltage

# Hybrid Charging Configuration
hybrid_charging:
  max_charging_power: 10000    # Absolute cap for total charging power
  grid_charging_power: 10000   # Cap for grid contribution specifically

# Coordinator Settings
coordinator:
  decision_interval_minutes: 15  # How often to make decisions
  health_check_interval_minutes: 5  # Health check frequency
  emergency_stop_conditions:
    battery_temp_max: 53.0  # GoodWe Lynx-D max temperature
    battery_voltage_min: 320.0  # GoodWe Lynx-D min voltage
    battery_voltage_max: 480.0  # GoodWe Lynx-D max voltage
  
  # Enhanced Safety Settings
  safety:
    max_grid_power: 10000   # Maximum grid power usage in watts (0 to disable)
```

## 📚 **Documentation**

### **🎯 Master Coordinator**
- **[README_MASTER_COORDINATOR.md](docs/README_MASTER_COORDINATOR.md)** - Master Coordinator documentation and usage

### **📚 Knowledge Base**
- **[TARIFF_CONFIGURATION.md](docs/TARIFF_CONFIGURATION.md)** - Complete Polish tariff guide (G11, G12, G13s, G14dynamic)
- **[SMART_CRITICAL_CHARGING.md](docs/SMART_CRITICAL_CHARGING.md)** - Logic behind critical charging optimization
- **[ADDING_NEW_INVERTER.md](docs/ADDING_NEW_INVERTER.md)** - Adding support for other brands
- **[TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Developer guide for test suite

### **📜 History & Archive**
- **[HISTORY.md](HISTORY.md)** - Log of all major project updates
- **[Project History Archive](docs/archive/PROJECT_HISTORY.md)** - Detailed development logs and past plans

### **🌐 Remote Access**
- **[REMOTE_LOG_ACCESS.md](docs/REMOTE_LOG_ACCESS.md)** - Remote access guide including web dashboard, API, and ngrok public access

### **🛡️ Safety Compliance**
- **[GOODWE_LYNX_D_SAFETY_COMPLIANCE.md](docs/GOODWE_LYNX_D_SAFETY_COMPLIANCE.md)** - GoodWe Lynx-D safety compliance documentation

### **🔌 Fast Charging Control**
- **[README_fast_charge.md](docs/README_fast_charge.md)** - Basic GoodWe inverter fast charging control

### **⚡ Automated Price-Based Charging**
- **[README_automated_charging.md](docs/README_automated_charging.md)** - Intelligent charging based on electricity prices

### **🧪 Testing & Quality**

**Test Suite Status:** ![Tests](https://github.com/RMachnik/goodwe-dynamic-price-optimiser/workflows/CI/badge.svg)

- **655 Tests Passing** - 100% pass rate with 0 warnings
- **14.78s Execution Time** - 7.8% faster than baseline
- **Phase 1 & 2 Complete** - Fixed async issues, eliminated warnings, established testing standards
- **Comprehensive Documentation** - See [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for standards and patterns
- **Test Scripts** in `test/` directory for connectivity and sensor investigation

**Running Tests:**
```bash
# Run all tests
python -m pytest test/ -q

# Run with coverage
python -m pytest test/ --cov=src --cov-report=term-missing

# Run performance baseline
python scripts/test_performance.py
```

**For Contributors:**
- All tests use isolated configurations - production config changes don't break tests
- See [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for test writing standards
- Phase 3 & 4 in progress: Coverage enhancement and CI/CD integration

## 🎯 **Current Status**

### **✅ System Status - PRODUCTION READY**
- **🎯 Master Coordinator**: Central orchestration with multi-factor decision engine
- **🌙 Night Charging**: Smart night charging for high price day preparation  
- **⚡ Battery Discharge**: Intelligent discharge during high price periods
- **🔄 Multi-Session Charging**: Multiple daily charging sessions for maximum optimization
- **☀️ Weather Integration**: Real-time weather data for accurate PV forecasting
- **🛡️ Safety Compliant**: Full GoodWe Lynx-D safety monitoring
- **🧠 Enhanced Scoring**: PV vs consumption analysis for intelligent decisions
- **📊 392/393 Tests Passing**: Comprehensive test coverage with 99.7% success rate (isolated from production config)
- **🔧 Configuration System**: Fixed critical config loading bug (December 2024)
- **🛠️ Recent Fixes**: Price window analyzer timing, critical battery thresholds, test data formats
- **✅ Test Isolation**: All tests use isolated configs - change your tariff without breaking tests!

## 🚀 **Getting Started**

1. **Quick Setup**: Use the automated Ubuntu setup script
2. **Manual Setup**: Follow the manual installation steps
3. **Test**: Run the master coordinator in test mode
4. **Deploy**: Set up as a systemd service for production use

## 🤝 **Contributing**

1. **Fork** the repository
2. **Create** a feature branch
3. **Make** your changes
4. **Test** thoroughly
5. **Submit** a pull request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 **Acknowledgments**

- **GoodWe Technology** for the excellent inverter API
- **Home Assistant Community** for the custom component framework
- **Polish Electricity Market (PSE)** for reliable CSDAC-PLN price data access
- **Gadek.pl** for price validation and reference data

## 📞 **Support**

For questions, issues, or contributions, please refer to the documentation in the `docs/` directory or create an issue in the repository.

---

**🎯 The Master Coordinator is now fully operational and ready for production use!**

Ready to transform your GoodWe inverter into an intelligent energy manager? 

✅ **Start with smart price-based charging:**
```bash
python src/automated_price_charging.py --schedule-today
```

📋 **For detailed guidance:**
- **[Project Plan](docs/PROJECT_PLAN_Enhanced_Energy_Management.md)** - Complete roadmap and progress
- **[Automated Charging Guide](docs/README_automated_charging.md)** - Smart charging setup
- **[Fast Charging Guide](docs/README_fast_charge.md)** - Basic inverter control
- **[Test Configuration Isolation](docs/TEST_CONFIGURATION_ISOLATION.md)** - How tests are isolated from production config

🚀⚡🔋 **Validated, efficient, and ready to save you money!**

---

### 7-day charging effectiveness analysis

Generate a 7-day analysis of charging vs prices and potential selling opportunities. This uses the dashboard API and writes results to `out/`:

```bash
python3 scripts/analyze_last_7_days.py \
  --base-url http://192.168.33.10:8080 \
  --days 7 \
  --min-soc 0.2 \
  --sell-soc-threshold 0.5
```

Outputs:
- `out/charge_deferral_findings.csv` – candidate charge events above p25 with estimated savings
- `out/sell_opportunity_findings.csv` – p80 price windows with SOC condition
- `out/analysis_7d_summary.md` – concise summary

