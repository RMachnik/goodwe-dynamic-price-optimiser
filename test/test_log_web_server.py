#!/usr/bin/env python3
"""
Log Web Server Tests
Tests the log web server for remote log access and monitoring

This test suite verifies:
- Web server initialization and configuration
- Log file serving and streaming
- Remote access functionality
- Authentication and security
- Performance and reliability
- Error handling and recovery
"""

import unittest
import asyncio
import json
import tempfile
import shutil
import threading
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from log_web_server import LogWebServer


class TestLogWebServer(unittest.TestCase):
    """Test log web server functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Test server configuration
        self.test_host = '127.0.0.1'
        self.test_port = 8080
        
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Create sample log files
        self.create_sample_log_files()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'web_server': {
                'enabled': True,
                'host': self.test_host,
                'port': self.test_port,
                'log_directory': self.logs_dir,
                'max_log_size_mb': 10,
                'log_retention_days': 7,
                'enable_authentication': False,
                'enable_ssl': False
            },
            'security': {
                'allowed_ips': ['127.0.0.1', '192.168.1.0/24'],
                'rate_limit_requests_per_minute': 60,
                'max_concurrent_connections': 10
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def create_sample_log_files(self):
        """Create sample log files for testing"""
        # Create master coordinator log
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        with open(master_log, 'w') as f:
            f.write("2025-09-07 10:00:00 - INFO - Master coordinator started\n")
            f.write("2025-09-07 10:00:01 - INFO - Initializing data collector\n")
            f.write("2025-09-07 10:00:02 - INFO - Data collector initialized successfully\n")
            f.write("2025-09-07 10:00:03 - INFO - Price analyzer initialized\n")
            f.write("2025-09-07 10:00:04 - INFO - Decision engine ready\n")
            f.write("2025-09-07 10:00:05 - INFO - System fully operational\n")
        
        # Create data collector log
        data_log = os.path.join(self.logs_dir, 'enhanced_data_collector.log')
        with open(data_log, 'w') as f:
            f.write("2025-09-07 10:00:01 - INFO - Data collection started\n")
            f.write("2025-09-07 10:00:01 - INFO - Connected to GoodWe inverter\n")
            f.write("2025-09-07 10:00:02 - INFO - Battery SOC: 45.2%\n")
            f.write("2025-09-07 10:00:02 - INFO - PV Power: 2.5 kW\n")
            f.write("2025-09-07 10:00:02 - INFO - Grid Power: -0.3 kW (export)\n")
        
        # Create charging log
        charging_log = os.path.join(self.logs_dir, 'fast_charge.log')
        with open(charging_log, 'w') as f:
            f.write("2025-09-07 10:00:05 - INFO - Charging decision made\n")
            f.write("2025-09-07 10:00:05 - INFO - Action: start_charging\n")
            f.write("2025-09-07 10:00:05 - INFO - Reason: Low price window detected\n")
            f.write("2025-09-07 10:00:06 - INFO - Charging started at 3.0 kW\n")
    
    def test_web_server_initialization(self):
        """Test web server initialization"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        self.assertIsNotNone(server, "Web server should be created")
        self.assertEqual(server.host, self.test_host, "Host should be set correctly")
        self.assertEqual(server.port, self.test_port, "Port should be set correctly")
        self.assertEqual(str(server.log_dir), self.logs_dir, "Log directory should be set correctly")
    
    def test_log_file_discovery(self):
        """Test discovery of log files"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        log_files = server.discover_log_files()
        
        self.assertIsNotNone(log_files, "Log files should be discovered")
        self.assertIsInstance(log_files, list, "Log files should be a list")
        self.assertGreater(len(log_files), 0, "Should discover at least one log file")
        
        # Verify expected log files are found
        log_names = [os.path.basename(f) for f in log_files]
        self.assertIn('master_coordinator.log', log_names, "Should find master coordinator log")
        self.assertIn('enhanced_data_collector.log', log_names, "Should find data collector log")
        self.assertIn('fast_charge.log', log_names, "Should find charging log")
    
    def test_log_file_reading(self):
        """Test reading log file contents"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test reading master coordinator log
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        content = server.read_log_file(master_log)
        
        self.assertIsNotNone(content, "Log content should be read")
        self.assertIsInstance(content, str, "Log content should be a string")
        self.assertIn("Master coordinator started", content, "Should contain expected log entry")
        self.assertIn("System fully operational", content, "Should contain expected log entry")
    
    def test_log_file_streaming(self):
        """Test log file streaming functionality"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test streaming master coordinator log
        master_log_name = 'master'  # Use log name, not full path
        
        # Simulate streaming by reading in chunks
        stream_content = ""
        for chunk in server.stream_log_file(master_log_name, chunk_size=50):
            stream_content += chunk
        
        self.assertIsNotNone(stream_content, "Stream content should be generated")
        self.assertIn("Master coordinator started", stream_content, "Should contain expected log entry")
    
    def test_log_file_filtering(self):
        """Test log file filtering by level and time"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test filtering by log level
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        info_logs = server.filter_log_entries(master_log, level='INFO')
        
        self.assertIsNotNone(info_logs, "Filtered logs should be returned")
        self.assertIsInstance(info_logs, list, "Filtered logs should be a list")
        self.assertGreater(len(info_logs), 0, "Should find INFO level logs")
        
        # Verify all entries are INFO level
        for entry in info_logs:
            self.assertIn("INFO", entry, "All entries should be INFO level")
    
    def test_log_file_search(self):
        """Test searching log file contents"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test searching for specific terms
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        search_results = server.search_log_file(master_log, "coordinator")
        
        self.assertIsNotNone(search_results, "Search results should be returned")
        self.assertIsInstance(search_results, list, "Search results should be a list")
        self.assertGreater(len(search_results), 0, "Should find matching entries")
        
        # Verify search results contain the search term
        for result in search_results:
            self.assertIn("coordinator", result.lower(), "Search results should contain search term")
    
    def test_log_file_statistics(self):
        """Test log file statistics generation"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test generating log statistics
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        stats = server.get_log_statistics(master_log)
        
        self.assertIsNotNone(stats, "Log statistics should be generated")
        self.assertIn('total_lines', stats, "Should include total lines")
        self.assertIn('file_size_bytes', stats, "Should include file size")
        self.assertIn('last_modified', stats, "Should include last modified time")
        self.assertIn('log_levels', stats, "Should include log level distribution")
        
        # Verify statistics values
        self.assertGreater(stats['total_lines'], 0, "Should have positive line count")
        self.assertGreater(stats['file_size_bytes'], 0, "Should have positive file size")
        self.assertIn('INFO', stats['log_levels'], "Should include INFO level count")
    
    def test_web_server_routes(self):
        """Test web server route handling"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test route registration
        routes = server.get_available_routes()
        
        self.assertIsNotNone(routes, "Routes should be available")
        self.assertIsInstance(routes, list, "Routes should be a list")
        self.assertGreater(len(routes), 0, "Should have at least one route")
        
        # Verify expected routes exist
        route_paths = [route for route in routes]  # routes are already strings
        self.assertTrue(any('/logs' in route for route in route_paths), "Should have logs route")
        self.assertTrue(any('/logs/files' in route for route in route_paths), "Should have logs files route")
        self.assertTrue(any('/logs/download' in route for route in route_paths), "Should have logs download route")
    
    def test_error_handling_invalid_log_file(self):
        """Test error handling for invalid log files"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test reading non-existent log file
        invalid_log = os.path.join(self.logs_dir, 'non_existent.log')
        
        # Should handle invalid file gracefully
        try:
            content = server.read_log_file(invalid_log)
            self.assertIsNone(content, "Should return None for non-existent file")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle invalid file gracefully, got exception: {e}")
    
    def test_error_handling_permission_denied(self):
        """Test error handling for permission denied"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Create a file with restricted permissions (if possible)
        restricted_log = os.path.join(self.logs_dir, 'restricted.log')
        with open(restricted_log, 'w') as f:
            f.write("Test log content\n")
        
        # Try to read the file (should work in test environment)
        try:
            content = server.read_log_file(restricted_log)
            self.assertIsNotNone(content, "Should be able to read file in test environment")
        except Exception as e:
            # Should handle permission errors gracefully
            self.assertIn("permission", str(e).lower(), "Should handle permission errors")
    
    def test_log_file_rotation(self):
        """Test log file rotation functionality"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test log rotation detection
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        needs_rotation = server.check_log_rotation_needed(master_log)
        
        self.assertIsInstance(needs_rotation, bool, "Rotation check should return boolean")
        
        # Test log rotation execution
        if needs_rotation:
            rotated_file = server.rotate_log_file(master_log)
            self.assertIsNotNone(rotated_file, "Should return rotated file path")
            self.assertTrue(os.path.exists(rotated_file), "Rotated file should exist")
    
    def test_log_file_cleanup(self):
        """Test log file cleanup functionality"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Create old log file
        old_log = os.path.join(self.logs_dir, 'old_log.log')
        with open(old_log, 'w') as f:
            f.write("Old log content\n")
        
        # Modify file timestamp to be old
        old_time = time.time() - (8 * 24 * 3600)  # 8 days ago
        os.utime(old_log, (old_time, old_time))
        
        # Test cleanup
        cleaned_files = server.cleanup_old_logs()
        
        self.assertIsNotNone(cleaned_files, "Cleanup should return list of cleaned files")
        self.assertIsInstance(cleaned_files, list, "Cleaned files should be a list")
    
    def test_web_server_security(self):
        """Test web server security features"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test IP filtering
        allowed_ip = '127.0.0.1'
        blocked_ip = '192.168.100.100'
        
        is_allowed = server.is_ip_allowed(allowed_ip)
        is_blocked = server.is_ip_allowed(blocked_ip)
        
        self.assertTrue(is_allowed, "Allowed IP should be permitted")
        self.assertFalse(is_blocked, "Blocked IP should be denied")
        
        # Test rate limiting
        client_ip = '127.0.0.1'
        for i in range(5):  # Make 5 requests
            is_rate_limited = server.is_rate_limited(client_ip)
            self.assertFalse(is_rate_limited, "Should not be rate limited for normal usage")
    
    def test_web_server_performance(self):
        """Test web server performance characteristics"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test log file reading performance
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        
        start_time = time.time()
        for i in range(100):  # Read file 100 times
            content = server.read_log_file(master_log)
        end_time = time.time()
        
        duration = end_time - start_time
        avg_time = duration / 100
        
        # Performance assertions
        self.assertLess(duration, 5.0, "100 file reads should complete within 5 seconds")
        self.assertLess(avg_time, 0.05, "Average read time should be less than 50ms")
    
    def test_web_server_concurrent_access(self):
        """Test web server concurrent access handling"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test concurrent log file reading
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        
        def read_log():
            return server.read_log_file(master_log)
        
        # Create multiple threads
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(target=lambda: results.append(read_log()))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all reads succeeded
        self.assertEqual(len(results), 10, "All concurrent reads should complete")
        for result in results:
            self.assertIsNotNone(result, "All reads should return content")
    
    def test_web_server_configuration_validation(self):
        """Test web server configuration validation"""
        # Test with invalid configuration
        invalid_config = {
            'web_server': {
                'enabled': True,
                'host': '',  # Invalid empty host
                'port': 0,   # Invalid port
                'log_directory': '/non/existent/path'  # Invalid directory
            }
        }
        
        invalid_config_path = os.path.join(self.temp_dir, 'invalid_config.yaml')
        import yaml
        with open(invalid_config_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # Should handle invalid configuration gracefully
        try:
            server = LogWebServer(invalid_config_path)
            self.assertIsNotNone(server, "Should create server even with invalid config")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle invalid config gracefully, got exception: {e}")


class TestLogWebServerIntegration(unittest.TestCase):
    """Test log web server integration with actual web server"""
    
    def setUp(self):
        """Set up integration test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Test server configuration
        self.test_host = '127.0.0.1'
        self.test_port = 8081  # Different port to avoid conflicts
        
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Create sample log files
        self.create_sample_log_files()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'web_server': {
                'enabled': True,
                'host': self.test_host,
                'port': self.test_port,
                'log_directory': self.logs_dir,
                'max_log_size_mb': 10,
                'log_retention_days': 7,
                'enable_authentication': False,
                'enable_ssl': False
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def create_sample_log_files(self):
        """Create sample log files for testing"""
        # Create master coordinator log
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        with open(master_log, 'w') as f:
            f.write("2025-09-07 10:00:00 - INFO - Master coordinator started\n")
            f.write("2025-09-07 10:00:01 - INFO - System initialized\n")
    
    def test_web_server_startup_and_shutdown(self):
        """Test web server startup and shutdown"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test server creation and configuration
        self.assertIsNotNone(server, "Server should be created successfully")
        self.assertEqual(server.host, self.test_host, "Server should have correct host")
        self.assertEqual(server.port, self.test_port, "Server should have correct port")
        self.assertEqual(str(server.log_dir), self.logs_dir, "Server should have correct log directory")
        
        # Test server state management
        self.assertFalse(server.is_running(), "Server should not be running initially")
        
        # Test server stop (should not raise exception even if not running)
        server.stop()
        self.assertFalse(server.is_running(), "Server should not be running after stop")
    
    def test_web_server_health_check(self):
        """Test web server health check functionality"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test health check
        health = server.get_health_status()
        
        self.assertIsNotNone(health, "Health status should be available")
        self.assertIn('status', health, "Should include status")
        self.assertIn('uptime', health, "Should include uptime")
        self.assertIn('memory_usage', health, "Should include memory usage")
        self.assertIn('log_files_count', health, "Should include log files count")
        
        # Verify health status values
        self.assertIn(health['status'], ['healthy', 'degraded', 'unhealthy'], 
                     "Status should be one of the expected values")
        self.assertGreaterEqual(health['log_files_count'], 0, "Log files count should be non-negative")


class TestLogWebServerPerformance(unittest.TestCase):
    """Test log web server performance characteristics"""
    
    def setUp(self):
        """Set up performance test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Test server configuration
        self.test_host = '127.0.0.1'
        self.test_port = 8082  # Different port to avoid conflicts
        
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'web_server': {
                'enabled': True,
                'host': '127.0.0.1',
                'port': 8082,
                'log_directory': self.logs_dir,
                'max_log_size_mb': 10,
                'log_retention_days': 7
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def test_memory_usage(self):
        """Test memory usage of log web server"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create server
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Get memory usage after creation
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 20MB)
        self.assertLess(memory_increase, 20 * 1024 * 1024, 
                       f"Memory increase should be less than 20MB, got {memory_increase / 1024 / 1024:.2f}MB")
    
    def test_initialization_time(self):
        """Test log web server initialization time"""
        start_time = time.time()
        
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        end_time = time.time()
        initialization_time = end_time - start_time
        
        # Initialization should be fast (less than 2 seconds)
        self.assertLess(initialization_time, 2.0, 
                       f"Initialization should be less than 2 seconds, got {initialization_time:.2f} seconds")


class TestDecisionHistoryBadgeCounts(unittest.TestCase):
    """Test decision history badge count functionality"""
    
    def setUp(self):
        """Set up test environment for badge count tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.energy_data_dir = os.path.join(self.temp_dir, 'out', 'energy_data')
        os.makedirs(self.energy_data_dir, exist_ok=True)
        
        # Test server configuration
        self.test_host = '127.0.0.1'
        self.test_port = 8083  # Different port to avoid conflicts
        
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Create sample decision files
        self.create_sample_decision_files()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'web_server': {
                'enabled': True,
                'host': self.test_host,
                'port': self.test_port,
                'log_directory': os.path.join(self.temp_dir, 'logs'),
                'max_log_size_mb': 10,
                'log_retention_days': 7
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def create_sample_decision_files(self):
        """Create sample decision files for testing badge counts"""
        from datetime import datetime, timedelta
        import json
        
        base_time = datetime.now() - timedelta(hours=2)  # More recent for 1h test
        
        # Create charging decision files (with action='wait' but charging intent)
        charging_decisions = [
            {
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "action": "wait",
                "source": "grid",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.8,
                "reason": "Start charging from grid - low price window detected",
                "priority": "high",
                "battery_soc": 45,
                "pv_power": 0,
                "house_consumption": 200,
                "current_price": 0.25,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            },
            {
                "timestamp": (base_time + timedelta(minutes=20)).isoformat(),
                "action": "wait",
                "source": "pv",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.9,
                "reason": "Start PV charging - overproduction available",
                "priority": "medium",
                "battery_soc": 50,
                "pv_power": 3000,
                "house_consumption": 1000,
                "current_price": 0.30,
                "cheapest_price": 0.25,
                "cheapest_hour": 3
            },
            {
                "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                "action": "start_pv_charging",
                "source": "pv",
                "duration": 120,
                "energy_kwh": 2.5,
                "estimated_cost_pln": 0.75,
                "estimated_savings_pln": 1.25,
                "confidence": 0.95,
                "reason": "PV charging started - optimal conditions",
                "priority": "high",
                "battery_soc": 55,
                "pv_power": 3500,
                "house_consumption": 800,
                "current_price": 0.30,
                "cheapest_price": 0.25,
                "cheapest_hour": 3
            }
        ]
        
        # Create wait decision files (genuine wait decisions)
        wait_decisions = [
            {
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                "action": "wait",
                "source": "unknown",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.4,
                "reason": "Wait for better conditions (PV overproduction, lower prices, or higher consumption)",
                "priority": "low",
                "battery_soc": 69,
                "pv_power": 0,
                "house_consumption": 287,
                "current_price": 0.45,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            },
            {
                "timestamp": (base_time + timedelta(minutes=15)).isoformat(),
                "action": "wait",
                "source": "unknown",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.3,
                "reason": "Wait for better conditions - current price too high",
                "priority": "low",
                "battery_soc": 68,
                "pv_power": 0,
                "house_consumption": 273,
                "current_price": 0.50,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            }
        ]
        
        # Create battery selling decision files
        battery_selling_decisions = [
            {
                "timestamp": (base_time + timedelta(minutes=25)).isoformat(),
                "action": "battery_selling",
                "decision": "start_selling",
                "confidence": 0.85,
                "expected_revenue_pln": 2.50,
                "selling_power_w": 2000,
                "estimated_duration_hours": 2.0,
                "reasoning": "High price window detected - optimal for battery selling",
                "safety_checks_passed": True,
                "risk_level": "low",
                "current_price_pln": 0.75,
                "battery_soc": 85,
                "pv_power": 0,
                "house_consumption": 500,
                "energy_sold_kwh": 4.0,
                "revenue_per_kwh_pln": 0.75,
                "safety_status": "safe"
            },
            {
                "timestamp": (base_time + timedelta(minutes=35)).isoformat(),
                "action": "battery_selling",
                "decision": "wait",
                "confidence": 0.0,
                "expected_revenue_pln": 0.0,
                "selling_power_w": 0,
                "estimated_duration_hours": 0.0,
                "reasoning": "Battery SOC (45%) below minimum selling threshold (80%)",
                "safety_checks_passed": True,
                "risk_level": "low",
                "current_price_pln": 0.75,
                "battery_soc": 45,
                "pv_power": 200,
                "house_consumption": 1200,
                "energy_sold_kwh": 0.0,
                "revenue_per_kwh_pln": 0.75,
                "safety_status": "safe"
            }
        ]
        
        # Write charging decision files
        for i, decision in enumerate(charging_decisions):
            filename = f"charging_decision_20250909_{base_time.strftime('%H%M%S')}_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        # Write wait decision files
        for i, decision in enumerate(wait_decisions):
            filename = f"charging_decision_20250909_{base_time.strftime('%H%M%S')}_wait_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        # Write battery selling decision files
        for i, decision in enumerate(battery_selling_decisions):
            filename = f"battery_selling_decision_20250909_{base_time.strftime('%H%M%S')}_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
    
    def test_badge_count_categorization(self):
        """Test that decisions are correctly categorized for badge counts"""
        # Mock the energy data directory path
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get decision history
            history = server._get_decision_history(time_range='24h', decision_type='all')
            
            # Verify counts
            self.assertEqual(history['total_count'], 7, "Should have 7 total decisions")
            self.assertEqual(history['charging_count'], 3, "Should have 3 charging decisions")
            self.assertEqual(history['wait_count'], 2, "Should have 2 wait decisions")
            self.assertEqual(history['battery_selling_count'], 2, "Should have 2 battery selling decisions")
    
    def test_charging_decision_identification(self):
        """Test that charging decisions are correctly identified"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only charging decisions
            history = server._get_decision_history(time_range='24h', decision_type='charging')
            
            # Verify only charging decisions are returned
            self.assertEqual(history['charging_count'], 3, "Should have 3 charging decisions")
            self.assertEqual(history['wait_count'], 0, "Should have 0 wait decisions in charging filter")
            self.assertEqual(history['battery_selling_count'], 0, "Should have 0 battery selling decisions in charging filter")
            
            # Verify all returned decisions are charging-related
            for decision in history['decisions']:
                reason = decision.get('reason', '') or decision.get('reasoning', '')
                action = decision.get('action', '')
                self.assertTrue(
                    'charging' in reason.lower() or 
                    action in ['start_pv_charging', 'start_grid_charging', 'charging'],
                    f"Decision should be charging-related: {decision}"
                )
    
    def test_wait_decision_identification(self):
        """Test that wait decisions are correctly identified"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only wait decisions
            history = server._get_decision_history(time_range='24h', decision_type='wait')
            
            # Verify only wait decisions are returned
            self.assertEqual(history['charging_count'], 0, "Should have 0 charging decisions in wait filter")
            self.assertEqual(history['wait_count'], 2, "Should have 2 wait decisions")
            self.assertEqual(history['battery_selling_count'], 0, "Should have 0 battery selling decisions in wait filter")
            
            # Verify all returned decisions are wait-related
            for decision in history['decisions']:
                reason = decision.get('reason', '') or decision.get('reasoning', '')
                self.assertTrue(
                    'wait' in reason.lower() or 'better conditions' in reason.lower(),
                    f"Decision should be wait-related: {decision}"
                )
    
    def test_battery_selling_decision_identification(self):
        """Test that battery selling decisions are correctly identified"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only battery selling decisions
            history = server._get_decision_history(time_range='24h', decision_type='battery_selling')
            
            # Verify only battery selling decisions are returned
            self.assertEqual(history['charging_count'], 0, "Should have 0 charging decisions in battery selling filter")
            self.assertEqual(history['wait_count'], 0, "Should have 0 wait decisions in battery selling filter")
            self.assertEqual(history['battery_selling_count'], 2, "Should have 2 battery selling decisions")
            
            # Verify all returned decisions are battery selling-related
            for decision in history['decisions']:
                action = decision.get('action', '')
                decision_type = decision.get('decision', '')
                self.assertTrue(
                    action == 'battery_selling' or decision_type == 'battery_selling',
                    f"Decision should be battery selling-related: {decision}"
                )
    
    def test_decision_categorization_edge_cases(self):
        """Test edge cases in decision categorization"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test with empty decisions (use a very short time range)
            empty_history = server._get_decision_history(time_range='1s', decision_type='all')
            self.assertEqual(empty_history['total_count'], 0, "Should have 0 decisions for 1s range")
            self.assertEqual(empty_history['charging_count'], 0, "Should have 0 charging decisions")
            self.assertEqual(empty_history['wait_count'], 0, "Should have 0 wait decisions")
            self.assertEqual(empty_history['battery_selling_count'], 0, "Should have 0 battery selling decisions")
    
    def test_decision_categorization_with_missing_fields(self):
        """Test decision categorization with missing or malformed fields"""
        # Create a decision file with missing fields
        malformed_decision = {
            "timestamp": datetime.now().isoformat(),
            "action": "",  # Empty action
            "reason": "",  # Empty reason
        }
        
        malformed_file = os.path.join(self.energy_data_dir, "malformed_decision.json")
        with open(malformed_file, 'w') as f:
            json.dump(malformed_decision, f, indent=2)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get decision history including malformed decision
            history = server._get_decision_history(time_range='24h', decision_type='all')
            
            # Malformed decision should default to wait category
            self.assertGreaterEqual(history['wait_count'], 2, "Should include malformed decision in wait count")
    
    def test_time_range_filtering(self):
        """Test that time range filtering works correctly"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test 7-day range (should include all decisions)
            history_7d = server._get_decision_history(time_range='7d', decision_type='all')
            self.assertEqual(history_7d['total_count'], 7, "Should have 7 decisions for 7-day range")
            
            # Test 1-hour range (should have fewer decisions)
            history_1h = server._get_decision_history(time_range='1h', decision_type='all')
            self.assertLessEqual(history_1h['total_count'], 7, "Should have fewer or equal decisions for 1-hour range")
    
    def test_decision_categorization_performance(self):
        """Test performance of decision categorization with many decisions"""
        # Create many decision files
        from datetime import datetime, timedelta
        import json
        
        base_time = datetime.now() - timedelta(hours=2)  # More recent for 1h test
        
        for i in range(100):  # Create 100 decision files
            decision = {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "action": "wait",
                "reason": f"Test decision {i} - wait for better conditions",
                "battery_soc": 50 + (i % 30),
                "confidence": 0.5
            }
            
            filename = f"charging_decision_20250909_{base_time.strftime('%H%M%S')}_test_{i:03d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test performance
            start_time = time.time()
            history = server._get_decision_history(time_range='7d', decision_type='all')
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Should complete within reasonable time (less than 2 seconds)
            self.assertLess(duration, 2.0, f"Decision categorization should complete within 2 seconds, got {duration:.2f}s")
            
            # Should have correct total count
            self.assertGreaterEqual(history['total_count'], 100, "Should process all 100 test decisions")


class TestTimeSeriesFunctionality(unittest.TestCase):
    """Test Time Series visualization functionality"""
    
    def setUp(self):
        """Set up test environment for Time Series tests"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Test server configuration
        self.test_host = '127.0.0.1'
        self.test_port = 8084  # Different port to avoid conflicts
        
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Create sample coordinator state files
        self.create_sample_coordinator_state_files()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'web_server': {
                'enabled': True,
                'host': self.test_host,
                'port': self.test_port,
                'log_directory': self.logs_dir,
                'max_log_size_mb': 10,
                'log_retention_days': 7
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def create_sample_coordinator_state_files(self):
        """Create sample coordinator state files for testing"""
        from datetime import datetime, timedelta
        import json
        
        # Create out directory structure
        out_dir = os.path.join(self.temp_dir, 'out')
        os.makedirs(out_dir, exist_ok=True)
        
        # Create recent coordinator state file with real data
        recent_time = datetime.now() - timedelta(minutes=5)
        state_data = {
            "timestamp": recent_time.isoformat(),
            "current_data": {
                "battery": {
                    "soc_percent": 64.5,
                    "power_w": 1200,
                    "voltage_v": 48.2,
                    "current_a": 25.0
                },
                "photovoltaic": {
                    "current_power_w": 0,
                    "daily_energy_kwh": 12.5,
                    "efficiency_percent": 95.2
                },
                "grid": {
                    "power_w": -500,
                    "voltage_v": 230.1,
                    "frequency_hz": 50.0
                },
                "house": {
                    "consumption_w": 800,
                    "daily_consumption_kwh": 15.2
                }
            },
            "system_status": "operational",
            "last_update": recent_time.isoformat()
        }
        
        # Write coordinator state file
        state_filename = f"coordinator_state_{recent_time.strftime('%Y%m%d_%H%M%S')}.json"
        state_filepath = os.path.join(out_dir, state_filename)
        with open(state_filepath, 'w') as f:
            json.dump(state_data, f, indent=2)
    
    def test_historical_data_api_endpoint(self):
        """Test the /historical-data API endpoint"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Mock the project root to point to our test directory
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            # Test the historical data method
            data = server._get_historical_time_series_data()
            
            # Verify response structure
            self.assertIsNotNone(data, "Historical data should be returned")
            self.assertIn('data_source', data, "Should include data source")
            self.assertIn('data_points', data, "Should include data points count")
            self.assertIn('soc_data', data, "Should include SOC data")
            self.assertIn('pv_power_data', data, "Should include PV power data")
            self.assertIn('timestamps', data, "Should include timestamps")
            self.assertIn('current_soc', data, "Should include current SOC")
            self.assertIn('current_pv_power', data, "Should include current PV power")
            self.assertIn('soc_range', data, "Should include SOC range")
            self.assertIn('pv_peak', data, "Should include PV peak")
    
    def test_real_data_integration(self):
        """Test real data integration from coordinator state files"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            # Test real data retrieval
            data = server._get_real_historical_data()
            
            if data:  # If real data is available
                self.assertEqual(data['data_source'], 'real_data_based', "Should use real data")
                self.assertEqual(data['current_soc'], 64.5, "Should have correct current SOC")
                self.assertEqual(data['current_pv_power'], 0, "Should have correct current PV power")
                self.assertEqual(data['data_points'], 1440, "Should have 1440 data points (24 hours)")
                
                # Verify data arrays
                self.assertEqual(len(data['soc_data']), 1440, "SOC data should have 1440 points")
                self.assertEqual(len(data['pv_power_data']), 1440, "PV power data should have 1440 points")
                self.assertEqual(len(data['timestamps']), 1440, "Timestamps should have 1440 points")
    
    def test_mock_data_fallback(self):
        """Test mock data fallback when real data is not available"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Mock empty coordinator state directory
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path('/non/existent/path')
            
            # Test mock data generation
            data = server._get_historical_time_series_data()
            
            self.assertIsNotNone(data, "Mock data should be generated")
            self.assertEqual(data['data_source'], 'mock_data', "Should use mock data")
            self.assertEqual(data['data_points'], 1440, "Should have 1440 data points")
            
            # Verify data structure
            self.assertIn('soc_data', data, "Should include SOC data")
            self.assertIn('pv_power_data', data, "Should include PV power data")
            self.assertIn('timestamps', data, "Should include timestamps")
    
    def test_historical_data_structure(self):
        """Test historical data structure and validation"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            data = server._get_historical_time_series_data()
            
            # Test data types
            self.assertIsInstance(data['soc_data'], list, "SOC data should be a list")
            self.assertIsInstance(data['pv_power_data'], list, "PV power data should be a list")
            self.assertIsInstance(data['timestamps'], list, "Timestamps should be a list")
            
            # Test data ranges
            if data['soc_data']:
                self.assertTrue(all(0 <= soc <= 100 for soc in data['soc_data']), 
                              "SOC values should be between 0 and 100")
            
            if data['pv_power_data']:
                self.assertTrue(all(pv >= 0 for pv in data['pv_power_data']), 
                              "PV power values should be non-negative")
            
            # Test timestamp format
            if data['timestamps']:
                for timestamp in data['timestamps'][:5]:  # Check first 5 timestamps
                    self.assertRegex(timestamp, r'^\d{2}:\d{2}$', 
                                   f"Timestamp should be in HH:MM format, got: {timestamp}")
    
    def test_time_series_data_processing(self):
        """Test time series data processing and pattern generation"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            data = server._get_historical_time_series_data()
            
            # Test data consistency
            self.assertEqual(len(data['soc_data']), len(data['pv_power_data']), 
                           "SOC and PV power data should have same length")
            self.assertEqual(len(data['soc_data']), len(data['timestamps']), 
                           "SOC data and timestamps should have same length")
            
            # Test realistic patterns
            if data['data_source'] == 'real_data_based':
                # SOC should be around the current value (64.5) with some variation
                soc_values = data['soc_data']
                current_soc = data['current_soc']
                self.assertTrue(any(abs(soc - current_soc) < 20 for soc in soc_values), 
                              "SOC data should include values close to current SOC")
                
                # PV power should show daily pattern (0 at night, higher during day)
                pv_values = data['pv_power_data']
                self.assertTrue(any(pv == 0 for pv in pv_values), 
                              "PV power should have some zero values (night time)")
    
    def test_time_series_error_handling(self):
        """Test error handling in time series data generation"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        # Test with invalid coordinator state file
        invalid_state_file = os.path.join(self.temp_dir, 'out', 'invalid_state.json')
        with open(invalid_state_file, 'w') as f:
            f.write("invalid json content")
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            # Should handle invalid JSON gracefully
            data = server._get_historical_time_series_data()
            self.assertIsNotNone(data, "Should return data even with invalid state file")
            self.assertIn('data_source', data, "Should include data source")
    
    def test_time_series_performance(self):
        """Test performance of time series data generation"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            # Test performance
            start_time = time.time()
            data = server._get_historical_time_series_data()
            end_time = time.time()
            
            duration = end_time - start_time
            
            # Should complete within reasonable time (less than 1 second)
            self.assertLess(duration, 1.0, 
                          f"Time series data generation should complete within 1 second, got {duration:.2f}s")
            
            # Should generate correct amount of data
            self.assertEqual(data['data_points'], 1440, "Should generate 1440 data points")
    
    def test_time_series_data_validation(self):
        """Test data validation for time series"""
        server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            data = server._get_historical_time_series_data()
            
            # Test required fields
            required_fields = [
                'data_source', 'data_points', 'soc_data', 'pv_power_data', 
                'timestamps', 'current_soc', 'current_pv_power', 'soc_range', 'pv_peak'
            ]
            
            for field in required_fields:
                self.assertIn(field, data, f"Should include required field: {field}")
                self.assertIsNotNone(data[field], f"Field {field} should not be None")
            
            # Test data point count
            self.assertEqual(data['data_points'], 1440, "Should have 1440 data points")
            
            # Test SOC range calculation
            if data['soc_range']:
                self.assertIn('min', data['soc_range'], "SOC range should include min")
                self.assertIn('max', data['soc_range'], "SOC range should include max")
                self.assertLessEqual(data['soc_range']['min'], data['soc_range']['max'], 
                                   "SOC min should be <= max")
            
            # Test PV peak calculation
            if data['pv_peak']:
                self.assertGreaterEqual(data['pv_peak'], 0, "PV peak should be non-negative")


if __name__ == '__main__':
    unittest.main(verbosity=2)
