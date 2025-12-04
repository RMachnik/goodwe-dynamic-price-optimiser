# Testing Guide

> **Created**: 2025-12-04  
> **Purpose**: Guide for writing high-quality, well-documented tests

---

## Overview

This guide provides standards and best practices for writing tests in the GoodWe Dynamic Price Optimiser project. Following these guidelines ensures tests are maintainable, understandable, and reliable.

---

## Test Documentation Standards

### Module-Level Docstrings

Every test module should start with a comprehensive docstring explaining:
- What functionality is being tested
- Why these tests are important
- Any special considerations or dependencies

**Example:**
```python
#!/usr/bin/env python3
"""
Tests for PSE Peak Hours Integration

This module tests the integration with Polish Power System (PSE) peak hours data,
including async data fetching, caching behavior, and usage code mappings.

The PSE system provides forecasts for grid load and usage patterns, which are used
to optimize battery charging and discharging decisions.
"""
```

### Class-Level Docstrings

Test classes should have clear docstrings describing the component or feature being tested:

```python
class TestBatterySellingEngine(unittest.TestCase):
    """
    Test battery selling decision engine.
    
    Verifies that the engine correctly:
    - Detects selling opportunities based on price thresholds
    - Calculates expected revenue accurately
    - Respects SOC constraints and safety limits
    """
```

### Method-Level Docstrings

Every test method must have a docstring that includes:
1. **Brief summary**: One-line description of what is tested
2. **Scenario**: Initial conditions and setup
3. **Expected behavior**: What should happen
4. **Edge cases** (if applicable): Special conditions being tested

**Template:**
```python
def test_feature_name(self):
    """
    Test [feature] under [specific conditions].
    
    Scenario:
        - [Initial state]
        - [Action performed]
        - [Context or configuration]
    
    Expected behavior:
        - [What should happen]
        - [Expected results]
    
    Edge cases:
        - [Special condition 1]
        - [Special condition 2]
    """
```

**Good Example:**
```python
def test_parse_and_cache(self):
    """
    Test PSE peak hours parsing and caching with async support.
    
    This test verifies:
    1. Async fetching of peak hours data from PSE API
    2. Correct parsing of usage forecast codes and labels
    3. Caching behavior to avoid redundant API calls
    
    Scenario:
    - Mock PSE API response with 2 forecast entries
    - Fetch data and verify correct parsing
    - Second fetch should use cache (no API call)
    
    Expected behavior:
    - First call: Makes API request, returns 2 peak hour records
    - Usage code 3 maps to "WYMAGANE OGRANICZANIE" label
    - Second call: Uses cache, no API request made
    """
```

**Bad Example (Avoid):**
```python
def test_feature(self):
    """Test feature"""  # Too vague
    # Test code...
```

---

## Test Organization

### File Naming

Test files should follow the pattern: `test_<module_name>.py`

Examples:
- `test_battery_selling_engine.py`
- `test_price_date_behavior.py`
- `test_peak_hours_integration.py`

### Test Grouping

Group related tests into classes:

```python
class TestBatterySellingOpportunityDetection(unittest.TestCase):
    """Tests for selling opportunity detection logic"""
    
    def test_high_price_triggers_opportunity(self):
        """..."""
    
    def test_low_price_no_opportunity(self):
        """..."""
    
    def test_insufficient_soc_blocks_opportunity(self):
        """..."""


class TestBatterySellingRevenueCalculation(unittest.TestCase):
    """Tests for revenue calculation accuracy"""
    
    def test_revenue_calculation_basic(self):
        """..."""
    
    def test_revenue_with_efficiency_factor(self):
        """..."""
```

---

## Using Test Fixtures

### Available Fixtures

The project provides several pytest fixtures in `test/conftest.py`:

#### `isolated_config`
Provides a standard test configuration with G12w tariff.

**Usage:**
```python
def test_with_standard_config(isolated_config):
    """Test using standard G12w configuration"""
    charger = AutomatedPriceCharger(config_path=isolated_config)
    # Test code...
```

#### `custom_config`
Factory fixture for creating custom configurations.

**Usage:**
```python
def test_with_g14dynamic(custom_config):
    """Test with G14dynamic tariff configuration"""
    config_path = custom_config({
        'electricity_tariff': {
            'tariff_type': 'g14dynamic',
            'sc_component_pln_kwh': 0.0892
        }
    })
    charger = AutomatedPriceCharger(config_path=config_path)
    # Test code...
```

