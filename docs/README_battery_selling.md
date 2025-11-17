# Battery Energy Selling - Documentation

## Overview

The Battery Energy Selling functionality enables your GoodWe inverter to sell excess battery energy back to the grid during high-price periods, generating additional revenue while maintaining conservative safety parameters.

## Key Features

### 🔋 **Conservative Safety Parameters**
- **Minimum SOC**: 80% (only sell when battery is well-charged)
- **Safety Margin**: 50% (never discharge below 50% SOC)
- **Revenue Potential**: ~520 PLN/year (conservative estimate with smart timing)
- **Battery Protection**: Excellent protection against degradation

### ⚡ **Smart Selling Logic**
- **Price-Aware**: Only sells when electricity prices are above threshold
- **PV-Aware**: Avoids selling when PV production is sufficient
- **Peak Hours**: Optimizes for high-price periods (5-9 PM)
- **Night Preservation**: Never sells during night hours (10 PM - 6 AM)

### 🎯 **Smart Timing (ENHANCED - Phase 1)**
- **Extended Forecast Analysis**: Analyzes upcoming **12 hours** for better prices (upgraded from 6h)
- **Peak Detection**: Identifies peak prices and waits to sell at optimal times
- **Enhanced Percentile Thresholds**: 
  - Top 5% prices: Aggressive immediate selling
  - Top 15% prices: Standard selling if no better peak within 2h
  - Top 25% prices: Conditional selling with opportunity cost check
- **Improved Opportunity Cost**:
  - 30%+ gain: Definitely wait (high confidence)
  - 15-30% gain: Wait if low risk and <3h to peak
  - 10-15% gain: Consider waiting if <1h away
  - <10% gain: Sell now
- **Trend Analysis**: Detects rising/falling price trends for better decisions
- **Multi-Session Support**: Plans multiple selling sessions throughout the day
- **Confidence-Based**: Adjusts decisions based on forecast reliability

### 🛡️ **Comprehensive Safety Monitoring**
- **Real-time Safety Checks**: Battery temperature, SOC, grid voltage
- **Emergency Stop**: Automatic stop on critical conditions
- **GoodWe Integration**: Uses standard inverter features
- **Health Tracking**: Monitors battery degradation

## Configuration

### Master Configuration

Add to `config/master_coordinator_config.yaml`:

```yaml
# Battery Energy Selling Configuration (Conservative Safety Parameters)
battery_selling:
  enabled: true                    # Enable battery energy selling functionality
  min_selling_price_pln: 0.50     # Minimum price to start selling (PLN/kWh)
  min_battery_soc: 80              # Minimum SOC to start selling (%)
  safety_margin_soc: 50            # Safety margin SOC - never discharge below this (%)
  max_daily_cycles: 2              # Maximum discharge cycles per day
  peak_hours: [17, 18, 19, 20, 21] # High price selling hours (5-9 PM)
  operation_mode: "eco_discharge"   # GoodWe operation mode for selling
  grid_export_limit_w: 5000        # Max export power (5kW)
  battery_dod_limit: 50            # Max discharge depth (50% = 50% SOC min)
  
  # Smart Timing Configuration (Avoid Selling Too Early)
  smart_timing:
    enabled: true                          # Enable smart timing logic
    forecast_lookahead_hours: 6            # Look ahead 6 hours for better prices
    near_peak_threshold_percent: 95        # Sell if within 95% of forecasted peak
    min_peak_difference_percent: 15        # Wait only if peak is 15%+ higher
    max_wait_time_hours: 4                 # Maximum 4 hours to wait for better price
    min_forecast_confidence: 0.6           # Minimum forecast confidence to trust
    
    # Opportunity cost thresholds
    opportunity_cost:
      significant_savings_percent: 20      # 20%+ revenue gain = significant (definitely wait)
      marginal_savings_percent: 5          # 5%+ revenue gain = marginal (consider waiting)
      
    # Trend analysis configuration
    trend_analysis:
      enabled: true                        # Enable price trend analysis
      trend_window_hours: 2                # Analyze 2-hour price trends
      rising_threshold: 0.02               # 2% increase = rising trend
      falling_threshold: -0.02             # 2% decrease = falling trend
      
    # Multi-session selling configuration
    multi_session:
      enabled: true                        # Enable multiple selling sessions per day
      max_sessions_per_day: 3              # Maximum 3 selling sessions
      min_session_gap_hours: 1             # Minimum 1 hour between sessions
      reserve_battery_percent: 20          # Reserve 20% battery for house usage
  
  # Revenue estimation (conservative)
  expected_daily_revenue_pln: 1.43  # ~1.43 PLN/day (5.7 kWh × 0.25 PLN/kWh)
  expected_monthly_revenue_pln: 21  # ~21 PLN/month
  expected_annual_revenue_pln: 260  # ~260 PLN/year
  
  # Safety parameters (GoodWe Lynx-D compliant)
  safety_checks:
    battery_temp_max: 50.0          # Max battery temperature (°C)
    battery_temp_min: -20.0         # Min battery temperature (°C)
    grid_voltage_min: 200.0         # Min grid voltage (V)
    grid_voltage_max: 250.0         # Max grid voltage (V)
    night_hours: [22, 23, 0, 1, 2, 3, 4, 5]  # Preserve night charge (10 PM - 6 AM)
  
  # Performance monitoring
  monitoring:
    track_revenue: true             # Track actual revenue vs estimates
    track_battery_health: true      # Monitor battery degradation
    track_cycles: true              # Track discharge cycles
    alert_on_anomalies: true        # Alert on unusual patterns
```

