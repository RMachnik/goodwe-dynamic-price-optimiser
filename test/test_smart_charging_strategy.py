#!/usr/bin/env python3
"""
Tests for smart charging strategy
Verifies that the system correctly implements multi-factor charging decisions
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from automated_price_charging import AutomatedPriceCharger


class TestSmartChargingStrategy(unittest.TestCase):
    """Test smart charging strategy implementation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.charger = AutomatedPriceCharger()
        
        # Mock price data
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-07 08:00',
                    'period': '08:00 - 08:15',
                    'csdac_pln': 365.0,  # 0.365 PLN/kWh
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                },
                {
                    'dtime': '2025-09-07 13:00',
                    'period': '13:00 - 13:15',
                    'csdac_pln': 118.0,  # 0.118 PLN/kWh (cheapest)
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                },
                {
                    'dtime': '2025-09-07 20:00',
                    'period': '20:00 - 20:15',
                    'csdac_pln': 800.0,  # 0.800 PLN/kWh (most expensive)
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                }
            ]
        }
    
    def test_critical_battery_charging(self):
        """Test that critical battery level always triggers charging"""
        current_data = {
            'battery': {'soc_percent': 15},  # Critical level
            'photovoltaic': {'current_power_w': 0},
            'house_consumption': {'current_power_w': 1000},
            'grid': {'power_w': 1000, 'flow_direction': 'Import'}
        }
        
        decision = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
        
        self.assertTrue(decision['should_charge'])
        self.assertEqual(decision['priority'], 'critical')
        self.assertGreaterEqual(decision['confidence'], 0.8)
        self.assertIn('Critical battery', decision['reason'])
    
    def test_pv_overproduction_no_charging(self):
        """Test that PV overproduction prevents grid charging"""
        current_data = {
            'battery': {'soc_percent': 40},  # Medium level
            'photovoltaic': {'current_power_w': 2000},
            'house_consumption': {'current_power_w': 1000},  # 1000W overproduction
            'grid': {'power_w': -1000, 'flow_direction': 'Export'}
        }
        
        decision = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
        
        self.assertFalse(decision['should_charge'])
        self.assertEqual(decision['priority'], 'high')
        self.assertEqual(decision['confidence'], 0.9)
        self.assertIn('PV overproduction', decision['reason'])
    
    def test_price_optimization_wait(self):
        """Test that system waits for better prices when significant savings available"""
        current_data = {
            'battery': {'soc_percent': 45},  # Medium level
            'photovoltaic': {'current_power_w': 500},
            'house_consumption': {'current_power_w': 1000},
            'grid': {'power_w': 500, 'flow_direction': 'Import'}
        }
        
        # Mock current time to 08:00 (expensive price)
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 8, 0)
            
            decision = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
            
            self.assertFalse(decision['should_charge'])
            self.assertEqual(decision['priority'], 'medium')
            self.assertGreater(decision['confidence'], 0.6)
            self.assertIn('Much cheaper price available', decision['reason'])
    
    def test_low_battery_high_consumption_charging(self):
        """Test that low battery with high consumption triggers charging"""
        current_data = {
            'battery': {'soc_percent': 25},  # Low level
            'photovoltaic': {'current_power_w': 200},
            'house_consumption': {'current_power_w': 1500},
            'grid': {'power_w': 1300, 'flow_direction': 'Import'}  # High consumption
        }
        
        decision = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
        
        self.assertTrue(decision['should_charge'])
        self.assertEqual(decision['priority'], 'high')
        self.assertEqual(decision['confidence'], 0.8)
        self.assertIn('Low battery', decision['reason'])
        self.assertIn('high grid consumption', decision['reason'])
    
    def test_price_analysis_method(self):
        """Test price analysis helper method"""
        # Mock current time to 08:00 to match our test data
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 8, 0)
            
            current_price, cheapest_price, cheapest_hour = self.charger._analyze_prices(self.mock_price_data)
            
            # Should find current price (0.365 PLN/kWh at 08:00)
            self.assertIsNotNone(current_price)
            self.assertAlmostEqual(current_price, 0.365, places=3)
            
            # Should find cheapest price (0.118 PLN/kWh at 13:00)
            self.assertIsNotNone(cheapest_price)
            self.assertAlmostEqual(cheapest_price, 0.118, places=3)
            self.assertEqual(cheapest_hour, 13)
    
    def test_savings_calculation(self):
        """Test savings calculation method"""
        current_price = 0.365
        cheapest_price = 0.118
        
        savings = self.charger._calculate_savings(current_price, cheapest_price)
        
        # Should calculate ~67.7% savings
        self.assertAlmostEqual(savings, 67.7, places=1)
    
    def test_decision_history_tracking(self):
        """Test that decisions are tracked in history"""
        current_data = {
            'battery': {'soc_percent': 30},
            'photovoltaic': {'current_power_w': 1000},
            'house_consumption': {'current_power_w': 800},
            'grid': {'power_w': -200, 'flow_direction': 'Export'}
        }
        
        # Make multiple decisions
        decision1 = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
        decision2 = self.charger.make_smart_charging_decision(current_data, self.mock_price_data)
        
        # Check that history is maintained
        self.assertEqual(len(self.charger.decision_history), 2)
        self.assertIn('timestamp', self.charger.decision_history[0])
        self.assertIn('decision', self.charger.decision_history[0])
        self.assertIn('current_data', self.charger.decision_history[0])
    
    def test_edge_case_no_price_data(self):
        """Test behavior when no price data is available"""
        current_data = {
            'battery': {'soc_percent': 30},
            'photovoltaic': {'current_power_w': 1000},
            'house_consumption': {'current_power_w': 800},
            'grid': {'power_w': -200, 'flow_direction': 'Export'}
        }
        
        empty_price_data = {'value': []}
        
        decision = self.charger.make_smart_charging_decision(current_data, empty_price_data)
        
        # Should default to waiting
        self.assertFalse(decision['should_charge'])
        self.assertEqual(decision['priority'], 'low')
        self.assertIn('Wait for better conditions', decision['reason'])
    
    def test_edge_case_invalid_data(self):
        """Test behavior with invalid current data"""
        invalid_data = {}  # Empty data
        
        decision = self.charger.make_smart_charging_decision(invalid_data, self.mock_price_data)
        
        # Should handle gracefully - empty data defaults to 0% battery which triggers emergency charging
        self.assertTrue(decision['should_charge'])
        self.assertEqual(decision['priority'], 'emergency')
        self.assertIn('Emergency battery level', decision['reason'])


if __name__ == '__main__':
    unittest.main()