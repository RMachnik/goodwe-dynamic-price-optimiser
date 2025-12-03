# Test Suite Quality Improvement Plan

> **Created**: 2025-12-03  
> **Last Updated**: 2025-12-03  
> **Status**: ✅ Phase 1 Complete, 🚧 Phase 2 In Progress  
> **Priority**: HIGH - Ensuring test reliability and maintainability

---

## Executive Summary

This plan addresses improvements to the test suite quality, focusing on fixing failing tests, eliminating warnings, improving test organization, and enhancing overall test reliability and maintainability.

**Initial State (2025-12-03):**
- ❌ **648 tests passing, 7 failing** (async/await issues)
- ⚠️ **146 warnings** (mainly unknown pytest marks)
- ✅ **11 tests skipped** (expected - integration tests)
- ⏱️ **16.03 seconds** test execution time
- 📊 **~23,000 lines of test code** across 70+ test files

**Current State (After Phase 1):**
- ✅ **655 tests passing, 0 failing** 
- ✅ **0 warnings** (100% elimination!)
- ✅ **11 tests skipped** (expected - integration tests)
- ⏱️ **14.81 seconds** test execution time (7.6% faster)
- ✅ **100% test pass rate achieved**

---

## Problem Analysis

### 1. Failing Tests (7 failures)

#### Issue #1: Async/Await Handling in Price Fetching Tests
**Files Affected:**
- `test/test_price_date_behavior.py` (6 failures)
- `test/test_peak_hours_integration.py` (1 failure)

**Root Cause:**
Tests are calling async functions (`fetch_today_prices()`, `parse_and_cache()`) without awaiting them, resulting in coroutine objects being returned instead of actual results.

**Examples:**
```python
# Current (BROKEN):
prices = self.charger.fetch_today_prices()  # Returns coroutine, not data
self.assertIsNotNone(prices)  # Fails - comparing coroutine object

# Expected (FIXED):
prices = asyncio.run(self.charger.fetch_today_prices())  # Await the coroutine
self.assertIsNotNone(prices)  # Now works correctly
```

**Failed Tests:**
1. `test_price_date_behavior.py::TestPriceDateBehavior::test_date_transition_at_midnight`
2. `test_price_date_behavior.py::TestPriceDateBehavior::test_error_handling_api_failure`
3. `test_price_date_behavior.py::TestPriceDateBehavior::test_error_handling_no_data`
4. `test_price_date_behavior.py::TestPriceDateBehavior::test_fetch_today_prices_correct_date`
5. `test_price_date_behavior.py::TestPriceDateBehavior::test_price_data_covers_full_day`
6. `test_price_date_behavior.py::TestPriceDateBehavior::test_publication_timing_correctness`
7. `test_peak_hours_integration.py::test_parse_and_cache`

### 2. Pytest Warning Issues (146 warnings)

#### Issue #2a: Unknown Pytest Marks
**Affected Files:**
- `test/test_weather_aware_decisions.py` (9 warnings)
- `test/test_weather_integration.py` (20+ warnings)

**Root Cause:**
Tests use `@pytest.mark.timeout(10)` decorator, but `pytest-timeout` plugin is not installed or configured.

**Warning Message:**
```
PytestUnknownMarkWarning: Unknown pytest.mark.timeout - is this a typo?
```

#### Issue #2b: Deprecation Warnings
Other warnings may include:
- DeprecationWarning from library dependencies
- PytestCollectionWarning for test collection issues
- ResourceWarning for unclosed files/connections

### 3. Test Organization and Maintainability

#### Issue #3a: Large Test Files
Some test files are very large (>1000 lines):
- `test_log_web_server.py`: 1423 lines
- `test_database_infrastructure.py`: 940 lines
- `test_pv_consumption_analysis.py`: 730 lines

**Problems:**
- Hard to navigate
- Long test execution times
- Difficult to identify failing test context
- Increased cognitive load for maintenance

#### Issue #3b: Missing Test Documentation
Some tests lack clear docstrings explaining:
- What behavior is being tested
- Expected outcomes
- Edge cases being covered
- Why the test is important

#### Issue #3c: Test Isolation Issues
Some tests may share state or have dependencies:
- Temporary files not cleaned up
- Mock objects not properly reset
- Global state modifications

---

## Proposed Solutions

### Solution 1: Fix Async/Await Issues (Priority: CRITICAL)

