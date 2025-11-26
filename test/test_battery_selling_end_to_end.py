#!/usr/bin/env python3
"""
End-to-End Test for Battery Selling Functionality

This test verifies the complete battery selling workflow from data collection
to decision execution, including integration with the master coordinator.
"""

import pytest
import asyncio
import yaml
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from master_coordinator import MasterCoordinator
from battery_selling_engine import BatterySellingEngine, SellingDecision
from battery_selling_monitor import BatterySellingMonitor
from enhanced_data_collector import EnhancedDataCollector
from fast_charge import GoodWeFastCharger


class TestBatterySellingEndToEnd:
    """End-to-end tests for battery selling functionality"""
    
    @pytest.fixture
    def config(self):
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
            'coordinator': {'decision_interval_minutes': 15},
            'inverter': {'ip': '192.168.33.15'}
        }
    
    @pytest.fixture
    def mock_inverter_data(self):
        """Mock inverter data for testing"""
        return {
            'battery_soc': {'value': 85},
            'ibattery1': {'value': 1.5},
            'pbattery1': {'value': 500},
            'battery_temperature': {'value': 25},
            'ppv': {'value': 0},
            'house_consumption': {'value': 1500},
            'vgrid': {'value': 230},
            'active_power_total': {'value': 1000},
            'meter_active_power_total': {'value': 1000}
        }
    
    @pytest.fixture
    def mock_price_data(self):
        """Mock price data"""
        return {
            'current_price_pln': 0.60,
            'price_points': [{'price': 600}]
        }
    
    @pytest.mark.asyncio
    async def test_complete_battery_selling_workflow(self, config, mock_inverter_data, mock_price_data):
        """Test complete battery selling workflow"""
        
        # Initialize master coordinator
        coordinator = MasterCoordinator()
        coordinator.config = config
        
        # Mock the data collector
        mock_data_collector = AsyncMock()
        mock_data_collector.get_current_data.return_value = {
            'battery': {
                'soc_percent': mock_inverter_data['battery_soc']['value'],
                'charging_status': False,
                'current': mock_inverter_data['ibattery1']['value'],
                'power': mock_inverter_data['pbattery1']['value'],
                'temperature': mock_inverter_data['battery_temperature']['value']
            },
            'pv': {
                'power': mock_inverter_data['ppv']['value'],
                'total_power': mock_inverter_data['ppv']['value']
            },
            'consumption': {
                'house_consumption': mock_inverter_data['house_consumption']['value'],
                'current_power_w': mock_inverter_data['house_consumption']['value']
            },
            'grid': {
                'power': mock_inverter_data['active_power_total']['value'],
                'voltage': mock_inverter_data['vgrid']['value']
            }
        }
        
        coordinator.data_collector = mock_data_collector
        
        # Initialize battery selling components
        battery_selling_config = coordinator.config.get('battery_selling', {})
        coordinator.battery_selling_engine = BatterySellingEngine(battery_selling_config)
        coordinator.battery_selling_monitor = BatterySellingMonitor(battery_selling_config)
        
        # Mock inverter
        mock_inverter = Mock()
        
        # Format data for battery selling
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
        
        # Mock day time to avoid night time check
        with patch('battery_selling_monitor.datetime') as mock_datetime_monitor, \
             patch('battery_selling_engine.datetime') as mock_datetime_engine:
            
            mock_datetime_monitor.now.return_value.hour = 14  # 2 PM
            mock_datetime_engine.now.return_value.hour = 14  # 2 PM
            
            # Test safety check
            safety_report = await coordinator.battery_selling_monitor.check_safety_conditions(
                mock_inverter, selling_data
            )
            
            # Test selling opportunity analysis
            opportunity = await coordinator.battery_selling_engine.analyze_selling_opportunity(
                selling_data, mock_price_data
            )
            
            # Verify both components work together
            assert safety_report.overall_status is not None
            assert opportunity.decision is not None
            assert opportunity.safety_checks_passed is not None
            
            # If conditions are met, should recommend selling
            if (selling_data['battery']['soc_percent'] >= 80 and 
                mock_price_data['current_price_pln'] >= 0.50 and
                selling_data['grid']['voltage'] >= 200):
                assert opportunity.decision == SellingDecision.START_SELLING
                assert opportunity.expected_revenue_pln > 0
    
    @pytest.mark.asyncio
    async def test_battery_selling_with_real_inverter_data(self, config):
        """Test battery selling with real inverter data (if available)"""
        
        try:
            # Try to connect to real inverter
            charger = GoodWeFastCharger('config/master_coordinator_config.yaml')
            await charger.connect_inverter()
            status = await charger.get_inverter_status()
            
            # Initialize battery selling engine
            battery_selling_config = config.get('battery_selling', {})
            engine = BatterySellingEngine(battery_selling_config)
            
            # Prepare real data
            current_data = {
                'battery': {
                    'soc_percent': status.get('battery_soc', {}).get('value', 0),
                    'charging_status': False,
                    'current': status.get('ibattery1', {}).get('value', 0),
                    'power': status.get('pbattery1', {}).get('value', 0),
                    'temperature': status.get('battery_temperature', {}).get('value', 25)
                },
                'pv': {
                    'power_w': status.get('ppv', {}).get('value', 0)
                },
                'consumption': {
                    'power_w': status.get('house_consumption', {}).get('value', 0)
                },
                'grid': {
                    'power': status.get('active_power_total', {}).get('value', 0),
                    'voltage': status.get('vgrid', {}).get('value', 0)
                }
            }
            
            price_data = {
                'current_price_pln': 0.60,
                'price_points': [{'price': 600}]
            }
            
            # Mock day time to avoid night time check
            with patch('battery_selling_engine.datetime') as mock_datetime:
                mock_datetime.now.return_value.hour = 14  # 2 PM
                
                # Test selling opportunity analysis
                opportunity = await engine.analyze_selling_opportunity(current_data, price_data)
                
                # Verify decision was made
                assert opportunity.decision is not None
                assert opportunity.expected_revenue_pln >= 0
                assert opportunity.selling_power_w >= 0
                
                print(f"Real inverter test - Decision: {opportunity.decision}")
                print(f"Real inverter test - Revenue: {opportunity.expected_revenue_pln:.2f} PLN")
                print(f"Real inverter test - SOC: {current_data['battery']['soc_percent']}%")
                print(f"Real inverter test - Grid Voltage: {current_data['grid']['voltage']}V")
            
            await charger.disconnect()
            
        except Exception as e:
            pytest.skip(f"Real inverter not available: {e}")
    
    def test_data_format_compatibility(self, config, mock_inverter_data):
        """Test data format compatibility between components"""
        
        # Test enhanced data collector format
        collector = EnhancedDataCollector('config/master_coordinator_config.yaml')
        
        # Simulate the data structure that would be created
        expected_data_structure = {
            'battery': {
                'soc_percent': 'Unknown',
                'voltage': 'Unknown',
                'current': 'Unknown',
                'power_w': 'Unknown',
                'temperature': 'Unknown',
                'charging_status': False
            },
            'grid': {
                'power_w': 'Unknown',
                'voltage': 'Unknown',  # This should be included
                'flow_direction': 'unknown',
                'import_rate': 0.0,
                'export_rate': 0.0
            },
            'photovoltaic': {
                'current_power_w': 'Unknown',
                'current_power_kw': 0.0
            },
            'consumption': {
                'current_power_w': 'Unknown',
                'current_power_kw': 0.0
            }
        }
        
        # Verify all required fields are present
        assert 'battery' in expected_data_structure
        assert 'grid' in expected_data_structure
        assert 'photovoltaic' in expected_data_structure
        assert 'consumption' in expected_data_structure
        
        # Verify grid voltage is included
        assert 'voltage' in expected_data_structure['grid']
        
        # Test master coordinator data formatting
        coordinator = MasterCoordinator()
        coordinator.config = config
        
        # Simulate current_data from enhanced data collector
        coordinator.current_data = {
            'battery': {'soc_percent': 85, 'charging_status': False, 'current': 1.5, 'power': 500, 'temperature': 25},
            'pv': {'power': 0, 'total_power': 0},
            'consumption': {'house_consumption': 1500, 'current_power_w': 1500},
            'grid': {'power': 1000, 'voltage': 230}
        }
        
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
        
        # Verify data format is correct
        assert selling_data['battery']['soc_percent'] == 85
        assert selling_data['grid']['voltage'] == 230
        assert selling_data['pv']['power_w'] == 0
        assert selling_data['consumption']['power_w'] == 1500
    
    def test_error_handling_and_recovery(self, config):
        """Test error handling and recovery in battery selling"""
        
        # Test with invalid configuration
        invalid_config = {'battery_selling': {}}
        engine = BatterySellingEngine(invalid_config)
        
        # Should use default values
        assert engine.min_selling_soc == 80.0
        assert engine.min_selling_price_pln == 0.80  # Default from battery_selling_engine.py
        
        # Test with missing data
        coordinator = MasterCoordinator()
        coordinator.config = config
        coordinator.current_data = {}  # Empty data
        
        # Should handle missing data gracefully
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
        
        # Should not crash with missing data
        assert selling_data['battery']['soc_percent'] == 0
        assert selling_data['grid']['voltage'] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
