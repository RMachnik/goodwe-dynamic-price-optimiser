"""
Data Collector Port Interface

Defines the interface for collecting data from inverters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime

from ..models.battery_status import BatteryData


@dataclass
class PVData:
    """Photovoltaic system data."""
    current_power_w: float
    current_power_kw: float
    daily_generation_kwh: float
    string1_power_w: float = 0.0
    string2_power_w: float = 0.0
    string1_voltage_v: float = 0.0
    string2_voltage_v: float = 0.0
    string1_current_a: float = 0.0
    string2_current_a: float = 0.0
    efficiency_percent: float = 0.0


@dataclass
class GridData:
    """Grid connection data."""
    current_power_w: float
    current_power_kw: float
    daily_import_kwh: float
    daily_export_kwh: float
    voltage: float = 0.0
    frequency: float = 0.0
    phase1_current_a: float = 0.0
    phase2_current_a: float = 0.0
    phase3_current_a: float = 0.0


@dataclass
class ConsumptionData:
    """House consumption data."""
    current_power_w: float
    current_power_kw: float
    daily_consumption_kwh: float


@dataclass
class ComprehensiveData:
    """Comprehensive system data collected from inverter."""
    timestamp: str
    date: str
    time: str
    battery: Dict[str, Any]
    photovoltaic: Dict[str, Any]
    grid: Dict[str, Any]
    house_consumption: Dict[str, Any]
    inverter: Dict[str, Any]
    daily_totals: Dict[str, Any]


class DataCollectorPort(ABC):
    """
    Abstract interface for collecting data from inverters.
    
    Implementations of this port provide vendor-specific data collection
    while maintaining a consistent interface for the application.
    """
    
    @abstractmethod
    async def collect_battery_data(self) -> BatteryData:
        """
        Collect battery data from inverter.
        
        Returns:
            BatteryData object with current battery metrics
            
        Raises:
            RuntimeError: If inverter not connected or data collection fails
        """
        pass
    
    @abstractmethod
    async def collect_pv_data(self) -> PVData:
        """
        Collect photovoltaic system data.
        
        Returns:
            PVData object with current PV metrics
            
        Raises:
            RuntimeError: If inverter not connected or data collection fails
        """
        pass
    
    @abstractmethod
    async def collect_grid_data(self) -> GridData:
        """
        Collect grid connection data.
        
        Returns:
            GridData object with current grid metrics
            
        Raises:
            RuntimeError: If inverter not connected or data collection fails
        """
        pass
    
    @abstractmethod
    async def collect_consumption_data(self) -> ConsumptionData:
        """
        Collect house consumption data.
        
        Returns:
            ConsumptionData object with current consumption metrics
            
        Raises:
            RuntimeError: If inverter not connected or data collection fails
        """
        pass
    
    @abstractmethod
    async def collect_comprehensive_data(self) -> ComprehensiveData:
        """
        Collect all available data from inverter.
        
        This method collects a complete snapshot of the system state including
        battery, PV, grid, consumption, and inverter data.
        
        Returns:
            ComprehensiveData object with all system metrics
            
        Raises:
            RuntimeError: If inverter not connected or data collection fails
        """
        pass

