# UI Display Bug Fix - Partial Charging

## Issue Reported

The UI showed **"🚫 BLOCKED"** status for a charging decision, but the system **actually charged** the battery. This was confusing because:

```
20:05:20 - Partial charge to 77% (2.6 kWh)
Status: 🚫 BLOCKED
Energy: 0.00 kWh
Cost: 0.00 PLN
```

But logs showed: `✅ Charging started successfully at SOC Unknown%`

## Root Causes Found

### 1. **Master Coordinator Not Using Partial Charge Values**

**File**: `src/master_coordinator.py` (lines 682-704)

**Problem**: When recording a partial charge decision, the coordinator ignored the actual `target_soc` and `required_kwh` from the decision and instead used:
- Hardcoded `target_soc = 80%` (instead of actual 77%)
- Calculated energy based on current SOC to 80%
- This calculation sometimes resulted in 0 energy being recorded

**Impact**: Decision was recorded with `energy_kwh = 0`, `cost = 0`, `savings = 0`

### 2. **UI Incorrectly Interprets Zero Values**

**File**: `src/log_web_server.py` (lines 1903-1904)

**Problem**: UI logic assumed:
```javascript
if (energy === 0 && cost === 0 && savings === 0) {
    status = 'BLOCKED'
}
```

This was wrong for:
- Partial charges in progress (not yet completed)
- Decisions where energy tracking failed
- Early-stage charging sessions

**Impact**: UI showed "BLOCKED" even though charging was actually happening

## Fixes Implemented

### Fix 1: Use Actual Partial Charge Values (master_coordinator.py)

```python
if should_charge:
    # Check if this is a partial charge with explicit energy requirement
    if decision_record['decision'].get('partial_charge', False):
        # Use the actual values from partial charging decision
        energy_kwh = decision_record['decision'].get('required_kwh', 0)
        target_soc = decision_record['decision'].get('target_soc', 80)
        
        logger.debug(f"Partial charge decision: {energy_kwh:.2f} kWh to {target_soc}% SOC")
    else:
        # Calculate energy needed based on battery capacity and current SOC
        battery_capacity = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)
        current_soc = self.current_data.get('battery', {}).get('soc_percent', 0)
        target_soc = 80.0  # Target 80% SOC
        energy_needed = battery_capacity * (target_soc - current_soc) / 100.0
        energy_kwh = max(0, min(energy_needed, 5.0))  # Cap at 5kWh per decision
```

**What Changed**:
- Now checks if `partial_charge = True` in the decision
- Uses `required_kwh` and `target_soc` from the partial charge decision
- Falls back to calculated values for regular charges

### Fix 2: Better UI Status Detection (log_web_server.py)

```javascript
// If all values are 0, likely not executed - determine why
if (energy === 0 && cost === 0 && savings === 0) {
    // Check if this is a charge decision that hasn't completed yet
    const isChargeAction = decision.action === 'charge' || decision.action === 'fast_charge';
    const hasPositivePrice = decision.current_price > 0;
    
    // If it's a charge action with positive price but 0 energy, it might be in progress
    if (isChargeAction && hasPositivePrice) {
        return { 
            status: 'IN_PROGRESS', 
            color: '#ffc107', 
            icon: '⏳',
            reason: `Charging in progress (${socText})`,
            soc: batterySoc
        };
    }
    
    // ... rest of blocking logic ...
}
```

**What Changed**:
- Added detection for "in progress" state
- If action is "charge" and price is positive but energy is 0, show "⏳ IN_PROGRESS"
- Only shows "BLOCKED" if it's actually a wait/blocked decision

## Expected Behavior After Fix

### Scenario 1: Partial Charge Decision (Your Case)

**Before Fix**:
```
20:05:20 - Partial charge to 77% (2.6 kWh)
🚫 BLOCKED
Energy: 0.00 kWh
Cost: 0.00 PLN
```

**After Fix**:
```
20:05:20 - Partial charge to 77% (2.6 kWh)
⏳ IN_PROGRESS (or ✅ EXECUTED with correct values)
Energy: 2.6 kWh
Cost: 2.85 PLN
Savings: 0.00 PLN
```

### Scenario 2: Actually Blocked Charge

**Before and After** (no change - correct behavior):
```
20:05:20 - Wait for better window
🚫 BLOCKED
Much cheaper price available in 23:00
Energy: 0.00 kWh
```

### Scenario 3: In-Progress Charge

**Before Fix**:
```
🚫 BLOCKED
Energy: 0.00 kWh
```

**After Fix**:
```
⏳ IN_PROGRESS
Charging in progress (SOC: 64%)
```

## UI Status Legend (Updated)

| Icon | Status | Meaning |
|------|--------|---------|
| ✅ | EXECUTED | Charging completed with tracked energy/cost |
| ⏳ | IN_PROGRESS | Charging started but not yet complete |
| 🚫 | BLOCKED | Decision was to wait (not charge) |
| ❌ | FAILED | Charging attempt failed with error |
| ⏸️ | N/A | No decision made |

## Testing

### Validation Done
- ✅ Python syntax validated for both files
- ✅ Logic review confirms fix addresses both root causes

### Integration Testing Needed
1. Deploy the fix and monitor next partial charge decision
2. Verify UI shows correct status and values
3. Check that energy_kwh and cost values are populated correctly

### Test Scenario
Wait for next partial charge situation:
- SOC: 60%+
- Current price: moderate
- Better window: 2-3h away

**Expected**:
- With new partial charge fix: Decision should be **blocked** (SOC-aware threshold)
- UI should show: "🚫 BLOCKED - Partial charging blocked at XX% SOC"
- If it does charge (low SOC scenario): UI should show "⏳ IN_PROGRESS" or "✅ EXECUTED" with correct kWh/cost

## Files Modified

1. **src/master_coordinator.py**
   - Lines 682-704: Added partial charge value handling
   - Uses `required_kwh` and `target_soc` from decision

2. **src/log_web_server.py**
   - Lines 1903-1920: Added IN_PROGRESS status detection
   - Better distinction between blocked vs in-progress

## Related Fixes

This fix works together with the partial charging SOC-aware threshold fix to provide:
1. **Better decisions** (SOC-aware thresholds prevent bad charges)
2. **Accurate tracking** (correct energy/cost values recorded)
3. **Clear UI feedback** (proper status display)

---

**Implementation Date**: December 3, 2025  
**Issue Type**: UI display bug + data tracking bug  
**Impact**: Medium - affects user visibility and decision tracking accuracy
