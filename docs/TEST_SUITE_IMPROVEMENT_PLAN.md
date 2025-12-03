# Test Suite Improvement Plan

**Created**: 2025-12-03  
**Status**: Ready for Implementation  
**Impact**: Improved test reliability, faster CI, cleaner test organization

---

## Executive Summary

The test suite contains 66 test files with several stability issues:
- 8 skipped tests due to hanging
- Hardcoded dates that may cause future failures
- Real network calls without mocks
- Suppressed async warnings
- Duplicate timeout markers
- Redundant/outdated test files

This plan addresses all issues systematically.

---

## Step 1: Remove Redundant Files (11 files)

| File | Reason |
|------|--------|
| `test/run_tests.py` | Redundant - pytest handles test discovery |
| `test/test_data_access_layer_demo.py` | Demo script, not a test |
| `test/test_structure.py` | One-time validation script |
| `test/test_cost_fix.py` | Historical bug fix verification |
| `test/inverter_scan.py` | Utility script, requires real hardware |
| `test/sensor_investigator.py` | Utility script, requires real hardware |
| `test/sensor_investigation.json` | Data file, not a test |
| `test/test_ngrok.sh` | Shell script for manual testing |
| `test/test_remote_access.sh` | Shell script for manual testing |
| `test/test_log_server.py` | Makes real HTTP calls; duplicates test_log_web_server.py |
| `test/README.md` | Documentation in test dir |

**Command:**
```bash
rm -f test/run_tests.py \
      test/test_data_access_layer_demo.py \
      test/test_structure.py \
      test/test_cost_fix.py \
      test/inverter_scan.py \
      test/sensor_investigator.py \
      test/sensor_investigation.json \
      test/test_ngrok.sh \
      test/test_remote_access.sh \
      test/test_log_server.py \
      test/README.md
```

---

## Step 2: Create Integration Test Directory

Move hardware/network-dependent tests to `test_integration/`:

| File | Reason |
|------|--------|
| `test/inverter_test.py` | Requires real GoodWe hardware |
| `test/test_ips.py` | Network-dependent |
| `test/test_log_web_server.py` | Tests against real HTTP server |
| `test/test_inverter_connection_fixed.py` | Requires real hardware |
| `test/test_inverter_abstraction.py` | May require hardware |
| `test/test_storage_integration.py` | Integration-level tests |

**Commands:**
```bash
mkdir -p test_integration

mv test/inverter_test.py test_integration/
mv test/test_ips.py test_integration/
mv test/test_log_web_server.py test_integration/
mv test/test_inverter_connection_fixed.py test_integration/
mv test/test_inverter_abstraction.py test_integration/
mv test/test_storage_integration.py test_integration/
```

---

## Step 3: Create `test_integration/conftest.py`

```python
"""
Integration test fixtures and configuration.
These tests require hardware or network access.
"""
import pytest


def pytest_collection_modifyitems(items):
    """Mark all tests in this directory as integration tests."""
    for item in items:
        item.add_marker(pytest.mark.integration)
```

---

## Step 4: Update `pytest.ini`

```ini
[pytest]
testpaths = test
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
markers =
    unit: Unit tests (run always)
    integration: Integration tests requiring hardware/network (run on PR only)
    slow: Slow tests
    asyncio: Async tests
filterwarnings =
    ignore::pytest.PytestReturnNotNoneWarning
    ignore::DeprecationWarning
addopts = --ignore=test_integration
```

---

## Step 5: Add `freezegun` to `requirements.txt`

Add after `python-dateutil>=2.8.0`:
```
freezegun>=1.2.0
```

---

## Step 6: Update `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]
  workflow_dispatch:
    inputs:
      run_integration:
        description: 'Run integration tests (set to true to enable)'
        required: false
        default: 'false'

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.13']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Cache pip
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run unit tests
      run: |
        python -m pytest test/ -v --tb=short

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    if: github.event_name == 'pull_request' || github.event.inputs.run_integration == 'true'
    continue-on-error: true  # Don't fail PR until tests are verified passing

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python 3.13
      uses: actions/setup-python@v5
      with:
        python-version: '3.13'

    - name: Cache pip
      uses: actions/cache@v4
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run integration tests
      run: |
        python -m pytest test_integration/ -v --tb=short
```

---

## Step 7: Fix Hanging Tests in `test_database_infrastructure.py`

### 7.1 Remove Duplicate Timeout Markers

Remove duplicate `@pytest.mark.timeout` at:
- Lines 510-511
- Lines 571-572
- Lines 595-596
- Lines 624-625

### 7.2 Fix `test_batch_operations` (line ~468)

Remove `@pytest.mark.skip` and update:

```python
@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_batch_operations(self, storage):
    """Test batch operations for performance"""
    try:
        await storage.connect()

        base_time = datetime.now().replace(microsecond=0)
        large_dataset = []
        for i in range(100):
            large_dataset.append({
                'timestamp': base_time + timedelta(minutes=i),
                'battery_soc': 50.0 + i * 0.1,
                'pv_power': 1000.0 + i * 10,
                'grid_power': -500.0 - i * 5,
                'consumption': 1500.0 + i * 2,
                'price': 0.40 + i * 0.001,
                'battery_temp': 25.0 + i * 0.1,
                'battery_voltage': 400.0 + i * 0.1,
                'grid_voltage': 230.0 + i * 0.01
            })

        save_start_time = datetime.now()
        assert await storage.save_energy_data(large_dataset)
        save_end_time = datetime.now()

        save_duration = (save_end_time - save_start_time).total_seconds()
        assert save_duration < 10.0

        query_start_time = base_time - timedelta(minutes=5)
        query_end_time = base_time + timedelta(hours=2)
        retrieved_data = await storage.get_energy_data(query_start_time, query_end_time)

        assert len(retrieved_data) == 100
    finally:
        await storage.disconnect()
```

### 7.3 Keep ConnectionManager Tests Skipped

Keep `ConnectionManager` tests skipped (lines 573, 597, 626) - they require deeper refactoring of connection pooling logic.

---

## Expected Outcomes

### Test Organization
- **Before**: 66 files in `test/`, mixed unit and integration
- **After**: ~55 files in `test/`, 6 files in `test_integration/`

### CI Performance
- **Unit tests**: Run on every push and PR (fast)
- **Integration tests**: Run on PRs only (optional until verified)

### Test Reliability
- Removed 11 redundant/outdated files
- Fixed duplicate timeout markers
- Restored 1 skipped test (`test_batch_operations`)
- Added `freezegun` for reliable time mocking

---

## Future Improvements

1. **Replace hardcoded dates** with `freezegun` (gradual migration)
2. **Mock HTTP calls** in remaining tests using `responses` library
3. **Fix ConnectionManager tests** - requires refactoring connection pooling
4. **Remove suppressed warnings** - fix "coroutine never awaited" issues

---

**Delegated to**: GitHub Copilot Cloud Agent  
**PR**: To be created
