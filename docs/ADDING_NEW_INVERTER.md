# Adding New Inverter Support

## Overview

This guide explains how to add support for new inverter brands to the system. The process involves implementing an adapter that translates between the generic port interface and the vendor-specific library/API.

## Prerequisites

Before adding a new inverter:

1. **Identify vendor library**: Find a Python library for the inverter (e.g., `pyfronius`, `pysma`)
2. **Understand capabilities**: Know what operations the inverter supports
3. **Check API documentation**: Review vendor's API documentation
4. **Test hardware access**: Ensure you can connect to the inverter

## Step-by-Step Guide

### Step 1: Create Adapter File

Create a new file in `src/inverter/adapters/` for your inverter:

```
src/inverter/adapters/
├── __init__.py
├── goodwe_adapter.py          # Existing
└── fronius_adapter.py          # New adapter
```

### Step 2: Implement Adapter Class

Your adapter must implement the `InverterPort` interface. Start with this template:

```python
"""
Fronius Inverter Adapter

Adapter implementation for Fronius inverters.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Import vendor library
try:
    import pyfronius  # Example library
    FRONIUS_AVAILABLE = True
except ImportError:
    FRONIUS_AVAILABLE = False
    print("Warning: pyfronius library not available")

from ..ports.inverter_port import InverterPort
from ..models.operation_mode import OperationMode
from ..models.inverter_config import InverterConfig, SafetyConfig
from ..models.inverter_data import InverterStatus, InverterState, SensorReading
from ..models.battery_status import BatteryStatus, BatteryData
from ..ports.data_collector_port import PVData, GridData, ConsumptionData, ComprehensiveData


class FroniusInverterAdapter(InverterPort):
    """
    Fronius inverter adapter implementing the InverterPort interface.
    """
    
    # Operation mode mapping: Generic -> Vendor-specific
    OPERATION_MODE_MAP = {
        OperationMode.GENERAL: "automatic",
        OperationMode.ECO_CHARGE: "charge",
        OperationMode.ECO_DISCHARGE: "discharge",
        # Map other modes as supported by Fronius
    }
    
    def __init__(self):
        """Initialize Fronius adapter."""
        if not FRONIUS_AVAILABLE:
            raise ImportError("pyfronius library not available")
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self._inverter: Optional[Any] = None
        self._config: Optional[InverterConfig] = None
    
    @property
    def vendor_name(self) -> str:
        """Get vendor name."""
        return "fronius"
    
    @property
    def model_name(self) -> str:
        """Get inverter model name."""
        if self._inverter:
            return self._inverter.model  # Adjust to actual property
        return ""
    
    @property
    def serial_number(self) -> str:
        """Get inverter serial number."""
        if self._inverter:
            return self._inverter.serial  # Adjust to actual property
        return ""
    
    async def connect(self, config: InverterConfig) -> bool:
        """Connect to Fronius inverter."""
        # Implement connection logic
        pass
    
    async def disconnect(self) -> None:
        """Disconnect from inverter."""
        pass
    
    def is_connected(self) -> bool:
        """Check if inverter is connected."""
        return self._inverter is not None
    
    async def get_status(self) -> InverterStatus:
        """Get current inverter status."""
        # Implement status retrieval
        pass
    
    async def get_battery_status(self) -> BatteryStatus:
        """Get current battery status."""
        # Implement battery status retrieval
        pass
    
    async def read_runtime_data(self) -> Dict[str, Any]:
        """Read all runtime data from inverter."""
        # Implement runtime data reading
        pass
    
    async def check_safety_conditions(
        self, 
        safety_config: SafetyConfig
    ) -> tuple[bool, list[str]]:
        """Check if current conditions are safe."""
        # Implement safety checks
        pass
    
    # Implement all other required methods...
    # (See InverterPort interface for complete list)
```

### Step 3: Implement Required Methods

Implement all methods from the `InverterPort` interface:

#### Connection Management

