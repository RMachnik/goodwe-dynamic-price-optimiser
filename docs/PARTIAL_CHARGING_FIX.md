# Partial Charging Logic Fix - December 2025

## Issue Identified

On December 3rd, 2025 at 20:05, the system made a suboptimal charging decision:

- **Situation**: Battery at 64% SOC, current price 1.095 PLN/kWh
- **Decision**: Started partial charging to 77% (2.6 kWh)
- **Reasoning**: "Bridge 1.9h until better window at 22:00 (0.451 PLN/kWh)"
- **Problem**: System charged at very expensive price when battery had sufficient capacity to wait

### Cost Analysis
- Charging 2.6 kWh at 1.095 PLN/kWh = **2.85 PLN**
- Waiting and charging at 0.451 PLN/kWh = **1.17 PLN**
- **Wasted cost: 1.68 PLN** (59% more expensive)

## Root Cause

The `_evaluate_partial_charging()` method only checked if the current price was below the critical threshold (1.20 PLN/kWh fallback), without considering:

1. **Current SOC level**: At 64% SOC with only 1.9h to wait, there was no urgency
2. **Price magnitude vs future window**: 1.095 PLN/kWh vs 0.451 PLN/kWh is a huge difference (143% more expensive)

## Fix Implementation

### SOC-Aware Price Thresholds

Modified `src/automated_price_charging.py` to implement SOC-aware price thresholds for partial charging:

```python
# At 60%+ SOC: Very conservative (50% of critical threshold or window_price + 20%)
if battery_soc >= 60:
    max_acceptable_price = min(
        critical_threshold * 0.5,
        best_window_price * 1.2
    )

# At 40-59% SOC: Moderate (70% of critical threshold or window_price + 30%)
elif battery_soc >= 40:
    max_acceptable_price = min(
        critical_threshold * 0.7,
        best_window_price * 1.3
    )

# Below 40% SOC: Use full critical threshold (more urgency)
else:
    max_acceptable_price = critical_threshold
```

### Enhanced Logging

Added cost comparison logging to help monitor partial charging decisions:

```
💡 Partial charging analysis at 64% SOC: 
   Charge 2.6 kWh now at 1.095 PLN/kWh (cost: 2.85 PLN) 
   vs wait 1.9h for 0.451 PLN/kWh (cost: 1.17 PLN). 
   Extra cost: 1.68 PLN
```

## Expected Behavior After Fix

### Scenario 1: High SOC (60%+), Expensive Price
- **Current**: 64% SOC, 1.095 PLN/kWh, better window at 0.451 PLN/kWh in 1.9h
- **Old behavior**: ❌ Charged immediately (wasted 1.68 PLN)
- **New behavior**: ✅ Wait for better window
  - Max acceptable: min(1.20 * 0.5, 0.451 * 1.2) = min(0.60, 0.54) = **0.54 PLN/kWh**
  - Current 1.095 > 0.54 → **BLOCKED**

### Scenario 2: Medium SOC (40-59%), Moderate Price
- **Example**: 45% SOC, 0.70 PLN/kWh, better window at 0.50 PLN/kWh in 3h
- **New behavior**: ✅ Wait for better window
  - Max acceptable: min(1.20 * 0.7, 0.50 * 1.3) = min(0.84, 0.65) = **0.65 PLN/kWh**
  - Current 0.70 > 0.65 → **BLOCKED**

### Scenario 3: Low SOC (<40%), High Price
- **Example**: 35% SOC, 0.90 PLN/kWh, better window at 0.45 PLN/kWh in 4h
- **New behavior**: ✅ Allow partial charge (urgent)
  - Max acceptable: 1.20 PLN/kWh (critical threshold)
  - Current 0.90 < 1.20 → **ALLOWED** (SOC urgency)

### Scenario 4: Low SOC (<40%), Extreme Price
- **Example**: 35% SOC, 1.50 PLN/kWh, better window at 0.45 PLN/kWh in 2h
- **New behavior**: ✅ Wait if possible
  - Max acceptable: 1.20 PLN/kWh
  - Current 1.50 > 1.20 → **BLOCKED** (too expensive even at low SOC)

## Monitoring Recommendations

### 1. Watch Partial Charging Log Messages

Look for these new log entries:

```bash
# Good decision - blocked expensive partial charge
grep "Partial charging blocked at" /opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log

# Partial charge analysis with cost comparison
grep "💡 Partial charging analysis" /opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log
```

### 2. Daily Cost Analysis

Create a monitoring script to track partial charging decisions:

