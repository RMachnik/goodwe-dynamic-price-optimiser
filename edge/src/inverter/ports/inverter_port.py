"""
Inverter Port Interface

Main interface for inverter abstraction layer. Combines all port capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..models.inverter_config import InverterConfig, SafetyConfig
from ..models.inverter_data import InverterStatus
from ..models.battery_status import BatteryStatus
from .command_executor_port import CommandExecutorPort
from .data_collector_port import DataCollectorPort


class InverterPort(CommandExecutorPort, DataCollectorPort, ABC):
    """
    Main inverter interface.
    
    This port combines command execution and data collection capabilities,
    providing a complete interface for inverter interaction.
    
    Adapters implement this interface to provide vendor-specific functionality
    while maintaining a consistent API for the application.
    """
    
    @abstractmethod
    async def connect(self, config: InverterConfig) -> bool:
        """
        Connect to the inverter.
        
        Args:
            config: Inverter configuration
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If connection fails after retries
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the inverter.
        
        Cleanly closes the connection to the inverter.
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if inverter is connected.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_status(self) -> InverterStatus:
        """
        Get current inverter status.
        
        Returns:
            InverterStatus object with current inverter state
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def get_battery_status(self) -> BatteryStatus:
        """
        Get current battery status.
        
        Returns:
            BatteryStatus object with current battery state
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def read_runtime_data(self) -> Dict[str, Any]:
        """
        Read all runtime data from inverter.
        
        Returns dictionary with all sensor readings in vendor-specific format.
        For compatibility with existing code that expects raw sensor data.
        
        Returns:
            Dictionary of sensor_id -> value mappings
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def check_safety_conditions(self, safety_config: SafetyConfig) -> tuple[bool, list[str]]:
        """
        Check if current conditions are safe for operation.
        
        Args:
            safety_config: Safety configuration with thresholds
            
        Returns:
            Tuple of (is_safe, list_of_issues)
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """
        Get vendor name.
        
        Returns:
            Vendor name (e.g., "goodwe", "fronius", "sma")
        """
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get inverter model name.
        
        Returns:
            Model name or empty string if not connected
        """
        pass
    
    @property
    @abstractmethod
    def serial_number(self) -> str:
        """
        Get inverter serial number.
        
        Returns:
            Serial number or empty string if not connected
        """
        pass

