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
        master_log = os.path.join(self.logs_dir, 'master_coordinator.log')
        
        # Simulate streaming by reading in chunks
        stream_content = ""
        for chunk in server.stream_log_file(master_log, chunk_size=50):
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
        route_paths = [route['path'] for route in routes]
        self.assertIn('/logs', route_paths, "Should have logs route")
        self.assertIn('/logs/list', route_paths, "Should have logs list route")
        self.assertIn('/logs/stream', route_paths, "Should have logs stream route")
    
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
        
        # Test server startup
        try:
            server.start()
            self.assertTrue(server.is_running(), "Server should be running after start")
            
            # Test server shutdown
            server.stop()
            self.assertFalse(server.is_running(), "Server should not be running after stop")
            
        except Exception as e:
            # Handle cases where server cannot start (port conflicts, etc.)
            self.assertIn("port", str(e).lower(), "Should handle port conflicts gracefully")
    
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
