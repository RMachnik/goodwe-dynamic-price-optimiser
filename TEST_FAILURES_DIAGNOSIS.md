# Test Failures Diagnosis Report

**Date:** 2025-10-20  
**Total Tests:** 404  
**Passed:** 391 (96.8%)  
**Failed:** 13 (3.2%)

---

## Summary

Out of 13 failing tests:
- **1 test has LOGIC ISSUE** (battery selling timing)
- **12 tests have TEST LOGIC ISSUES** (decision filtering and categorization)

---

## Detailed Analysis

### 1. Battery Selling Timing Test (1 failure) - **LOGIC ISSUE**

**Test:** `test_battery_selling_timing.py::TestTimingIntegrationScenarios::test_scenario_early_afternoon_with_evening_peak`

**Diagnosis:** **LOGIC ISSUE in implementation**

**Details:**
- **What the test expects:** When current price is 0.60 PLN/kWh and there's a peak at 0.95 PLN/kWh in 5 hours, the system should recommend `WAIT_FOR_PEAK` or `WAIT_FOR_HIGHER`
- **What actually happens:** The system returns `NO_OPPORTUNITY` with reasoning "Current price 0.600 PLN/kWh below high threshold (only 14.3th percentile)"
- **Root cause:** The battery selling timing logic is incorrectly categorizing a 58% price increase opportunity as "NO_OPPORTUNITY" simply because the current price is at a low percentile

**Recommendation:** **FIX THE IMPLEMENTATION**
- The logic in `battery_selling_timing.py` needs to be adjusted to:
  1. Detect significant future price peaks even when current price is at a low percentile
  2. Calculate opportunity cost correctly (0.95 vs 0.60 is a ~58% increase, which should be detected)
  3. Recommend waiting for peak when the price increase justifies it

---

### 2. Decision Filtering Tests (8 failures) - **TEST LOGIC ISSUES**

**Tests:**
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_all_filter_returns_all_decisions_with_correct_categorization`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_battery_selling_filter_returns_only_battery_selling_decisions`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_charging_filter_returns_only_charging_decisions`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_decision_filtering_performance`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_filtering_consistency_across_different_time_ranges`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_filtering_edge_cases`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_filtering_with_malformed_decisions`
- `test_decision_filtering_comprehensive.py::TestDecisionFilteringComprehensive::test_wait_filter_returns_only_wait_decisions`

**Diagnosis:** **TEST LOGIC ISSUES**

**Details:**
- **Test expects:** 3 charging decisions to be categorized from files named `charging_decision_*.json`
- **What actually happens:** Only 1 charging decision is counted
- **Root cause:** The test creates decision files with `action="wait"` but expects them to be categorized as "charging decisions" based on the filename and reason field

Looking at the test data:
```python
# These have action="wait" but reason contains charging intent
{
    "action": "wait",  # <-- This is the problem
    "reason": "Start charging from grid - low price window detected",
}
```

Looking at the implementation in `log_web_server.py` (lines 2829-2842):
```python
# Wait decisions - check action first to avoid misclassification
elif action == 'wait':
    wait_decisions.append(decision)
# Charging decisions - look for actual charging intent...
elif (action in ['charge', 'charging', 'start_pv_charging', 'start_grid_charging'] or
      'start charging' in reason_lower or ...):
    charging_decisions.append(decision)
```

**The problem:** The implementation checks `action == 'wait'` BEFORE checking the reason field for charging intent. So decisions with `action="wait"` are always categorized as wait decisions, even if the reason contains charging intent.

**However,** this is actually CORRECT behavior! The action field should take precedence. The test is creating invalid test data by setting `action="wait"` when the actual action is to start charging.

**Recommendation:** **FIX THE TESTS**
- Tests should use proper action values: `"start_pv_charging"`, `"start_grid_charging"`, etc.
- Don't use `action="wait"` when the intent is to charge
- The categorization logic in the implementation is correct as-is

---

### 3. Log Web Server Badge Count Tests (4 failures) - **TEST LOGIC ISSUES**

**Tests:**
- `test_log_web_server.py::TestDecisionHistoryBadgeCounts::test_badge_count_categorization`
- `test_log_web_server.py::TestDecisionHistoryBadgeCounts::test_battery_selling_decision_identification`
- `test_log_web_server.py::TestDecisionHistoryBadgeCounts::test_charging_decision_identification`
- `test_log_web_server.py::TestDecisionHistoryBadgeCounts::test_wait_decision_identification`

**Diagnosis:** **TEST LOGIC ISSUES** (Same root cause as #2)

**Details:**
- Same issue as the decision filtering tests above
- Tests create decision files with `action="wait"` but expect them to be categorized as charging decisions
- The test setup uses the exact same flawed test data structure

**Recommendation:** **FIX THE TESTS**
- Same fix as above: use proper action values in test data
- Change `action="wait"` to `action="start_pv_charging"` or `action="start_grid_charging"` when creating charging decision test data

---

## Action Items

### Priority 1: Fix Battery Selling Timing Logic ❗
**File:** `src/battery_selling_timing.py`

The `analyze_selling_timing` method needs to:
1. Detect significant future peaks even when current price is low
2. Not return `NO_OPPORTUNITY` when there's a clear 50%+ price increase ahead
3. Calculate proper opportunity cost for waiting

### Priority 2: Fix Test Data in Decision Filtering Tests
**Files:**
- `test/test_decision_filtering_comprehensive.py`
- `test/test_log_web_server.py`

Changes needed:
1. In test data creation methods, change decision objects from:
   ```python
   {
       "action": "wait",
       "reason": "Start charging from grid - low price window detected",
   }
   ```
   To:
   ```python
   {
       "action": "start_grid_charging",  # or "start_pv_charging"
       "reason": "Start charging from grid - low price window detected",
   }
   ```

2. Keep `action="wait"` only for genuine wait decisions:
   ```python
   {
       "action": "wait",
       "reason": "Wait for better conditions (PV overproduction, lower prices, or higher consumption)",
   }
   ```

---

## Test Categorization Summary

| Test Category | Count | Diagnosis | Action Required |
|--------------|-------|-----------|-----------------|
| Battery Selling Timing | 1 | Logic Issue in Implementation | Fix implementation logic |
| Decision Filtering | 8 | Test Logic Issue | Fix test data |
| Badge Count Tests | 4 | Test Logic Issue | Fix test data |
| **Total** | **13** | **1 logic + 12 test issues** | **Fix both** |

---

## Conclusion

- **96.8% of tests are passing** - the codebase is in good health overall
- **1 implementation bug** needs to be fixed in battery selling timing logic
- **12 test issues** are due to incorrect test data setup (using `action="wait"` when actual action is charging)
- The implementation's decision categorization logic is **correct** - tests need to be updated to match proper data structure


