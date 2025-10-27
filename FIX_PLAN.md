# Test Failures Fix Plan

## Overview
Fixing 13 failing tests: 1 implementation bug + 12 test data issues

---

## Fix 1: Battery Selling Timing Logic (Implementation Bug)

**File:** `src/battery_selling_timing.py`

**Issue:** Returns `NO_OPPORTUNITY` when there's a significant future peak (58% price increase)

**Changes needed:**
1. Update `analyze_selling_timing()` method to detect significant future peaks even when current price is at low percentile
2. Adjust the logic to prioritize peak detection over current price percentile
3. Ensure opportunity cost calculation properly identifies waiting benefits

**Specific logic adjustment:**
- Before returning `NO_OPPORTUNITY` due to low current price, check if there's a significant peak ahead
- If peak price is >20% higher than current price and within forecast window, recommend WAIT instead of NO_OPPORTUNITY
- Maintain existing safety checks (min confidence, max wait time, etc.)

---

## Fix 2: Decision Filtering Test Data (8 Tests)

**File:** `test/test_decision_filtering_comprehensive.py`

**Issue:** Tests create charging decisions with `action="wait"` instead of proper action values

**Changes needed in `_create_test_decision_data()` method:**

### Charging decisions (lines 47-101):
Change from:
```python
{
    "action": "wait",  # ❌ Wrong
    "reason": "Start charging from grid - low price window detected",
    ...
}
```

To:
```python
{
    "action": "start_grid_charging",  # ✅ Correct
    "reason": "Start charging from grid - low price window detected",
    ...
}
```

**Specific changes:**
1. Line ~51: Change `"action": "wait"` to `"action": "start_grid_charging"`
2. Line ~69: Change `"action": "wait"` to `"action": "start_pv_charging"`
3. Keep line ~86 as is: `"action": "start_pv_charging"` (already correct)
4. Keep genuine wait decisions (lines 104-142) with `action="wait"` unchanged

---

## Fix 3: Badge Count Test Data (4 Tests)

**File:** `test/test_log_web_server.py`

**Issue:** Same as Fix 2 - charging decisions with `action="wait"`

**Changes needed in `create_sample_decision_files()` method (around line 608):**

### Charging decisions (lines 616-670):
Same changes as Fix 2:
1. Line ~619: Change `"action": "wait"` to `"action": "start_grid_charging"`
2. Line ~638: Change `"action": "wait"` to `"action": "start_pv_charging"`
3. Keep line ~655 as is: `"action": "start_pv_charging"` (already correct)
4. Keep wait decisions (lines 674-710) with `action="wait"` unchanged

---

## Testing Plan

After applying all fixes:

1. Run all tests: `pytest test/ -v`
2. Run specific fixed tests:
   - `pytest test/test_battery_selling_timing.py::TestTimingIntegrationScenarios::test_scenario_early_afternoon_with_evening_peak -v`
   - `pytest test/test_decision_filtering_comprehensive.py -v`
   - `pytest test/test_log_web_server.py::TestDecisionHistoryBadgeCounts -v`
3. Verify all 404 tests pass

---

## Expected Results

- **Before:** 391 passed, 13 failed (96.8% pass rate)
- **After:** 404 passed, 0 failed (100% pass rate)

---

## Risk Assessment

✅ **Low Risk:**
- Test data changes don't affect production code
- Implementation fix is localized to timing logic
- Existing passing tests provide regression safety net

---

## Rollback Plan (if needed)

If fixes cause issues:
1. Git revert the changes
2. Review test expectations vs implementation behavior
3. Adjust strategy based on findings