```python
async def connect(self, config: InverterConfig) -> bool:
    """Connect to inverter."""
    self._config = config
    
    # Validate vendor
    if config.vendor.lower() != "fronius":
        raise ValueError(f"Invalid vendor for Fronius adapter: {config.vendor}")
    
    # Extract vendor-specific config
    device_id = config.vendor_config.get('device_id', 1)
    
    # Connect with retries
    for attempt in range(config.retries):
        try:
            if attempt > 0:
                await asyncio.sleep(config.retry_delay)
            
            # Create connection (adjust to vendor library)
            self._inverter = await pyfronius.Fronius(
                host=config.ip_address,
                port=config.port,
                device_id=device_id,
                timeout=config.timeout
            )
            
            self.logger.info(f"Connected to {self.model_name}")
            return True
            
        except Exception as e:
            if attempt < config.retries - 1:
                self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            else:
                self.logger.error(f"Failed to connect: {e}")
    
    return False
```

#### Data Collection

```python
async def collect_battery_data(self) -> BatteryData:
    """Collect battery data."""
    if not self._inverter:
        raise RuntimeError("Inverter not connected")
    
    try:
        # Get battery data from vendor library
        battery_info = await self._inverter.get_battery_info()
        
        # Map to generic BatteryStatus
        battery_status = BatteryStatus(
            soc_percent=float(battery_info['soc']),
            voltage=float(battery_info['voltage']),
            current=float(battery_info['current']),
            power=float(battery_info['power']),
            temperature=float(battery_info['temperature']),
            is_charging=battery_info['current'] < 0,
            is_discharging=battery_info['current'] > 0,
            timestamp=datetime.now()
        )
        
        return BatteryData(
            status=battery_status,
            daily_charge_kwh=float(battery_info.get('daily_charge', 0)),
            daily_discharge_kwh=float(battery_info.get('daily_discharge', 0))
        )
        
    except Exception as e:
        self.logger.error(f"Failed to collect battery data: {e}")
        raise RuntimeError(f"Failed to collect battery data: {e}")
```

#### Command Execution

```python
async def set_operation_mode(
    self,
    mode: OperationMode,
    power_w: int = 0,
    min_soc: int = 0
) -> bool:
    """Set inverter operation mode."""
    if not self._inverter:
        raise RuntimeError("Inverter not connected")
    
    try:
        # Map generic mode to vendor mode
        if mode not in self.OPERATION_MODE_MAP:
            self.logger.error(f"Unsupported operation mode: {mode}")
            return False
        
        vendor_mode = self.OPERATION_MODE_MAP[mode]
        
        # Set mode (adjust to vendor API)
        await self._inverter.set_mode(vendor_mode)
        
        self.logger.info(f"Operation mode set to {mode}")
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to set operation mode: {e}")
        return False
```

### Step 4: Register Adapter in Factory

Update `src/inverter/factory/inverter_factory.py`:

```python
from ..adapters.fronius_adapter import FroniusInverterAdapter

class InverterFactory:
    """Factory for creating inverter adapters."""
    
    _ADAPTERS = {
        'goodwe': GoodWeInverterAdapter,
        'fronius': FroniusInverterAdapter,  # Add new adapter
        # Add more as needed
    }
```

### Step 5: Update Adapter Module

Update `src/inverter/adapters/__init__.py`:

```python
from .goodwe_adapter import GoodWeInverterAdapter
from .fronius_adapter import FroniusInverterAdapter

__all__ = [
    'GoodWeInverterAdapter',
    'FroniusInverterAdapter',
]
```

### Step 6: Configuration

Document vendor-specific configuration in `config/master_coordinator_config.yaml`:

```yaml
inverter:
  vendor: "fronius"
  ip_address: "192.168.1.100"
  port: 80
  timeout: 5
  retries: 3
  retry_delay: 2.0
  
  # Fronius-specific settings (optional)
  device_id: 1
  scan_interval: 10
```

### Step 7: Create Tests

Create comprehensive tests in `test/test_fronius_adapter.py`:

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

from inverter.adapters.fronius_adapter import FroniusInverterAdapter
from inverter.models.inverter_config import InverterConfig
from inverter.factory.inverter_factory import InverterFactory


class TestFroniusAdapter:
    """Test Fronius adapter implementation."""
    
    @pytest.fixture
    def adapter(self):
        """Create Fronius adapter for testing."""
        return FroniusInverterAdapter()
    
    def test_vendor_name(self, adapter):
        """Test vendor name property."""
        assert adapter.vendor_name == "fronius"
    
    @pytest.mark.asyncio
    async def test_connect(self, adapter):
        """Test connecting to inverter."""
        config = InverterConfig(
            vendor="fronius",
            ip_address="192.168.1.100",
            vendor_config={'device_id': 1}
        )
        
        with patch('pyfronius.Fronius', new_callable=AsyncMock) as mock_fronius:
            mock_inverter = Mock()
            mock_fronius.return_value = mock_inverter
            
            result = await adapter.connect(config)
            
            assert result is True
            assert adapter.is_connected() is True
    
    @pytest.mark.asyncio
    async def test_get_battery_status(self, adapter):
        """Test getting battery status."""
        # Mock battery data
        # Test data collection
        pass
    
    # Add more tests for all critical operations