#### Implementation Steps:

**Step 1.1: Update `test_price_date_behavior.py`**

Add async test support and properly await coroutines:

```python
import asyncio
import pytest

class TestPriceDateBehavior(unittest.TestCase):
    # ... existing setup ...
    
    def test_fetch_today_prices_correct_date(self):
        """Test that fetch_today_prices requests correct date"""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {}
            
            # FIX: Use asyncio.run() to await the coroutine
            result = asyncio.run(self.charger.fetch_today_prices())
            
            # Now assertions work correctly
            self.assertIsNotNone(result)
    
    def test_date_transition_at_midnight(self):
        """Test price data transitions correctly at midnight"""
        # FIX: Await async calls
        prices = asyncio.run(self.charger.fetch_today_prices())
        self.assertIsNotNone(prices)
```

**Alternative Approach:** Use pytest-asyncio for cleaner async test syntax:

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_today_prices_async():
    """Test async price fetching"""
    charger = AutomatedPriceCharger(config_path=test_config_path)
    prices = await charger.fetch_today_prices()
    assert prices is not None
```

**Step 1.2: Update `test_peak_hours_integration.py`**

```python
def test_parse_and_cache():
    """Test PSE peak hours parsing and caching"""
    collector = PSEPeakHoursCollector()
    
    # FIX: Await the coroutine
    result = asyncio.run(collector.parse_and_cache())
    
    assert len(result) > 0  # Now works - result is actual data
```

**Expected Impact:**
- ✅ All 7 failing tests will pass
- ✅ Proper async/await handling established as pattern
- ✅ Tests correctly validate async functionality

---

### Solution 2: Fix Pytest Warnings (Priority: HIGH)

#### Step 2.1: Configure pytest-timeout Plugin

Add to `requirements.txt`:
```
pytest-timeout>=2.0.0
```

Add to `pytest.ini`:
```ini
[pytest]
markers =
    timeout: mark test to run with a timeout
    integration: mark test as integration test requiring external resources
    slow: mark test as slow running
```

#### Step 2.2: Alternative - Replace timeout marks with pytest-timeout

If `pytest-timeout` is not desired, replace decorator usage:

```python
# Before:
@pytest.mark.timeout(10)
def test_weather_integration():
    pass

# After - use pytest's built-in timeout if available, or remove:
def test_weather_integration():
    # Test code with manual timeout handling if needed
    pass
```

#### Step 2.3: Suppress or Fix Deprecation Warnings

Add to `pytest.ini`:
```ini
[pytest]
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
    # Or more targeted:
    ignore::DeprecationWarning:goodwe.*
```

**Expected Impact:**
- ⬇️ 146 warnings → 0-10 warnings
- ✅ Cleaner test output
- ✅ Easier to spot real issues

---

### Solution 3: Improve Test Organization (Priority: MEDIUM)

#### Step 3.1: Split Large Test Files

Break down large test files into focused modules:

**Example: `test_log_web_server.py` (1423 lines)**

Split into:
- `test_log_web_server_api.py` - API endpoint tests
- `test_log_web_server_caching.py` - Response caching tests
- `test_log_web_server_metrics.py` - System metrics tests
- `test_log_web_server_snapshots.py` - Snapshot integration tests

**Benefits:**
- Faster test discovery
- Easier to run specific test categories
- Better test organization
- Reduced cognitive load

#### Step 3.2: Add Test Documentation Standards

Create template for test docstrings:

```python
def test_battery_selling_opportunity_detection(self):
    """
    Test battery selling opportunity detection logic.
    
    Scenario:
        - Current price: 1.50 PLN/kWh (high)
        - Battery SOC: 80%
        - Expected behavior: Should detect selling opportunity
    
    Validates:
        - Price threshold comparison
        - SOC sufficiency check
        - Revenue calculation accuracy
    
    Edge Cases:
        - Price exactly at threshold
        - SOC at minimum selling level
    """
    # Test implementation
```

#### Step 3.3: Standardize Test Fixtures

Create reusable fixtures in `conftest.py`:

```python
# test/conftest.py

@pytest.fixture
def isolated_config():
    """Provides isolated test configuration"""
    config = {
        'electricity_tariff': {
            'tariff_type': 'g12w',
            # ... standard test config
        }
    }
    config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(config, config_file)
    config_file.close()
    
    yield config_file.name
    
    os.unlink(config_file.name)

