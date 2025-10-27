# Inverter Abstraction Layer

## Overview

The Inverter Abstraction Layer provides a vendor-agnostic interface for inverter integration using the **Port and Adapter Pattern** (also known as Hexagonal Architecture). This design enables the energy management algorithm to work with multiple inverter brands while maintaining clean separation between business logic and hardware integration.

## Architecture

### Port and Adapter Pattern

The abstraction follows the port and adapter pattern:

- **Ports** (`src/inverter/ports/`): Define interfaces that the application needs
- **Adapters** (`src/inverter/adapters/`): Implement ports for specific inverter vendors
- **Models** (`src/inverter/models/`): Define vendor-agnostic data structures
- **Factory** (`src/inverter/factory/`): Creates appropriate adapter based on configuration

```
┌─────────────────────────────────────────┐
│     Energy Management Algorithm         │
│  (price optimization, charging logic)   │
└────────────────┬────────────────────────┘
                 │
                 │ uses
                 ▼
┌─────────────────────────────────────────┐
│          InverterPort Interface          │
│  (connect, read_data, set_mode, etc.)   │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┬───────────┐
        │                 │           │
        ▼                 ▼           ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   GoodWe     │  │   Fronius    │  │     SMA      │
│   Adapter    │  │   Adapter    │  │   Adapter    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       ▼                 ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   goodwe     │  │  pyfronius   │  │   pysma      │
│   library    │  │   library    │  │   library    │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Components

### 1. Port Interfaces

#### InverterPort (`src/inverter/ports/inverter_port.py`)

Main interface combining all inverter capabilities:

```python
from inverter import InverterFactory, InverterConfig

# Create inverter from config
config = InverterConfig.from_yaml_config(yaml_config['inverter'])
inverter = InverterFactory.create_inverter(config)

# Connect
await inverter.connect(config)

# Check connection
if inverter.is_connected():
    # Get battery status
    battery = await inverter.get_battery_status()
    print(f"Battery SOC: {battery.soc_percent}%")
    
    # Start charging
    await inverter.start_charging(power_pct=90, target_soc=100)
    
    # Set operation mode
    await inverter.set_operation_mode(OperationMode.ECO_DISCHARGE)
```

#### CommandExecutorPort (`src/inverter/ports/command_executor_port.py`)

Interface for executing commands:
- `set_operation_mode()` - Change inverter mode
- `start_charging()` - Start battery charging
- `stop_charging()` - Stop battery charging
- `set_grid_export_limit()` - Set export power limit
- `set_battery_dod()` - Set depth of discharge limit
- `emergency_stop()` - Execute emergency stop

#### DataCollectorPort (`src/inverter/ports/data_collector_port.py`)

Interface for collecting data:
- `collect_battery_data()` - Battery metrics
- `collect_pv_data()` - Photovoltaic data
- `collect_grid_data()` - Grid connection data
- `collect_consumption_data()` - House consumption
- `collect_comprehensive_data()` - Complete system snapshot

### 2. Domain Models

#### OperationMode (`src/inverter/models/operation_mode.py`)

Generic operation modes that work across all inverters:

```python
from inverter import OperationMode

# Available modes
OperationMode.GENERAL          # Normal operation
OperationMode.ECO              # Self-consumption optimization
OperationMode.ECO_CHARGE       # Charge from grid
OperationMode.ECO_DISCHARGE    # Discharge to grid (selling)
OperationMode.OFF_GRID         # Battery priority
OperationMode.BACKUP           # Backup mode
OperationMode.FAST_CHARGE      # Maximum charging power
```

#### InverterConfig (`src/inverter/models/inverter_config.py`)

Configuration for inverter connection:

```python
from inverter import InverterConfig

config = InverterConfig(
    vendor="goodwe",
    ip_address="192.168.1.100",
    port=8899,
    timeout=1.0,
    retries=3,
    retry_delay=2.0,
    vendor_config={'family': 'ET', 'comm_addr': 0xf7}
)
```

#### BatteryStatus (`src/inverter/models/battery_status.py`)

Vendor-agnostic battery status:

```python
@dataclass
class BatteryStatus:
    soc_percent: float          # State of charge (%)
    voltage: float              # Battery voltage (V)
    current: float              # Battery current (A)
    power: float                # Battery power (W)
    temperature: float          # Temperature (°C)
    is_charging: bool           # Is charging
    is_discharging: bool        # Is discharging
    timestamp: datetime         # Reading timestamp
```

### 3. GoodWe Adapter

The GoodWe adapter (`src/inverter/adapters/goodwe_adapter.py`) wraps the existing `goodwe` Python library:

- Maps generic `OperationMode` to GoodWe-specific modes
- Extracts sensor data into generic formats
- Implements retry logic and error handling
- Maintains backward compatibility with existing code

### 4. Factory Pattern

The `InverterFactory` creates the appropriate adapter based on configuration:

```python
from inverter import InverterFactory, InverterConfig

# From InverterConfig object
config = InverterConfig(vendor="goodwe", ip_address="192.168.1.100")
inverter = InverterFactory.create_inverter(config)