```bash
#!/bin/bash
# Save as: scripts/monitor_partial_charging.sh

TODAY=$(date +%Y-%m-%d)
LOG_FILE="/opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log"

echo "=== Partial Charging Analysis for $TODAY ==="
echo ""

echo "Blocked decisions (saved money):"
grep "$TODAY" "$LOG_FILE" | grep "Partial charging blocked at" | \
    awk -F'SOC: ' '{print $2}' | \
    awk -F'current price ' '{print "  SOC:", $1, "Price:", $2}'

echo ""
echo "Approved partial charges:"
grep "$TODAY" "$LOG_FILE" | grep "💡 Partial charging analysis" | \
    awk -F'Extra cost: ' '{print "  "$2}'

echo ""
echo "Total partial charging sessions:"
grep "$TODAY" "$LOG_FILE" | grep "Partial charging session recorded" | wc -l
```

### 3. Key Metrics to Track

Monitor these daily:

1. **Blocked partial charges at high SOC (60%+)**
   - Should increase after fix
   - Indicates money saved

2. **Average price paid for partial charges**
   - Should decrease after fix
   - Target: < 0.60 PLN/kWh for partial charges

3. **Partial charging frequency**
   - Should remain stable or decrease slightly
   - Target: < 2 sessions per day

4. **SOC levels when partial charging occurs**
   - Should shift towards lower SOC ranges (40% and below)
   - High SOC (60%+) partial charges should be rare

### 4. Alert Thresholds

Set up alerts for problematic patterns:

```bash
# Alert if partial charge at high price and high SOC
if grep "Partial charge.*65%.*at.*[1-9]\." "$LOG_FILE" | grep -q "$TODAY"; then
    echo "⚠️  ALERT: Expensive partial charge at high SOC detected"
fi

# Alert if many partial charges in one day (>4)
PARTIAL_COUNT=$(grep "$TODAY.*Partial charging session recorded" "$LOG_FILE" | wc -l)
if [ "$PARTIAL_COUNT" -gt 4 ]; then
    echo "⚠️  ALERT: Too many partial charges today ($PARTIAL_COUNT)"
fi
```

### 5. Configuration Validation

Verify these config values are set correctly:

```yaml
# config/master_coordinator_config.yaml
timing_awareness:
  smart_critical_charging:
    partial_charging:
      enabled: true
      safety_margin_percent: 10        # Good default
      max_partial_sessions_per_day: 4  # Reasonable limit
      min_partial_charge_kwh: 2.0      # Prevents tiny charges
```

## Testing the Fix

### Manual Test Scenarios

Test these scenarios after deployment:

1. **High SOC + Expensive price scenario**
   ```
   Simulate: 65% SOC, 1.10 PLN/kWh current, 0.45 PLN/kWh in 2h
   Expected: Should wait, NOT charge
   Check: Look for "Partial charging blocked" message
   ```

2. **Medium SOC + Moderate price scenario**
   ```
   Simulate: 50% SOC, 0.75 PLN/kWh current, 0.50 PLN/kWh in 3h
   Expected: Should wait (0.75 > 0.65 threshold)
   Check: Look for "Partial charging blocked" message
   ```

3. **Low SOC + Acceptable price scenario**
   ```
   Simulate: 35% SOC, 0.65 PLN/kWh current, 0.45 PLN/kWh in 4h
   Expected: Allow partial charge (urgency + reasonable price)
   Check: Look for "Partial charging analysis" with cost comparison
   ```

## Rollback Plan

If issues arise, revert by:

```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
git diff HEAD src/automated_price_charging.py > partial_charging_fix.patch
git checkout HEAD -- src/automated_price_charging.py
sudo systemctl restart goodwe-optimizer
```

## Success Metrics (30 days post-deployment)

Track these metrics to measure improvement:

1. **Cost savings**: Reduced spending on partial charges (target: 20-30% reduction)
2. **Decision quality**: Higher average SOC when partial charging occurs
3. **User satisfaction**: Fewer "why did it charge now?" incidents
4. **System stability**: No increase in emergency charges or battery depletion events

## Related Configuration

The fix works with existing adaptive threshold configuration:

```yaml
smart_critical_charging:
  adaptive_thresholds:
    enabled: true                    # Uses adaptive thresholds
    lookback_days: 7                 # 7-day price history
    method: 'multiplier'             # Multiplier-based (recommended)
    high_price_multiplier: 1.5       # High price detection
    critical_price_multiplier: 1.3   # Critical threshold calculation
    fallback_critical_price_pln: 1.20  # Fallback when insufficient data
```

The SOC-aware logic applies on top of these thresholds, making them more conservative at high SOC levels.

---

**Implementation Date**: December 3, 2025  
**Modified Files**: `src/automated_price_charging.py`  
**Impact**: Improved partial charging decision quality, reduced unnecessary charging costs