@pytest.fixture
def mock_inverter():
    """Provides mock inverter for testing"""
    inverter = MagicMock()
    inverter.get_data.return_value = {
        'ppv': 1500,
        'battery_soc': 75,
        'load_power': 800
    }
    return inverter
```

---

### Solution 4: Enhance Test Coverage and Quality (Priority: MEDIUM)

#### Step 4.1: Add Missing Test Cases

Identify gaps in coverage:

**Battery Selling Engine:**
- ✅ Opportunity detection (covered)
- ✅ Revenue calculation (covered)
- ❌ Edge case: Multiple selling sessions per day (missing)
- ❌ Edge case: Selling during grid outage (missing)
- ❌ Recovery from interrupted selling session (missing)

**Price Charging Logic:**
- ✅ Cheap hour detection (covered)
- ✅ Multi-window charging (covered)
- ❌ Edge case: Price data unavailable (partial)
- ❌ Edge case: Timezone transitions (missing)
- ❌ Leap year/DST handling (missing)

#### Step 4.2: Improve Test Assertions

Replace weak assertions with specific checks:

```python
# Weak:
self.assertTrue(result)  # What does True mean?

# Strong:
self.assertEqual(result['action'], 'start_charging')
self.assertAlmostEqual(result['expected_revenue'], 12.50, places=2)
self.assertIn('price_threshold_met', result['reasons'])
```

#### Step 4.3: Add Performance Regression Tests

```python
import time

def test_price_calculation_performance():
    """Ensure price calculations complete within reasonable time"""
    charger = AutomatedPriceCharger(config_path=test_config)
    
    start = time.time()
    for _ in range(100):
        charger.calculate_final_price(0.300, datetime.now())
    duration = time.time() - start
    
    # Should process 100 calculations in < 1 second
    assert duration < 1.0, f"Performance regression: {duration:.2f}s"
```

---

### Solution 5: Continuous Integration Improvements (Priority: LOW)

#### Step 5.1: Add Test Result Reporting

```yaml
# .github/workflows/tests.yml
- name: Run Tests with Coverage
  run: |
    pytest test/ \
      --cov=src \
      --cov-report=xml \
      --cov-report=html \
      --junitxml=test-results.xml \
      -v

- name: Upload Coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

#### Step 5.2: Add Test Performance Tracking

Track test execution time over commits to identify regressions.

#### Step 5.3: Implement Test Flakiness Detection

Identify and fix flaky tests (tests that pass/fail inconsistently).

---

## Implementation Priority

### ✅ Phase 1: Critical Fixes (Week 1) - **IN PROGRESS**

**Goal:** Get all tests passing and eliminate warnings

1. ✅ **Fix async/await issues** in `test_price_date_behavior.py`
   - Update 6 failing test methods to use `asyncio.run()`
   - Ensure proper async test patterns
   
2. ✅ **Fix async/await issues** in `test_peak_hours_integration.py`
   - Update 1 failing test to properly await coroutine
   
3. ✅ **Configure pytest-timeout**
   - Add `pytest-timeout>=2.0.0` to requirements.txt
   - Configure markers in pytest.ini
   - Or remove timeout decorators if not needed

4. ✅ **Address deprecation warnings**
   - Add warning filters to pytest.ini
   - Update deprecated API usage where critical

**Success Criteria:**
- 0 failing tests
- <10 warnings
- All tests complete in <30 seconds

**Estimated Effort:** 4-6 hours

---

### 🔄 Phase 2: Test Organization (Week 2)

**Goal:** Improve test maintainability and organization

1. 🔄 **Split large test files**
   - Break `test_log_web_server.py` into 4 modules
   - Break `test_database_infrastructure.py` into 3 modules
   - Update imports and test discovery

2. 🔄 **Standardize test documentation**
   - Add docstrings to all test methods
   - Document test scenarios and edge cases
   - Create documentation template

3. 🔄 **Create reusable fixtures**
   - Move common setup to `conftest.py`
   - Create fixtures for isolated config, mock inverter, etc.
   - Update tests to use fixtures

**Success Criteria:**
- No test file >600 lines
- 100% of tests have docstrings
- Common patterns extracted to fixtures

**Estimated Effort:** 8-12 hours

---

### 📈 Phase 3: Coverage Enhancement (Week 3-4)

**Goal:** Improve test coverage and quality

