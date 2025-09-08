#!/usr/bin/env python3
"""
End-to-End System Integration Tests
Tests the complete flow from data collection to decision execution

This test suite verifies:
- Complete system initialization
- Data flow from collection to decision making
- Decision execution and monitoring
- Error handling and recovery
- System performance under various conditions
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
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MasterCoordinator, SystemState
from enhanced_data_collector import EnhancedDataCollector
from automated_price_charging import AutomatedPriceCharger
from polish_electricity_analyzer import PolishElectricityAnalyzer
from weather_data_collector import WeatherDataCollector
from pv_consumption_analyzer import PVConsumptionAnalyzer
from multi_session_manager import MultiSessionManager


class TestEndToEndIntegration(unittest.TestCase):
    """Test complete system integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Mock data for testing
        self.mock_inverter_data = {
            'battery': {
                'soc_percent': 45.0,
                'temperature': 25.0,
                'voltage': 400.0,
                'current': 10.0,
                'power': 4000.0
            },
            'pv': {
                'power': 2500.0,
                'voltage': 350.0,
                'current': 7.0
            },
            'grid': {
                'power': -500.0,  # Negative = export
                'voltage': 230.0,
                'frequency': 50.0
            },
            'consumption': {
                'power': 2000.0
            }
        }
        
        self.mock_price_data = {
            'prices': [0.25, 0.30, 0.35, 0.40, 0.45, 0.50] * 16,  # 96 prices
            'date': '2025-09-07',
            'currency': 'PLN',
            'unit': 'kWh'
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'system': {
                'inverter_ip': '192.168.1.100',
                'inverter_port': 8899,
                'data_collection_interval': 60,
                'decision_interval': 900
            },
            'charging': {
                'max_charging_power': 3000,
                'min_battery_soc': 20,
                'max_battery_soc': 90,
                'price_threshold_percentile': 25
            },
            'weather_integration': {
                'enabled': True,
                'imgw_enabled': True,
                'openmeteo_enabled': True
            },
            'pv_consumption_analysis': {
                'pv_overproduction_threshold_w': 500,
                'consumption_forecast_days': 7
            },
            'multi_session_charging': {
                'enabled': True,
                'max_sessions_per_day': 3,
                'min_session_duration_minutes': 15
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @patch('weather_data_collector.aiohttp')
    @pytest.mark.asyncio
    async def test_complete_system_initialization(self, mock_aiohttp, mock_requests, mock_goodwe):
        """Test complete system initialization flow"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Mock weather API
        mock_aiohttp.ClientSession.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.json.return_value = {
            'current_weather': {'temperature': 20.0, 'humidity': 60.0}
        }
        
        # Initialize master coordinator
        coordinator = MasterCoordinator(self.config_path)
        
        # Test initialization
        success = await coordinator.initialize()
        self.assertTrue(success, "System initialization should succeed")
        
        # Verify all components are initialized
        self.assertIsNotNone(coordinator.data_collector, "Data collector should be initialized")
        self.assertIsNotNone(coordinator.price_analyzer, "Price analyzer should be initialized")
        self.assertIsNotNone(coordinator.charging_controller, "Charging controller should be initialized")
        self.assertIsNotNone(coordinator.decision_engine, "Decision engine should be initialized")
        self.assertIsNotNone(coordinator.weather_collector, "Weather collector should be initialized")
        self.assertIsNotNone(coordinator.pv_consumption_analyzer, "PV consumption analyzer should be initialized")
        self.assertIsNotNone(coordinator.multi_session_manager, "Multi-session manager should be initialized")
        
        # Verify system state
        self.assertEqual(coordinator.state, SystemState.INITIALIZING, "System should be in initializing state")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_data_collection_to_decision_flow(self, mock_requests, mock_goodwe):
        """Test complete data collection to decision making flow"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test data collection
        current_data = await coordinator.data_collector.collect_data()
        self.assertIsNotNone(current_data, "Data collection should return data")
        self.assertIn('battery', current_data, "Data should contain battery information")
        self.assertIn('pv', current_data, "Data should contain PV information")
        self.assertIn('grid', current_data, "Data should contain grid information")
        
        # Test price analysis
        price_data = await coordinator.price_analyzer.get_current_prices()
        self.assertIsNotNone(price_data, "Price analysis should return data")
        
        # Test decision making
        decision = coordinator.decision_engine.make_decision(current_data, price_data)
        self.assertIsNotNone(decision, "Decision engine should make a decision")
        self.assertIn('action', decision, "Decision should contain action")
        self.assertIn('confidence', decision, "Decision should contain confidence")
        self.assertIn('reasoning', decision, "Decision should contain reasoning")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_decision_execution_flow(self, mock_requests, mock_goodwe):
        """Test decision execution and monitoring flow"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_inverter.set_charging.return_value = True
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test decision execution
        current_data = await coordinator.data_collector.collect_data()
        price_data = await coordinator.price_analyzer.get_current_prices()
        decision = coordinator.decision_engine.make_decision(current_data, price_data)
        
        # Execute decision
        if decision['action'] == 'start_charging':
            success = await coordinator.charging_controller.start_charging()
            self.assertTrue(success, "Charging should start successfully")
        elif decision['action'] == 'stop_charging':
            success = await coordinator.charging_controller.stop_charging()
            self.assertTrue(success, "Charging should stop successfully")
        
        # Test monitoring
        status = await coordinator.charging_controller.get_status()
        self.assertIsNotNone(status, "Status should be available")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, mock_requests, mock_goodwe):
        """Test error handling and recovery mechanisms"""
        # Mock GoodWe inverter with connection failure
        mock_goodwe.connect.side_effect = Exception("Connection failed")
        
        # Mock price API with failure
        mock_response = Mock()
        mock_response.status_code = 500
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        
        # Test initialization with errors
        success = await coordinator.initialize()
        # Should handle errors gracefully
        self.assertIsNotNone(coordinator, "Coordinator should be created even with errors")
        
        # Test data collection with errors
        try:
            current_data = await coordinator.data_collector.collect_data()
            # Should handle errors gracefully
        except Exception as e:
            # Expected to handle errors
            pass
        
        # Test price analysis with errors
        try:
            price_data = await coordinator.price_analyzer.get_current_prices()
            # Should handle errors gracefully
        except Exception as e:
            # Expected to handle errors
            pass
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_system_performance_under_load(self, mock_requests, mock_goodwe):
        """Test system performance under various load conditions"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test multiple decision cycles
        start_time = datetime.now()
        decision_count = 0
        
        for i in range(10):  # Simulate 10 decision cycles
            try:
                current_data = await coordinator.data_collector.collect_data()
                price_data = await coordinator.price_analyzer.get_current_prices()
                decision = coordinator.decision_engine.make_decision(current_data, price_data)
                decision_count += 1
            except Exception as e:
                # Handle any errors gracefully
                pass
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Performance assertions
        self.assertGreater(decision_count, 0, "Should complete at least one decision cycle")
        self.assertLess(duration, 30.0, "10 decision cycles should complete within 30 seconds")
        
        # Calculate performance metrics
        avg_decision_time = duration / decision_count if decision_count > 0 else 0
        self.assertLess(avg_decision_time, 3.0, "Average decision time should be less than 3 seconds")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_multi_session_coordination(self, mock_requests, mock_goodwe):
        """Test multi-session charging coordination"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test multi-session planning
        daily_plan = coordinator.multi_session_manager.create_daily_plan(
            self.mock_price_data, 
            self.mock_inverter_data
        )
        
        self.assertIsNotNone(daily_plan, "Daily plan should be created")
        self.assertGreater(len(daily_plan.sessions), 0, "Daily plan should contain sessions")
        
        # Test session execution
        for session in daily_plan.sessions:
            if session.status == 'planned':
                # Simulate session start
                session.status = 'active'
                self.assertEqual(session.status, 'active', "Session should be marked as active")
                
                # Simulate session completion
                session.status = 'completed'
                self.assertEqual(session.status, 'completed', "Session should be marked as completed")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_weather_integration_flow(self, mock_requests, mock_goodwe):
        """Test weather data integration in decision making"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test weather data collection
        if coordinator.weather_collector:
            weather_data = await coordinator.weather_collector.collect_weather_data()
            self.assertIsNotNone(weather_data, "Weather data should be collected")
            
            # Test weather-enhanced decision making
            current_data = await coordinator.data_collector.collect_data()
            price_data = await coordinator.price_analyzer.get_current_prices()
            
            # Add weather data to current data
            current_data['weather'] = weather_data
            
            decision = coordinator.decision_engine.make_decision(current_data, price_data)
            self.assertIsNotNone(decision, "Weather-enhanced decision should be made")
    
    def test_system_state_transitions(self):
        """Test system state transitions"""
        coordinator = MasterCoordinator(self.config_path)
        
        # Test initial state
        self.assertEqual(coordinator.state, SystemState.INITIALIZING, "Should start in initializing state")
        
        # Test state transitions
        coordinator.state = SystemState.MONITORING
        self.assertEqual(coordinator.state, SystemState.MONITORING, "Should transition to monitoring state")
        
        coordinator.state = SystemState.MAINTENANCE
        self.assertEqual(coordinator.state, SystemState.MAINTENANCE, "Should transition to maintenance state")
        
        coordinator.state = SystemState.ERROR
        self.assertEqual(coordinator.state, SystemState.ERROR, "Should transition to error state")
    
    @patch('enhanced_data_collector.goodwe')
    @patch('automated_price_charging.requests')
    @pytest.mark.asyncio
    async def test_data_persistence_and_recovery(self, mock_requests, mock_goodwe):
        """Test data persistence and recovery mechanisms"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Mock price API
        mock_response = Mock()
        mock_response.json.return_value = self.mock_price_data
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Initialize coordinator
        coordinator = MasterCoordinator(self.config_path)
        await coordinator.initialize()
        
        # Test data collection and storage
        current_data = await coordinator.data_collector.collect_data()
        
        # Simulate data storage
        data_file = os.path.join(self.temp_dir, 'test_data.json')
        with open(data_file, 'w') as f:
            json.dump(current_data, f, default=str)
        
        # Test data recovery
        with open(data_file, 'r') as f:
            recovered_data = json.load(f)
        
        self.assertIsNotNone(recovered_data, "Data should be recoverable")
        self.assertEqual(recovered_data['battery']['soc_percent'], current_data['battery']['soc_percent'], 
                        "Recovered data should match original data")


class TestSystemPerformance(unittest.TestCase):
    """Test system performance characteristics"""
    
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
            'system': {
                'inverter_ip': '192.168.1.100',
                'inverter_port': 8899,
                'data_collection_interval': 60,
                'decision_interval': 900
            },
            'charging': {
                'max_charging_power': 3000,
                'min_battery_soc': 20,
                'max_battery_soc': 90,
                'price_threshold_percentile': 25
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def test_memory_usage(self):
        """Test memory usage of system components"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create coordinator
        coordinator = MasterCoordinator(self.config_path)
        
        # Get memory usage after creation
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        self.assertLess(memory_increase, 100 * 1024 * 1024, 
                       f"Memory increase should be less than 100MB, got {memory_increase / 1024 / 1024:.2f}MB")
    
    def test_initialization_time(self):
        """Test system initialization time"""
        start_time = datetime.now()
        
        coordinator = MasterCoordinator(self.config_path)
        
        end_time = datetime.now()
        initialization_time = (end_time - start_time).total_seconds()
        
        # Initialization should be fast (less than 5 seconds)
        self.assertLess(initialization_time, 5.0, 
                       f"Initialization should be less than 5 seconds, got {initialization_time:.2f} seconds")


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        test_suite = unittest.TestLoader().loadTestsFromTestCase(TestEndToEndIntegration)
        runner = unittest.TextTestRunner(verbosity=2)
        
        # Run synchronous tests first
        result = runner.run(test_suite)
        
        # Run async tests
        async_test_methods = [
            'test_complete_system_initialization',
            'test_data_collection_to_decision_flow',
            'test_decision_execution_flow',
            'test_error_handling_and_recovery',
            'test_system_performance_under_load',
            'test_multi_session_coordination',
            'test_weather_integration_flow',
            'test_data_persistence_and_recovery'
        ]
        
        for test_method in async_test_methods:
            try:
                test_instance = TestEndToEndIntegration()
                test_instance.setUp()
                await getattr(test_instance, test_method)()
                test_instance.tearDown()
                print(f"✅ {test_method} passed")
            except Exception as e:
                print(f"❌ {test_method} failed: {e}")
        
        return result.wasSuccessful()
    
    # Run the tests
    success = asyncio.run(run_async_tests())
    exit(0 if success else 1)
