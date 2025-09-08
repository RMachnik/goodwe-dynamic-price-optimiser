# Smart Critical Charging Implementation

## Overview

The Smart Critical Charging feature optimizes battery charging decisions at low battery levels by considering electricity prices and timing, rather than blindly charging at any price when the battery reaches a critical level.

## Problem Solved

**Previous Behavior:**
- Critical threshold: 20% SOC
- Always charged immediately regardless of price
- Example: Charged at 1.577 PLN/kWh when 0.468 PLN/kWh was available 3 hours later
- Result: Unnecessary high-cost charging

**New Behavior:**
- Emergency threshold: 5% SOC (always charge)
- Critical threshold: 10% SOC (price-aware)
- Considers price, timing, and savings potential
- Result: Optimal charging decisions even at low battery levels

## Configuration

### Battery SOC Thresholds

```yaml
battery_management:
  soc_thresholds:
    critical: 10               # Critical level - price aware charging
    emergency: 5               # Emergency level - always charge regardless of price
    low: 40                    # Low level - charge during low/medium prices
    medium: 70                 # Medium level - charge during low prices only
    high: 90                   # High level - charge during very low prices only
```

### Smart Critical Charging Parameters

```yaml
timing_awareness:
  smart_critical_charging:
    enabled: true                    # Enable smart critical charging logic
    max_critical_price_pln: 0.6     # Maximum price to charge at critical level (PLN/kWh)
    max_wait_hours: 6               # Maximum hours to wait for better price
    min_price_savings_percent: 30  # Minimum savings % to wait for better price
    emergency_override_price: true  # Always charge at emergency level regardless of price
```

## Decision Logic

### Super Low Price Level (≤ 0.3 PLN/kWh) - **HIGHEST PRIORITY**
- **Action**: Always charge fully from grid (target 100% SOC)
- **Reason**: Capture super cheap electricity for later PV selling
- **Override**: Overrides PV charging during super low prices
- **Economic Benefit**: Up to 66.7% savings compared to normal price charging

### Emergency Level (≤ 5% SOC)
- **Action**: Always charge immediately
- **Reason**: Battery safety override
- **Price**: Ignored (safety first)

### Critical Level (6-10% SOC)
The system analyzes three factors:

1. **Current Price**
   - If ≤ 0.6 PLN/kWh → Charge immediately
   - If > 0.6 PLN/kWh → Continue analysis

2. **Better Price Available**
   - If better price within 6 hours AND savings ≥ 30% → Wait
   - Otherwise → Charge now

3. **Safety Fallback**
   - If no price data available → Charge immediately

## Example Scenarios

### Scenario 1: Super Low Price (NEW)
- **Battery**: 60% SOC
- **Current Price**: 0.2 PLN/kWh (super low!)
- **PV Available**: 2 kW (could charge to 100% in 2 hours)
- **Decision**: Charge fully from grid NOW
- **Reason**: "Super low price (0.200 PLN/kWh ≤ 0.300 PLN/kWh) + PV insufficient (2000W) - charging fully from grid to 100%"
- **Economic Benefit**: 66.7% savings vs normal price charging

### Scenario 2: Acceptable Price
- **Battery**: 8% SOC
- **Current Price**: 0.5 PLN/kWh
- **Decision**: Charge immediately
- **Reason**: "Critical battery (8%) + acceptable price (0.500 PLN/kWh ≤ 0.6 PLN/kWh)"

### Scenario 3: High Price, Good Savings Soon
- **Battery**: 8% SOC
- **Current Price**: 1.5 PLN/kWh
- **Better Price**: 0.4 PLN/kWh at 23:00 (2 hours away)
- **Savings**: 73% (1.5 → 0.4)
- **Decision**: Wait
- **Reason**: "Critical battery (8%) but much cheaper price in 2h (0.400 vs 1.500 PLN/kWh, 73.3% savings)"

### Scenario 4: High Price, Long Wait
- **Battery**: 8% SOC
- **Current Price**: 1.5 PLN/kWh
- **Better Price**: 0.4 PLN/kWh at 06:00 (8 hours away)
- **Savings**: 73%
- **Decision**: Charge now
- **Reason**: "Critical battery (8%) + high price (1.500 PLN/kWh) but waiting 8h for 73.3% savings not optimal"

### Scenario 5: High Price, Insufficient Savings
- **Battery**: 8% SOC
- **Current Price**: 1.0 PLN/kWh
- **Better Price**: 0.9 PLN/kWh at 23:00 (2 hours away)
- **Savings**: 10% (insufficient)
- **Decision**: Charge now
- **Reason**: "Critical battery (8%) + high price (1.000 PLN/kWh) but waiting 2h for 10.0% savings not optimal"

## Implementation Details

### Files Modified

1. **Configuration**: `config/master_coordinator_config.yaml`
   - Updated SOC thresholds
   - Added smart critical charging parameters

2. **Automated Price Charging**: `src/automated_price_charging.py`
   - Added `_smart_critical_charging_decision()` method
   - Updated decision logic for critical levels

3. **Hybrid Charging Logic**: `src/hybrid_charging_logic.py`
   - Added `_create_smart_critical_charging_decision()` method
   - Updated emergency vs critical handling

4. **Master Coordinator**: `src/master_coordinator.py`
   - Updated force start logic (only for emergency level)
   - Added smart critical charging support

### Testing

Run the test script to validate the implementation:

```bash
python test_smart_critical_charging.py
```

The test covers:
- Emergency level charging (always charge)
- Critical level with acceptable price
- Critical level with high price and good savings
- Critical level with high price and long wait
- Critical level with insufficient savings

## Benefits

1. **Cost Optimization**: Avoids expensive charging when better prices are available soon
2. **Battery Safety**: Maintains emergency override for truly critical levels
3. **Flexibility**: Configurable thresholds and parameters
4. **Intelligence**: Considers timing, price, and savings potential
5. **Fallback Safety**: Always charges if no price data available

## Monitoring

The system logs detailed reasons for charging decisions:

```
2025-09-08 19:47:11 - INFO - Critical battery (8%) but much cheaper price in 2h (0.400 vs 1.500 PLN/kWh, 73.3% savings)
2025-09-08 19:47:11 - INFO - Decision: Wait for better price
```

This provides transparency into the decision-making process and helps with troubleshooting.

## Future Enhancements

1. **Dynamic Thresholds**: Adjust thresholds based on historical price patterns
2. **Weather Integration**: Consider PV forecast when making critical charging decisions
3. **Load Forecasting**: Factor in expected house consumption
4. **Machine Learning**: Learn optimal thresholds from historical data
5. **User Preferences**: Allow users to set their own risk tolerance levels