1. 📈 **Add missing test cases**
   - Identify coverage gaps
   - Add edge case tests
   - Add error handling tests

2. 📈 **Improve test assertions**
   - Replace weak assertions with specific checks
   - Add assertion messages for clarity
   - Validate all return values

3. 📈 **Add performance tests**
   - Create performance regression suite
   - Set performance baselines
   - Monitor execution time trends

**Success Criteria:**
- Code coverage >85%
- All edge cases covered
- Performance baselines established

**Estimated Effort:** 12-16 hours

---

### 🚀 Phase 4: CI/CD Integration (Week 4)

**Goal:** Enhance testing infrastructure

1. 🚀 **Add coverage reporting**
   - Configure coverage.py
   - Upload to Codecov or similar
   - Add coverage badges

2. 🚀 **Test performance tracking**
   - Track execution time trends
   - Alert on performance regressions
   - Optimize slow tests

3. 🚀 **Flakiness detection**
   - Run tests multiple times
   - Identify inconsistent results
   - Fix or quarantine flaky tests

**Success Criteria:**
- Coverage reports on all PRs
- Performance trends visible
- <1% test flakiness rate

**Estimated Effort:** 6-8 hours

---

## Testing & Validation

### Pre-Implementation Baseline

Run baseline metrics before starting improvements:

```bash
# Full test run with timing
python -m pytest test/ -v --durations=20

# Test count
python -m pytest test/ --collect-only | grep "<Function" | wc -l

# Warning count
python -m pytest test/ -q 2>&1 | grep "warning" | wc -l

# Coverage
python -m pytest test/ --cov=src --cov-report=term-missing
```

**Baseline Results (2025-12-03):**
- Total tests: 666 (648 passed, 7 failed, 11 skipped)
- Total warnings: 146
- Test execution time: 16.03 seconds
- Coverage: (to be measured)

### Post-Implementation Validation

After each phase, measure improvements:

```bash
# Phase 1 - All tests passing?
python -m pytest test/ -q
# Target: 655 passed, 11 skipped, 0 failed, <10 warnings

# Phase 2 - Better organization?
find test/ -name "*.py" -exec wc -l {} \; | awk '{if ($1 > 600) print $0}'
# Target: No files >600 lines

# Phase 3 - Better coverage?
python -m pytest test/ --cov=src --cov-report=term
# Target: >85% coverage

# Phase 4 - CI integration?
# Check GitHub Actions results
# Target: Coverage reports, performance tracking visible
```

---

## Expected Outcomes

### Phase 1 Completion
- ✅ **Test Reliability**: 100% test pass rate
- ✅ **Clean Output**: <10 warnings, clear failure messages
- ✅ **Async Patterns**: Established best practices for async testing
- ✅ **Quick Feedback**: Tests complete in <30 seconds

### Phase 2 Completion
- ✅ **Maintainability**: Smaller, focused test modules
- ✅ **Documentation**: All tests clearly documented
- ✅ **Reusability**: Common patterns extracted to fixtures
- ✅ **Discoverability**: Easy to find relevant tests

### Phase 3 Completion
- ✅ **Coverage**: >85% code coverage
- ✅ **Completeness**: All edge cases tested
- ✅ **Quality**: Strong, specific assertions
- ✅ **Performance**: Regression tests in place

### Phase 4 Completion
- ✅ **Visibility**: Coverage and performance trends tracked
- ✅ **Confidence**: Low flakiness rate (<1%)
- ✅ **Automation**: Full CI/CD integration
- ✅ **Monitoring**: Performance baselines established

---

## Risk Mitigation

### Risk 1: Breaking Changes During Refactoring
**Mitigation:**
- Make changes incrementally
- Run full test suite after each change
- Keep git history clean for easy rollback
- Review diffs carefully

### Risk 2: Tests Become Too Slow
**Mitigation:**
- Monitor test execution time
- Use pytest markers for slow tests
- Parallelize test execution where possible
- Mock external dependencies

### Risk 3: False Sense of Security from Coverage
**Mitigation:**
- Focus on meaningful tests, not just coverage numbers
- Review test quality, not just quantity
- Include edge cases and error conditions
- Manual testing for critical paths

---

## Available Test Fixtures

### Configuration Fixtures

#### `isolated_config`
Provides a standard test configuration file with commonly used settings.