## How It Works

### 1. **Decision Process**

The system continuously monitors:
- **Battery SOC**: Must be ≥80% to start selling
- **Electricity Price**: Must be ≥0.50 PLN/kWh
- **PV Production**: Only sells when PV insufficient for consumption
- **Safety Conditions**: Temperature, voltage, error codes
- **Price Forecast**: Analyzes next 6 hours for better selling opportunities
- **Price Trends**: Detects if prices are rising, falling, or stable

### 2. **Selling Logic**

```python
def should_start_selling(battery_soc, current_price, pv_power, consumption):
    return (
        battery_soc >= 80 and                    # Min SOC requirement
        current_price >= 0.50 and                # Min selling price
        battery_soc > 50 and                     # Safety margin
        pv_power < consumption and               # PV insufficient
        not is_night_time()                      # Not during night
    )
```

### 3. **Smart Timing Process**

The smart timing engine performs these steps:

1. **Fetch Price Forecast**: Get next 6 hours of price forecasts from PSE
2. **Analyze Price Context**: Calculate percentiles, identify high/low prices
3. **Detect Peak**: Find peak price within forecast window
4. **Analyze Trend**: Determine if price is rising, falling, or stable
5. **Calculate Opportunity Cost**: Compare revenue now vs. waiting for peak
6. **Make Decision**:
   - **SELL NOW** if at/near peak (top 10% prices)
   - **SELL NOW** if falling trend and no better peak ahead
   - **WAIT** if significant peak ahead (20%+ higher revenue)
   - **WAIT** if moderate peak ahead and good forecast confidence
   - **NO OPPORTUNITY** if price too low overall

### 4. **GoodWe Integration**

Uses standard GoodWe inverter features:
- **Operation Mode**: `eco_discharge` for battery selling
- **Grid Export**: Controlled via `set_grid_export_limit()`
- **Battery DOD**: Limited via `set_ongrid_battery_dod()`

## Revenue Analysis

### **Conservative Estimates**

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Battery Capacity** | 20 kWh | 2x GoodWe Lynx-D 10kWh |
| **Usable Energy** | 6.0 kWh | 80% - 50% = 30% usable |
| **Net Sellable** | 5.7 kWh | 6.0 kWh × 95% efficiency |
| **Daily Cycles** | 1-2 | Conservative with 50% safety margin |
| **Price Spread** | 0.20-0.30 PLN/kWh | Average price difference |
| **Daily Revenue** | ~1.43 PLN | 5.7 kWh × 0.25 PLN/kWh |
| **Monthly Revenue** | ~43 PLN | 1.43 PLN × 30 days |
| **Annual Revenue** | ~520 PLN | Conservative estimate |

### **Risk Assessment**

**✅ Conservative Approach Benefits:**
- **High Safety Margin**: 50% SOC safety margin prevents deep discharge
- **High Min SOC**: 80% minimum ensures battery longevity
- **Battery Protection**: Significantly reduces wear and degradation
- **GoodWe Compliance**: Uses standard inverter features

**⚠️ Trade-offs:**
- **Reduced Revenue**: Lower than original estimate but much safer
- **Limited Cycles**: Conservative approach reduces daily cycles
- **Higher SOC Threshold**: Requires more battery charge to start selling

## Safety Features

### **Real-time Monitoring**

The system continuously monitors:

1. **Battery Temperature**: 0°C to 50°C (GoodWe Lynx-D spec)
2. **Battery SOC**: Never below 50% safety margin
3. **Grid Voltage**: 200V to 250V safe range
4. **Inverter Errors**: Automatic stop on error codes
5. **Night Hours**: Preserves battery charge 10 PM - 6 AM

### **Emergency Stop Conditions**