#### `temp_db`
Creates a temporary SQLite database for testing.

**Usage:**
```python
def test_database_operations(temp_db):
    """Test with temporary database"""
    storage = SQLiteStorage(temp_db)
    # Test code...
```

#### `storage` (async)
Provides a connected SQLiteStorage instance.

**Usage:**
```python
@pytest.mark.asyncio
async def test_async_storage(storage):
    """Test with connected storage instance"""
    await storage.store_data({'test': 'data'})
    # Automatically disconnects after test
```

### Benefits of Using Fixtures

1. **Consistency**: All tests use the same baseline configuration
2. **Isolation**: Each test gets a fresh, independent setup
3. **Cleanup**: Automatic resource cleanup after tests
4. **Reusability**: No code duplication across tests

---

## Async Testing Patterns

### Using asyncio.run()

For unittest-based tests calling async functions:

```python
def test_async_function(self):
    """Test async function with asyncio.run()"""
    # Use asyncio.run() to execute async code in sync test
    result = asyncio.run(self.charger.fetch_today_prices())
    self.assertIsNotNone(result)
```

### Using @pytest.mark.asyncio

For pure async tests with pytest:

```python
@pytest.mark.asyncio
async def test_async_with_pytest():
    """Test using pytest async support"""
    collector = PSEPeakHoursCollector(config)
    result = await collector.fetch_peak_hours()
    assert len(result) > 0
```

### Mocking Async Functions

Use `AsyncMock` for mocking async methods:

```python
from unittest.mock import AsyncMock, patch

def test_with_async_mock(self):
    """Test with async mock"""
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={'data': 'value'})
        mock_get.return_value.__aenter__.return_value = mock_response
        
        result = asyncio.run(fetch_data())
        # Assertions...
```

---

## Test Assertions

### Use Specific Assertions

**Good:**
```python
self.assertEqual(result['action'], 'start_charging')
self.assertAlmostEqual(result['expected_revenue'], 12.50, places=2)
self.assertIn('price_threshold_met', result['reasons'])
```

**Bad:**
```python
self.assertTrue(result)  # What does True mean?
self.assertTrue(result['action'] == 'start_charging')  # Use assertEqual
```

### Add Assertion Messages

For complex conditions, add failure messages:

```python
self.assertTrue(
    price > threshold,
    f"Price {price} should be above threshold {threshold}"
)
```

---

## Test Coverage Goals

### Priority Levels

1. **Critical (Must Have)**: Core business logic, safety features, financial calculations
2. **High**: Integration points, error handling, edge cases
3. **Medium**: UI components, utility functions
4. **Low**: Logging, formatting, display logic

### Coverage Targets

- **Overall**: >85% code coverage
- **Critical modules**: >95% coverage
- **New code**: 100% coverage required

### Running Coverage

```bash
# Generate coverage report
python -m pytest test/ --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

---

## Integration Tests

### Marking Integration Tests

Tests requiring external resources should be marked:

```python
@pytest.mark.integration
def test_real_inverter_connection():
    """Test connection to actual GoodWe inverter"""
    # This test requires real hardware
    inverter = GoodWeInverter(ip='192.168.1.100')
    # Test code...
```

### Running Integration Tests

```bash
# Skip integration tests (default)
python -m pytest test/

# Run only integration tests
python -m pytest test/ -m integration

# Run with external resources enabled
RUN_EXTERNAL_TESTS=1 python -m pytest test/
```

See `docs/INTEGRATION_TESTS.md` for more details.

---

## Common Patterns

### Testing Configuration Isolation

Always use isolated configurations to avoid depending on production settings:

```python
def setUp(self):
    """Set up test with isolated configuration"""
    test_config = {
        'electricity_tariff': {'tariff_type': 'g12w'},
        'battery_management': {'soc_thresholds': {'critical': 12}}
    }
    
    self.temp_config_file = tempfile.NamedTemporaryFile(
        mode='w', suffix='.yaml', delete=False
    )
    yaml.dump(test_config, self.temp_config_file)
    self.temp_config_file.close()
    
    self.component = MyComponent(config_path=self.temp_config_file.name)

def tearDown(self):
    """Clean up test resources"""
    if hasattr(self, 'temp_config_file'):
        os.unlink(self.temp_config_file.name)
