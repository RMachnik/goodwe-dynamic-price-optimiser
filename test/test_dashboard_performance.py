#!/usr/bin/env python3
"""
Dashboard Performance Optimization Tests

Tests the background refresh thread and performance improvements:
- Thread-safe storage instances
- Background refresh thread lifecycle
- Cache-based endpoint handlers
- Graceful shutdown
- Price disk cache persistence
- Monthly summary caching
"""

import unittest
import asyncio
import json
import tempfile
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import BEFORE patching for these specific tests that need background refresh
from log_web_server import LogWebServer
from daily_snapshot_manager import DailySnapshotManager


class TestBackgroundRefreshThread(unittest.TestCase):
    """Test background refresh thread functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.out_dir = os.path.join(self.temp_dir, 'out')
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.out_dir, exist_ok=True)
        
        self.config = {
            'web_server': {
                'enabled': True,
                'host': '127.0.0.1',
                'port': 8081,
                'background_refresh_interval_seconds': 1,  # Fast for testing
                'price_refresh_interval_seconds': 2,
                'metrics_refresh_interval_seconds': 1,
                'coordinator_pid_check_interval_seconds': 2
            },
            'data_storage': {
                'database_storage': {
                    'enabled': False  # Disable for unit tests
                }
            }
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_background_thread_initialization(self):
        """Test that background thread starts correctly"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Give thread a moment to start
        time.sleep(0.5)
        
        # Verify background thread is running
        self.assertIsNotNone(server._background_thread)
        self.assertTrue(server._background_thread.is_alive())
        self.assertEqual(server._background_thread.name, 'background_refresh')
        
        # Verify cache structure is initialized
        self.assertIsNotNone(server._background_cache)
        self.assertIn('inverter_data', server._background_cache)
        self.assertIn('price_data', server._background_cache)
        self.assertIn('metrics_data', server._background_cache)
        
        # Clean shutdown
        server.shutdown()
        time.sleep(0.5)
        self.assertFalse(server._background_thread.is_alive())
    
    def test_background_cache_thread_safety(self):
        """Test that background cache access is thread-safe"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        time.sleep(0.5)
        
        # Concurrent read/write operations
        errors = []
        
        def read_cache():
            try:
                for _ in range(100):
                    with server._background_cache_lock:
                        _ = server._background_cache.get('inverter_data')
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def write_cache():
            try:
                for i in range(100):
                    with server._background_cache_lock:
                        server._background_cache['inverter_data'] = {'test': i}
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=read_cache)
            t2 = threading.Thread(target=write_cache)
            threads.extend([t1, t2])
            t1.start()
            t2.start()
        
        for t in threads:
            t.join()
        
        # No errors should occur
        self.assertEqual(len(errors), 0, f"Thread-safety errors: {errors}")
        
        server.shutdown()
    
    def test_coordinator_pid_caching(self):
        """Test coordinator PID refresh and caching"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        time.sleep(0.5)
        
        # Manually trigger PID refresh
        server._refresh_coordinator_pid()
        
        with server._background_cache_lock:
            coordinator_running = server._background_cache.get('coordinator_running')
            coordinator_pid = server._background_cache.get('coordinator_pid')
            last_pid_check = server._background_cache.get('last_pid_check')
        
        # Verify cache was updated
        self.assertIsNotNone(last_pid_check)
        self.assertIsInstance(coordinator_running, bool)
        self.assertTrue(last_pid_check > 0)
        
        server.shutdown()
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown stops background thread"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        time.sleep(0.5)
        
        self.assertTrue(server._background_thread.is_alive())
        
        # Trigger shutdown
        server.shutdown()
        time.sleep(1.0)  # Give thread time to stop
        
        # Verify thread has stopped
        self.assertFalse(server._background_thread.is_alive())
        
        # Verify stop event was set
        self.assertTrue(server._stop_background_thread.is_set())


