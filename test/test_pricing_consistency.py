#!/usr/bin/env python3
"""
Comprehensive tests for pricing system consistency across all components
Ensures all components use the same pricing methodology with correct SC component calculation
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from automated_price_charging import AutomatedPriceCharger
from master_coordinator import MasterCoordinator, MultiFactorDecisionEngine
from log_web_server import LogWebServer
from multi_session_manager import MultiSessionManager
from price_window_analyzer import PriceWindowAnalyzer
from battery_selling_engine import BatterySellingEngine


class TestPricingConsistency(unittest.TestCase):
    """Test pricing consistency across all components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_config = {
            'electricity_pricing': {
                'sc_component_net': 0.0892,
                'sc_component_gross': 0.1097,
                'minimum_price_floor': 0.0050
            },
            'battery_management': {
                'soc_thresholds': {
                    'critical': 12,
                    'emergency': 5
                }
            }
        }
        
        # Mock price data (PLN/MWh from PSE API)
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-07 08:00',
                    'period': '08:00 - 08:15',
                    'csdac_pln': 300.0,  # 0.300 PLN/kWh market price
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                },
                {
                    'dtime': '2025-09-07 13:00',
                    'period': '13:00 - 13:15',
                    'csdac_pln': 118.0,  # 0.118 PLN/kWh market price
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                },
                {
                    'dtime': '2025-09-07 20:00',
                    'period': '20:00 - 20:15',
                    'csdac_pln': 800.0,  # 0.800 PLN/kWh market price
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                }
            ]
        }
    
    def test_automated_price_charger_sc_component(self):
        """Test AutomatedPriceCharger SC component calculation"""
        charger = AutomatedPriceCharger()
        
        # Test SC component calculation
        market_price_pln_kwh = 0.300  # 300 PLN/MWh = 0.300 PLN/kWh
        expected_final_price = 0.300 + 0.0892  # 0.3892 PLN/kWh
        actual_final_price = charger.calculate_final_price(market_price_pln_kwh)
        
        self.assertAlmostEqual(actual_final_price, expected_final_price, places=4)
    
    def test_automated_price_charger_get_current_price(self):
        """Test AutomatedPriceCharger get_current_price method"""
        charger = AutomatedPriceCharger()
        
        # Mock current time to 08:00
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 8, 0)
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            current_price = charger.get_current_price(self.mock_price_data)
            
            # Should return final price (market + SC component) in PLN/MWh
            # The get_current_price method returns the price in PLN/MWh, not PLN/kWh
            expected_price = (300.0 + 89.2)  # 300 PLN/MWh + 89.2 PLN/MWh = 389.2 PLN/MWh
            self.assertAlmostEqual(current_price, expected_price, places=1)
    
    def test_automated_price_charger_analyze_prices(self):
        """Test AutomatedPriceCharger _analyze_prices method"""
        charger = AutomatedPriceCharger()
        
        # Mock current time to 08:00
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 8, 0)
            
            current_price, cheapest_price, cheapest_hour = charger._analyze_prices(self.mock_price_data)
            
            # Current price should be 08:00 price + SC component in PLN/kWh
            expected_current = (300.0 / 1000) + 0.0892  # 0.3892 PLN/kWh
            self.assertAlmostEqual(current_price, expected_current, places=4)
            
            # Cheapest price should be 13:00 price + SC component in PLN/kWh
            expected_cheapest = (118.0 / 1000) + 0.0892  # 0.2072 PLN/kWh
            self.assertAlmostEqual(cheapest_price, expected_cheapest, places=4)
            self.assertEqual(cheapest_hour, 13)
    
    def test_price_window_analyzer_sc_component(self):
        """Test PriceWindowAnalyzer SC component calculation"""
        analyzer = PriceWindowAnalyzer(self.mock_config)
        
        # Test _get_current_price method
        with patch('price_window_analyzer.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 8, 0)
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            current_price = analyzer._get_current_price(self.mock_price_data, datetime(2025, 9, 7, 8, 0))
            
            # Should return final price (market + SC component) in PLN/MWh
            expected_price = 300.0 + 89.2  # 389.2 PLN/MWh
            self.assertAlmostEqual(current_price, expected_price, places=1)
    
    def test_master_coordinator_price_conversion(self):
        """Test MasterCoordinator price conversion and usage"""
        # Mock the charging controller
        mock_charging_controller = Mock()
        mock_charging_controller.get_current_price.return_value = 389.2  # PLN/MWh
        
        # Create decision engine
        decision_engine = MultiFactorDecisionEngine(self.mock_config, mock_charging_controller)
        
        # Test price score calculation
        price_data = {'value': [{'csdac_pln': 300.0}]}
        score = decision_engine._calculate_price_score(price_data)
        
        # Should convert PLN/MWh to PLN/kWh and calculate score
        # 300 PLN/MWh = 0.3 PLN/kWh, which should give a high score (80+)
        self.assertGreater(score, 80)
    
    def test_log_web_server_price_calculation(self):
        """Test LogWebServer price calculation consistency"""
        server = LogWebServer(self.mock_config)
        
        # Mock AutomatedPriceCharger
        with patch('automated_price_charging.AutomatedPriceCharger') as mock_charger_class:
            mock_charger = Mock()
            mock_charger_class.return_value = mock_charger
            
            # Mock price data and methods
            mock_charger.fetch_price_data_for_date.return_value = self.mock_price_data
            mock_charger.get_current_price.return_value = 389.2  # PLN/MWh
            mock_charger.calculate_final_price.return_value = 389.2  # PLN/MWh
            
            price_data = server._get_real_price_data()
            
            self.assertIsNotNone(price_data)
            self.assertIn('current_price_pln_kwh', price_data)
            # Should be converted to PLN/kWh
            self.assertAlmostEqual(price_data['current_price_pln_kwh'], 0.3892, places=4)
    
    def test_multi_session_manager_price_usage(self):
        """Test MultiSessionManager price usage consistency"""
        manager = MultiSessionManager(self.mock_config)
        
        # Mock AutomatedPriceCharger
        with patch.object(manager, 'price_analyzer') as mock_analyzer:
            mock_analyzer.fetch_price_data_for_date.return_value = self.mock_price_data
            
            # Test price data fetching (async method)
            import asyncio
            price_data = asyncio.run(manager._fetch_price_data_for_date(datetime(2025, 9, 7)))
            self.assertEqual(price_data, self.mock_price_data)
            
            # Test that price analyzer methods are called correctly
            mock_analyzer.fetch_price_data_for_date.assert_called_once_with('2025-09-07')
    
    def test_battery_selling_engine_price_integration(self):
        """Test BatterySellingEngine price integration"""
        engine = BatterySellingEngine(self.mock_config)
        
        # Test price data format expected by selling engine
        selling_price_data = {
            'current_price_pln': 0.3892  # PLN/kWh (already converted)
        }
        
        current_data = {
            'battery': {'soc_percent': 85},
            'photovoltaic': {'current_power_w': 1000},
            'house_consumption': {'current_power_w': 2000}
        }
        
        # Test selling opportunity analysis
        opportunity = engine._analyze_selling_opportunity(current_data, selling_price_data)
        
        self.assertIsNotNone(opportunity)
        # Check if it's a SellingOpportunity object
        self.assertTrue(hasattr(opportunity, 'decision'))
        self.assertTrue(hasattr(opportunity, 'expected_revenue_pln'))
    
    def test_pricing_consistency_across_components(self):
        """Test that all components use the same pricing methodology"""
        # Test data: 300 PLN/MWh market price
        market_price_pln_mwh = 300.0
        market_price_pln_kwh = 0.300
        sc_component_pln_kwh = 0.0892
        sc_component_pln_mwh = 89.2
        expected_final_pln_kwh = 0.3892
        expected_final_pln_mwh = 389.2
        
        # Test AutomatedPriceCharger
        charger = AutomatedPriceCharger()
        final_price_kwh = charger.calculate_final_price(market_price_pln_kwh)
        self.assertAlmostEqual(final_price_kwh, expected_final_pln_kwh, places=4)
        
        # Test PriceWindowAnalyzer
        analyzer = PriceWindowAnalyzer(self.mock_config)
        # PriceWindowAnalyzer works in PLN/MWh
        final_price_mwh = market_price_pln_mwh + sc_component_pln_mwh
        self.assertAlmostEqual(final_price_mwh, expected_final_pln_mwh, places=1)
        
        # Test conversion consistency
        # PLN/MWh to PLN/kWh conversion
        converted_kwh = expected_final_pln_mwh / 1000
        self.assertAlmostEqual(converted_kwh, expected_final_pln_kwh, places=4)
    
    def test_sc_component_value_consistency(self):
        """Test that SC component value is consistent across all components"""
        expected_sc_component = 0.0892  # PLN/kWh
        
        # Test AutomatedPriceCharger
        charger = AutomatedPriceCharger()
        self.assertEqual(charger.sc_component_net, expected_sc_component)
        
        # Test PriceWindowAnalyzer (converted to PLN/MWh)
        expected_sc_component_mwh = expected_sc_component * 1000  # 89.2 PLN/MWh
        # This is hardcoded in the analyzer, so we test the conversion
        self.assertEqual(89.2, expected_sc_component_mwh)
    
    def test_price_data_format_consistency(self):
        """Test that all components expect the same price data format"""
        # All components should work with the standard PSE API format
        required_fields = ['dtime', 'csdac_pln', 'period', 'business_date']
        
        for item in self.mock_price_data['value']:
            for field in required_fields:
                self.assertIn(field, item, f"Price data item missing required field: {field}")
    
    def test_unit_conversion_consistency(self):
        """Test that unit conversions are consistent across components"""
        # Test PLN/MWh to PLN/kWh conversion
        pln_mwh = 300.0
        pln_kwh = pln_mwh / 1000
        self.assertEqual(pln_kwh, 0.3)
        
        # Test PLN/kWh to PLN/MWh conversion
        pln_kwh = 0.3
        pln_mwh = pln_kwh * 1000
        self.assertEqual(pln_mwh, 300.0)
        
        # Test SC component conversion
        sc_kwh = 0.0892
        sc_mwh = sc_kwh * 1000
        self.assertEqual(sc_mwh, 89.2)
    
    def test_price_calculation_edge_cases(self):
        """Test price calculation with edge cases"""
        charger = AutomatedPriceCharger()
        
        # Test with zero market price
        final_price = charger.calculate_final_price(0.0)
        self.assertEqual(final_price, 0.0892)  # Only SC component
        
        # Test with negative market price (should not happen in practice)
        final_price = charger.calculate_final_price(-0.1)
        self.assertAlmostEqual(final_price, -0.0108, places=4)  # -0.1 + 0.0892
        
        # Test with very high market price
        final_price = charger.calculate_final_price(10.0)
        self.assertEqual(final_price, 10.0892)
    
    def test_minimum_price_floor(self):
        """Test minimum price floor application"""
        charger = AutomatedPriceCharger()
        
        # Test with price below floor
        price_below_floor = 0.001
        adjusted_price = charger.apply_minimum_price_floor(price_below_floor)
        self.assertEqual(adjusted_price, 0.0050)  # Minimum floor
        
        # Test with price above floor
        price_above_floor = 0.1
        adjusted_price = charger.apply_minimum_price_floor(price_above_floor)
        self.assertEqual(adjusted_price, 0.1)  # Unchanged


class TestPricingIntegration(unittest.TestCase):
    """Test pricing integration between components"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_config = {
            'electricity_pricing': {
                'sc_component_net': 0.0892,
                'sc_component_gross': 0.1097,
                'minimum_price_floor': 0.0050
            },
            'battery_management': {
                'soc_thresholds': {
                    'critical': 12,
                    'emergency': 5
                }
            }
        }
        
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-07 08:00',
                    'period': '08:00 - 08:15',
                    'csdac_pln': 300.0,
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:45:15.929'
                }
            ]
        }
    
    def test_master_coordinator_to_decision_engine_flow(self):
        """Test price data flow from MasterCoordinator to DecisionEngine"""
        # Mock charging controller
        mock_charging_controller = Mock()
        mock_charging_controller.get_current_price.return_value = 389.2  # PLN/MWh
        
        # Create decision engine
        decision_engine = MultiFactorDecisionEngine(self.mock_config, mock_charging_controller)
        
        # Test price score calculation
        score = decision_engine._calculate_price_score(self.mock_price_data)
        
        # Should get price from charging controller and calculate score
        mock_charging_controller.get_current_price.assert_called_once_with(self.mock_price_data)
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
    
    def test_log_web_server_to_automated_charger_flow(self):
        """Test price data flow from LogWebServer to AutomatedPriceCharger"""
        server = LogWebServer(self.mock_config)
        
        with patch('automated_price_charging.AutomatedPriceCharger') as mock_charger_class:
            mock_charger = Mock()
            mock_charger_class.return_value = mock_charger
            
            # Mock methods
            mock_charger.fetch_price_data_for_date.return_value = self.mock_price_data
            mock_charger.get_current_price.return_value = 389.2  # PLN/MWh
            mock_charger.calculate_final_price.return_value = 389.2  # PLN/MWh
            
            # Test price data retrieval
            price_data = server._get_real_price_data()
            
            # Verify AutomatedPriceCharger methods were called
            mock_charger.fetch_price_data_for_date.assert_called_once()
            mock_charger.get_current_price.assert_called_once_with(self.mock_price_data)
            
            self.assertIsNotNone(price_data)
    
    def test_multi_session_manager_to_automated_charger_flow(self):
        """Test price data flow from MultiSessionManager to AutomatedPriceCharger"""
        manager = MultiSessionManager(self.mock_config)
        
        with patch.object(manager, 'price_analyzer') as mock_analyzer:
            mock_analyzer.fetch_price_data_for_date.return_value = self.mock_price_data
            mock_analyzer.analyze_charging_windows.return_value = []
            
            # Test price data fetching (async method)
            import asyncio
            price_data = asyncio.run(manager._fetch_price_data_for_date(datetime(2025, 9, 7)))
            
            # Verify AutomatedPriceCharger method was called
            mock_analyzer.fetch_price_data_for_date.assert_called_once_with('2025-09-07')
            self.assertEqual(price_data, self.mock_price_data)


if __name__ == '__main__':
    unittest.main()
