# Enhanced Aggressive Charging System

## Overview

The Enhanced Aggressive Charging System replaces the old fixed-threshold logic with intelligent, adaptive price analysis that:

✅ **Compares to median/percentiles** (not just cheapest)  
✅ **Uses percentage-based thresholds** (adapts to market)  
✅ **Detects continuous cheap periods** (not just ±1 hour)  
✅ **Checks tomorrow's forecast** (PSE D+1 integration)  
✅ **Implements price categories** (super_cheap, very_cheap, cheap, moderate, expensive)  
✅ **Coordinates with battery selling** (reserves capacity for selling opportunities)  

## Problem Solved

### Old Logic Issues:
- ❌ Fixed 0.05 PLN/kWh threshold → doesn't adapt to market
- ❌ Only ±1 hour window → misses extended cheap periods
- ❌ Doesn't check tomorrow → misses better opportunities
- ❌ No median/percentile comparison → charges at "expensive" prices
- ❌ Conflicts with battery selling → charges to 85% (can't sell at 80%+)

### Example from Gadek.pl API:
```
Current: 0.8 PLN/kWh (expensive!)
Median: 0.74 PLN/kWh
Cheapest: 10:00-16:00 tomorrow

Old logic: Would charge (0.8 within 0.05 of something)
New logic: DON'T CHARGE (0.8 > median, above 75th percentile, tomorrow cheaper)
```

## How It Works

### 1. Price Analysis
```python
PriceAnalysis:
  - current_price: 0.80 PLN/kWh
  - median_price: 0.74 PLN/kWh
  - percentile_25th: 0.30 PLN/kWh
  - percentile_75th: 0.85 PLN/kWh
  - current_percentile: 65th  # Current price rank
  - category: EXPENSIVE
  - is_historically_cheap: False  # Not in bottom 25%
  - is_below_median: False
```

### 2. Price Categories
```yaml
SUPER_CHEAP: < 0.20 PLN/kWh → Charge to 100%
VERY_CHEAP: 0.20-0.30 → Charge to 90%
CHEAP: 0.30-0.40 → Charge to 80%
MODERATE: 0.40-0.60 → Normal logic
EXPENSIVE: 0.60-0.80 → Don't charge
VERY_EXPENSIVE: > 0.80 → Don't charge
```

### 3. Decision Rules

**Rule 1: Historical Percentile Check**
- Only charge if price in bottom 25% of historical prices
- Example: Median=0.74, 25th percentile=0.30, Current=0.80 → DON'T CHARGE

**Rule 2: Continuous Period Detection**
- Detects multi-hour cheap periods (not just ±1 hour)
- Example: 10:00-16:00 all below 0.35 → entire 6-hour window

**Rule 3: Tomorrow's Forecast Check**
- If tomorrow has 30%+ cheaper prices → WAIT
- Example: Today=0.40, Tomorrow=0.25 (37% cheaper) → WAIT

**Rule 4: Price Category Based Charging**
- SUPER_CHEAP (< 0.20) → Always charge to 100%
- VERY_CHEAP (0.20-0.30) + below median → Charge to 90%
- CHEAP (0.30-0.40) + historically cheap + near cheapest → Charge to 80%

**Rule 5: Battery Selling Coordination**
- If selling enabled, target 80%+ SOC during cheap prices
- Reserve capacity for high-price selling later
- Don't charge to 85% if high prices coming (want room to sell)

## Configuration

```yaml
coordinator:
  cheapest_price_aggressive_charging:
    enabled: true
    
    # Percentage-based threshold (adapts to market)
    price_threshold_percent: 10      # Within 10% of cheapest
    
    # Price categories (PLN/kWh)
    super_cheap_threshold: 0.20
    very_cheap_threshold: 0.30
    cheap_threshold: 0.40
    moderate_threshold: 0.60
    expensive_threshold: 0.80
    
    # Target SOC by category
    super_cheap_target_soc: 100
    very_cheap_target_soc: 90
    cheap_target_soc: 80
    
    # Battery selling coordination
    coordinate_with_selling: true
    min_selling_reserve_percent: 5
    
    # Historical price analysis
    use_percentile_analysis: true
    percentile_threshold: 25         # Bottom 25%
    
    # Forecast integration
    use_d1_forecast: true
    min_tomorrow_price_diff_percent: 30  # Wait if 30%+ cheaper
    
    # SOC ranges
    min_battery_soc_for_aggressive: 30
    max_battery_soc_for_aggressive: 85
```

## Examples

### Example 1: Current Price Too High
```
Gadek.pl API Data:
- Current: 0.80 PLN/kWh
- Median: 0.74 PLN/kWh
- Cheapest: 10:00-16:00 tomorrow

Decision: DON'T CHARGE
Reason: Price 0.80 PLN/kWh not historically cheap (65th percentile, need <25%)
```

### Example 2: Super Cheap Period
```
Time: 02:00
Price: 0.15 PLN/kWh
Median: 0.45 PLN/kWh
Category: SUPER_CHEAP

Decision: CHARGE TO 100%
Reason: SUPER CHEAP price 0.15 PLN/kWh (< 0.20)
```

### Example 3: Tomorrow Much Cheaper
```
Time: 20:00
Current: 0.35 PLN/kWh (cheap)
Tomorrow minimum: 0.20 PLN/kWh (43% cheaper)

Decision: WAIT
Reason: Tomorrow has much cheaper prices (0.20 vs 0.35, 43% savings)
```

### Example 4: Continuous Cheap Period
```
Detected period: 10:00-16:00
Average price: 0.28 PLN/kWh
Category: VERY_CHEAP
Current time: 11:00

Decision: CHARGE TO 90%
Reason: In cheap period (10:00-16:00), VERY CHEAP average 0.28 PLN/kWh
```

### Example 5: Battery Selling Coordination
```
Price: 0.35 PLN/kWh (cheap)
Battery SOC: 50%
Forecast: High prices (0.95 PLN/kWh) at 19:00
Battery selling enabled: Yes

Decision: CHARGE TO 80%
Reason: CHEAP price + high prices coming → prepare for selling
Target: 80% (min_selling_soc for selling opportunities)
```

## Integration

### Automated Price Charging
```python
from enhanced_aggressive_charging import EnhancedAggressiveCharging

# Initialize
enhanced = EnhancedAggressiveCharging(config)

# Make decision
decision = enhanced.should_charge_aggressively(
    battery_soc=50,
    price_data=price_data,  # From PSE API
    forecast_data=forecast_data,  # From PSE D+1 forecast
    current_data=current_data  # System state
)

if decision.should_charge:
    print(f"Charge to {decision.target_soc}%")
    print(f"Reason: {decision.reason}")
    print(f"Category: {decision.price_category.value}")
```

### Price Analysis
```python
# Analyze prices
analysis = enhanced.analyze_prices(price_data, forecast_data)

print(f"Current: {analysis.current_price:.3f} PLN/kWh")
print(f"Median: {analysis.median_price:.3f} PLN/kWh")
print(f"Percentile: {analysis.current_percentile:.1f}%")
print(f"Category: {analysis.category.value}")
print(f"Historically cheap: {analysis.is_historically_cheap}")
```

### Period Detection
```python
# Detect charging periods
periods = enhanced.detect_charging_periods(price_data)

for period in periods:
    print(f"{period.start_hour:02d}:00-{period.end_hour:02d}:00")
    print(f"  Avg: {period.avg_price:.3f} PLN/kWh")
    print(f"  Category: {period.category.value}")
```

## Benefits

### Revenue Impact:
- **Avoid expensive charging**: Don't charge at 0.80 PLN/kWh when 0.30 available
- **Coordinate with selling**: Charge to 80%+ during cheap prices for selling at high prices
- **Optimize timing**: Wait for truly cheap periods (bottom 25%)

**Example Savings:**
```
Old logic: Charge 10kWh at 0.80 PLN/kWh = 8.00 PLN
New logic: Wait for 0.30 PLN/kWh = 3.00 PLN
Savings: 5.00 PLN per session (62.5% cost reduction)

Monthly (4 sessions): 20 PLN saved
Annual: 240 PLN saved
```

### Coordination Benefits:
```
Scenario: Cheap prices now (0.35), high prices later (0.95)

Old logic:
- Charge to 85% at 0.35 PLN/kWh
- Can only sell 5% (85% → 80%) = 1kWh
- Selling revenue: 1kWh × 0.95 = 0.95 PLN

New logic:
- Charge to 80% at 0.35 PLN/kWh
- Can sell 30% (80% → 50%) = 6kWh
- Selling revenue: 6kWh × 0.95 = 5.70 PLN
- Additional revenue: +4.75 PLN (500% increase!)
```

## Fallback Behavior

If enhanced logic fails or forecast unavailable:
- Falls back to legacy aggressive charging logic
- Uses basic ±1 hour and 0.05 PLN/kWh thresholds
- Ensures system continues to function
- Logs errors for debugging

## Monitoring

### Logs
```
INFO: Enhanced Aggressive Charging initialized (enabled: True)
INFO: Price threshold: 10% of cheapest
DEBUG: Price analysis: current=0.80, median=0.74, percentile=65%, category=expensive
DEBUG: Detected 2 charging periods
DEBUG:   Period: 10:00-16:00, avg=0.28, category=very_cheap
DEBUG:   Period: 01:00-04:00, avg=0.22, category=very_cheap
INFO: Decision: DON'T CHARGE - Price not historically cheap (65th percentile, need <25%)
```

### Decision Output
```python
ChargingDecision:
  should_charge: True
  reason: "VERY CHEAP price 0.28 PLN/kWh (< 0.30, below median 0.45) - charge to 90%"
  priority: "high"
  confidence: 0.85
  target_soc: 90
  estimated_duration_hours: 2.5
  price_category: VERY_CHEAP
  opportunity_cost: 0.0
```

## Testing

See `test/test_enhanced_aggressive_charging.py` for comprehensive tests covering:
- Price analysis and percentile calculation
- Price category classification
- Period detection
- Forecast integration
- Battery selling coordination
- Edge cases and error handling

## Validation

The Enhanced Aggressive Charging system has been **validated against real-world data**:

### Gadek.pl API Validation
✅ **Validated**: System behavior matches [Gadek.pl API](https://www.gadek.pl/api) recommendations  
📊 **Test Case**: g14d tariff (day tariff) with real market prices  
🎯 **Result**: System correctly refuses to charge at median prices (50th percentile)  
✓ **Accuracy**: Price calculations within 0.01 PLN/kWh of Gadek API  
✓ **Decision**: Matches Gadek optimal charging period recommendations

**See**: [Complete Validation Report](GADEK_VALIDATION_SUMMARY.md)

### Key Validation Results:
```
Current price: 0.74 PLN/kWh (50th percentile)
Gadek recommendation: Wait for tomorrow 00:00-03:00
Our decision: DON'T CHARGE (not in bottom 25%)
Result: ✅ CORRECT - Behavior matches Gadek API
```

### Tariff Compatibility:
The system has been validated to work correctly with different Polish electricity tariffs:
- ✅ **g12w** (two-zone): Uses both percentile and absolute thresholds
- ✅ **g14d** (day tariff): Adapts using percentile-based approach
- ✅ **g12wcd** (multi-zone): Flexible charging across all zones

## Migration from Old Logic

The new system is **backward compatible**:
- Old configuration still works (uses fallback logic)
- New configuration enables enhanced features
- Can be disabled via `enabled: false`
- Gradual rollout supported

## Conclusion

The Enhanced Aggressive Charging System fixes all major issues with the old logic:

✅ Compares to median (not just cheapest)  
✅ Uses adaptive thresholds (percentage-based)  
✅ Detects multi-hour periods (not just ±1 hour)  
✅ Checks tomorrow's forecast (avoids missing better prices)  
✅ Implements smart categories (charges more when super cheap)  
✅ Coordinates with selling (reserves capacity for high-price selling)  

**Result**: Significantly reduced charging costs + better battery selling revenue!