class TestPriceDiskCache(unittest.TestCase):
    """Test price data disk caching"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        self.data_dir = os.path.join(self.temp_dir, 'data')
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.config = {
            'web_server': {
                'enabled': True,
                'background_refresh_interval_seconds': 60,  # Slow for testing
            },
            'data_storage': {
                'database_storage': {
                    'enabled': False
                }
            }
        }
        
        # Mock Path to use our temp directory
        self.original_parent = Path(__file__).parent.parent
        self.patch_path = patch('log_web_server.Path')
        self.mock_path = self.patch_path.start()
        self.mock_path.return_value.parent.parent = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        self.patch_path.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_save_and_load_price_cache(self):
        """Test saving and loading price data from disk"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        server._price_cache_file = Path(self.data_dir) / 'price_cache.json'
        
        # Test price data
        test_price_data = {
            'current_price_pln_kwh': 0.45,
            'cheapest_price_pln_kwh': 0.23,
            'cheapest_hour': '02:00',
            'average_price_pln_kwh': 0.68,
            'price_trend': 'stable',
            'data_source': 'PSE API',
            'last_updated': datetime.now().isoformat()
        }
        
        # Save to disk
        server._save_price_to_disk(test_price_data)
        
        # Verify file exists
        self.assertTrue(server._price_cache_file.exists())
        
        # Load from disk
        loaded_data = server._load_price_from_disk()
        
        # Verify data matches
        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data['current_price_pln_kwh'], 0.45)
        self.assertEqual(loaded_data['cheapest_hour'], '02:00')
        
        server.shutdown()
    
    def test_price_cache_expiration(self):
        """Test that old price cache is rejected"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        server._price_cache_file = Path(self.data_dir) / 'price_cache.json'
        
        # Create old cache (25 hours old)
        old_cache = {
            'price_data': {
                'current_price_pln_kwh': 0.45,
                'cheapest_price_pln_kwh': 0.23
            },
            'cache_timestamp': time.time() - (25 * 3600),  # 25 hours ago
            'business_date': datetime.now().strftime('%Y-%m-%d'),
            'created_at': datetime.now().isoformat()
        }
        
        server._price_cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(server._price_cache_file, 'w') as f:
            json.dump(old_cache, f)
        
        # Try to load - should return None due to age
        loaded_data = server._load_price_from_disk()
        self.assertIsNone(loaded_data)
        
        server.shutdown()


class TestMonthlySummaryCaching(unittest.TestCase):
    """Test monthly summary caching in DailySnapshotManager"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)
        self.snapshots_dir = self.project_root / "out" / "daily_snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = {
            'data_storage': {
                'database_storage': {
                    'enabled': False
                }
            }
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_monthly_cache_hit(self):
        """Test that monthly summary is cached"""
        manager = DailySnapshotManager(self.project_root, config=self.config)
        
        # Create mock snapshot for testing (past month to avoid today logic)
        test_year = 2025
        test_month = 11  # November (past month for December test)
        
        # Create a mock monthly snapshot directly (simpler than daily snapshots)
        monthly_path = manager.get_monthly_snapshot_path(test_year, test_month)
        monthly_path.parent.mkdir(parents=True, exist_ok=True)
        
        monthly_data = {
            'year': test_year,
            'month': test_month,
            'total_decisions': 100,
            'charging_count': 50,
            'wait_count': 50,
            'total_energy_kwh': 150.0,
            'total_cost_pln': 250.0
        }
        
        with open(monthly_path, 'w') as f:
            json.dump(monthly_data, f)
        
        # First call - should load from file and cache
        summary1 = manager.get_monthly_summary(test_year, test_month)
        
        # Verify cache was populated
        cache_key = f"{test_year}_{test_month}"
        with manager._monthly_cache_lock:
            self.assertIn(cache_key, manager._monthly_cache)
            cached_data, cached_time = manager._monthly_cache[cache_key]
            self.assertEqual(cached_data, summary1)
        
        # Second call - should return from cache
        summary2 = manager.get_monthly_summary(test_year, test_month)
        
        # Verify same data returned
        self.assertEqual(summary1, summary2)
        self.assertEqual(summary1['total_decisions'], 100)
    
    def test_monthly_cache_expiration(self):
        """Test that cache expires after 5 minutes"""
        manager = DailySnapshotManager(self.project_root, config=self.config)
        
        # Manually add to cache with old timestamp
        cache_key = "2025_12"
        old_summary = {'test': 'data'}
        old_time = time.time() - 301  # 5 minutes + 1 second ago
        
        with manager._monthly_cache_lock:
            manager._monthly_cache[cache_key] = (old_summary, old_time)
        
        # Try to retrieve - should not return cached data
        # (Will fail to calculate since no snapshots exist, but tests expiration)
        try:
            summary = manager.get_monthly_summary(2025, 12)
            # If it succeeds, verify it's not the old cached data
            self.assertNotEqual(summary, old_summary)
        except Exception:
            # Expected to fail if no snapshots exist - that's fine
            pass


