#!/usr/bin/env python3
"""
Tests for price data date behavior and transitions
Verifies that the system correctly handles Polish electricity market day-ahead pricing
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from automated_price_charging import AutomatedPriceCharger


class TestPriceDateBehavior(unittest.TestCase):
    """Test price data date behavior and transitions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.charger = AutomatedPriceCharger()
        
        # Mock price data for different dates
        self.mock_price_data_2025_09_06 = {
            'value': [
                {
                    'dtime': '2025-09-06 00:15',
                    'period': '00:00 - 00:15',
                    'csdac_pln': 431.26,
                    'business_date': '2025-09-06',
                    'publication_ts': '2025-09-05 13:47:15.939'
                },
                {
                    'dtime': '2025-09-06 12:00',
                    'period': '12:00 - 12:15',
                    'csdac_pln': 450.00,
                    'business_date': '2025-09-06',
                    'publication_ts': '2025-09-05 13:47:15.939'
                },
                {
                    'dtime': '2025-09-07 00:00',
                    'period': '23:45 - 24:00',
                    'csdac_pln': 451.48,
                    'business_date': '2025-09-06',
                    'publication_ts': '2025-09-05 13:47:15.939'
                }
            ]
        }
        
        self.mock_price_data_2025_09_07 = {
            'value': [
                {
                    'dtime': '2025-09-07 00:15',
                    'period': '00:00 - 00:15',
                    'csdac_pln': 420.00,
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:30:00.000'
                },
                {
                    'dtime': '2025-09-07 12:00',
                    'period': '12:00 - 12:15',
                    'csdac_pln': 480.00,
                    'business_date': '2025-09-07',
                    'publication_ts': '2025-09-06 13:30:00.000'
                }
            ]
        }
    
    @patch('requests.get')
    def test_fetch_today_prices_correct_date(self, mock_get):
        """Test that fetch_today_prices uses the correct date"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_price_data_2025_09_06
        mock_get.return_value = mock_response
        
        # Test with a specific date
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 10, 30)  # 6.09.2025 10:30
            mock_datetime.strftime = datetime.strftime
            
            result = self.charger.fetch_today_prices()
            
            # Verify the API was called with the correct date
            expected_url = "https://api.raporty.pse.pl/api/csdac-pln?$filter=business_date%20eq%20'2025-09-06'"
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            self.assertIn('2025-09-06', call_args[0][0])
            
            # Verify the result
            self.assertIsNotNone(result)
            self.assertEqual(len(result['value']), 3)
    
    @patch('requests.get')
    def test_date_transition_at_midnight(self, mock_get):
        """Test that the system correctly transitions to next day's prices at midnight"""
        # Mock successful API response for next day
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_price_data_2025_09_07
        mock_get.return_value = mock_response
        
        # Test at midnight (00:00) - need to patch the datetime module properly
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 0, 0)  # 7.09.2025 00:00
            mock_datetime.strftime = datetime.strftime
            
            result = self.charger.fetch_today_prices()
            
            # Verify the API was called with the correct date (next day)
            call_args = mock_get.call_args
            self.assertIn('2025-09-07', call_args[0][0])
            
            # Verify the result
            self.assertIsNotNone(result)
            self.assertEqual(len(result['value']), 2)
    
    @patch('requests.get')
    def test_price_data_covers_full_day(self, mock_get):
        """Test that price data covers the full day (00:00-24:00)"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_price_data_2025_09_06
        mock_get.return_value = mock_response
        
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 15, 30)  # 6.09.2025 15:30
            mock_datetime.strftime = datetime.strftime
            
            result = self.charger.fetch_today_prices()
            
            # Verify the data covers the full day
            self.assertIsNotNone(result)
            price_data = result['value']
            
            # Check that we have data from start to end of day
            start_time = datetime.strptime(price_data[0]['dtime'], '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(price_data[-1]['dtime'], '%Y-%m-%d %H:%M')
            
            # Start should be around 00:00
            self.assertEqual(start_time.hour, 0)
            self.assertLessEqual(start_time.minute, 15)
            
            # End should be around 24:00 (next day 00:00)
            self.assertEqual(end_time.hour, 0)
            self.assertEqual(end_time.minute, 0)
            self.assertEqual(end_time.day, 7)  # Next day
    
    def test_get_current_price_within_day(self):
        """Test that get_current_price correctly finds the current price within the day"""
        # Test with current time within the price data
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)  # 6.09.2025 12:00
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            current_price = self.charger.get_current_price(self.mock_price_data_2025_09_06)
            
            # Should find the price for 12:00
            self.assertIsNotNone(current_price)
            # Price should be market price + SC component (450.00 + 89.2 = 539.2 PLN/MWh)
            self.assertAlmostEqual(current_price, 539.2, places=1)
    
    def test_get_current_price_outside_day(self):
        """Test that get_current_price returns None when outside the day's data"""
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 8, 12, 0)  # 8.09.2025 12:00
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            current_price = self.charger.get_current_price(self.mock_price_data_2025_09_06)
            
            # Should return None as the time is outside the data range
            self.assertIsNone(current_price)
    
    @patch('requests.get')
    def test_publication_timing_correctness(self, mock_get):
        """Test that the system correctly handles publication timing"""
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_price_data_2025_09_06
        mock_get.return_value = mock_response
        
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 14, 0)  # 6.09.2025 14:00 (after publication)
            mock_datetime.strftime = datetime.strftime
            
            result = self.charger.fetch_today_prices()
            
            # Verify the data has the correct publication timestamp
            self.assertIsNotNone(result)
            price_data = result['value']
            
            # Check publication timestamp (should be from previous day around 1-2 PM)
            publication_ts = price_data[0]['publication_ts']
            pub_time = datetime.strptime(publication_ts, '%Y-%m-%d %H:%M:%S.%f')
            
            # Publication should be on 5.09.2025 around 13:47
            self.assertEqual(pub_time.day, 5)
            self.assertEqual(pub_time.month, 9)
            self.assertEqual(pub_time.year, 2025)
            self.assertEqual(pub_time.hour, 13)
            self.assertEqual(pub_time.minute, 47)
    
    def test_business_date_consistency(self):
        """Test that all price points have consistent business_date"""
        price_data = self.mock_price_data_2025_09_06
        
        # All price points should have the same business_date
        business_dates = set(point['business_date'] for point in price_data['value'])
        self.assertEqual(len(business_dates), 1)
        self.assertEqual(list(business_dates)[0], '2025-09-06')
    
    @patch('requests.get')
    def test_error_handling_no_data(self, mock_get):
        """Test error handling when no price data is available"""
        # Mock API response with no data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'value': []}
        mock_get.return_value = mock_response
        
        result = self.charger.fetch_today_prices()
        
        # Should return empty data, not None
        self.assertIsNotNone(result)
        self.assertEqual(len(result['value']), 0)
    
    @patch('requests.get')
    def test_error_handling_api_failure(self, mock_get):
        """Test error handling when API call fails"""
        # Mock API failure
        mock_get.side_effect = Exception("Network error")
        
        result = self.charger.fetch_today_prices()
        
        # Should return None on error
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