Automatic emergency stop triggers on:
- Battery temperature >50°C or <-20°C
- Battery SOC ≤50% (safety margin)
- Grid voltage outside 200-250V range
- Inverter error codes detected
- Any critical safety condition

### **Safety Recommendations**

1. **Monitor Battery Health**: Regular health checks and degradation tracking
2. **Temperature Management**: Ensure proper battery cooling
3. **Grid Connection**: Maintain stable grid connection
4. **Regular Maintenance**: Follow GoodWe maintenance schedule

## Performance Analytics

### **Revenue Tracking**

The system tracks:
- **Session Records**: Individual selling sessions with revenue
- **Daily Summaries**: Daily revenue and performance metrics
- **Monthly Reports**: Monthly financial performance
- **Efficiency Metrics**: Actual vs. theoretical performance

### **Key Metrics**

- **Total Revenue**: Cumulative revenue from selling
- **Energy Sold**: Total energy sold back to grid
- **Efficiency**: Actual performance vs. theoretical maximum
- **Safety Rate**: Percentage of sessions without safety incidents
- **ROI**: Return on investment vs. expected revenue

### **Analytics Dashboard**

Access analytics via:
- **Web Interface**: Real-time performance metrics
- **API Endpoints**: Programmatic access to data
- **Export Functions**: JSON export for external analysis

## Usage Examples

### **Basic Usage**

```python
from battery_selling_engine import BatterySellingEngine
from battery_selling_monitor import BatterySellingMonitor

# Initialize components
engine = BatterySellingEngine(config)
monitor = BatterySellingMonitor(config)

# Analyze selling opportunity (with smart timing)
opportunity = await engine.analyze_selling_opportunity(current_data, price_data)

# Check timing recommendation
if opportunity.timing_recommendation:
    print(f"Decision: {opportunity.timing_recommendation.decision}")
    print(f"Reasoning: {opportunity.timing_recommendation.reasoning}")
    print(f"Opportunity cost: {opportunity.opportunity_cost_pln:.2f} PLN")
    if opportunity.should_wait_for_peak:
        print(f"Peak expected at: {opportunity.optimal_sell_time}")
        print(f"Peak price: {opportunity.peak_price:.3f} PLN/kWh")

# Check safety conditions
safety_report = await monitor.check_safety_conditions(inverter, current_data)

# Start selling session (if safe and profitable)
if opportunity.decision == "start_selling" and safety_report.overall_status == "safe":
    success = await engine.start_selling_session(inverter, opportunity)
```

### **Smart Timing Example Scenarios**

#### Scenario 1: Wait for Evening Peak
```
Time: 14:00
Current Price: 0.60 PLN/kWh (decent)
Forecast: Peak at 19:00 with 0.95 PLN/kWh

Decision: WAIT
Reasoning: Peak expected in 5h at 0.95 PLN/kWh (+58%, opportunity cost: 2.00 PLN)
Action: System will wait and sell at 19:00
Result: +2.00 PLN revenue gain vs selling immediately
```

#### Scenario 2: Already at Peak
```
Time: 19:00
Current Price: 0.95 PLN/kWh (peak)
Forecast: Prices dropping to 0.70 PLN/kWh

Decision: SELL NOW
Reasoning: Current price 0.95 PLN/kWh is at peak (top 10%, 100th percentile)
Action: Sell immediately
Result: Maximize revenue by selling at peak
```

#### Scenario 3: Falling Trend - Sell Now
```
Time: 20:00
Current Price: 0.80 PLN/kWh
Forecast: Prices falling to 0.60 PLN/kWh

Decision: SELL NOW
Reasoning: Price is falling and no significant peak ahead - sell now
Action: Sell immediately before price drops
Result: Avoid revenue loss from price decline
```

#### Scenario 4: Price Too Low - Wait
```
Time: 12:00
Current Price: 0.35 PLN/kWh (low)
Forecast: Only rises to 0.40 PLN/kWh

Decision: NO OPPORTUNITY
Reasoning: Current price 0.35 PLN/kWh below high threshold (only 20th percentile)
Action: Don't sell, keep battery for house usage
Result: Preserve battery for when it's actually needed
```

### **Revenue Analysis**

```python
from battery_selling_analytics import BatterySellingAnalytics

# Initialize analytics
analytics = BatterySellingAnalytics(config)

# Get revenue summary
summary = analytics.get_revenue_summary(days=30)
print(f"30-day revenue: {summary['total_revenue_pln']} PLN")
print(f"Average daily: {summary['average_daily_revenue_pln']} PLN")

# Get performance metrics
metrics = analytics.get_performance_metrics()
print(f"Safety rate: {metrics['safety']['safety_rate_percent']}%")
print(f"Efficiency: {metrics['efficiency']['actual_efficiency_percent']}%")
```

