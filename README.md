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

**For detailed implementation strategy, technical specifications, and current progress, see the [Project Plan](docs/PROJECT_PLAN_Enhanced_Energy_Management.md).**

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

## 🆕 **Latest Updates (October 2025)**

### **Codebase Cleanup** 🧹
- **Removed Unused Files**: Cleaned up `src/` directory by removing unused modules
- **Removed**: `battery_selling_scheduler.py` (never integrated), `battery_selling_analytics.py` (test-only), `polish_electricity_analyzer.py` (superseded by tariff_pricing.py)
- **Cleaned Database Directory**: Removed empty `src/database/` directory
- **Updated Tests**: All tests passing (20 battery selling, 19 G13s, 2 structure tests)
- **Updated Documentation**: Removed outdated references from README and test files

### **G13s Seasonal Tariff Implementation** 🎉
- **Default Tariff**: G13s now the default with full seasonal awareness
- **Polish Holiday Detection**: Automatic detection of all Polish public holidays (fixed and movable)
- **Day-Type Awareness**: Weekends and holidays use flat 0.110 PLN/kWh rate
- **Seasonal Pricing**: Different time zones for summer (Apr-Sep) and winter (Oct-Mar)
- **Optimal Rates**: Summer day off-peak as low as 0.100 PLN/kWh
- **19 New Tests**: All passing, comprehensive coverage of all scenarios
- **Zero Breaking Changes**: All existing tariffs (G11, G12, G12as, G12w, G14dynamic) still work
- **See [G13s Implementation Summary](docs/G13S_IMPLEMENTATION_SUMMARY.md) for complete details**

### **Multi-Inverter Support via Abstraction Layer** 🎉
- **Vendor-Agnostic Architecture**: Port and Adapter pattern (hexagonal architecture) enables support for multiple inverter brands
- **Currently Supported**: GoodWe (ET, ES, DT families) with full backward compatibility
- **Easy Extension**: Simple framework to add Fronius, SMA, Huawei, and other inverter brands
- **Flexible Configuration**: Specify inverter vendor in configuration file
- **Comprehensive Testing**: 22 new tests for abstraction layer, all passing ✅
- **Zero Regression**: All 473 existing tests still passing, no breaking changes
- **See [Inverter Abstraction Documentation](docs/INVERTER_ABSTRACTION.md) for architecture details**
- **See [Adding New Inverter Guide](docs/ADDING_NEW_INVERTER.md) for extending to other brands**

### **SOC Display and Blocking Reason Enhancement**
- **Prominent SOC Display**: Battery State of Charge now shown prominently for all charging decisions
- **Color-Coded SOC Badges**: Visual indicators (⚡ for executed, 🔋 for blocked) with color coding (Red <20%, Yellow 20-50%, Green >50%)
- **Detailed Blocking Reasons**: Enhanced explanation of why charging decisions were blocked (peak hours, price conditions, safety)
- **Enhanced Logging**: All decision logs now include SOC at moment of decision for better debugging
- **Kompas Peak Hours Details**: Clear indication when charging blocked due to grid reduction requirements
- **Better User Experience**: Immediate visibility into battery state and decision context
- **All Tests Passing**: 404/405 tests passing (99.75% pass rate) - All previously failing tests fixed

### **Dynamic SOC Threshold Update (November 2025)**
- **Peak Hour Flexibility**: `battery_selling.smart_timing.dynamic_soc_thresholds.require_peak_hours` is now `false`, letting premium price windows trigger selling outside `[17, 21]` when SoC thresholds are met.
- **Recharge Forecast Advisory**: `require_recharge_forecast` is also `false`, so recharge forecasts no longer block premium selling but remain part of advisory logic.
- **Config Reference**: Update lives in `config/master_coordinator_config.yaml`; no other files require changes for this behavior shift.

## 🆕 **Updates (September 2025)**

### **Logging System Optimization**
- **Eliminated Log Spam**: Implemented log deduplication to prevent repeated messages flooding systemd journal
- **Reduced Inverter Requests**: Increased cache TTL from 10s to 60s, reducing inverter communication by 83%
- **Request Throttling**: Added 5-second throttling to prevent excessive API calls from dashboard polling
- **Smart Status Logging**: Status messages only logged when values change or every 5 minutes
- **Enhanced Caching**: Endpoint-specific caching (30s) for status, metrics, and current-state endpoints
- **Improved Debugging**: Clean systemd journal logs now show actual events instead of repetitive status messages

