# Fix: Enhanced Aggressive Charging Override by Legacy Fallback

**Date:** 1 December 2025  
**Issue:** Legacy charging logic was overriding smart enhanced aggressive charging decisions  
**Status:** ✅ FIXED

## Problem Description

The system was making suboptimal charging decisions where it would charge at a higher price instead of waiting for a better window identified by the enhanced aggressive charging logic.

### Example from Real System

At **11:05:22**:
- Current price: **1.122 PLN/kWh**
- Decision: **CHARGE** ❌ (Wrong!)
- Reason: "Aggressive charging during cheapest price period"

At **11:20:59**:
- Better window found at **11:30** with price: **0.661 PLN/kWh**
- Decision: **WAIT** ✅ (Correct!)
- Net benefit: **4.61 PLN** saved

**Question:** Why did the system charge at 11:05 (1.122 PLN/kWh) when it later correctly identified a much better window at 11:30 (0.661 PLN/kWh)?

## Root Cause

In `src/automated_price_charging.py`, the decision flow had two charging logic paths:

1. **Enhanced Aggressive Charging** (smart, considers future windows, interim costs, percentile analysis)
2. **Legacy Fallback Logic** (simple, just compares current price to cheapest price)

The bug was in how these interacted:

```python
# ENHANCED AGGRESSIVE CHARGING
if self.enhanced_aggressive:
    decision = self.enhanced_aggressive.should_charge_aggressively(...)
    
    if decision.should_charge:
        return {...}  # Return charge decision
    # BUG: When decision.should_charge=False, code continues...

# FALLBACK: Legacy aggressive charging logic
if self._check_aggressive_cheapest_price_conditions(...):  # Always runs!
    return {'should_charge': True, ...}  # Overrides smart decision!
```

**Problem Flow:**
1. Enhanced aggressive correctly returned `should_charge=False` (wait for better window)
2. Code **continued** to legacy fallback instead of respecting the decision
3. Legacy fallback saw current price (1.122) matched cheapest price in its limited data
4. Legacy fallback returned `should_charge=True`, **overriding the smart decision**

## Solution

Changed the legacy fallback to only run when enhanced aggressive is **disabled**:

```python
# ENHANCED AGGRESSIVE CHARGING
if self.enhanced_aggressive:
    decision = self.enhanced_aggressive.should_charge_aggressively(...)
    
    if decision.should_charge:
        return {'should_charge': True, ...}
    else:
        # Enhanced aggressive returned "don't charge" - respect that decision
        # This prevents legacy fallback from overriding smart decisions
        logger.debug(f"Enhanced aggressive decided not to charge: {decision.reason}")
        pass  # Continue to other conditions, but skip legacy fallback

# FALLBACK: Legacy aggressive charging logic (only if enhanced disabled)
elif self._check_aggressive_cheapest_price_conditions(...):  # Changed to 'elif'
    return {'should_charge': True, ...}
```

**Key Changes:**
1. Changed `if` to `elif` for legacy fallback
2. Added explicit handling when enhanced aggressive returns "don't charge"
3. Added debug logging for transparency

## Benefits

✅ **Respects smart decisions**: Enhanced aggressive analysis is now final  
✅ **Better cost savings**: System waits for truly optimal windows  
✅ **Considers full context**: Interim costs, future windows, percentile analysis  
✅ **Backward compatible**: Legacy fallback still works when enhanced is disabled  

## Testing

Created comprehensive tests in `test/test_aggressive_charging_priority.py`:

1. ✅ Enhanced aggressive "don't charge" blocks legacy fallback
2. ✅ Enhanced aggressive "charge" decision is returned  
3. ✅ Legacy fallback works when enhanced is disabled

## Impact

**Before Fix:**
- Charged at 1.122 PLN/kWh (11:05)
- Missed better window at 0.661 PLN/kWh (11:30)
- Lost savings: ~4.61 PLN per charging session

**After Fix:**
- Waits at 1.122 PLN/kWh (11:05)
- Charges at 0.661 PLN/kWh (11:30)
- Saves: ~4.61 PLN per charging session

**Annual savings estimate:**
- If this happens 2-3 times per week: **~500-700 PLN/year** in additional savings

## Configuration

Enhanced aggressive charging is controlled in `config/master_coordinator_config.yaml`:

```yaml
coordinator:
  cheapest_price_aggressive_charging:
    enabled: true  # When true, uses smart logic (respects its decisions)
```

When `enabled: false`, the system falls back to legacy simple logic.

## Related Files

- **Fixed:** `src/automated_price_charging.py` (lines 2225-2275)
- **Tests:** `test/test_aggressive_charging_priority.py` (new)
- **Config:** `config/master_coordinator_config.yaml`
- **Docs:** `docs/ENHANCED_AGGRESSIVE_CHARGING.md`

## Lessons Learned

1. **Decision hierarchy matters**: Higher-level logic should be final
2. **Fallbacks must respect**: Don't let simple logic override complex analysis
3. **Test decision flow**: Ensure smart decisions aren't silently overridden
4. **Log decision reasons**: Makes debugging these issues much easier
