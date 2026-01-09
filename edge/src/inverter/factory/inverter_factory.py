"""
Inverter Factory

Creates inverter adapter instances based on vendor configuration.
"""

import logging
from typing import Dict, Any

from ..ports.inverter_port import InverterPort
from ..models.inverter_config import InverterConfig
from ..adapters.goodwe_adapter import GoodWeInverterAdapter


class InverterFactory:
    """
    Factory for creating inverter adapters.
    
    The factory reads the vendor from configuration and instantiates
    the appropriate adapter implementation.
    """
    
    # Registry of supported vendors and their adapter classes
    _ADAPTERS = {
        'goodwe': GoodWeInverterAdapter,
        # Future adapters:
        # 'fronius': FroniusInverterAdapter,
        # 'sma': SMAInverterAdapter,
        # 'huawei': HuaweiInverterAdapter,
    }
    
    @classmethod
    def create_inverter(cls, config: InverterConfig) -> InverterPort:
        """
        Create an inverter adapter instance based on configuration.
        
        Args:
            config: Inverter configuration including vendor information
            
        Returns:
            InverterPort implementation for the specified vendor
            
        Raises:
            ValueError: If vendor is not supported
            RuntimeError: If adapter instantiation fails
        """
        logger = logging.getLogger(cls.__name__)
        
        # Validate configuration
        is_valid, error_msg = config.validate()
        if not is_valid:
            raise ValueError(f"Invalid inverter configuration: {error_msg}")
        
        # Get vendor (lowercase for comparison)
        vendor = config.vendor.lower().strip()
        
        # Check if vendor is supported
        if vendor not in cls._ADAPTERS:
            supported = ', '.join(cls._ADAPTERS.keys())
            raise ValueError(
                f"Unsupported inverter vendor: '{vendor}'. "
                f"Supported vendors: {supported}"
            )
        
        # Get adapter class
        adapter_class = cls._ADAPTERS[vendor]
        
        try:
            # Instantiate adapter
            adapter = adapter_class()
            logger.info(f"Created {vendor} inverter adapter")
            return adapter
            
        except Exception as e:
            logger.error(f"Failed to create {vendor} adapter: {e}")
            raise RuntimeError(f"Failed to create inverter adapter: {e}")
    
    @classmethod
    def create_from_yaml_config(cls, config_dict: Dict[str, Any]) -> InverterPort:
        """
        Create inverter adapter from YAML configuration dictionary.
        
        Convenience method that creates InverterConfig from YAML dict
        and then creates the appropriate adapter.
        
        Args:
            config_dict: Configuration dictionary from YAML (inverter section)
            
        Returns:
            InverterPort implementation
            
        Raises:
            ValueError: If configuration is invalid or vendor unsupported
        """
        inverter_config = InverterConfig.from_yaml_config(config_dict)
        return cls.create_inverter(inverter_config)
    
    @classmethod
    def get_supported_vendors(cls) -> list[str]:
        """
        Get list of supported inverter vendors.
        
        Returns:
            List of supported vendor names
        """
        return list(cls._ADAPTERS.keys())
    
    @classmethod
    def is_vendor_supported(cls, vendor: str) -> bool:
        """
        Check if a vendor is supported.
        
        Args:
            vendor: Vendor name to check
            
        Returns:
            True if vendor is supported, False otherwise
        """
        return vendor.lower().strip() in cls._ADAPTERS

