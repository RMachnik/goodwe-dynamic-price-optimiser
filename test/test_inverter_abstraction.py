#!/usr/bin/env python3
"""
Tests for Inverter Abstraction Layer

Tests the port interfaces, adapters, and factory pattern.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from inverter.models.inverter_config import InverterConfig, SafetyConfig
from inverter.models.operation_mode import OperationMode
from inverter.factory.inverter_factory import InverterFactory


class TestInverterConfig:
    """Test inverter configuration models."""
    
    def test_create_from_yaml_goodwe(self):
        """Test creating GoodWe config from YAML dict."""
        config_dict = {
            'vendor': 'goodwe',
            'ip_address': '192.168.1.100',
            'port': 8899,
            'timeout': 2.0,
            'retries': 3,
            'retry_delay': 1.0,
            'family': 'ET',
            'comm_addr': 0xf7
        }
        
        config = InverterConfig.from_yaml_config(config_dict)
        
        assert config.vendor == 'goodwe'
        assert config.ip_address == '192.168.1.100'
        assert config.port == 8899
        assert config.timeout == 2.0
        assert config.retries == 3
        assert config.retry_delay == 1.0
        assert config.vendor_config['family'] == 'ET'
        assert config.vendor_config['comm_addr'] == 0xf7
    
    def test_config_validation_success(self):
        """Test successful config validation."""
        config = InverterConfig(
            vendor='goodwe',
            ip_address='192.168.1.100',
            port=8899
        )
        
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None
    
    def test_config_validation_missing_vendor(self):
        """Test validation fails with missing vendor."""
        config = InverterConfig(
            vendor='',
            ip_address='192.168.1.100'
        )
        
        is_valid, error = config.validate()
        assert is_valid is False
        assert 'Vendor' in error
    
    def test_config_validation_missing_ip(self):
        """Test validation fails with missing IP."""
        config = InverterConfig(
            vendor='goodwe',
            ip_address=''
        )
        
        is_valid, error = config.validate()
        assert is_valid is False
        assert 'IP address' in error
    
    def test_config_validation_invalid_port(self):
        """Test validation fails with invalid port."""
        config = InverterConfig(
            vendor='goodwe',
            ip_address='192.168.1.100',
            port=70000  # Invalid port
        )
        
        is_valid, error = config.validate()
        assert is_valid is False
        assert 'port' in error.lower()
    
    def test_backward_compatibility_default_vendor(self):
        """Test backward compatibility - defaults to 'goodwe' if vendor not specified."""
        config_dict = {
            'ip_address': '192.168.1.100',
            'family': 'ET'
        }
        
        config = InverterConfig.from_yaml_config(config_dict)
        
        assert config.vendor == 'goodwe'  # Should default to goodwe


class TestOperationMode:
    """Test operation mode enum."""
    
    def test_operation_modes_exist(self):
        """Test all expected operation modes exist."""
        assert OperationMode.GENERAL
        assert OperationMode.ECO
        assert OperationMode.ECO_CHARGE
        assert OperationMode.ECO_DISCHARGE
        assert OperationMode.OFF_GRID
        assert OperationMode.BACKUP
    
    def test_mode_to_string(self):
        """Test operation mode string conversion."""
        assert str(OperationMode.GENERAL) == "general"
        assert str(OperationMode.ECO_DISCHARGE) == "eco_discharge"
    
    def test_mode_from_string(self):
        """Test creating mode from string."""
        mode = OperationMode.from_string("general")
        assert mode == OperationMode.GENERAL
        
        mode = OperationMode.from_string("ECO_DISCHARGE")
        assert mode == OperationMode.ECO_DISCHARGE
    
    def test_mode_from_invalid_string(self):
        """Test creating mode from invalid string raises error."""
        with pytest.raises(ValueError):
            OperationMode.from_string("invalid_mode")


class TestSafetyConfig:
    """Test safety configuration."""
    
    def test_create_from_yaml(self):
        """Test creating safety config from YAML."""
        config_dict = {
            'safety': {
                'max_battery_temp': 50,
                'min_battery_soc': 10,
                'max_grid_power': 10000
            },
            'coordinator': {
                'emergency_stop_conditions': {
                    'battery_temp_max': 53.0,
                    'battery_voltage_min': 320.0,
                    'battery_voltage_max': 480.0,
                    'grid_voltage_min': 200.0,
                    'grid_voltage_max': 250.0
                }
            },
            'charging': {
                'safety_current_max': 32.0
            }
        }
        
        safety_config = SafetyConfig.from_yaml_config(config_dict)
        
        assert safety_config.battery_temp_max == 53.0
        assert safety_config.battery_voltage_min == 320.0
        assert safety_config.battery_voltage_max == 480.0
        assert safety_config.grid_voltage_min == 200.0
        assert safety_config.grid_voltage_max == 250.0
        assert safety_config.battery_current_max == 32.0


class TestInverterFactory:
    """Test inverter factory."""
    
    def test_supported_vendors(self):
        """Test getting supported vendors."""
        vendors = InverterFactory.get_supported_vendors()
        
        assert 'goodwe' in vendors
        assert len(vendors) >= 1
    
    def test_is_vendor_supported(self):
        """Test checking vendor support."""
        assert InverterFactory.is_vendor_supported('goodwe') is True
        assert InverterFactory.is_vendor_supported('GoodWe') is True  # Case insensitive
        assert InverterFactory.is_vendor_supported('unknown_vendor') is False
    
    def test_create_goodwe_adapter(self):
        """Test creating GoodWe adapter."""
        config = InverterConfig(
            vendor='goodwe',
            ip_address='192.168.1.100'
        )
        
        adapter = InverterFactory.create_inverter(config)
        
        assert adapter is not None
        assert adapter.vendor_name == 'goodwe'
    
    def test_create_from_yaml_config(self):
        """Test creating adapter from YAML config dict."""
        config_dict = {
            'vendor': 'goodwe',
            'ip_address': '192.168.1.100',
            'family': 'ET'
        }
        
        adapter = InverterFactory.create_from_yaml_config(config_dict)
        
        assert adapter is not None
        assert adapter.vendor_name == 'goodwe'
    
    def test_create_unsupported_vendor_raises_error(self):
        """Test creating unsupported vendor raises ValueError."""
        config = InverterConfig(
            vendor='unsupported_brand',
            ip_address='192.168.1.100'
        )
        
        with pytest.raises(ValueError) as exc_info:
            InverterFactory.create_inverter(config)
        
        assert 'Unsupported inverter vendor' in str(exc_info.value)
    
    def test_create_invalid_config_raises_error(self):
        """Test creating with invalid config raises ValueError."""
        config = InverterConfig(
            vendor='goodwe',
            ip_address='',  # Invalid - empty IP
        )
        
        with pytest.raises(ValueError) as exc_info:
            InverterFactory.create_inverter(config)
        
        assert 'Invalid inverter configuration' in str(exc_info.value)


class TestGoodWeAdapter:
    """Test GoodWe adapter implementation."""
    
    @pytest.fixture
    def adapter(self):
        """Create GoodWe adapter for testing."""
        config_dict = {
            'vendor': 'goodwe',
            'ip_address': '192.168.1.100',
            'family': 'ET'
        }
        return InverterFactory.create_from_yaml_config(config_dict)
    
    def test_adapter_properties(self, adapter):
        """Test adapter properties."""
        assert adapter.vendor_name == 'goodwe'
        assert adapter.is_connected() is False  # Not connected yet
        assert adapter.model_name == ''  # No model until connected
        assert adapter.serial_number == ''  # No serial until connected
    
    def test_adapter_not_connected_raises_error(self, adapter):
        """Test that operations fail when not connected."""
        with pytest.raises(RuntimeError):
            # This should fail because not connected
            import asyncio
            asyncio.run(adapter.get_status())
    
    @pytest.mark.asyncio
    async def test_connect_with_mock(self, adapter):
        """Test connection with mocked goodwe library."""
        # Mock the goodwe.connect function
        mock_inverter = Mock()
        mock_inverter.model_name = "GW10K-ET"
        mock_inverter.serial_number = "12345678"
        
        with patch('goodwe.connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_inverter
            
            config = InverterConfig(
                vendor='goodwe',
                ip_address='192.168.1.100',
                vendor_config={'family': 'ET', 'comm_addr': 0xf7}
            )
            
            result = await adapter.connect(config)
            
            assert result is True
            assert adapter.is_connected() is True
            assert adapter.model_name == "GW10K-ET"
            assert adapter.serial_number == "12345678"
    
    @pytest.mark.asyncio
    async def test_disconnect(self, adapter):
        """Test disconnecting from inverter."""
        await adapter.disconnect()
        
        assert adapter.is_connected() is False
        assert adapter.model_name == ''
        assert adapter.serial_number == ''


def test_abstraction_layer_imports():
    """Test that all abstraction layer components can be imported."""
    # Test port imports
    from inverter.ports.inverter_port import InverterPort
    from inverter.ports.command_executor_port import CommandExecutorPort
    from inverter.ports.data_collector_port import DataCollectorPort
    
    # Test model imports
    from inverter.models.operation_mode import OperationMode
    from inverter.models.inverter_config import InverterConfig, SafetyConfig
    from inverter.models.battery_status import BatteryStatus, BatteryData
    from inverter.models.inverter_data import InverterStatus, SensorReading
    
    # Test adapter imports
    from inverter.adapters.goodwe_adapter import GoodWeInverterAdapter
    
    # Test factory imports
    from inverter.factory.inverter_factory import InverterFactory
    
    # Test main package imports
    from inverter import InverterFactory as MainFactory
    from inverter import InverterPort as MainPort
    from inverter import OperationMode as MainMode
    
    assert InverterPort is not None
    assert CommandExecutorPort is not None
    assert DataCollectorPort is not None
    assert OperationMode is not None
    assert InverterConfig is not None
    assert SafetyConfig is not None
    assert BatteryStatus is not None
    assert BatteryData is not None
    assert InverterStatus is not None
    assert SensorReading is not None
    assert GoodWeInverterAdapter is not None
    assert InverterFactory is not None
    assert MainFactory is not None
    assert MainPort is not None
    assert MainMode is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

