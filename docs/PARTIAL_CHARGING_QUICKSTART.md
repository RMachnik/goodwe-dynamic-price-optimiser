# Partial Charging Fix - Quick Start Guide

## What Was Fixed

The system was making poor partial charging decisions at high battery SOC (State of Charge). It would charge at expensive prices even when:
- Battery had sufficient charge to wait
- A much cheaper price window was coming soon

**Example from December 3, 2025:**
- ❌ Charged at 1.095 PLN/kWh with 64% SOC
- ✅ Should have waited 1.9h for 0.451 PLN/kWh
- 💸 Wasted: ~1.68 PLN

## The Solution

Implemented **SOC-aware price thresholds** for partial charging:

| SOC Level | Max Price Threshold | Logic |
|-----------|---------------------|-------|
| **60%+** | 50% of critical threshold OR window_price × 1.2 | Very conservative - plenty of battery |
| **40-59%** | 70% of critical threshold OR window_price × 1.3 | Moderate - some urgency |
| **<40%** | Full critical threshold | More permissive - higher urgency |

## How to Deploy

### 1. Restart the Service

```bash
# If running with systemd
sudo systemctl restart goodwe-optimizer

# Or if running manually
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
./run_master_coordinator.sh
```

### 2. Verify Deployment

Check that the new code is active:

```bash
# Look for the new log format with cost analysis
tail -100 /opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log | \
    grep "💡 Partial charging analysis"
```

You should see lines like:
```
💡 Partial charging analysis at 64% SOC: 
   Charge 2.6 kWh now at 1.095 PLN/kWh (cost: 2.85 PLN) 
   vs wait 1.9h for 0.451 PLN/kWh (cost: 1.17 PLN). 
   Extra cost: 1.68 PLN
```

Or for blocked charges:
```
Partial charging blocked at 65% SOC: current price 1.095 > max acceptable 0.541 PLN/kWh
```

## Monitor Daily

Run the monitoring script daily:

```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser

# Check today's decisions
./scripts/monitor_partial_charging.sh

# Check a specific date
./scripts/monitor_partial_charging.sh 2025-12-03
```

## What to Look For

### Good Signs ✅
- More "Partial charging blocked" messages at high SOC (60%+)
- Lower average prices for approved partial charges
- Cost analysis showing reasonable extra costs (<0.50 PLN per charge)
- Fewer than 3-4 partial charges per day

### Warning Signs ⚠️
- Partial charges above 0.80 PLN/kWh
- Many partial charges at high SOC (60%+)
- Large extra costs in the analysis (>1.00 PLN)
- More than 4 partial charges per day

## Example Scenarios

### Before the Fix ❌

```
20:05 - SOC: 64%, Price: 1.095 PLN/kWh
Decision: Charge to 77% (2.6 kWh)
Reasoning: Bridge 1.9h until 22:00 (0.451 PLN/kWh)
Cost: 2.85 PLN vs 1.17 PLN if waited
Result: ❌ Wasted 1.68 PLN
```

### After the Fix ✅

```
20:05 - SOC: 64%, Price: 1.095 PLN/kWh
Decision: Wait for better window
Reasoning: 1.095 > 0.541 (max acceptable at 64% SOC)
Next window: 22:00 at 0.451 PLN/kWh
Result: ✅ Saved 1.68 PLN
```

## Rollback If Needed

If you encounter issues:

```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
git checkout HEAD -- src/automated_price_charging.py
sudo systemctl restart goodwe-optimizer
```

Then check logs to confirm rollback:
```bash
# Old code won't have the "💡 Partial charging analysis" logs
tail -100 /opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log
```

## Configuration

No configuration changes needed. The fix works with existing settings:

```yaml
# config/master_coordinator_config.yaml
timing_awareness:
  smart_critical_charging:
    partial_charging:
      enabled: true                        # Keep enabled
      safety_margin_percent: 10            # Current setting is good
      max_partial_sessions_per_day: 4      # Reasonable limit
      min_partial_charge_kwh: 2.0          # Prevents tiny charges
```

The SOC-aware thresholds are applied automatically on top of these settings.

## Testing

To test the fix is working, observe system behavior when:

1. **High SOC + expensive price scenario** (should WAIT)
   - Battery: 60%+ SOC
   - Current price: 1.0+ PLN/kWh
   - Better window: 0.5 PLN/kWh in 2-3 hours
   - Expected: "Partial charging blocked" message

2. **Low SOC + reasonable price scenario** (may CHARGE)
   - Battery: <40% SOC  
   - Current price: 0.6-0.8 PLN/kWh
   - Better window: 0.4 PLN/kWh in 4+ hours
   - Expected: May approve partial charge (urgency justifies it)

## Support

For questions or issues:

1. Check the full documentation: `docs/PARTIAL_CHARGING_FIX.md`
2. Review logs: `tail -f /opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log`
3. Run monitoring: `./scripts/monitor_partial_charging.sh`

---

**Implementation Date**: December 3, 2025  
**Files Changed**: `src/automated_price_charging.py`  
**Status**: Ready for deployment
