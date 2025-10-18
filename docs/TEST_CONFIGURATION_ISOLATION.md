# Test Configuration Isolation

## Overview

All tests in this project are now **isolated from the production configuration**. This means you can change your tariff configuration in `config/master_coordinator_config.yaml` without breaking any tests.

## Why This Matters

Previously, tests loaded the real production configuration file (`config/master_coordinator_config.yaml`), which caused:

- ❌ **Tests failing when you changed your tariff** (e.g., from G12w to G14dynamic)
- ❌ **Hardcoded test expectations** that only worked for specific tariff settings
- ❌ **Lack of true test isolation** - production config changes broke tests

## How It Works Now

Each test suite now:

1. ✅ Creates a **temporary, isolated configuration** in `setUp()`
2. ✅ Passes this temporary config to all components under test
3. ✅ Cleans up the temporary config in `tearDown()`
4. ✅ Uses **tariff-agnostic assertions** or documents the tariff being tested

## Test Configuration Structure

All test suites use a standard test configuration:

```python
test_config = {
    'electricity_pricing': {
        'sc_component_net': 0.0892,
        'sc_component_gross': 0.1097,
        'minimum_price_floor': 0.0050
    },
    'electricity_tariff': {
        'tariff_type': 'g12w',  # Tests use G12w by default
        'sc_component_pln_kwh': 0.0892,
        'distribution_pricing': {
            'g12w': {
                'type': 'time_based',
                'peak_hours': {'start': 7, 'end': 22},
                'prices': {'peak': 0.3566, 'off_peak': 0.0749}
            }
        }
    },
    'battery_management': {
        'soc_thresholds': {
            'critical': 12,
            'emergency': 5
        }
    },
    'cheapest_price_aggressive_charging': {
        'enabled': True
    }
}
```

## Example: Before and After

### Before (Coupled to Production Config)

```python
def setUp(self):
    self.charger = AutomatedPriceCharger()  # Loads production config!

def test_price_calculation(self):
    price = self.charger.calculate_final_price(0.300, timestamp)
    # This assertion only works if production config has G12w tariff!
    self.assertAlmostEqual(price, 745.8)  # Fails if you switch to G14dynamic
```

### After (Isolated Test Config)

```python
def setUp(self):
    # Create temporary test config
    self.temp_config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(test_config, self.temp_config_file)
    self.temp_config_file.close()
    
    # Pass test config to component
    self.charger = AutomatedPriceCharger(config_path=self.temp_config_file.name)

def tearDown(self):
    # Clean up
    if hasattr(self, 'temp_config_file') and os.path.exists(self.temp_config_file.name):
        os.unlink(self.temp_config_file.name)

def test_price_calculation(self):
    price = self.charger.calculate_final_price(0.300, timestamp)
    # Assertion is documented with the tariff used in test config
    # 300 + 89.2 + 356.6 (G12w peak) = 745.8 PLN/MWh
    self.assertAlmostEqual(price, 745.8)  # Works regardless of production config!
```

## Test Suites Updated

The following test suites have been refactored for configuration isolation:

1. **`test/test_pricing_consistency.py`** - 17 tests
   - All `AutomatedPriceCharger`, `PriceWindowAnalyzer`, etc. instances use isolated configs
   
2. **`test/test_smart_charging_strategy.py`** - 9 tests
   - All charging decision tests use isolated configs
   
3. **`test/test_price_date_behavior.py`** - 9 tests
   - Date handling and price transitions use isolated configs

## Benefits

✅ **Freedom to Change Production Config**: Switch between G12w, G14dynamic, G11, etc. without breaking tests

✅ **True Unit Testing**: Tests are isolated from external configuration state

✅ **Explicit Test Assumptions**: Test configs make it clear what tariff/settings are being tested

✅ **Parallel Test Execution**: No shared config state means tests can run in parallel safely

✅ **Easier Debugging**: When a test fails, you know it's not due to your production config changes

## Running Tests

All tests now pass regardless of your production tariff configuration:

```bash
# Run all tests
python -m pytest test/ -v

# Run specific test suite
python -m pytest test/test_pricing_consistency.py -v

# Run tests even after changing your production tariff
vim config/master_coordinator_config.yaml  # Change tariff_type to g14dynamic
python -m pytest test/ -v  # Still passes! ✅
```

## Adding New Tests

When writing new tests, always use the isolated config pattern:

```python
import tempfile
import yaml

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        # Define test config
        test_config = {
            'electricity_tariff': {
                'tariff_type': 'g12w',  # Or whatever tariff you want to test
                # ... rest of config
            }
        }
        
        # Create temporary config file
        self.temp_config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(test_config, self.temp_config_file)
        self.temp_config_file.close()
        
        # Pass to components under test
        self.component = MyComponent(config_path=self.temp_config_file.name)
    
    def tearDown(self):
        # Clean up
        if hasattr(self, 'temp_config_file') and os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)
```

## Testing Multiple Tariffs

If you want to test behavior across different tariffs, create separate test methods or parameterized tests:

```python
def test_price_calculation_g12w(self):
    """Test price calculation with G12w tariff"""
    # Create config with g12w
    # ...
    
def test_price_calculation_g14dynamic(self):
    """Test price calculation with G14dynamic tariff"""
    # Create config with g14dynamic
    # ...
```

## Summary

Your tests are now **completely independent** of your production configuration. Feel free to experiment with different tariffs, pricing strategies, and settings without worrying about breaking the test suite! 🚀

