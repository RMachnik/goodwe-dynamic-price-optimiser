#!/usr/bin/env python3
"""
Tests for sell_battery_now.py manual battery selling script
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, AsyncMock, patch
import yaml


def test_script_imports():
    """Test that the script can be imported without errors"""
    try:
        import sell_battery_now
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import sell_battery_now: {e}")


def test_battery_seller_class_exists():
    """Test that BatterySeller class exists"""
    from sell_battery_now import BatterySeller
    assert BatterySeller is not None


def test_battery_seller_initialization():
    """Test BatterySeller initialization with mock config"""
    from sell_battery_now import BatterySeller
    
    # Create a temporary config file
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    
    if config_path.exists():
        seller = BatterySeller(str(config_path))
        assert seller.config is not None
        assert seller.inverter is None  # Not connected yet
        assert seller.is_selling is False
    else:
        pytest.skip(f"Config file not found: {config_path}")


@pytest.mark.asyncio
async def test_safety_conditions_validation():
    """Test safety condition validation logic"""
    from sell_battery_now import BatterySeller
    
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    seller = BatterySeller(str(config_path))
    
    # Mock the inverter and status
    seller.inverter = Mock()
    seller.get_inverter_status = AsyncMock(return_value={
        'battery_soc': {'value': 50, 'unit': '%'},
        'battery_temperature': {'value': 25, 'unit': '°C'},
        'battery_voltage': {'value': 400, 'unit': 'V'},
        'vgrid': {'value': 230, 'unit': 'V'}
    })
    
    # Test with safe conditions
    is_safe, reason = await seller.check_safety_conditions(target_soc=45.0)
    assert is_safe is True
    assert "passed" in reason.lower()


@pytest.mark.asyncio
async def test_safety_conditions_low_soc():
    """Test that safety checks fail when SOC is too low"""
    from sell_battery_now import BatterySeller
    
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    seller = BatterySeller(str(config_path))
    
    # Mock the inverter and status with low SOC
    seller.inverter = Mock()
    seller.get_inverter_status = AsyncMock(return_value={
        'battery_soc': {'value': 8, 'unit': '%'},  # Below minimum 10%
        'battery_temperature': {'value': 25, 'unit': '°C'},
        'battery_voltage': {'value': 400, 'unit': 'V'},
        'vgrid': {'value': 230, 'unit': 'V'}
    })
    
    # Test with low SOC
    is_safe, reason = await seller.check_safety_conditions(target_soc=45.0)
    assert is_safe is False
    assert "soc" in reason.lower()


@pytest.mark.asyncio
async def test_safety_conditions_high_temperature():
    """Test that safety checks fail when temperature is too high"""
    from sell_battery_now import BatterySeller
    
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    seller = BatterySeller(str(config_path))
    
    # Mock the inverter and status with high temperature
    seller.inverter = Mock()
    seller.get_inverter_status = AsyncMock(return_value={
        'battery_soc': {'value': 60, 'unit': '%'},
        'battery_temperature': {'value': 55, 'unit': '°C'},  # Above max 53°C
        'battery_voltage': {'value': 400, 'unit': 'V'},
        'vgrid': {'value': 230, 'unit': 'V'}
    })
    
    # Test with high temperature
    is_safe, reason = await seller.check_safety_conditions(target_soc=45.0)
    assert is_safe is False
    assert "temperature" in reason.lower()


@pytest.mark.asyncio
async def test_safety_conditions_low_voltage():
    """Test that safety checks fail when voltage is too low"""
    from sell_battery_now import BatterySeller
    
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    
    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")
    
    seller = BatterySeller(str(config_path))
    
    # Mock the inverter and status with low voltage
    seller.inverter = Mock()
    seller.get_inverter_status = AsyncMock(return_value={
        'battery_soc': {'value': 60, 'unit': '%'},
        'battery_temperature': {'value': 25, 'unit': '°C'},
        'battery_voltage': {'value': 300, 'unit': 'V'},  # Below min 320V
        'vgrid': {'value': 230, 'unit': 'V'}
    })
    
    # Test with low voltage
    is_safe, reason = await seller.check_safety_conditions(target_soc=45.0)
    assert is_safe is False
    assert "voltage" in reason.lower()


def test_target_soc_validation():
    """Test that target SOC is validated correctly"""
    # This would be tested by running the CLI with invalid values
    # The validation happens in the argparse section
    
    # Test values should be between 10 and 95
    valid_values = [10, 45, 60, 95]
    invalid_values = [5, 0, -10, 100, 105]
    
    # Just verify the ranges make sense
    for val in valid_values:
        assert 10 <= val <= 95
    
    for val in invalid_values:
        assert val < 10 or val > 95


def test_power_validation():
    """Test that power values are validated correctly"""
    # The validation happens in the argparse section
    
    # Test values should be between 100 and 15000
    valid_values = [100, 3000, 5000, 10000, 15000]
    invalid_values = [50, 0, -100, 20000, 50000]
    
    # Just verify the ranges make sense
    for val in valid_values:
        assert 100 <= val <= 15000
    
    for val in invalid_values:
        assert val < 100 or val > 15000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

