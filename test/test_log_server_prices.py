
import unittest
import json
import tempfile
import shutil
import os
import sys
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from log_web_server import LogWebServer

class TestLogWebServerPrices(unittest.TestCase):
    """Test log web server prices endpoint"""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level patches"""
        cls.background_refresh_patcher = patch('log_web_server.LogWebServer._start_background_refresh', lambda self: None)
        cls.background_refresh_patcher.start()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level patches"""
        cls.background_refresh_patcher.stop()
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.logs_dir = os.path.join(self.temp_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        self.test_host = '127.0.0.1'
        self.test_port = 8084
        
        # Create server instance
        self.server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=self.logs_dir)
        self.client = self.server.app.test_client()
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def test_get_prices_endpoint(self):
        """Test the /prices endpoint returns 200 and correct structure"""
        
        # Mock background cache with sample price data
        sample_price_data = {
            'current_price_pln_kwh': 0.50,
            'cheapest_price_pln_kwh': 0.40,
            'cheapest_hour': "14:00",
            'average_price_pln_kwh': 0.45,
            'prices': [
                {'hour': 13, 'hour_str': '13:00', 'price': 0.50, 'market_price': 0.50},
                {'hour': 14, 'hour_str': '14:00', 'price': 0.40, 'market_price': 0.40}
            ]
        }
        
        with self.server._background_cache_lock:
             self.server._background_cache['price_data'] = sample_price_data
             
        response = self.client.get('/prices')
        self.assertEqual(response.status_code, 200)
        
        data = response.get_json()
        self.assertIn('current_price_pln_kwh', data)
        self.assertEqual(data['current_price_pln_kwh'], 0.50)
        self.assertIn('prices', data)
        self.assertEqual(len(data['prices']), 2)
        self.assertEqual(data['prices'][0]['hour'], 13)

    def test_get_prices_endpoint_no_data(self):
        """Test the /prices endpoint returns 404 when no data"""
        
        # Ensure cache is empty
        with self.server._background_cache_lock:
            if 'price_data' in self.server._background_cache:
                del self.server._background_cache['price_data']
        
        # Mock load from disk to return None
        with patch.object(self.server, '_load_price_from_disk', return_value=None):
            response = self.client.get('/prices')
            self.assertEqual(response.status_code, 404)
            data = response.get_json()
            self.assertIn('error', data)

if __name__ == '__main__':
    unittest.main()
