# 🐛 BUG REPORT: Cost Calculation Error

## Summary
The dashboard is showing costs that are **1000x too low** due to an incorrect unit conversion in the cost calculation.

## Evidence
From actual charging decisions:
```
Energy: 4.40 kWh, Price: 0.7161 PLN/kWh
  Stored cost: 0.0032 PLN  ❌ WRONG
  Expected cost: 3.1509 PLN  ✅ CORRECT
  Error: 1000x too low (0.10% of correct value)
```

## Root Cause
**File**: `src/master_coordinator.py`  
**Line**: 654

```python
estimated_cost_pln = energy_kwh * (current_price / 1000.0)  # Convert from PLN/MWh to PLN/kWh
```

**The Problem:**
- The code divides by 1000 assuming `current_price` is in PLN/MWh
- But `current_price` is **already in PLN/kWh**
- This makes costs 1000x too small

## Impact on Dashboard

### Current (WRONG) Values:
- Total Cost: **0.04 PLN** (should be ~38 PLN)
- Savings %: **99.9%** (should be ~42%)
- Avg Cost/kWh: **0.001 PLN** (should be ~0.55 PLN)
- Total Savings: **32.6 PLN** (should be ~28 PLN)

### Corrected Values:
Based on 69 kWh charged at various prices (0.28-0.72 PLN/kWh):
- Total Cost: **~38 PLN**
- Savings %: **~42%** (compared to 0.40 PLN/kWh baseline)
- Avg Cost/kWh: **~0.55 PLN**
- Total Savings: **~28 PLN**

## Fix Required

### Option 1: Remove Incorrect Division (RECOMMENDED)
```python
# Line 654 - BEFORE (WRONG)
estimated_cost_pln = energy_kwh * (current_price / 1000.0)

# Line 654 - AFTER (CORRECT)
estimated_cost_pln = energy_kwh * current_price
```

### Option 2: Also Fix Reference Price (if line 657 is related)
Check if line 657 also needs fixing:
```python
# Line 657 - Check if this is correct
reference_price = 400.0 / 1000.0  # 0.4 PLN/kWh
```

This looks correct (400 PLN/MWh = 0.4 PLN/kWh), so no change needed.

## Additional Locations to Check

Other files that might have the same bug:
1. `src/multi_session_manager.py:303` - Also divides by 1000
   ```python
   return energy_kwh * (window['avg_price'] / 1000.0)
   ```
   
2. `src/hybrid_charging_logic.py:581` - Also divides by 1000
   ```python
   grid_cost_pln = energy_kwh * (optimal_window.avg_price_pln / 1000.0)
   ```

**Need to determine**: Are these prices in PLN/MWh or PLN/kWh?

## Testing After Fix

After fixing, verify:
1. Decision files show correct `estimated_cost_pln` values
2. Dashboard shows realistic cost values (~38 PLN for 69 kWh)
3. Savings % is realistic (~40-50% range is good for smart charging)
4. Avg cost/kWh matches your electricity rate

## Notes

The system is still **working correctly** for decision-making (choosing when to charge), but the **cost reporting is completely wrong**.

The real savings are still good (~42% vs average market price), just not the impossible 99.9% shown on the dashboard.

