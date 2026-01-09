"""
Inverter Data Models

Data structures for representing inverter state and sensor readings.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class InverterState(Enum):
    """Inverter operational state."""
    UNKNOWN = "unknown"
    OFFLINE = "offline"
    INITIALIZING = "initializing"
    STANDBY = "standby"
    NORMAL = "normal"
    FAULT = "fault"
    MAINTENANCE = "maintenance"


@dataclass
class SensorReading:
    """
    Generic sensor reading.
    
    Represents a single sensor value with metadata.
    """
    
    # Sensor identifier
    sensor_id: str
    
    # Human-readable sensor name
    name: str
    
    # Sensor value
    value: Any
    
    # Unit of measurement
    unit: str
    
    # Timestamp of reading
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Quality indicator (0-1, where 1 is highest quality)
    quality: float = 1.0
    
    def __str__(self):
        return f"{self.name}: {self.value} {self.unit}"


@dataclass
class InverterStatus:
    """
    Current inverter status.
    
    Vendor-agnostic representation of inverter state.
    """
    
    # Inverter identification
    model_name: str
    serial_number: str
    firmware_version: str
    
    # Operational state
    state: InverterState
    
    # Connection status
    is_connected: bool
    
    # Timestamp
    timestamp: datetime
    
    # All sensor readings
    sensors: Dict[str, SensorReading] = field(default_factory=dict)
    
    # Error/warning messages
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def get_sensor_value(self, sensor_id: str, default: Any = None) -> Any:
        """
        Get sensor value by ID.
        
        Args:
            sensor_id: Sensor identifier
            default: Default value if sensor not found
            
        Returns:
            Sensor value or default
        """
        if sensor_id in self.sensors:
            return self.sensors[sensor_id].value
        return default
    
    def has_errors(self) -> bool:
        """Check if inverter has any errors."""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Check if inverter has any warnings."""
        return len(self.warnings) > 0


@dataclass
class InverterCapabilities:
    """
    Inverter capabilities and specifications.
    
    Defines what the inverter supports and its technical limits.
    """
    
    # Power ratings (W)
    rated_power: int
    max_input_power: int
    max_output_power: int
    
    # PV inputs
    pv_string_count: int
    max_pv_voltage: float
    max_pv_current: float
    
    # Grid connection
    phases: int  # 1 or 3
    grid_voltage_nominal: float
    grid_frequency_nominal: float
    
    # Supported operation modes
    supported_modes: List[str] = field(default_factory=list)
    
    # Features
    supports_battery: bool = True
    supports_grid_export: bool = True
    supports_backup: bool = False
    supports_remote_control: bool = True
    
    # Communication
    communication_protocols: List[str] = field(default_factory=list)

