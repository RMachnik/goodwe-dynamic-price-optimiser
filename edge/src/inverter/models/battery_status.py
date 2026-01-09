"""
Battery Status Models

Data structures for representing battery state and capabilities.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class BatteryStatus:
    """
    Current battery status snapshot.
    
    Provides a vendor-agnostic representation of battery state.
    """
    
    # State of Charge (%)
    soc_percent: float
    
    # Voltage (V)
    voltage: float
    
    # Current (A) - negative for charging, positive for discharging
    current: float
    
    # Power (W) - negative for charging, positive for discharging
    power: float
    
    # Temperature (Celsius)
    temperature: float
    
    # Is battery currently charging
    is_charging: bool
    
    # Is battery currently discharging
    is_discharging: bool
    
    # Timestamp of reading
    timestamp: datetime
    
    # Health status (optional)
    health_status: Optional[str] = None
    
    @property
    def power_kw(self) -> float:
        """Get power in kilowatts."""
        return self.power / 1000.0
    
    @property
    def is_idle(self) -> bool:
        """Check if battery is idle (not charging or discharging)."""
        return not self.is_charging and not self.is_discharging


@dataclass
class BatteryData:
    """
    Detailed battery metrics and information.
    
    Extended battery information beyond simple status.
    """
    
    # Basic status
    status: BatteryStatus
    
    # Daily statistics
    daily_charge_kwh: float = 0.0
    daily_discharge_kwh: float = 0.0
    daily_cycles: int = 0
    
    # Battery module information (for multi-module systems)
    module_count: int = 1
    modules_data: dict = None
    
    # Battery Management System (BMS) info
    bms_version: Optional[str] = None
    bms_status: Optional[str] = None
    
    def __post_init__(self):
        if self.modules_data is None:
            self.modules_data = {}


@dataclass
class BatteryCapabilities:
    """
    Battery system capabilities and specifications.
    
    Defines what the battery system can do and its limits.
    """
    
    # Capacity (kWh)
    capacity_kwh: float
    
    # Voltage range (V)
    voltage_min: float
    voltage_max: float
    
    # Current limits (A)
    max_charge_current: float
    max_discharge_current: float
    
    # Power limits (W)
    max_charge_power: float
    max_discharge_power: float
    
    # Battery chemistry
    chemistry: str = "LFP"  # LFP, NMC, LTO, etc.
    
    # Temperature limits (Celsius)
    temp_min_charge: float = 0.0
    temp_max_charge: float = 53.0
    temp_min_discharge: float = -20.0
    temp_max_discharge: float = 53.0
    
    # Cycle life
    expected_cycles: Optional[int] = None
    
    # Depth of Discharge limit (%)
    max_dod: float = 90.0

