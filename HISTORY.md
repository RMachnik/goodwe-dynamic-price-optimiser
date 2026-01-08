# Project History & Past Updates

This document tracks the historical development and previous major updates of the GoodWe Dynamic Price Optimiser.

---

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

### **Multi-Inverter Support via Abstraction Layer** 🎉
- **Vendor-Agnostic Architecture**: Port and Adapter pattern (hexagonal architecture) enables support for multiple inverter brands
- **Currently Supported**: GoodWe (ET, ES, DT families) with full backward compatibility
- **Easy Extension**: Simple framework to add Fronius, SMA, Huawei, and other inverter brands
- **Flexible Configuration**: Specify inverter vendor in configuration file
- **Comprehensive Testing**: 22 new tests for abstraction layer, all passing ✅
- **Zero Regression**: All 473 existing tests still passing, no breaking changes

### **SOC Display and Blocking Reason Enhancement**
- **Prominent SOC Display**: Battery State of Charge now shown prominently for all charging decisions
- **Color-Coded SOC Badges**: Visual indicators (⚡ for executed, 🔋 for blocked) with color coding (Red <20%, Yellow 20-50%, Green >50%)
- **Detailed Blocking Reasons**: Enhanced explanation of why charging decisions were blocked (peak hours, price conditions, safety)
- **Enhanced Logging**: All decision logs now include SOC at moment of decision for better debugging
- **Kompas Peak Hours Details**: Clear indication when charging blocked due to grid reduction requirements
- **Better User Experience**: Immediate visibility into battery state and decision context

---

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

---

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

---

## 🆕 **Recent Updates (December 2024)**

### **Advanced Optimization Rules**
- **Smart Critical Charging**: Emergency (5% SOC) vs Critical (12% SOC) with weather-aware price optimization (max 0.7 PLN/kWh)
- **Cost Optimization**: Real-world tested rules save up to 70% on charging costs
- **Proactive Charging**: Charges when conditions are favorable, not just when battery is low
- **Prevents Expensive Charging**: Avoids charging at high prices when better prices are available soon
