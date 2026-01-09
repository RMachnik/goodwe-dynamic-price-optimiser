"""
Command Executor Port Interface

Defines the interface for executing commands on inverters.
"""

from abc import ABC, abstractmethod
from ..models.operation_mode import OperationMode


class CommandExecutorPort(ABC):
    """
    Abstract interface for executing commands on inverters.
    
    Implementations of this port provide vendor-specific command execution
    while maintaining a consistent interface for the application.
    """
    
    @abstractmethod
    async def set_operation_mode(
        self, 
        mode: OperationMode, 
        power_w: int = 0, 
        min_soc: int = 0
    ) -> bool:
        """
        Set inverter operation mode.
        
        Args:
            mode: Desired operation mode
            power_w: Power limit in watts (for modes that support it)
            min_soc: Minimum SOC percentage (for discharge modes)
            
        Returns:
            True if command successful, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def start_charging(self, power_pct: int, target_soc: int) -> bool:
        """
        Start battery charging.
        
        Args:
            power_pct: Charging power as percentage (0-100)
            target_soc: Target State of Charge percentage (0-100)
            
        Returns:
            True if charging started successfully, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
            ValueError: If parameters out of range
        """
        pass
    
    @abstractmethod
    async def stop_charging(self) -> bool:
        """
        Stop battery charging.
        
        Returns:
            True if charging stopped successfully, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def set_grid_export_limit(self, power_w: int) -> bool:
        """
        Set grid export power limit.
        
        Args:
            power_w: Maximum export power in watts
            
        Returns:
            True if limit set successfully, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass
    
    @abstractmethod
    async def set_battery_dod(self, depth_pct: int) -> bool:
        """
        Set battery Depth of Discharge limit.
        
        Args:
            depth_pct: Maximum discharge depth as percentage (0-100)
            
        Returns:
            True if DoD set successfully, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
            ValueError: If percentage out of range
        """
        pass
    
    @abstractmethod
    async def emergency_stop(self) -> bool:
        """
        Execute emergency stop procedure.
        
        Returns inverter to safe state (GENERAL mode, disable export, etc.)
        
        Returns:
            True if emergency stop successful, False otherwise
            
        Raises:
            RuntimeError: If inverter not connected
        """
        pass

