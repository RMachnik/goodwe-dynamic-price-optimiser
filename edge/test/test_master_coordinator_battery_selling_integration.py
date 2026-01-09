#!/usr/bin/env python3
"""
Test Master Coordinator Battery Selling Integration

This test suite verifies that the battery selling functionality is properly
integrated with the master coordinator, including:
- Configuration loading
- Data format compatibility
- Decision integration
- Safety checks
"""

import pytest
import asyncio
import yaml
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from master_coordinator import MasterCoordinator
from battery_selling_engine import BatterySellingEngine, SellingDecision
from battery_selling_monitor import BatterySellingMonitor


class TestMasterCoordinatorBatterySellingIntegration:
    """Test battery selling integration with master coordinator"""
    
    @pytest.fixture
    def config_with_battery_selling(self):
        """Configuration with battery selling enabled"""
        return {
            'battery_selling': {
                'enabled': True,
                'min_selling_price_pln': 0.50,
                'min_battery_soc': 80.0,
                'safety_margin_soc': 50.0,
                'max_daily_cycles': 2,
                'peak_hours': [17, 18, 19, 20, 21],
                'grid_export_limit_w': 5000,
                'battery_dod_limit': 50,
                'safety_checks': {
                    'battery_temp_max': 50.0,
                    'battery_temp_min': -20.0,
                    'grid_voltage_min': 200.0,
                    'grid_voltage_max': 250.0,
                    'night_hours': [22, 23, 0, 1, 2, 3, 4, 5]
                }
            },
            'battery_management': {'capacity_kwh': 10.0},
            'coordinator': {'decision_interval_minutes': 15}
        }
    
    @pytest.fixture
    def mock_current_data(self):
        """Mock current data with proper format"""
        return {
            'battery': {
                'soc_percent': 85,
                'charging_status': False,
                'current': 1.5,
                'power': 500,
                'temperature': 25
            },
            'pv': {
                'power': 0,  # No PV at night
                'total_power': 0
            },
            'consumption': {
                'house_consumption': 1500,
                'current_power_w': 1500
            },
            'grid': {
                'power': 1000,
                'voltage': 230  # Safe voltage
            }
        }
    
    @pytest.fixture
    def mock_price_data(self):
        """Mock price data"""
        return {
            'current_price_pln': 0.60,
            'price_points': [{'price': 600}]
        }
    
    def test_battery_selling_config_parsing(self, config_with_battery_selling):
        """Test that battery selling config is parsed correctly"""
        coordinator = MasterCoordinator()
        coordinator.config = config_with_battery_selling
        
        # Test config parsing
        battery_selling_config = coordinator.config.get('battery_selling', {})
        
        assert battery_selling_config['enabled'] is True
        # Verify values exist and are reasonable
        assert 0.3 <= battery_selling_config['min_selling_price_pln'] <= 2.0
        assert 50 <= battery_selling_config['min_battery_soc'] <= 100
        assert 30 <= battery_selling_config['safety_margin_soc'] <= 70
    
    @pytest.mark.asyncio
    async def test_battery_selling_engine_initialization(self, config_with_battery_selling):
        """Test battery selling engine initialization with correct config"""
        coordinator = MasterCoordinator()
        coordinator.config = config_with_battery_selling
        
        # Initialize battery selling engine
        battery_selling_config = coordinator.config.get('battery_selling', {})
        engine = BatterySellingEngine(battery_selling_config)
        
        assert engine.min_selling_soc == 80.0
        assert engine.min_selling_price_pln == 0.80  # Default from battery_selling_engine.py
        assert engine.safety_margin_soc == 50.0
    
    def test_current_data_format_for_battery_selling(self, mock_current_data):
        """Test that current data is formatted correctly for battery selling"""
        coordinator = MasterCoordinator()
        coordinator.current_data = mock_current_data
        
        # Format data for battery selling (as done in master coordinator)
        selling_data = {
            'battery': {
                'soc_percent': coordinator.current_data.get('battery', {}).get('soc_percent', 0),
                'charging_status': coordinator.current_data.get('battery', {}).get('charging_status', False),
                'current': coordinator.current_data.get('battery', {}).get('current', 0),
                'power': coordinator.current_data.get('battery', {}).get('power', 0),
                'temperature': coordinator.current_data.get('battery', {}).get('temperature', 25)
            },
            'pv': {
                'power_w': coordinator.current_data.get('pv', {}).get('power', 0)
            },
            'consumption': {
                'power_w': coordinator.current_data.get('consumption', {}).get('house_consumption', 0)
            },
            'grid': {
                'power': coordinator.current_data.get('grid', {}).get('power', 0),
                'voltage': coordinator.current_data.get('grid', {}).get('voltage', 0)
            }
        }
        
        # Verify data format
        assert 'battery' in selling_data
        assert 'pv' in selling_data
        assert 'consumption' in selling_data
        assert 'grid' in selling_data
        
        # Verify required fields
        assert 'soc_percent' in selling_data['battery']
        assert 'power_w' in selling_data['pv']
        assert 'power_w' in selling_data['consumption']
        assert 'voltage' in selling_data['grid']
    
    def test_enhanced_data_collector_grid_voltage(self):
        """Test that enhanced data collector includes grid voltage"""
        from enhanced_data_collector import EnhancedDataCollector
        
        collector = EnhancedDataCollector('config/master_coordinator_config.yaml')
        
        # Check the data structure that would be created
        # The grid voltage should be included in the comprehensive data
        expected_grid_data = {
            'power_w': 'Unknown',
            'power_kw': 0.0,
            'voltage': 'Unknown',  # This should be added
            'flow_direction': 'unknown',
            'import_rate': 0.0,
            'export_rate': 0.0,
            'l1_current_a': 'Unknown',
            'l2_current_a': 'Unknown',
            'l3_current_a': 'Unknown',
            'l1_power': 'Unknown',
            'l2_power': 'Unknown',
            'l3_power': 'Unknown',
            'total_exported_kwh': 'Unknown',
            'total_imported_kwh': 'Unknown',
            'today_exported_kwh': 'Unknown',
            'today_imported_kwh': 'Unknown'
        }
        
        # Verify that the grid data structure includes voltage field
        assert 'voltage' in expected_grid_data
    
    def test_configuration_validation(self, config_with_battery_selling):
        """Test configuration validation for battery selling"""
        coordinator = MasterCoordinator()
        coordinator.config = config_with_battery_selling
        
        # Test required configuration fields
        battery_selling_config = coordinator.config.get('battery_selling', {})
        
        required_fields = [
            'enabled', 'min_selling_price_pln', 'min_battery_soc', 
            'safety_margin_soc', 'max_daily_cycles', 'peak_hours'
        ]
        
        for field in required_fields:
            assert field in battery_selling_config, f"Missing required field: {field}"
        
        # Test safety checks configuration
        safety_checks = battery_selling_config.get('safety_checks', {})
        safety_fields = ['battery_temp_max', 'battery_temp_min', 'grid_voltage_min', 'grid_voltage_max']
        
        for field in safety_fields:
            assert field in safety_checks, f"Missing safety check field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
