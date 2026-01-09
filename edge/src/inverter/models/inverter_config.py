"""
Inverter Configuration Models

Data structures for inverter connection and safety configuration.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class InverterConfig:
    """
    Configuration for inverter connection.
    
    This is a vendor-agnostic configuration that contains common connection
    parameters as well as vendor-specific settings.
    """
    
    # Vendor identification
    vendor: str  # e.g., "goodwe", "fronius", "sma", "huawei"
    
    # Common connection parameters
    ip_address: str
    port: int = 8899
    timeout: float = 1.0
    retries: int = 3
    retry_delay: float = 2.0
    
    # Vendor-specific parameters (stored as dict)
    vendor_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_yaml_config(cls, config_dict: Dict[str, Any]) -> 'InverterConfig':
        """
        Create InverterConfig from YAML configuration dict.
        
        Args:
            config_dict: Configuration dictionary from YAML
            
        Returns:
            InverterConfig instance
        """
        # Get vendor (default to "goodwe" for backward compatibility)
        vendor = config_dict.get('vendor', 'goodwe')
        
        # Extract common parameters
        ip_address = config_dict.get('ip_address', '')
        port = config_dict.get('port', 8899)
        timeout = config_dict.get('timeout', 1.0)
        retries = config_dict.get('retries', 3)
        retry_delay = config_dict.get('retry_delay', 2.0)
        
        # Extract vendor-specific config
        vendor_config = {}
        if vendor == 'goodwe':
            vendor_config = {
                'family': config_dict.get('family', 'ET'),
                'comm_addr': config_dict.get('comm_addr', 0xf7),
            }
        
        return cls(
            vendor=vendor,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
            vendor_config=vendor_config
        )
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.vendor:
            return False, "Vendor must be specified"
        
        if not self.ip_address:
            return False, "IP address must be specified"
        
        if self.port <= 0 or self.port > 65535:
            return False, f"Invalid port number: {self.port}"
        
        if self.timeout <= 0:
            return False, f"Timeout must be positive: {self.timeout}"
        
        if self.retries < 0:
            return False, f"Retries must be non-negative: {self.retries}"
        
        return True, None


@dataclass
class SafetyConfig:
    """
    Safety thresholds and limits for inverter operation.
    
    These values define safe operating ranges for battery, grid, and inverter.
    """
    
    # Battery temperature limits (Celsius)
    battery_temp_min: float = 0.0
    battery_temp_max: float = 53.0
    battery_temp_warning: float = 50.0
    
    # Battery voltage limits (Volts)
    battery_voltage_min: float = 320.0
    battery_voltage_max: float = 480.0
    
    # Battery current limits (Amps)
    battery_current_max: float = 32.0
    
    # Grid voltage limits (Volts)
    grid_voltage_min: float = 200.0
    grid_voltage_max: float = 250.0
    
    # Grid power limits (Watts)
    max_grid_power: float = 10000.0
    
    # Battery SOC limits (%)
    min_battery_soc: float = 10.0
    max_battery_soc: float = 100.0
    
    @classmethod
    def from_yaml_config(cls, config_dict: Dict[str, Any]) -> 'SafetyConfig':
        """
        Create SafetyConfig from YAML configuration dict.
        
        Args:
            config_dict: Configuration dictionary from YAML
            
        Returns:
            SafetyConfig instance
        """
        safety_dict = config_dict.get('safety', {})
        emergency_dict = config_dict.get('coordinator', {}).get('emergency_stop_conditions', {})
        
        return cls(
            battery_temp_min=emergency_dict.get('battery_temp_min', 0.0),
            battery_temp_max=emergency_dict.get('battery_temp_max', 53.0),
            battery_temp_warning=emergency_dict.get('battery_temp_warning', 50.0),
            battery_voltage_min=emergency_dict.get('battery_voltage_min', 320.0),
            battery_voltage_max=emergency_dict.get('battery_voltage_max', 480.0),
            battery_current_max=config_dict.get('charging', {}).get('safety_current_max', 32.0),
            grid_voltage_min=emergency_dict.get('grid_voltage_min', 200.0),
            grid_voltage_max=emergency_dict.get('grid_voltage_max', 250.0),
            max_grid_power=safety_dict.get('max_grid_power', 10000.0),
            min_battery_soc=safety_dict.get('min_battery_soc', 10.0),
            max_battery_soc=100.0
        )

