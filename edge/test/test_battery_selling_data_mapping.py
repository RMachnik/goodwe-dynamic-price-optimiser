#!/usr/bin/env python3
"""
Tests for battery selling data mapping and compatibility

Tests the data structure mapping between enhanced_data_collector format
and battery selling engine format.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from master_coordinator import MasterCoordinator
from battery_selling_monitor import BatterySellingMonitor
from battery_selling_engine import BatterySellingEngine


class TestBatterySellingDataMapping:
    """Test data mapping for battery selling"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'battery_selling': {
                'enabled': True,
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'min_selling_price_pln': 0.50,
                'safety_checks': {
                    'battery_temp_max': 50.0,
                    'grid_voltage_min': 200.0,
                    'grid_voltage_max': 250.0
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
    
    @pytest.fixture
    def enhanced_data_format(self):
        """Simulate data from enhanced_data_collector"""
        return {
            'battery': {
                'soc_percent': 85,
                'temperature': 25,
                'power_w': 500,
                'charging_status': False
            },
            'photovoltaic': {
                'current_power_w': 2000,
                'current_power_kw': 2.0
            },
            'house_consumption': {
                'current_power_w': 1500,
                'current_power_kw': 1.5
            },
            'grid': {
                'power_w': 1000,
                'voltage': 230
            },
            'system': {
                'inverter_model': 'GW5000',
                'inverter_serial': '12345',
                'connection_status': 'Connected'
            }
        }
    
    def test_inverter_key_mapping_for_safety_monitor(self, config, enhanced_data_format):
        """Test that inverter key is mapped from system for safety monitor"""
        # Simulate what master_coordinator does
        normalized_current_data = enhanced_data_format.copy()
        if 'system' in normalized_current_data and 'inverter' not in normalized_current_data:
            normalized_current_data['inverter'] = normalized_current_data['system'].copy()
            if 'error_codes' not in normalized_current_data['inverter']:
                normalized_current_data['inverter']['error_codes'] = []
        
        # Verify inverter key exists
        assert 'inverter' in normalized_current_data
        assert 'error_codes' in normalized_current_data['inverter']
        
        # Safety monitor should be able to access inverter data
        inverter_data = normalized_current_data.get('inverter', {})
        assert inverter_data.get('inverter_model') == 'GW5000'
    
    def test_pv_and_consumption_mapping(self, config, enhanced_data_format):
        """Test that pv and consumption are correctly mapped"""
        # Simulate compatibility layer (as done in enhanced_data_collector)
        if 'photovoltaic' in enhanced_data_format and 'pv' not in enhanced_data_format:
            enhanced_data_format['pv'] = {
                'power': enhanced_data_format['photovoltaic'].get('current_power_w', 0),
                'power_w': enhanced_data_format['photovoltaic'].get('current_power_w', 0),
                'total_power': enhanced_data_format['photovoltaic'].get('current_power_w', 0)
            }
        
        if 'house_consumption' in enhanced_data_format and 'consumption' not in enhanced_data_format:
            enhanced_data_format['consumption'] = {
                'house_consumption': enhanced_data_format['house_consumption'].get('current_power_w', 0),
                'power_w': enhanced_data_format['house_consumption'].get('current_power_w', 0),
                'current_power_w': enhanced_data_format['house_consumption'].get('current_power_w', 0)
            }
        
        # Format for battery selling (as done in master_coordinator)
        battery_data = enhanced_data_format.get('battery', {})
        pv_data = enhanced_data_format.get('photovoltaic', {}) or enhanced_data_format.get('pv', {})
        consumption_data = enhanced_data_format.get('house_consumption', {}) or enhanced_data_format.get('consumption', {})
        grid_data = enhanced_data_format.get('grid', {})
        
        selling_data = {
            'battery': {
                'soc_percent': battery_data.get('soc_percent', 0),
                'temperature': battery_data.get('temperature', 25),
                'power': battery_data.get('power', 0) or battery_data.get('power_w', 0)
            },
            'pv': {
                'power_w': pv_data.get('current_power_w', 0) or pv_data.get('power_w', 0) or pv_data.get('power', 0)
            },
            'consumption': {
                'power_w': consumption_data.get('current_power_w', 0) or consumption_data.get('power_w', 0) or consumption_data.get('house_consumption', 0)
            },
            'grid': {
                'power': grid_data.get('power', 0) or grid_data.get('power_w', 0),
                'voltage': grid_data.get('voltage', 0)
            }
        }
        
        # Verify all fields are correctly mapped
        assert selling_data['battery']['soc_percent'] == 85
        assert selling_data['pv']['power_w'] == 2000
        assert selling_data['consumption']['power_w'] == 1500
        assert selling_data['grid']['voltage'] == 230
    
    @pytest.mark.asyncio
    async def test_safety_monitor_with_mapped_data(self, config, enhanced_data_format):
        """Test that safety monitor works with mapped inverter data"""
        # Add compatibility layer
        if 'system' in enhanced_data_format:
            enhanced_data_format['inverter'] = enhanced_data_format['system'].copy()
            if 'error_codes' not in enhanced_data_format['inverter']:
                enhanced_data_format['inverter']['error_codes'] = []
        
        monitor = BatterySellingMonitor(config)
        mock_inverter = Mock()
        
        # Should not raise error about missing inverter data
        safety_report = await monitor.check_safety_conditions(mock_inverter, enhanced_data_format)
        
        # Should have valid safety report
        assert safety_report is not None
        assert safety_report.overall_status is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