## Testing

### **Run Tests**

```bash
# Run all battery selling tests
python -m pytest test/test_battery_selling.py -v

# Run specific test categories
python -m pytest test/test_battery_selling.py::TestBatterySellingEngine -v
python -m pytest test/test_battery_selling.py::TestBatterySellingMonitor -v
python -m pytest test/test_battery_selling.py::TestBatterySellingAnalytics -v
```

### **Test Coverage**

The test suite covers:
- **Decision Engine**: All selling logic and safety checks
- **Safety Monitor**: Comprehensive safety condition testing
- **Analytics**: Revenue tracking and performance metrics
- **Integration**: Complete workflow testing
- **Configuration**: Parameter validation and defaults

## Troubleshooting

### **Common Issues**

1. **Selling Not Starting**
   - Check battery SOC (must be ≥80%)
   - Verify electricity price (must be ≥0.50 PLN/kWh)
   - Ensure PV insufficient for consumption
   - Check safety conditions

2. **Emergency Stops**
   - Monitor battery temperature
   - Check grid voltage stability
   - Verify inverter error codes
   - Ensure proper configuration

3. **Low Revenue**
   - Check price thresholds
   - Verify selling hours configuration
   - Monitor battery SOC levels
   - Review safety parameters

### **Debug Mode**

Enable debug logging:

```yaml
logging:
  level: "DEBUG"
  verbose_logging: true
```

### **Manual Selling Script**

For manual control of battery selling, use the `sell_battery_now.py` script:

```bash
# Start selling until battery reaches 45% SOC (with automatic monitoring)
python src/sell_battery_now.py --start --target-soc 45 --monitor

# Start selling with custom power limit
python src/sell_battery_now.py --start --target-soc 30 --power 3000 --monitor

# Start selling without monitoring (manual stop required)
python src/sell_battery_now.py --start --target-soc 45

# Stop current selling session
python src/sell_battery_now.py --stop

# Check selling status
python src/sell_battery_now.py --status
```

**Key Features:**
- **Manual Override**: Bypass automatic battery selling logic for direct control
- **Configurable Target SOC**: Set any target SOC between 10% and 95%
- **Power Control**: Adjust selling power from 100W to 15000W
- **Safety Checks**: Enforces critical safety conditions (temperature, voltage)
- **Real-time Monitoring**: Automatic monitoring and stop at target SOC (with `--monitor` flag)
- **Status Reporting**: Detailed status including SOC, power, duration, and energy sold

**Safety Notes:**
- Absolute minimum SOC is 10% (cannot sell below this)
- Safety checks still enforced (temperature, voltage, battery health)
- Automatically stops on critical safety conditions
- Gracefully restores inverter to normal operation mode

### **Manual Override (Programmatic)**

For testing or emergency situations using Python API:

```python
# Force start selling (bypass safety checks)
await engine.start_selling_session(inverter, opportunity, force=True)

# Emergency stop all selling
await monitor.emergency_stop(inverter)
```

## Best Practices

### **Configuration**

1. **Start Conservative**: Begin with default safety parameters
2. **Monitor Performance**: Track revenue and battery health
3. **Adjust Gradually**: Fine-tune parameters based on results
4. **Regular Review**: Monthly performance analysis

### **Maintenance**

1. **Battery Health**: Regular SOC and temperature monitoring
2. **Grid Connection**: Stable voltage and frequency
3. **Inverter Status**: Error code monitoring
4. **Data Backup**: Regular analytics data export

### **Safety**

1. **Never Override**: Don't bypass safety checks
2. **Monitor Closely**: Watch for unusual patterns
3. **Regular Updates**: Keep system updated
4. **Professional Support**: Contact support for issues

## Support

For technical support or questions:
- **Documentation**: Check this README and project documentation
- **Logs**: Review system logs for error details
- **Tests**: Run test suite to verify functionality
- **Configuration**: Validate configuration parameters

## Conclusion

The Battery Energy Selling functionality provides a safe, conservative way to generate additional revenue from your GoodWe inverter while protecting battery health. With comprehensive safety monitoring and performance analytics, you can optimize your energy management system for maximum benefit.

**Key Benefits:**
- ✅ **Safe**: Conservative parameters protect battery health
- ✅ **Profitable**: ~260 PLN/year additional revenue
- ✅ **Smart**: Price and PV-aware selling decisions
- ✅ **Monitored**: Comprehensive safety and performance tracking
- ✅ **Integrated**: Seamless integration with existing system
