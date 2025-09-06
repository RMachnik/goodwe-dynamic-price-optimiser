# GoodWe Dynamic Price Optimiser - Test Suite

This directory contains comprehensive tests for the GoodWe Dynamic Price Optimiser system.

## Test Files

### 1. `test_price_date_behavior.py`
Tests the price data date behavior and transitions for the Polish electricity market:
- ✅ Date transition at midnight
- ✅ Price data fetching for correct business dates
- ✅ Publication timing correctness
- ✅ Full day price coverage (00:00-24:00)
- ✅ Error handling for API failures
- ✅ Current price calculation within and outside day ranges

### 2. `test_scoring_algorithm.py`
Tests the multi-factor decision engine scoring algorithm:
- ✅ Price score calculation (low, medium, high, very high prices)
- ✅ Battery score calculation (critical, low, medium, high, full levels)
- ✅ PV score calculation (no, low, medium, high production)
- ✅ Consumption score calculation (very low, low, medium, high consumption)
- ✅ Weighted total score calculation
- ✅ Decision action determination (start, stop, continue, none)
- ✅ Confidence calculation
- ✅ Reasoning generation
- ✅ No price data handling

### 3. `test_master_coordinator_integration.py`
Integration tests for the master coordinator:
- ✅ Initialization success and failure scenarios
- ✅ Decision timing logic
- ✅ Charging decision making
- ✅ Emergency conditions checking
- ✅ GoodWe Lynx-D compliance checking
- ✅ System state updates
- ✅ Status reporting
- ✅ Emergency stop functionality
- ✅ Decision execution (start, stop, continue, none)

## Running Tests

### Run All Tests
```bash
cd test
python run_tests.py
```

### Run Specific Test Suite
```bash
cd test
python run_tests.py price_date      # Price date behavior tests
python run_tests.py scoring         # Scoring algorithm tests
python run_tests.py integration     # Master coordinator integration tests
```

### Run Individual Test Files
```bash
cd test
python -m unittest test_price_date_behavior
python -m unittest test_scoring_algorithm
python -m unittest test_master_coordinator_integration
```

## Test Coverage

The test suite covers:

1. **Date Behavior**: Verifies that the system correctly handles Polish electricity market day-ahead pricing
2. **Scoring Algorithm**: Tests all scoring components and decision logic
3. **Integration**: Tests the complete flow from data collection to decision execution
4. **Error Handling**: Tests various failure scenarios and edge cases
5. **Safety Compliance**: Tests GoodWe Lynx-D safety features and emergency conditions

## Key Test Scenarios

### Polish Electricity Market Timing
- Prices for day X are published on day X-1 around 1-2 PM
- System correctly fetches prices for current calendar date
- Automatic transition to next day's prices at midnight

### Multi-Factor Decision Making
- Price weight: 40%
- Battery weight: 25%
- PV weight: 20%
- Consumption weight: 15%
- Critical battery override (≤20% SoC)

### Safety and Compliance
- Battery temperature limits (0°C - 53°C)
- Battery voltage limits (320V - 480V)
- Emergency stop conditions
- GoodWe Lynx-D compliance checking

## Test Data

Tests use mock data that simulates:
- Real Polish electricity price data structure
- Battery, PV, and consumption data
- Various system states and conditions
- API responses and failures

## Continuous Integration

These tests should be run:
- Before any code changes
- After implementing new features
- During continuous integration builds
- Before production deployments