def test_fronius_factory_integration():
    """Test Fronius adapter can be created via factory."""
    config = InverterConfig(
        vendor="fronius",
        ip_address="192.168.1.100"
    )
    
    adapter = InverterFactory.create_inverter(config)
    
    assert adapter is not None
    assert adapter.vendor_name == "fronius"
```

Run tests:

```bash
pytest test/test_fronius_adapter.py -v
```

### Step 8: Documentation

Create vendor-specific documentation in `docs/FRONIUS_INTEGRATION.md`:

- Supported models
- Configuration options
- Known limitations
- Troubleshooting
- Example usage

### Step 9: Dependencies

Add vendor library to `requirements.txt`:

```
# Existing
goodwe==0.4.8

# New
pyfronius==0.7.2
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Operation Mode Mapping

Different inverters have different operation modes. Map generic modes to vendor-specific ones:

### Example Mapping Table

| Generic Mode | GoodWe | Fronius | SMA |
|-------------|--------|---------|-----|
| GENERAL | GENERAL | Automatic | Auto |
| ECO | ECO | Optimize | Optimized |
| ECO_CHARGE | ECO_CHARGE | ChargeFromGrid | GridCharge |
| ECO_DISCHARGE | ECO_DISCHARGE | FeedIn | GridFeed |
| OFF_GRID | OFF_GRID | Backup | IslandMode |

If an inverter doesn't support a mode, log a warning and return False.

## Testing Checklist

Before submitting your adapter:

- [ ] All `InverterPort` methods implemented
- [ ] Connection logic with retries works
- [ ] Data collection returns correct types
- [ ] Command execution tested
- [ ] Safety checks implemented
- [ ] Operation mode mapping complete
- [ ] Error handling comprehensive
- [ ] Unit tests written (>80% coverage)
- [ ] Integration tests pass
- [ ] Documentation complete
- [ ] Example configuration provided

## Common Pitfalls

### 1. Incomplete Interface Implementation

**Problem**: Missing required methods from `InverterPort`

**Solution**: Use IDE or mypy to check interface compliance:

```bash
mypy src/inverter/adapters/fronius_adapter.py
```

### 2. Incorrect Data Type Mapping

**Problem**: Vendor library returns strings, generic model expects floats

**Solution**: Always convert and validate types:

```python
soc = float(vendor_data.get('soc', 0.0))
```

### 3. Missing Error Handling

**Problem**: Exceptions crash the system

**Solution**: Wrap all vendor library calls in try/except:

```python
try:
    data = await self._inverter.get_data()
except Exception as e:
    self.logger.error(f"Failed: {e}")
    raise RuntimeError(f"Operation failed: {e}")
```

### 4. Hardcoded Values

**Problem**: Using hardcoded values instead of configuration

**Solution**: Always read from config:

```python
# Bad
device_id = 1

# Good
device_id = config.vendor_config.get('device_id', 1)
```

### 5. Forgetting Async/Await

**Problem**: Not using async/await for I/O operations

**Solution**: All network operations should be async:

```python
async def connect(self, config: InverterConfig) -> bool:
    await self._inverter.connect()  # Use await
```

## Reference Implementations

Study existing adapters:

- **GoodWe Adapter**: `src/inverter/adapters/goodwe_adapter.py` - Complete reference
- **Port Interfaces**: `src/inverter/ports/` - Interface definitions
- **Models**: `src/inverter/models/` - Data structures

## Getting Help

- Review [Inverter Abstraction Documentation](INVERTER_ABSTRACTION.md)
- Check existing adapter implementations
- Refer to vendor library documentation
- Test with mock data first before hardware

## Submission

When ready to contribute your adapter:

1. Ensure all tests pass
2. Add documentation
3. Update README with supported inverter
4. Create pull request with:
   - Adapter implementation
   - Tests
   - Documentation
   - Configuration example

Your contribution helps the community support more hardware! 🎉