```python
def test_with_isolated_config(isolated_config):
    """Test using standard test configuration"""
    charger = AutomatedPriceCharger(config_path=isolated_config)
    # Test code...
```

**Standard Configuration Includes:**
- G12w tariff (peak/off-peak pricing)
- SC component: 0.0892 PLN/kWh
- Battery SOC thresholds: critical=12%, emergency=5%
- Aggressive charging enabled

#### `custom_config`
Factory fixture for creating custom configuration files.

```python
def test_with_custom_tariff(custom_config):
    """Test with G14dynamic tariff"""
    config_path = custom_config({
        'electricity_tariff': {
            'tariff_type': 'g14dynamic',
            'sc_component_pln_kwh': 0.0892
        }
    })
    charger = AutomatedPriceCharger(config_path=config_path)
    # Test code...
```

### Database Fixtures

#### `temp_db`
Creates a temporary SQLite database file for testing.

```python
def test_database_operations(temp_db):
    """Test with temporary database"""
    # temp_db is the path to a temporary .db file
    storage = SQLiteStorage(temp_db)
    # Test code...
```

#### `storage_config`
Provides a configured StorageConfig instance.

```python
def test_with_storage_config(storage_config):
    """Test with standard storage configuration"""
    # storage_config has optimized test settings
    storage = SQLiteStorage(storage_config)
    # Test code...
```

#### `storage`
Async fixture providing a connected SQLiteStorage instance.

```python
@pytest.mark.asyncio
async def test_async_storage(storage):
    """Test with connected storage instance"""
    # storage is already connected
    await storage.store_data({'test': 'data'})
    # Automatically disconnects after test
```

---

## Related Documentation

- `docs/TEST_CONFIGURATION_ISOLATION.md` - Test isolation patterns
- `docs/INTEGRATION_TESTS.md` - Integration test guidelines
- `docs/PERFORMANCE_OPTIMIZATION_PLAN.md` - Performance testing strategy

---

## Progress Tracking

### ✅ Week 1 - Phase 1: Critical Fixes (2025-12-03) - **COMPLETE**
- [x] Fix async/await in test_price_date_behavior.py (6 tests) - **DONE**
- [x] Fix async/await in test_peak_hours_integration.py (1 test) - **DONE**
- [x] Configure pytest markers (pytest.ini) - **DONE**
- [x] Add pytest-timeout to requirements.txt - **DONE**
- [x] Verify all tests passing - **DONE** (655/655 passing)
- [x] Verify warnings reduced to <10 - **EXCEEDED** (0 warnings achieved!)

**Phase 1 Achievements:**
- ✅ 100% test pass rate (655 passed, 0 failed)
- ✅ 100% warning elimination (0 warnings, was 146)
- ✅ 7.6% performance improvement (14.81s, was 16.03s)
- ✅ Established async testing patterns with AsyncMock
- ✅ Configured pytest markers: timeout, integration, slow

### 🚧 Week 2 - Phase 2: Test Organization (2025-12-03 - In Progress)
- [x] Create reusable fixtures in conftest.py - **DONE**
  - Added `isolated_config` fixture for standard test configuration
  - Added `custom_config` factory fixture for flexible config creation
  - Existing `temp_db`, `storage_config`, `storage` fixtures available
- [ ] Add test docstrings (targeting 50% of tests)
- [ ] Document fixture usage patterns
- [ ] Identify and refactor tests to use new fixtures

**Note on File Splitting:**
- Large test files (`test_log_web_server.py`, `test_database_infrastructure.py`) are well-organized with logical class groupings
- Splitting these files would require significant refactoring with minimal benefit
- Decision: Keep files together but ensure good class/method organization and documentation

### Week 3-4 (2025-12-18 to 2025-12-31) - Phase 3: Coverage Enhancement
- [ ] Identify coverage gaps
- [ ] Add missing edge case tests
- [ ] Improve test assertions
- [ ] Add performance regression tests
- [ ] Measure and document coverage

### Week 4+ (2026-01-01+) - Phase 4: CI/CD Integration
- [ ] Configure coverage reporting in CI
- [ ] Add test performance tracking
- [ ] Implement flakiness detection
- [ ] Document testing best practices

---

**Created**: 2025-12-03  
**Last Updated**: 2025-12-03  
**Status**: Phase 1 in progress  
**Owner**: Development Team  
**Priority**: HIGH - Foundation for reliable development

