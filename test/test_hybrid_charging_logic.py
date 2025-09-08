#!/usr/bin/env python3
"""
Hybrid Charging Logic Tests
Tests the hybrid charging logic for optimal PV + Grid charging decisions

This test suite verifies:
- Hybrid charging decision making
- PV vs Grid charging source selection
- Timing-aware charging decisions
- Energy cost optimization
- Critical scenario handling (low price + insufficient PV timing)
- Charging efficiency calculations
"""

import unittest
import asyncio
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hybrid_charging_logic import HybridChargingLogic, ChargingDecision
from pv_forecasting import PVForecaster
from price_window_analyzer import PriceWindowAnalyzer, PriceWindow


class TestHybridChargingLogic(unittest.TestCase):
    """Test hybrid charging logic functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Mock data for testing
        self.mock_current_data = {
            'battery': {
                'soc_percent': 30.0,
                'temperature': 25.0,
                'voltage': 400.0,
                'current': 10.0,
                'power': 4000.0,
                'capacity_kwh': 10.0
            },
            'pv': {
                'power': 1500.0,  # 1.5 kW current PV
                'voltage': 350.0,
                'current': 4.3,
                'daily_energy': 8.5
            },
            'grid': {
                'power': -200.0,  # 200W export
                'voltage': 230.0,
                'frequency': 50.0
            },
            'consumption': {
                'power': 1300.0,  # 1.3 kW consumption
                'daily_energy': 6.2
            },
            'timestamp': datetime.now()
        }
        
        self.mock_price_data = {
            'prices': [0.15, 0.12, 0.08, 0.05, 0.03, 0.02] * 16,  # Very low prices
            'date': '2025-09-07',
            'currency': 'PLN',
            'unit': 'kWh',
            'current_price': 0.05,
            'low_price_threshold': 0.20
        }
        
        self.mock_pv_forecast = [
            {'hour': 0, 'power_kw': 1.5, 'confidence': 0.8},
            {'hour': 1, 'power_kw': 2.0, 'confidence': 0.7},
            {'hour': 2, 'power_kw': 2.5, 'confidence': 0.6},
            {'hour': 3, 'power_kw': 3.0, 'confidence': 0.5}
        ]
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'hybrid_charging': {
                'enabled': True,
                'max_charging_power': 3000,  # 3 kW
                'pv_charging_efficiency': 0.95,
                'grid_charging_efficiency': 0.90,
                'min_pv_power_threshold': 500,  # 500W minimum PV for charging
                'max_pv_charging_power': 2500,  # 2.5 kW max PV charging
                'grid_charging_power': 3000,    # 3 kW grid charging
                'battery_capacity_kwh': 10.0,
                'target_soc_percent': 80.0
            },
            'timing_analysis': {
                'max_wait_time_hours': 2.0,
                'min_price_savings_percent': 30.0,
                'critical_battery_soc': 20.0,
                'urgent_charging_soc': 15.0
            },
            'price_analysis': {
                'very_low_price_threshold': 0.15,  # 0.15 PLN/kWh
                'low_price_threshold': 0.35,       # 0.35 PLN/kWh
                'medium_price_threshold': 0.60,    # 0.60 PLN/kWh
                'high_price_threshold': 1.40,      # 1.40 PLN/kWh (to match test expectations)
                'very_high_price_threshold': 1.50, # 1.50 PLN/kWh
                'min_savings_threshold_pln': 0.1,  # Very low threshold for testing
                'reference_price_pln': 0.5  # Low reference price for testing
            },
            'cost_optimization': {
                'min_savings_threshold_pln': 2.0,
                'max_cost_per_kwh': 1.0,
                'prefer_pv_charging': True,
                'grid_charging_price_threshold': 0.25
            },
            'data_directory': 'out/energy_data'
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def load_config(self):
        """Load configuration from file"""
        import yaml
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_hybrid_charging_logic_initialization(self):
        """Test hybrid charging logic initialization"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        self.assertIsNotNone(logic, "Hybrid charging logic should be created")
        self.assertIsNotNone(logic.config, "Configuration should be loaded")
        self.assertEqual(logic.config['hybrid_charging']['max_charging_power'], 3000,
                        "Max charging power should be set correctly")
    
    def test_pv_only_charging_decision(self):
        """Test decision for PV-only charging when PV is sufficient"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # High PV production scenario
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 3000.0  # 3 kW PV
        current_data['consumption']['power'] = 1000.0  # 1 kW consumption
        current_data['battery']['soc_percent'] = 40.0  # 40% SOC
        
        decision = logic.make_charging_decision(
            current_data, self.mock_price_data, self.mock_pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertIsInstance(decision, ChargingDecision, "Decision should be ChargingDecision instance")
        self.assertEqual(decision.charging_source, 'pv', "Should choose PV charging")
        self.assertGreater(decision.confidence, 0.7, "Should have high confidence for PV charging")
    
    def test_grid_only_charging_decision(self):
        """Test decision for grid-only charging when PV is insufficient"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Low PV production scenario
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 200.0  # 200W PV (insufficient)
        current_data['consumption']['power'] = 1500.0  # 1.5 kW consumption
        current_data['battery']['soc_percent'] = 25.0  # 25% SOC
        
        # Very low price scenario
        price_data = self.mock_price_data.copy()
        price_data['current_price'] = 0.05  # Very low price
        
        decision = logic.make_charging_decision(
            current_data, price_data, self.mock_pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertEqual(decision.charging_source, 'grid', "Should choose grid charging")
        self.assertGreater(decision.confidence, 0.6, "Should have good confidence for grid charging")
    
    def test_hybrid_charging_decision(self):
        """Test decision for hybrid charging (PV + Grid)"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Moderate PV production scenario
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 800.0  # 0.8 kW PV (further reduced)
        current_data['consumption']['power'] = 500.0  # 0.5 kW consumption (reduced to allow PV charging)
        current_data['battery']['soc_percent'] = 22.0  # 22% SOC (low but not critical)
        
        # Create a short price window to force hybrid charging
        price_data = self.mock_price_data.copy()
        price_data['current_price'] = 0.08  # Low price
        price_data['prices'] = [0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23]  # Longer window (4 hours)
        
        # Reduce PV forecast to make PV charging insufficient
        pv_forecast = [
            {'hour': 0, 'power_kw': 0.8, 'confidence': 0.8},
            {'hour': 1, 'power_kw': 1.0, 'confidence': 0.7},
            {'hour': 2, 'power_kw': 1.2, 'confidence': 0.6},
            {'hour': 3, 'power_kw': 1.5, 'confidence': 0.5}
        ]
        
        decision = logic.make_charging_decision(
            current_data, price_data, pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertEqual(decision.charging_source, 'hybrid', "Should choose hybrid charging")
        self.assertGreater(decision.pv_contribution_kwh, 0, "Should use PV contribution")
        self.assertGreater(decision.grid_contribution_kwh, 0, "Should use grid contribution")
    
    def test_critical_scenario_low_price_insufficient_pv(self):
        """Test critical scenario: low price window + insufficient PV timing"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Critical scenario: Low price window ending soon, insufficient PV
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 800.0  # 800W PV (insufficient for fast charging)
        current_data['battery']['soc_percent'] = 25.0  # 25% SOC (low but not critical)
        current_data['battery']['capacity_kwh'] = 10.0
        
        # Very low price with short window
        price_data = self.mock_price_data.copy()
        price_data['current_price'] = 0.03  # Very low price
        # Use future prices to avoid being filtered out as past prices
        # Provide 4 price points (1 hour) to make window shorter and more urgent
        price_data['prices'] = [0.03, 0.04, 0.05, 0.06]  # 1-hour window (more urgent)
        price_data['price_window_remaining_hours'] = 1.0  # Very short window
        
        # PV forecast shows slow improvement
        pv_forecast = [
            {'hour': 0, 'power_kw': 0.8, 'confidence': 0.8},
            {'hour': 1, 'power_kw': 1.2, 'confidence': 0.7},
            {'hour': 2, 'power_kw': 1.8, 'confidence': 0.6},
            {'hour': 3, 'power_kw': 2.5, 'confidence': 0.5}
        ]
        
        decision = logic.make_charging_decision(
            current_data, price_data, pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertEqual(decision.charging_source, 'grid', "Should choose grid charging for critical scenario")
        self.assertGreater(decision.confidence, 0.8, "Should have high confidence for critical scenario")
        self.assertIn('low price window', decision.reason.lower(), "Should mention low price window in reasoning")
    
    def test_wait_decision_improving_pv(self):
        """Test decision to wait when PV is improving significantly"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Current low PV but improving forecast
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 600.0  # 600W current PV
        current_data['battery']['soc_percent'] = 45.0  # 45% SOC (not critical)
        
        # Medium price (not very low)
        price_data = self.mock_price_data.copy()
        price_data['current_price'] = 0.35  # Medium price
        
        # PV forecast shows significant improvement
        pv_forecast = [
            {'hour': 0, 'power_kw': 0.6, 'confidence': 0.8},
            {'hour': 1, 'power_kw': 1.5, 'confidence': 0.8},
            {'hour': 2, 'power_kw': 2.8, 'confidence': 0.7},
            {'hour': 3, 'power_kw': 3.5, 'confidence': 0.6}
        ]
        
        decision = logic.make_charging_decision(
            current_data, price_data, pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertEqual(decision.action, 'wait', "Should decide to wait for better PV")
        self.assertIn('pv improvement', decision.reason.lower(), "Should mention PV improvement in reasoning")
    
    def test_urgent_charging_critical_battery(self):
        """Test urgent charging when battery is critically low"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Critical battery scenario
        current_data = self.mock_current_data.copy()
        current_data['battery']['soc_percent'] = 12.0  # 12% SOC (critical)
        current_data['pv']['power'] = 500.0  # Low PV
        
        # High price scenario
        price_data = self.mock_price_data.copy()
        price_data['current_price'] = 0.85  # High price
        
        decision = logic.make_charging_decision(
            current_data, price_data, self.mock_pv_forecast
        )
        
        self.assertIsNotNone(decision, "Charging decision should be made")
        self.assertIn(decision.action, ['start_charging', 'start_grid_charging'], "Should start charging immediately")
        self.assertIn('critical', decision.reason.lower(), "Should mention critical battery in reasoning")
        self.assertGreater(decision.confidence, 0.9, "Should have very high confidence for critical scenario")
    
    def test_energy_cost_calculation(self):
        """Test energy cost calculation for different charging sources"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test PV charging cost (should be very low)
        pv_cost = logic.calculate_charging_cost('pv', 5.0, 0.0)  # 5 kWh, no grid price
        self.assertAlmostEqual(pv_cost, 0.0, places=2, msg="PV charging should have minimal cost")
        
        # Test grid charging cost
        grid_cost = logic.calculate_charging_cost('grid', 5.0, 0.25)  # 5 kWh at 0.25 PLN/kWh
        expected_cost = 5.0 * 0.25 / 0.90  # Account for efficiency
        self.assertAlmostEqual(grid_cost, expected_cost, places=2, 
                              msg="Grid charging cost should be calculated correctly")
        
        # Test hybrid charging cost
        hybrid_cost = logic.calculate_charging_cost('hybrid', 5.0, 0.20, pv_contribution=3.0)
        expected_cost = (3.0 * 0.0 + 2.0 * 0.20) / 0.90  # 3 kWh PV + 2 kWh grid
        self.assertAlmostEqual(hybrid_cost, expected_cost, places=2,
                              msg="Hybrid charging cost should be calculated correctly")
    
    def test_charging_efficiency_calculation(self):
        """Test charging efficiency calculations"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test PV charging efficiency
        pv_efficiency = logic.get_charging_efficiency('pv')
        self.assertEqual(pv_efficiency, 0.95, "PV charging efficiency should be 95%")
        
        # Test grid charging efficiency
        grid_efficiency = logic.get_charging_efficiency('grid')
        self.assertEqual(grid_efficiency, 0.90, "Grid charging efficiency should be 90%")
        
        # Test hybrid charging efficiency (weighted average)
        hybrid_efficiency = logic.get_charging_efficiency('hybrid', pv_ratio=0.6)
        expected_efficiency = 0.6 * 0.95 + 0.4 * 0.90  # Weighted average
        self.assertAlmostEqual(hybrid_efficiency, expected_efficiency, places=3,
                              msg="Hybrid charging efficiency should be weighted average")
    
    def test_charging_power_calculation(self):
        """Test charging power calculations"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test PV charging power
        pv_power = logic.calculate_charging_power('pv', 2000.0)  # 2 kW available PV
        self.assertEqual(pv_power, 2000.0, "PV charging power should match available PV")
        
        # Test grid charging power
        grid_power = logic.calculate_charging_power('grid', 0.0)  # No PV available
        self.assertEqual(grid_power, 3000.0, "Grid charging power should be max grid power")
        
        # Test hybrid charging power
        hybrid_power = logic.calculate_charging_power('hybrid', 1500.0)  # 1.5 kW PV available
        expected_power = min(1500.0, 2500.0) + 3000.0  # PV + Grid
        self.assertEqual(hybrid_power, expected_power, "Hybrid charging power should be PV + Grid")
    
    def test_charging_duration_calculation(self):
        """Test charging duration calculations"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test charging duration for different scenarios
        energy_needed = 5.0  # 5 kWh needed
        
        # PV charging duration
        pv_duration = logic.calculate_charging_duration('pv', energy_needed, 2000.0)  # 2 kW PV
        expected_duration = 5.0 / 2.0  # 2.5 hours
        self.assertAlmostEqual(pv_duration, expected_duration, places=2,
                              msg="PV charging duration should be calculated correctly")
        
        # Grid charging duration
        grid_duration = logic.calculate_charging_duration('grid', energy_needed, 0.0)  # 3 kW grid
        expected_duration = 5.0 / 3.0  # 1.67 hours
        self.assertAlmostEqual(grid_duration, expected_duration, places=2,
                              msg="Grid charging duration should be calculated correctly")
        
        # Hybrid charging duration
        hybrid_duration = logic.calculate_charging_duration('hybrid', energy_needed, 1500.0)  # 1.5 kW PV + 3 kW grid
        expected_duration = 5.0 / (1.5 + 3.0)  # 1.11 hours
        self.assertAlmostEqual(hybrid_duration, expected_duration, places=2,
                              msg="Hybrid charging duration should be calculated correctly")
    
    def test_savings_calculation(self):
        """Test savings calculation compared to average price"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test savings for different charging scenarios
        energy_needed = 5.0  # 5 kWh
        average_price = 0.50  # 0.50 PLN/kWh average
        
        # PV charging savings (should be maximum)
        pv_savings = logic.calculate_savings('pv', energy_needed, average_price, 0.0)
        expected_savings = 5.0 * 0.50  # Full savings
        self.assertAlmostEqual(pv_savings, expected_savings, places=2,
                              msg="PV charging should provide maximum savings")
        
        # Grid charging savings
        grid_savings = logic.calculate_savings('grid', energy_needed, average_price, 0.20)
        expected_savings = 5.0 * (0.50 - 0.20)  # Difference in price
        self.assertAlmostEqual(grid_savings, expected_savings, places=2,
                              msg="Grid charging savings should be calculated correctly")
    
    def test_decision_confidence_calculation(self):
        """Test decision confidence calculation"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test high confidence scenario (clear PV advantage)
        current_data = self.mock_current_data.copy()
        current_data['pv']['power'] = 3000.0  # High PV
        current_data['battery']['soc_percent'] = 40.0  # Good SOC
        
        confidence = logic.calculate_decision_confidence(current_data, self.mock_price_data, 'pv')
        self.assertGreater(confidence, 0.8, "Should have high confidence for clear PV advantage")
        
        # Test medium confidence scenario (mixed conditions)
        current_data['pv']['power'] = 1500.0  # Medium PV
        current_data['battery']['soc_percent'] = 30.0  # Medium SOC
        
        confidence = logic.calculate_decision_confidence(current_data, self.mock_price_data, 'hybrid')
        self.assertGreater(confidence, 0.5, "Should have medium confidence for mixed conditions")
        self.assertLess(confidence, 0.8, "Should not have very high confidence for mixed conditions")
        
        # Test low confidence scenario (unclear conditions)
        current_data['pv']['power'] = 800.0  # Low PV
        current_data['battery']['soc_percent'] = 50.0  # High SOC
        
        confidence = logic.calculate_decision_confidence(current_data, self.mock_price_data, 'wait')
        self.assertLess(confidence, 0.6, "Should have lower confidence for unclear conditions")
    
    def test_error_handling_invalid_data(self):
        """Test error handling with invalid data"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test with invalid current data
        invalid_data = {
            'battery': {'soc_percent': -10.0},  # Invalid SOC
            'pv': {'power': -100.0},  # Invalid PV power
            'timestamp': 'invalid_timestamp'
        }
        
        # Should handle invalid data gracefully
        try:
            decision = logic.make_charging_decision(
                invalid_data, self.mock_price_data, self.mock_pv_forecast
            )
            self.assertIsNotNone(decision, "Should handle invalid data gracefully")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle invalid data gracefully, got exception: {e}")
    
    def test_error_handling_missing_config(self):
        """Test error handling with missing configuration"""
        # Test with non-existent config file
        invalid_config_path = os.path.join(self.temp_dir, 'non_existent_config.yaml')
        
        # Should handle missing config gracefully
        try:
            logic = HybridChargingLogic(invalid_config_path)
            self.assertIsNotNone(logic, "Should create logic even with missing config")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle missing config gracefully, got exception: {e}")


class TestHybridChargingPerformance(unittest.TestCase):
    """Test hybrid charging logic performance characteristics"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'hybrid_charging': {
                'enabled': True,
                'max_charging_power': 3000,
                'pv_charging_efficiency': 0.95,
                'grid_charging_efficiency': 0.90,
                'battery_capacity_kwh': 10.0
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def load_config(self):
        """Load test configuration"""
        import yaml
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_decision_making_performance(self):
        """Test decision making performance"""
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Test multiple decision cycles
        start_time = datetime.now()
        decision_count = 0
        
        for i in range(100):  # 100 decision cycles
            try:
                current_data = {
                    'battery': {'soc_percent': 30.0 + (i % 50), 'capacity_kwh': 10.0},
                    'pv': {'power': 1000.0 + (i % 2000)},
                    'consumption': {'power': 1200.0},
                    'timestamp': datetime.now()
                }
                
                price_data = {
                    'current_price': 0.20 + (i % 100) * 0.01,
                    'low_price_threshold': 0.25
                }
                
                pv_forecast = [
                    {'hour': 0, 'power_kw': 1.0, 'confidence': 0.8},
                    {'hour': 1, 'power_kw': 1.5, 'confidence': 0.7}
                ]
                
                decision = logic.make_charging_decision(current_data, price_data, pv_forecast)
                decision_count += 1
            except Exception as e:
                pass
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Performance assertions
        self.assertGreater(decision_count, 90, "Should complete at least 90 decisions")
        self.assertLess(duration, 5.0, "100 decisions should complete within 5 seconds")
        
        # Calculate performance metrics
        avg_decision_time = duration / decision_count if decision_count > 0 else 0
        self.assertLess(avg_decision_time, 0.05, "Average decision time should be less than 50ms")
    
    def test_memory_usage(self):
        """Test memory usage of hybrid charging logic"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create logic
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        # Get memory usage after creation
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 5MB)
        self.assertLess(memory_increase, 5 * 1024 * 1024, 
                       f"Memory increase should be less than 5MB, got {memory_increase / 1024 / 1024:.2f}MB")
    
    def test_initialization_time(self):
        """Test hybrid charging logic initialization time"""
        start_time = datetime.now()
        
        config = self.load_config()
        logic = HybridChargingLogic(config)
        
        end_time = datetime.now()
        initialization_time = (end_time - start_time).total_seconds()
        
        # Initialization should be fast (less than 1 second)
        self.assertLess(initialization_time, 1.0, 
                       f"Initialization should be less than 1 second, got {initialization_time:.2f} seconds")


if __name__ == '__main__':
    unittest.main(verbosity=2)
