# Dynamic Minimum Selling Price Implementation

## Overview

Implemented adaptive minimum selling price calculation that adjusts based on market conditions and seasonal demand patterns. This prevents selling battery energy at prices that would result in net losses when recharging is needed later.

## Problem Statement

**Original Issue:** Battery was selling at 1.074 PLN/kWh at 07:23:29, which triggered because:
- Price was at p93.1 (top 6.9%) - exceeded p80 threshold
- No better peak detected within 2 hours
- System confidence: 86.7%

**Root Cause:** The system later had to recharge at similar or higher prices, resulting in a net loss. The fixed minimum price (0.50 PLN/kWh) and p80 threshold were too aggressive for market conditions.

## Solution: Dynamic Pricing with Seasonal Adjustments

### Configuration (`config/master_coordinator_config.yaml`)

```yaml
battery_selling:
  dynamic_min_price:
    enabled: true                      # Enable adaptive pricing
    base_multiplier: 1.5               # Base: 150% of market average
    
    seasonal_adjustments:
      winter:                          # High demand season (Nov-Feb)
        multiplier: 2.0                # 200% of market average
        months: [11, 12, 1, 2]
      
      summer:                          # Low demand season (Jun-Aug)
        multiplier: 1.3                # 130% of market average
        months: [6, 7, 8]
      
      spring_autumn:                   # Shoulder seasons
        multiplier: 1.5                # 150% of market average
        months: [3, 4, 5, 9, 10]
    
    lookback_days: 7                   # Calculate avg from last 7 days
    min_samples: 24                    # Minimum data points needed
    fallback_price_pln: 1.2            # Fallback if calc fails (winter-safe)
  
  # Legacy fixed price (used if dynamic disabled)
  min_selling_price_pln: 0.80
```

## Implementation Details

### Key Methods Added to `battery_selling_engine.py`

1. **`_get_current_season(month)`** - Determines season from month
2. **`_get_seasonal_multiplier(month)`** - Gets multiplier for season
3. **`_calculate_dynamic_min_price(price_data)`** - Main calculation logic

### Calculation Process

```
Dynamic Min Price = Market Average (7 days) × Seasonal Multiplier

Winter Example:
  Market Avg: 0.60 PLN/kWh
  Multiplier: 2.0x
  Min Price:  1.20 PLN/kWh ✓

Summer Example:
  Market Avg: 0.50 PLN/kWh
  Multiplier: 1.3x
  Min Price:  0.65 PLN/kWh
```

### Safety Features

1. **Minimum Sample Requirement**: Needs ≥24 price points for reliable average
2. **Fallback Mechanism**: Uses 1.2 PLN/kWh if calculation fails
3. **Historical Window**: 7-day rolling average adapts to market changes
4. **Validation**: Checks data quality and time validity

## Additional Improvements Made

### 1. More Conservative Percentile Threshold
- **Changed:** p80 → **p90** (top 20% → top 10%)
- **Impact:** Only sell during truly high prices

### 2. Increased Sell-Then-Buy Protection
- **Changed:** 1.5x → **2.0x** minimum savings ratio
- **Impact:** Selling revenue must be 2x the potential buy-back cost

### 3. Tightened Percentile Thresholds
```yaml
percentile_thresholds:
  aggressive_sell: 3      # Top 3% (was 5%)
  standard_sell: 10       # Top 10% (was 20%)
  conditional_sell: 15    # Top 15% (was 25%)
```

### 4. More Aggressive Wait Thresholds
```yaml
opportunity_cost:
  high_confidence_wait: 20     # 20%+ gain = wait (was 30%)
  medium_confidence_wait: 10   # 10-20% gain = wait (was 15-30%)
  low_confidence_wait: 5       # 5-10% gain = consider (was 10-15%)
  sell_threshold: 5            # <5% gain = sell now (was 10%)
```

## Example Scenarios

### Winter Operation (November)
```
Market Average: 0.60 PLN/kWh
Dynamic Min:    1.20 PLN/kWh (2.0x)
Percentile:     Must be p90+ (top 10%)

Price at 1.074 PLN/kWh:
  ❌ BLOCKED: Below dynamic minimum 1.20 PLN/kWh
  Result: No selling, battery preserved for evening peak
```

### Summer Operation (July)
```
Market Average: 0.50 PLN/kWh
Dynamic Min:    0.65 PLN/kWh (1.3x)
Percentile:     Must be p90+ (top 10%)

Price at 0.75 PLN/kWh at p92:
  ✅ ALLOWED: Above 0.65 PLN and in top 10%
  Result: Selling permitted (lower demand season)
```

### Data Insufficient
```
Price Samples: 15 (need 24)
Result: Use fallback 1.2 PLN/kWh (winter-safe default)
```

## Logging Output

The system now logs dynamic price calculations:

```
INFO: Dynamic min price: 1.179 PLN/kWh 
      (market avg: 0.590, season: winter, multiplier: 2.0x, samples: 168)

INFO: 🛡️ BLOCKED: Current price 1.074 PLN/kWh below dynamic minimum 1.179 PLN/kWh
```

## Testing

Test suite added: `test/test_dynamic_selling_price.py`

**Run tests:**
```bash
python test/test_dynamic_selling_price.py
```

**Test coverage:**
- ✅ Winter pricing (2.0x multiplier)
- ✅ Summer pricing (1.3x multiplier)
- ✅ Season detection
- ✅ Fallback when insufficient data
- ✅ Market average calculation

## Impact Analysis

### Before Changes
- **Minimum:** 0.50 PLN/kWh (fixed)
- **Trigger:** p80 (top 20%)
- **Result:** Sold at 1.074 PLN, later recharged at similar price → **net loss**

### After Changes
- **Minimum:** ~1.20 PLN/kWh (dynamic, winter)
- **Trigger:** p90 (top 10%)
- **Result:** Would block 1.074 PLN sale → **battery preserved for better opportunity**

### Expected Benefits
1. **Prevents premature selling** during suboptimal prices
2. **Adapts to seasonal demand** patterns automatically
3. **Reduces net losses** from sell-then-buy scenarios
4. **Maintains flexibility** in low-demand seasons

## Configuration Migration

### To Enable Dynamic Pricing

Ensure in `config/master_coordinator_config.yaml`:
```yaml
battery_selling:
  dynamic_min_price:
    enabled: true  # ← Set to true
```

### To Disable (Use Fixed Price)

```yaml
battery_selling:
  dynamic_min_price:
    enabled: false  # ← Set to false
  min_selling_price_pln: 0.80  # ← Will be used instead
```

## Future Enhancements

Potential improvements:
1. **Machine learning** for market average prediction
2. **Hour-of-day adjustments** (higher min during peak hours)
3. **Weather integration** (adjust for forecast PV production)
4. **Grid stress indicators** (Kompas S4 integration)
5. **User preference profiles** (conservative vs aggressive)

## Related Documentation

- [Battery Selling Engine](README_battery_selling.md)
- [Smart Timing](OPTIMIZATION_RULES_IMPLEMENTATION.md)
- [Sell-Then-Buy Prevention](COST_SAVINGS_EXPLAINED.md)
- [Master Coordinator](README_MASTER_COORDINATOR.md)

---

**Implementation Date:** November 21, 2025  
**Status:** ✅ Implemented and Tested  
**Impact:** High - Directly affects profitability of battery selling operations