### **PV Overproduction Threshold Optimization**
- **Enhanced Negative Price Handling**: PV overproduction threshold increased from 500W to 1500W
- **Better Market Utilization**: System now charges during negative prices (-0.25 PLN/kWh) even with moderate PV overproduction
- **Improved Decision Logic**: Prevents missing charging opportunities during excellent market conditions
- **Real-world Impact**: Better utilization of renewable energy market dynamics

## 🆕 **Previous Updates (January 2025)**

### **Enhanced Per-Phase Current Monitoring**
- **L1/L2/L3 Current Monitoring**: Real-time per-phase current readings (igrid, igrid2, igrid3)
- **High-Resolution Sampling**: 20-second intervals (180 samples/hour) for detailed phase analysis
- **Dashboard Integration**: Per-phase currents displayed in web dashboard current state panel
- **Load Balancing Detection**: Monitor phase imbalances and load distribution across L1/L2/L3
- **Enhanced Data Collection**: 4,320 data points per day (24 hours at 20-second intervals)
- **API Exposure**: L1/L2/L3 currents available via `/current-state` endpoint
- **Console Logging**: Per-phase current values printed in enhanced data collector output

### **Enhanced Critical Battery Charging**
- **More Conservative Threshold**: Critical battery level lowered from 20% to 12% SOC
- **Lower Price Limit**: Maximum critical charging price reduced from 0.6 to 0.7 PLN/kWh
- **Weather-Aware Decisions**: System now considers PV forecast even at critical battery levels
- **Smart PV Waiting**: Only waits for PV improvement if ≥2kW within 30 minutes AND price >0.4 PLN/kWh
- **Better Cost Control**: Prevents unnecessary expensive charging while maintaining safety
- **Dynamic Wait Times**: High savings (80%+) can wait up to 9 hours, considering both price and PV improvement
- **Intelligent Decision Matrix**: Considers both price savings AND weather/PV forecast for optimal decisions

## 🆕 **Recent Updates (December 2024)**

### **Advanced Optimization Rules**
- **Smart Critical Charging**: Emergency (5% SOC) vs Critical (12% SOC) with weather-aware price optimization (max 0.7 PLN/kWh)
- **Cost Optimization**: Real-world tested rules save up to 70% on charging costs
- **Proactive Charging**: Charges when conditions are favorable, not just when battery is low
- **Prevents Expensive Charging**: Avoids charging at high prices when better prices are available soon

### **Real-World Problems Solved**
- **Issue 1**: System charged at 1.577 PLN/kWh when 0.468 PLN/kWh was available 3.5 hours later
- **Solution 1**: Smart critical charging rules now prevent expensive charging decisions
- **Result 1**: Up to 70.3% cost savings on charging operations

- **Issue 2**: System waited for PV charging during super low prices (0.2 PLN/kWh), missing opportunity for full battery
- **Solution 2**: Super low price charging rule now charges fully from grid during super low prices
- **Result 2**: Up to 66.7% savings + full battery ready for PV selling at high prices

### **Enhanced Dashboard**
- **Decision Intelligence**: Real-time visibility into charging decisions and reasoning
- **Cost & Savings Tracking**: Live monitoring of energy costs and optimization savings
- **Performance Metrics**: System efficiency scores and decision analytics
- **Interactive Monitoring**: Tabbed interface with charts and real-time data
- **Parameter Visibility**: Monitor algorithm performance and decision factors
- **Smart State Handling**: Informative displays for "no data" and "waiting" scenarios
- **Historical Data Integration**: Includes older charging decisions for comprehensive metrics
- **Contextual Information**: Shows current system state and why system is waiting
- **Helpful Tooltips**: Explains what each metric means for better understanding
- **Time Series Visualization**: NEW - Dual-axis chart showing Battery SOC and PV production over time

### **New Documentation**
- [Smart Critical Charging Guide](docs/SMART_CRITICAL_CHARGING.md)
- [Enhanced Dashboard Documentation](docs/ENHANCED_DASHBOARD.md)
- [Battery Energy Selling Guide](docs/README_battery_selling.md)

