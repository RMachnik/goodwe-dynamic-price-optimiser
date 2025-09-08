#!/usr/bin/env python3
"""
Enhanced Data Collector Tests
Tests the enhanced data collection system for GoodWe inverter

This test suite verifies:
- Data collection from GoodWe inverter
- Data validation and processing
- Historical data storage and retrieval
- Error handling and recovery
- Performance and reliability
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

from enhanced_data_collector import EnhancedDataCollector


class TestEnhancedDataCollector(unittest.TestCase):
    """Test enhanced data collector functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.data_dir = os.path.join(self.temp_dir, 'energy_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.create_test_config()
        
        # Mock inverter data
        self.mock_inverter_data = {
            'battery': {
                'soc_percent': 45.0,
                'temperature': 25.0,
                'voltage': 400.0,
                'current': 10.0,
                'power': 4000.0,
                'charging_status': 'No charging',
                'fast_charging_enabled': False
            },
            'pv': {
                'power': 2500.0,
                'voltage': 350.0,
                'current': 7.0,
                'daily_energy': 12.5
            },
            'grid': {
                'power': -500.0,  # Negative = export
                'voltage': 230.0,
                'frequency': 50.0,
                'daily_import': 2.1,
                'daily_export': 24.5
            },
            'consumption': {
                'power': 2000.0,
                'daily_energy': 9.4
            },
            'inverter': {
                'temperature': 35.0,
                'power': 10000.0,
                'efficiency': 96.5
            }
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
                'data_storage_path': self.data_dir
            },
            'data_collection': {
                'enabled': True,
                'save_to_file': True,
                'file_format': 'json',
                'retention_days': 30
            },
            'sensors': {
                'battery': ['soc_percent', 'temperature', 'voltage', 'current', 'power'],
                'pv': ['power', 'voltage', 'current', 'daily_energy'],
                'grid': ['power', 'voltage', 'frequency', 'daily_import', 'daily_export'],
                'consumption': ['power', 'daily_energy'],
                'inverter': ['temperature', 'power', 'efficiency']
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def load_config(self):
        """Load configuration from file"""
        import yaml
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_data_collector_initialization(self, mock_goodwe):
        """Test data collector initialization"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        success = await collector.initialize()
        
        self.assertTrue(success, "Data collector should initialize successfully")
        self.assertIsNotNone(collector.inverter, "Inverter should be connected")
        self.assertEqual(collector.config['system']['inverter_ip'], '192.168.1.100', 
                        "Configuration should be loaded correctly")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_collection_success(self, mock_goodwe):
        """Test successful data collection"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize and collect data
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        data = await collector.collect_data()
        
        # Verify data structure
        self.assertIsNotNone(data, "Data should be collected")
        self.assertIn('timestamp', data, "Data should contain timestamp")
        self.assertIn('battery', data, "Data should contain battery information")
        self.assertIn('pv', data, "Data should contain PV information")
        self.assertIn('grid', data, "Data should contain grid information")
        self.assertIn('consumption', data, "Data should contain consumption information")
        self.assertIn('inverter', data, "Data should contain inverter information")
        
        # Verify data values
        self.assertEqual(data['battery']['soc_percent'], 45.0, "Battery SOC should match")
        self.assertEqual(data['pv']['power'], 2500.0, "PV power should match")
        self.assertEqual(data['grid']['power'], -500.0, "Grid power should match")
        self.assertEqual(data['consumption']['power'], 2000.0, "Consumption power should match")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_validation(self, mock_goodwe):
        """Test data validation and processing"""
        # Mock GoodWe inverter with invalid data
        mock_inverter = Mock()
        invalid_data = {
            'battery': {
                'soc_percent': -10.0,  # Invalid negative SOC
                'temperature': 200.0,  # Invalid high temperature
                'voltage': 0.0,        # Invalid zero voltage
                'current': 1000.0,     # Invalid high current
                'power': 50000.0       # Invalid high power
            }
        }
        mock_inverter.get_sensors.return_value = invalid_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize and collect data
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        data = await collector.collect_data()
        
        # Verify data validation
        self.assertIsNotNone(data, "Data should be collected even with invalid values")
        
        # Check if validation flags are set
        if 'validation_errors' in data:
            self.assertGreater(len(data['validation_errors']), 0, "Should detect validation errors")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_storage(self, mock_goodwe):
        """Test data storage functionality"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize and collect data
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        data = await collector.collect_data()
        
        # Test data storage
        success = await collector.save_data(data)
        self.assertTrue(success, "Data should be saved successfully")
        
        # Verify file was created
        data_files = list(Path(self.data_dir).glob('*.json'))
        self.assertGreater(len(data_files), 0, "Data file should be created")
        
        # Verify file content
        with open(data_files[0], 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data['battery']['soc_percent'], 45.0, "Saved data should match collected data")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_historical_data_retrieval(self, mock_goodwe):
        """Test historical data retrieval"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize and collect data
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Save some historical data
        for i in range(5):
            data = await collector.collect_data()
            data['timestamp'] = datetime.now() - timedelta(hours=i)
            await collector.save_data(data)
        
        # Test historical data retrieval
        historical_data = await collector.get_historical_data(hours=24)
        
        self.assertIsNotNone(historical_data, "Historical data should be retrieved")
        self.assertGreaterEqual(len(historical_data), 5, "Should retrieve at least 5 data points")
        
        # Verify data is sorted by timestamp
        timestamps = [item['timestamp'] for item in historical_data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True), "Data should be sorted by timestamp")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_error_handling_connection_failure(self, mock_goodwe):
        """Test error handling for connection failures"""
        # Mock connection failure
        mock_goodwe.connect.side_effect = Exception("Connection failed")
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        success = await collector.initialize()
        
        self.assertFalse(success, "Initialization should fail with connection error")
        self.assertIsNone(collector.inverter, "Inverter should not be connected")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_error_handling_data_collection_failure(self, mock_goodwe):
        """Test error handling for data collection failures"""
        # Mock GoodWe inverter with data collection failure
        mock_inverter = Mock()
        mock_inverter.get_sensors.side_effect = Exception("Data collection failed")
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize and attempt data collection
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        data = await collector.collect_data()
        
        # Should handle error gracefully
        self.assertIsNotNone(data, "Should return data even with collection errors")
        self.assertIn('error', data, "Should include error information")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_collection_performance(self, mock_goodwe):
        """Test data collection performance"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Test multiple data collection cycles
        start_time = datetime.now()
        collection_count = 0
        
        for i in range(10):
            try:
                data = await collector.collect_data()
                collection_count += 1
            except Exception as e:
                pass
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Performance assertions
        self.assertGreater(collection_count, 0, "Should complete at least one collection")
        self.assertLess(duration, 10.0, "10 collections should complete within 10 seconds")
        
        # Calculate performance metrics
        avg_collection_time = duration / collection_count if collection_count > 0 else 0
        self.assertLess(avg_collection_time, 1.0, "Average collection time should be less than 1 second")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_aggregation(self, mock_goodwe):
        """Test data aggregation and statistics"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Collect multiple data points
        data_points = []
        for i in range(5):
            data = await collector.collect_data()
            data['timestamp'] = datetime.now() - timedelta(minutes=i)
            data_points.append(data)
        
        # Test data aggregation
        aggregated_data = await collector.aggregate_data(data_points)
        
        self.assertIsNotNone(aggregated_data, "Aggregated data should be generated")
        self.assertIn('battery', aggregated_data, "Should contain battery aggregation")
        self.assertIn('pv', aggregated_data, "Should contain PV aggregation")
        self.assertIn('grid', aggregated_data, "Should contain grid aggregation")
        self.assertIn('consumption', aggregated_data, "Should contain consumption aggregation")
        
        # Verify aggregation includes statistics
        if 'battery' in aggregated_data:
            self.assertIn('avg_soc', aggregated_data['battery'], "Should include average SOC")
            self.assertIn('min_soc', aggregated_data['battery'], "Should include minimum SOC")
            self.assertIn('max_soc', aggregated_data['battery'], "Should include maximum SOC")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_export_functionality(self, mock_goodwe):
        """Test data export functionality"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Save some data
        for i in range(3):
            data = await collector.collect_data()
            data['timestamp'] = datetime.now() - timedelta(hours=i)
            await collector.save_data(data)
        
        # Test data export
        export_file = os.path.join(self.temp_dir, 'export.csv')
        success = await collector.export_data(export_file, format='csv', hours=24)
        
        self.assertTrue(success, "Data export should succeed")
        self.assertTrue(os.path.exists(export_file), "Export file should be created")
        
        # Verify export file content
        with open(export_file, 'r') as f:
            content = f.read()
            self.assertIn('timestamp', content, "Export should contain timestamp")
            self.assertIn('battery_soc_percent', content, "Export should contain battery data")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_data_cleanup_and_retention(self, mock_goodwe):
        """Test data cleanup and retention policies"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Create old data files
        old_timestamp = datetime.now() - timedelta(days=35)  # Older than retention period
        old_data = await collector.collect_data()
        old_data['timestamp'] = old_timestamp
        
        old_file = os.path.join(self.data_dir, f'energy_data_{old_timestamp.strftime("%Y%m%d_%H%M%S")}.json')
        with open(old_file, 'w') as f:
            json.dump(old_data, f, default=str)
        
        # Create recent data files
        recent_timestamp = datetime.now() - timedelta(days=5)  # Within retention period
        recent_data = await collector.collect_data()
        recent_data['timestamp'] = recent_timestamp
        
        recent_file = os.path.join(self.data_dir, f'energy_data_{recent_timestamp.strftime("%Y%m%d_%H%M%S")}.json')
        with open(recent_file, 'w') as f:
            json.dump(recent_data, f, default=str)
        
        # Test data cleanup
        await collector.cleanup_old_data()
        
        # Verify old file is removed and recent file is kept
        self.assertFalse(os.path.exists(old_file), "Old data file should be removed")
        self.assertTrue(os.path.exists(recent_file), "Recent data file should be kept")
    
    def test_configuration_validation(self):
        """Test configuration validation"""
        # Test with invalid configuration
        invalid_config = {
            'system': {
                'inverter_ip': '',  # Invalid empty IP
                'inverter_port': 0,  # Invalid port
                'data_collection_interval': -1  # Invalid interval
            }
        }
        
        invalid_config_path = os.path.join(self.temp_dir, 'invalid_config.yaml')
        import yaml
        with open(invalid_config_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # Should handle invalid configuration gracefully
        collector = EnhancedDataCollector(invalid_config_path)
        self.assertIsNotNone(collector, "Should create collector even with invalid config")
    
    @patch('enhanced_data_collector.goodwe')
    @pytest.mark.asyncio
    async def test_concurrent_data_collection(self, mock_goodwe):
        """Test concurrent data collection"""
        # Mock GoodWe inverter
        mock_inverter = Mock()
        mock_inverter.get_sensors.return_value = self.mock_inverter_data
        mock_goodwe.connect.return_value = mock_inverter
        
        # Initialize data collector
        collector = EnhancedDataCollector(self.config_path)
        await collector.initialize()
        
        # Test concurrent data collection
        async def collect_data_task():
            return await collector.collect_data()
        
        # Run multiple concurrent collections
        tasks = [collect_data_task() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all collections completed
        successful_collections = [r for r in results if not isinstance(r, Exception)]
        self.assertGreaterEqual(len(successful_collections), 3, "At least 3 concurrent collections should succeed")


class TestDataCollectorPerformance(unittest.TestCase):
    """Test data collector performance characteristics"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.data_dir = os.path.join(self.temp_dir, 'energy_data')
        os.makedirs(self.data_dir, exist_ok=True)
        
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
                'data_storage_path': self.data_dir
            },
            'data_collection': {
                'enabled': True,
                'save_to_file': True,
                'file_format': 'json',
                'retention_days': 30
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def test_memory_usage(self):
        """Test memory usage of data collector"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create data collector
        collector = EnhancedDataCollector(self.config_path)
        
        # Get memory usage after creation
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB)
        self.assertLess(memory_increase, 50 * 1024 * 1024, 
                       f"Memory increase should be less than 50MB, got {memory_increase / 1024 / 1024:.2f}MB")
    
    def test_initialization_time(self):
        """Test data collector initialization time"""
        start_time = datetime.now()
        
        collector = EnhancedDataCollector(self.config_path)
        
        end_time = datetime.now()
        initialization_time = (end_time - start_time).total_seconds()
        
        # Initialization should be fast (less than 2 seconds)
        self.assertLess(initialization_time, 2.0, 
                       f"Initialization should be less than 2 seconds, got {initialization_time:.2f} seconds")


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        test_suite = unittest.TestLoader().loadTestsFromTestCase(TestEnhancedDataCollector)
        runner = unittest.TextTestRunner(verbosity=2)
        
        # Run synchronous tests first
        result = runner.run(test_suite)
        
        # Run async tests
        async_test_methods = [
            'test_data_collector_initialization',
            'test_data_collection_success',
            'test_data_validation',
            'test_data_storage',
            'test_historical_data_retrieval',
            'test_error_handling_connection_failure',
            'test_error_handling_data_collection_failure',
            'test_data_collection_performance',
            'test_data_aggregation',
            'test_data_export_functionality',
            'test_data_cleanup_and_retention',
            'test_concurrent_data_collection'
        ]
        
        for test_method in async_test_methods:
            try:
                test_instance = TestEnhancedDataCollector()
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
