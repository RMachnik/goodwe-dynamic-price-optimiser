"""
Operation Mode Enumeration

Defines generic operation modes that are mapped to vendor-specific modes
by the adapter implementations.
"""

from enum import Enum


class OperationMode(Enum):
    """
    Generic inverter operation modes.
    
    These modes are vendor-agnostic and are translated to vendor-specific
    modes by each adapter implementation.
    """
    
    # General/Normal operation mode
    GENERAL = "general"
    
    # Off-grid mode (battery priority, minimal grid usage)
    OFF_GRID = "off_grid"
    
    # Backup mode (use battery when grid fails)
    BACKUP = "backup"
    
    # Eco mode (optimize for self-consumption)
    ECO = "eco"
    
    # Eco charge mode (charge from grid during low prices)
    ECO_CHARGE = "eco_charge"
    
    # Eco discharge mode (sell battery energy to grid)
    ECO_DISCHARGE = "eco_discharge"
    
    # Fast charging mode (maximum charging power)
    FAST_CHARGE = "fast_charge"
    
    # Battery standby (no charge/discharge)
    BATTERY_STANDBY = "battery_standby"
    
    def __str__(self):
        return self.value
    
    @classmethod
    def from_string(cls, mode_str: str) -> 'OperationMode':
        """
        Create OperationMode from string value.
        
        Args:
            mode_str: String representation of mode
            
        Returns:
            OperationMode enum value
            
        Raises:
            ValueError: If mode string is not recognized
        """
        mode_str_lower = mode_str.lower().strip()
        for mode in cls:
            if mode.value == mode_str_lower:
                return mode
        raise ValueError(f"Unknown operation mode: {mode_str}")