### **Enhanced Aggressive Charging (REVISED - NEW)**
- **🎯 Smart Price Detection**: Compares to median/percentiles (not just cheapest price)
- **📊 Price Categories**: Super cheap (<0.20), Very cheap (0.20-0.30), Cheap (0.30-0.40)
- **📈 Percentage-Based**: Uses 10% threshold that adapts to market (not fixed 0.05 PLN)
- **⏰ Period Detection**: Detects multi-hour cheap periods (not just ±1 hour window)
- **🔮 D+1 Forecast**: Checks tomorrow's prices before charging (avoids missing better opportunities)
- **🤝 Selling Coordination**: Reserves capacity for high-price battery selling
- **✅ Verified**: Validated against [Gadek.pl API](https://www.gadek.pl/api) - [See Validation Report](docs/GADEK_VALIDATION_SUMMARY.md)
- **💰 Impact**: 62.5% cost reduction + better selling revenue
- **See**: [Enhanced Aggressive Charging Documentation](docs/ENHANCED_AGGRESSIVE_CHARGING.md)

### **PSE Price Forecasts (NEW)**
- **Early Planning**: Price forecasts available before 12:42 CSDAC publication
- **Enhanced Decisions**: Better timing with 24-hour price predictions
- **Cost Savings**: 180-360 PLN/year additional savings from improved timing
- **API Integration**: Official PSE price-fcst API for reliable forecasts
- **Smart Waiting**: Wait for better prices when forecasts show 15%+ savings
- **Fallback Safety**: Automatic fallback to CSDAC if forecasts unavailable

### **PSE Peak Hours (Kompas Energetyczny) (NEW)**
- **Grid Status Awareness**: Real-time monitoring of Polish grid load status
- **Smart Charging Decisions**: Adapts charging behavior based on grid conditions
- **WYMAGANE OGRANICZANIE**: Blocks all grid charging when grid is overloaded
- **ZALECANE OSZCZĘDZANIE**: Increases wait thresholds and limits charging power
- **ZALECANE / NORMALNE UŻYTKOWANIE**: Relaxes charging conditions when grid has capacity
- **API Integration**: Official PSE pdgsz API for reliable grid status data
- **Network Stability**: Supports Polish grid stability by avoiding charging during peak load

### Bugfixes
- Fixed division-by-zero in forecast waiting logic when `current_price` is non-positive (0 or negative). This affects:
  - `src/pse_price_forecast_collector.py::should_wait_for_better_price`
  - `src/price_window_analyzer.py::should_wait_for_better_price`
  - `src/price_window_analyzer.py::_should_wait_for_better_price`
  Guard clauses now return safe results without raising `ZeroDivisionError`.

### **Battery Energy Selling (NEW - Enhanced with Smart Timing)**
- **🎯 Smart Timing**: Avoid selling too early - wait for peak prices using forecast analysis
- **📈 Peak Detection**: Automatically identifies and waits for optimal selling times
- **📊 Trend Analysis**: Detects rising/falling price trends for better decisions
- **💰 Revenue Generation**: ~520 PLN/year additional revenue (improved with smart timing)
- **⚡ Opportunity Cost**: Calculates revenue gains from waiting vs selling immediately
- **🔒 Conservative Safety**: 80% min SOC, 50% safety margin for battery protection
- **🔄 Multi-Session**: Plans multiple selling sessions throughout the day
- **🛡️ Safety Monitoring**: Real-time safety checks and emergency stop capabilities
- **🔌 GoodWe Integration**: Uses standard `eco_discharge` mode and grid export controls
- **📊 Performance Analytics**: Comprehensive revenue tracking and efficiency metrics

### **Implementation Status**
- **Overall Progress**: ~98% complete
- **Advanced Optimization Rules**: ✅ Fully implemented and tested
- **Smart Critical Charging**: ✅ Emergency (5% SOC) vs Critical (10% SOC) with price awareness
- **Battery Energy Selling**: ✅ Fully implemented with smart timing to avoid selling too early
- **Proactive Charging**: ✅ PV poor + battery <80% + low price + weather poor = charge
- **Cost Optimization**: ✅ Real-world tested rules save up to 70% on charging costs
- **Test Coverage**: ✅ 227/234 tests passing (97.0% pass rate)
- **Configuration System**: ✅ Fixed critical config loading bug
- **Recent Fixes**: ✅ Price window analyzer, critical battery thresholds, test data formats
- **Latest Updates**: ✅ Critical battery threshold lowered to 12% SOC, max price reduced to 0.7 PLN/kWh, weather-aware critical charging

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

#### **Option 1: Docker Setup (Recommended)**
```bash
# Clone the repository
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
cd goodwe-dynamic-price-optimiser

# Simple Docker setup (recommended for development)
docker compose -f docker-compose.simple.yml up --build

# Or use the management script
./scripts/docker_manage.sh build
./scripts/docker_manage.sh start

# Check status
./scripts/docker_manage.sh status

# View logs
./scripts/docker_manage.sh logs
```

#### **Option 2: Automated Ubuntu Docker Setup**
```bash
# Clone and run automated Docker setup
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
cd goodwe-dynamic-price-optimiser
chmod +x scripts/ubuntu_docker_setup.sh
./scripts/ubuntu_docker_setup.sh
```

#### **Option 3: Manual Ubuntu Setup (Systemd Services)**
```bash
# Clone and run automated setup
git clone https://github.com/rafalmachnik/goodwe-dynamic-price-optimiser.git
cd goodwe-dynamic-price-optimiser
chmod +x scripts/ubuntu_setup.sh
./scripts/ubuntu_setup.sh
```

#### **Option 4: Manual Setup**
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

4. **Configure PSE Price Forecasts (Optional)**
   ```yaml
   # PSE Price Forecast Configuration
   pse_price_forecast:
     enabled: true                              # Enable price forecasts
     api_url: "https://api.raporty.pse.pl/api/price-fcst"
     update_interval_minutes: 60                # Update every 60 minutes
     forecast_hours_ahead: 24                   # Forecast 24 hours ahead
     confidence_threshold: 0.7                  # Minimum confidence to use forecasts
     
     # Forecast-based decision rules
     decision_rules:
       wait_for_better_price_enabled: true      # Wait if forecast shows better prices
       min_savings_to_wait_percent: 15          # Wait if forecast shows 15%+ savings
       max_wait_time_hours: 4                   # Maximum time to wait for better price
       prefer_forecast_over_current: true       # Prefer forecast when available
       
     # Fallback configuration
     fallback:
       use_csdac_if_unavailable: true          # Use CSDAC if forecast unavailable
       retry_attempts: 3                        # Retry attempts for API calls
       retry_delay_seconds: 60                  # Delay between retries
   ```

5. **Configure PSE Peak Hours (Kompas Energetyczny) (Optional)**
   ```yaml
   # PSE Peak Hours Configuration (Kompas Energetyczny)
   pse_peak_hours:
     enabled: true                              # Enable Peak Hours monitoring
     api_url: "https://api.raporty.pse.pl/api/pdgsz"
     update_interval_minutes: 60                # Update every 60 minutes
     peak_hours_ahead: 24                     # Monitor 24 hours ahead
     
    # Decision rules based on Peak Hours status
    decision_rules:
      # WYMAGANE OGRANICZANIE (usage_fcst = 3)
      required_reduction:
        block_charging: true                 # Block all grid charging
        prefer_discharge_for_home: true      # Prefer battery discharge for home use
        ignore_price_opportunities: true     # Ignore low price opportunities
        
      # ZALECANE OSZCZĘDZANIE (usage_fcst = 2)
      recommended_saving:
        increase_wait_threshold_percent: 10  # Increase min_savings_to_wait_percent by 10%
        limit_charging_power_percent: 50    # Limit charging power to 50%
        
      # NORMALNE UŻYTKOWANIE (usage_fcst = 1)
      recommended_usage:
        decrease_wait_threshold_percent: 5   # Decrease min_savings_to_wait_percent by 5%
        
      # ZALECANE UŻYTKOWANIE (usage_fcst = 0)
      normal_usage:
        default_logic: true                  # Use default charging logic
         
     # Fallback configuration
     fallback:
       use_default_if_unavailable: true       # Use default logic if Peak Hours data unavailable
       retry_attempts: 3                      # Retry attempts for API calls
       retry_delay_seconds: 60                # Delay between retries
   ```

6. **Test the Master Coordinator**
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

### **📋 Project Planning**
- **[PROJECT_PLAN_Enhanced_Energy_Management.md](docs/PROJECT_PLAN_Enhanced_Energy_Management.md)** - Comprehensive project plan with tasks, timelines, and progress tracking

### **🎯 Master Coordinator**
- **[README_MASTER_COORDINATOR.md](docs/README_MASTER_COORDINATOR.md)** - Master Coordinator documentation and usage

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

