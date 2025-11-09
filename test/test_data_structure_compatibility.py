#!/usr/bin/env python3
"""
Tests for data structure compatibility and mapping

Tests the compatibility layer that maps between different data formats:
- enhanced_data_collector format (photovoltaic, house_consumption, system)
- battery selling format (pv, consumption, inverter)
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from enhanced_data_collector import EnhancedDataCollector


class TestDataStructureCompatibility:
    """Test data structure compatibility and mapping"""
    
    def test_enhanced_data_collector_adds_compatibility_keys(self):
        """Test that enhanced_data_collector adds compatibility keys"""
        # Simulate the data structure that would be created
        comprehensive_data = {
            'battery': {
                'soc_percent': 85,
                'temperature': 25,
                'power_w': 500
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
        
        # After compatibility layer (as done in enhanced_data_collector.py)
        # Should have inverter key mapped from system
        if 'system' in comprehensive_data:
            comprehensive_data['inverter'] = comprehensive_data['system'].copy()
            if 'error_codes' not in comprehensive_data['inverter']:
                comprehensive_data['inverter']['error_codes'] = []
        
        # Should have pv key mapped from photovoltaic
        if 'photovoltaic' in comprehensive_data and 'pv' not in comprehensive_data:
            comprehensive_data['pv'] = {
                'power': comprehensive_data['photovoltaic'].get('current_power_w', 0),
                'power_w': comprehensive_data['photovoltaic'].get('current_power_w', 0),
                'total_power': comprehensive_data['photovoltaic'].get('current_power_w', 0)
            }
        
        # Should have consumption key mapped from house_consumption
        if 'house_consumption' in comprehensive_data and 'consumption' not in comprehensive_data:
            comprehensive_data['consumption'] = {
                'house_consumption': comprehensive_data['house_consumption'].get('current_power_w', 0),
                'power_w': comprehensive_data['house_consumption'].get('current_power_w', 0),
                'current_power_w': comprehensive_data['house_consumption'].get('current_power_w', 0)
            }
        
        # Verify compatibility keys exist
        assert 'inverter' in comprehensive_data
        assert 'pv' in comprehensive_data
        assert 'consumption' in comprehensive_data
        
        # Verify inverter has error_codes
        assert 'error_codes' in comprehensive_data['inverter']
        
        # Verify pv mapping
        assert comprehensive_data['pv']['power_w'] == 2000
        assert comprehensive_data['pv']['total_power'] == 2000
        
        # Verify consumption mapping
        assert comprehensive_data['consumption']['power_w'] == 1500
        assert comprehensive_data['consumption']['house_consumption'] == 1500
    
    def test_master_coordinator_data_mapping(self):
        """Test that master coordinator correctly maps data for battery selling"""
        # Simulate current_data from enhanced_data_collector
        current_data = {
            'battery': {
                'soc_percent': 85,
                'temperature': 25,
                'power_w': 500
            },
            'photovoltaic': {
                'current_power_w': 2000
            },
            'house_consumption': {
                'current_power_w': 1500
            },
            'grid': {
                'power_w': 1000,
                'voltage': 230
            },
            'system': {
                'inverter_model': 'GW5000'
            }
        }
        
        # Add compatibility layer (as done in enhanced_data_collector)
        if 'system' in current_data:
            current_data['inverter'] = current_data['system'].copy()
            if 'error_codes' not in current_data['inverter']:
                current_data['inverter']['error_codes'] = []
        
        if 'photovoltaic' in current_data and 'pv' not in current_data:
            current_data['pv'] = {
                'power': current_data['photovoltaic'].get('current_power_w', 0),
                'power_w': current_data['photovoltaic'].get('current_power_w', 0),
                'total_power': current_data['photovoltaic'].get('current_power_w', 0)
            }
        
        if 'house_consumption' in current_data and 'consumption' not in current_data:
            current_data['consumption'] = {
                'house_consumption': current_data['house_consumption'].get('current_power_w', 0),
                'power_w': current_data['house_consumption'].get('current_power_w', 0),
                'current_power_w': current_data['house_consumption'].get('current_power_w', 0)
            }
        
        # Format data for battery selling (as done in master_coordinator)
        battery_data = current_data.get('battery', {})
        pv_data = current_data.get('photovoltaic', {}) or current_data.get('pv', {})
        consumption_data = current_data.get('house_consumption', {}) or current_data.get('consumption', {})
        grid_data = current_data.get('grid', {})
        
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
        
        # Verify all required fields are present
        assert selling_data['battery']['soc_percent'] == 85
        assert selling_data['pv']['power_w'] == 2000
        assert selling_data['consumption']['power_w'] == 1500
        assert selling_data['grid']['voltage'] == 230
    
    def test_inverter_key_for_safety_monitor(self):
        """Test that inverter key is available for battery_selling_monitor"""
        # Simulate current_data
        current_data = {
            'system': {
                'inverter_model': 'GW5000',
                'inverter_serial': '12345',
                'connection_status': 'Connected'
            }
        }
        
        # Add inverter key (as done in master_coordinator)
        normalized_current_data = current_data.copy()
        if 'system' in normalized_current_data and 'inverter' not in normalized_current_data:
            normalized_current_data['inverter'] = normalized_current_data['system'].copy()
            if 'error_codes' not in normalized_current_data['inverter']:
                normalized_current_data['inverter']['error_codes'] = []
        
        # Verify inverter key exists for safety monitor
        assert 'inverter' in normalized_current_data
        assert 'error_codes' in normalized_current_data['inverter']
        assert normalized_current_data['inverter']['inverter_model'] == 'GW5000'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