# From YAML config dictionary
yaml_config = {'vendor': 'goodwe', 'ip_address': '192.168.1.100', ...}
inverter = InverterFactory.create_from_yaml_config(yaml_config)

# Check supported vendors
vendors = InverterFactory.get_supported_vendors()  # ['goodwe']
is_supported = InverterFactory.is_vendor_supported('goodwe')  # True
```

## Configuration

### YAML Configuration

Add `vendor` field to your `config/master_coordinator_config.yaml`:

```yaml
inverter:
  vendor: "goodwe"  # Specifies inverter brand
  ip_address: "192.168.33.6"
  port: 8899
  timeout: 1
  retries: 3
  retry_delay: 2.0
  
  # GoodWe-specific settings
  family: "ET"      # ET, ES, DT
  comm_addr: 0xf7   # Communication address
```

### Backward Compatibility

If `vendor` field is not specified, the system defaults to `"goodwe"` for backward compatibility with existing configurations.

## Currently Supported Inverters

### GoodWe (Implemented)

- **Families**: ET, ES, DT
- **Models**: All GoodWe inverters supported by the `goodwe` Python library
- **Features**: Full support including charging, discharging, data collection, operation modes
- **Library**: [goodwe](https://pypi.org/project/goodwe/) v0.4.8+

### Future Support (Planned)

- **Fronius**: Symo, Primo, Gen24 series
- **SMA**: Sunny Boy, Sunny Tripower series  
- **Huawei**: SUN2000 series
- **Solax**: X1, X3 series
- **Multi-inverter**: Support for multiple inverters simultaneously

## Benefits

1. **Vendor Independence**: Algorithm works with any supported inverter
2. **Extensibility**: Easy to add new inverter brands
3. **Testability**: Mock adapters enable testing without hardware
4. **Maintainability**: Clear separation of concerns
5. **Type Safety**: Strong typing with abstract interfaces
6. **Backward Compatibility**: Existing GoodWe integration unchanged
7. **Future-Proof**: Ready for expansion to other brands

## Testing

The abstraction layer includes comprehensive tests (`test/test_inverter_abstraction.py`):

- Configuration validation (6 tests)
- Operation mode handling (4 tests)
- Safety configuration (1 test)
- Factory pattern (5 tests)
- GoodWe adapter (4 tests)
- Import verification (1 test)

Run tests:

```bash
pytest test/test_inverter_abstraction.py -v
```

All 22 abstraction layer tests passing ✅

## API Reference

### InverterPort Interface

**Connection Management:**
- `async connect(config: InverterConfig) -> bool`
- `async disconnect() -> None`
- `is_connected() -> bool`

**Status and Data:**
- `async get_status() -> InverterStatus`
- `async get_battery_status() -> BatteryStatus`
- `async read_runtime_data() -> Dict[str, Any]`
- `async check_safety_conditions(safety_config: SafetyConfig) -> tuple[bool, list[str]]`

**Command Execution:**
- `async set_operation_mode(mode: OperationMode, power_w: int, min_soc: int) -> bool`
- `async start_charging(power_pct: int, target_soc: int) -> bool`
- `async stop_charging() -> bool`
- `async set_grid_export_limit(power_w: int) -> bool`
- `async set_battery_dod(depth_pct: int) -> bool`
- `async emergency_stop() -> bool`

**Data Collection:**
- `async collect_battery_data() -> BatteryData`
- `async collect_pv_data() -> PVData`
- `async collect_grid_data() -> GridData`
- `async collect_consumption_data() -> ConsumptionData`
- `async collect_comprehensive_data() -> ComprehensiveData`

**Properties:**
- `vendor_name: str` - Vendor name (e.g., "goodwe")
- `model_name: str` - Inverter model
- `serial_number: str` - Inverter serial number

## Error Handling

All adapter methods raise appropriate exceptions:

- `RuntimeError`: When inverter not connected or operation fails
- `ValueError`: When parameters are invalid
- `ConnectionError`: When connection fails after retries

Example:

```python
try:
    await inverter.start_charging(power_pct=90, target_soc=100)
except RuntimeError as e:
    logger.error(f"Failed to start charging: {e}")
except ValueError as e:
    logger.error(f"Invalid parameters: {e}")
```

## Migration Guide

For existing code using direct GoodWe integration, migration is straightforward:

**Before (Direct GoodWe):**
```python
from fast_charge import GoodWeFastCharger

charger = GoodWeFastCharger(config_path)
await charger.connect_inverter()
status = await charger.get_inverter_status()
```

**After (Abstraction Layer):**
```python
from inverter import InverterFactory, InverterConfig

config = InverterConfig.from_yaml_config(yaml_config['inverter'])
inverter = InverterFactory.create_inverter(config)
await inverter.connect(config)
status = await inverter.read_runtime_data()
```

## Performance

The abstraction layer introduces minimal overhead:

- Single indirection through interface (negligible)
- Async operations unchanged
- No additional network calls
- Same performance as direct library usage

## See Also

- [Adding New Inverter Support](ADDING_NEW_INVERTER.md)
- [Project Plan](PROJECT_PLAN_Enhanced_Energy_Management.md)
- [Main README](../README.md)