```

### Testing Time-Dependent Code

Use mocking for datetime to control time in tests:

```python
with patch('automated_price_charging.datetime') as mock_datetime:
    mock_datetime.now.return_value = datetime(2025, 9, 6, 10, 30)
    mock_datetime.strftime = datetime.strftime
    
    result = self.charger.get_current_price()
    # Test with fixed time...
```

### Testing Error Conditions

Always test both success and failure paths:

```python
def test_error_handling_api_failure(self):
    """Test graceful handling of API failures"""
    mock_get.side_effect = Exception("Network error")
    
    result = asyncio.run(self.charger.fetch_today_prices())
    
    # Should return None on error, not raise exception
    self.assertIsNone(result)
```

---

## Performance Testing

### Test Execution Time

Mark slow tests:

```python
@pytest.mark.slow
def test_large_dataset_processing():
    """Test processing of large dataset (slow)"""
    # Test code that takes >5 seconds...
```

Run without slow tests:
```bash
python -m pytest test/ -m "not slow"
```

### Performance Regression Tests

Add performance benchmarks for critical operations:

```python
def test_price_calculation_performance(self):
    """Ensure price calculations complete within reasonable time"""
    start = time.time()
    for _ in range(100):
        self.charger.calculate_final_price(0.300, datetime.now())
    duration = time.time() - start
    
    # Should process 100 calculations in < 1 second
    self.assertLess(duration, 1.0, 
                   f"Performance regression: {duration:.2f}s")
```

---

## Debugging Failed Tests

### Run Specific Test

```bash
# Run single test file
python -m pytest test/test_battery_selling.py -v

# Run single test method
python -m pytest test/test_battery_selling.py::TestBatterySelling::test_opportunity_detection -v

# Run tests matching pattern
python -m pytest test/ -k "battery_selling" -v
```

### Show Full Output

```bash
# Show print statements
python -m pytest test/ -v -s

# Show full diff on assertion failures
python -m pytest test/ -vv

# Show local variables on failure
python -m pytest test/ -l
```

### Stop on First Failure

```bash
python -m pytest test/ -x  # Stop on first failure
python -m pytest test/ --maxfail=3  # Stop after 3 failures
```

---

## Test Maintenance

### Keeping Tests Green

1. **Run tests before committing**: `python -m pytest test/ -q`
2. **Fix broken tests immediately**: Don't commit with failing tests
3. **Update tests with code changes**: Keep tests in sync with implementation
4. **Monitor CI**: Check test results in CI pipeline

### Refactoring Tests

When tests become hard to maintain:

1. **Extract common setup**: Move to fixtures or setUp methods
2. **Split large test classes**: One class per feature
3. **Parametrize similar tests**: Use `@pytest.mark.parametrize`
4. **Remove duplicate assertions**: Create helper methods

### Deprecating Tests

When a feature is removed:

```python
@pytest.mark.skip(reason="Feature removed in v2.0")
def test_old_feature(self):
    """Test for deprecated feature (kept for reference)"""
    pass
```

---

## Related Documentation

- `docs/TEST_CONFIGURATION_ISOLATION.md` - Configuration isolation patterns
- `docs/INTEGRATION_TESTS.md` - Integration test guidelines
- `docs/TEST_SUITE_QUALITY_IMPROVEMENT_PLAN.md` - Test suite improvement roadmap

---

## Quick Reference

### Test Checklist

Before committing tests, verify:

- [ ] Module has descriptive docstring
- [ ] Each test method has detailed docstring
- [ ] Tests use isolated configuration (not production config)
- [ ] Async tests properly await coroutines
- [ ] Mocks are properly configured and cleaned up
- [ ] Assertions are specific and include messages
- [ ] Tests pass locally: `python -m pytest test/ -q`
- [ ] No warnings: Check pytest output
- [ ] Coverage is adequate for new code

### Common Commands

```bash
# Run all tests
python -m pytest test/ -q

# Run with coverage
python -m pytest test/ --cov=src --cov-report=term-missing

# Run specific file
python -m pytest test/test_battery_selling.py -v

# Run tests matching pattern
python -m pytest test/ -k "selling" -v

# Skip slow tests
python -m pytest test/ -m "not slow"

# Stop on first failure
python -m pytest test/ -x

# Show print statements
python -m pytest test/ -s
```

---

**Created**: 2025-12-04  
**Status**: Living Document  
**Maintained By**: Development Team