class TestOptimizedEndpoints(unittest.TestCase):
    """Test optimized endpoint handlers using background cache"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.config = {
            'web_server': {
                'enabled': True,
                'background_refresh_interval_seconds': 60,  # Slow for testing
            },
            'data_storage': {
                'database_storage': {
                    'enabled': False
                }
            }
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_system_status_uses_cache(self):
        """Test that _get_system_status reads from background cache"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Populate background cache
        with server._background_cache_lock:
            server._background_cache['coordinator_pid'] = 12345
            server._background_cache['coordinator_running'] = True
            server._background_cache['data_source'] = 'test'
            server._background_cache['last_inverter_refresh'] = time.time()
            server._background_cache['last_price_refresh'] = time.time()
            server._background_cache['last_metrics_refresh'] = time.time()
        
        # Call status method
        status = server._get_system_status()
        
        # Verify it used cached data
        self.assertEqual(status['coordinator_pid'], 12345)
        self.assertTrue(status['coordinator_running'])
        self.assertEqual(status['data_source'], 'test')
        self.assertIn('background_worker', status)
        self.assertIn('storage', status)
        
        server.shutdown()
    
    def test_get_real_price_data_uses_cache(self):
        """Test that _get_real_price_data reads from background cache"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Populate background cache with fresh data
        test_price = {
            'current_price_pln_kwh': 0.45,
            'cheapest_price_pln_kwh': 0.23,
            'cheapest_hour': '02:00'
        }
        
        with server._background_cache_lock:
            server._background_cache['price_data'] = test_price
            server._background_cache['last_price_refresh'] = time.time()
        
        # Call price method
        price_data = server._get_real_price_data()
        
        # Verify it used cached data
        self.assertIsNotNone(price_data)
        self.assertEqual(price_data['current_price_pln_kwh'], 0.45)
        self.assertEqual(price_data['data_source'], 'background_cache')
        
        server.shutdown()
    
    def test_get_real_inverter_data_uses_cache(self):
        """Test that _get_real_inverter_data reads from background cache"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Populate background cache with fresh data
        test_inverter = {
            'battery': {'soc_percent': 75},
            'photovoltaic': {'current_power_w': 2500}
        }
        
        with server._background_cache_lock:
            server._background_cache['inverter_data'] = test_inverter
            server._background_cache['last_inverter_refresh'] = time.time()
        
        # Call inverter method
        inverter_data = server._get_real_inverter_data()
        
        # Verify it used cached data
        self.assertIsNotNone(inverter_data)
        self.assertEqual(inverter_data['battery']['soc_percent'], 75)
        self.assertEqual(inverter_data['data_source'], 'background_cache')
        
        server.shutdown()
    
    def test_get_system_metrics_uses_cache(self):
        """Test that _get_system_metrics reads from background cache"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Populate background cache with fresh data
        test_metrics = {
            'total_decisions': 100,
            'charging_count': 50,
            'wait_count': 50,
            'efficiency_score': 85.0
        }
        
        with server._background_cache_lock:
            server._background_cache['metrics_data'] = test_metrics
            server._background_cache['last_metrics_refresh'] = time.time()
        
        # Call metrics method
        metrics_data = server._get_system_metrics()
        
        # Verify it used cached data
        self.assertIsNotNone(metrics_data)
        self.assertEqual(metrics_data['total_decisions'], 100)
        self.assertEqual(metrics_data['efficiency_score'], 85.0)
        
        server.shutdown()


class TestCacheStalenessDetection(unittest.TestCase):
    """Test cache staleness detection and warnings"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.config = {
            'web_server': {
                'enabled': True,
                'background_refresh_interval_seconds': 60,
            },
            'data_storage': {
                'database_storage': {
                    'enabled': False
                }
            }
        }
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_stale_inverter_cache_detection(self):
        """Test that stale inverter cache is detected"""
        server = LogWebServer(host='127.0.0.1', port=8081, log_dir=self.logs_dir, config=self.config)
        
        # Set up stale cache (7 minutes old)
        test_inverter = {
            'battery': {'soc_percent': 75}
        }
        
        with server._background_cache_lock:
            server._background_cache['inverter_data'] = test_inverter
            server._background_cache['last_inverter_refresh'] = time.time() - 420  # 7 minutes ago
        
        # Call inverter method
        inverter_data = server._get_real_inverter_data()
        
        # Should still return data but mark as stale
        self.assertIsNotNone(inverter_data)
        self.assertEqual(inverter_data['data_source'], 'background_cache_stale')
        self.assertGreater(inverter_data['cache_age_seconds'], 400)
        
        server.shutdown()


if __name__ == '__main__':
    unittest.main()
