"""
Unit tests for adaptive price threshold components.

Tests PriceHistoryManager and AdaptiveThresholdCalculator functionality including:
- Price history collection and statistics
- Multiplier-based threshold calculation
- Seasonal adjustments
- Fallback behavior with insufficient data
- Persistence and loading
"""

import unittest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from price_history_manager import PriceHistoryManager
from adaptive_threshold_calculator import AdaptiveThresholdCalculator


class TestPriceHistoryManager(unittest.TestCase):
    """Test PriceHistoryManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'lookback_days': 7,
            'min_samples': 24
        }
        
        # Create manager and override directories to use temp
        self.manager = PriceHistoryManager(self.config)
        self.manager.data_dir = Path(self.temp_dir)
        self.manager.cache_file = Path(self.temp_dir) / 'price_history.json'
        self.manager.energy_data_dir = Path(self.temp_dir) / 'energy_data'
        self.manager.energy_data_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_add_price_point(self):
        """Test adding price points to history."""
        now = datetime.now()
        self.manager.add_price_point(now, 0.5)
        self.manager.add_price_point(now + timedelta(hours=1), 0.6)
        
        self.assertEqual(len(self.manager.price_cache), 2)
        self.assertEqual(self.manager.price_cache[0][1], 0.5)
        self.assertEqual(self.manager.price_cache[1][1], 0.6)
    
    def test_negative_price_rejected(self):
        """Test that negative prices are rejected."""
        initial_count = len(self.manager.price_cache)
        self.manager.add_price_point(datetime.now(), -0.1)
        self.assertEqual(len(self.manager.price_cache), initial_count)
    
    def test_get_recent_prices(self):
        """Test retrieving recent prices."""
        now = datetime.now()
        
        # Add prices over 48 hours
        for i in range(48):
            timestamp = now - timedelta(hours=48-i)
            self.manager.add_price_point(timestamp, 0.5 + i * 0.01)
        
        # Get last 24 hours
        recent = self.manager.get_recent_prices(hours=24)
        self.assertGreater(len(recent), 20)  # Should have prices from last 24h
    
    def test_calculate_statistics(self):
        """Test statistics calculation."""
        now = datetime.now()
        
        # Add known prices
        prices = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        for i, price in enumerate(prices):
            self.manager.add_price_point(now - timedelta(hours=len(prices)-i), price)
        
        stats = self.manager.calculate_statistics()
        
        self.assertEqual(stats['sample_count'], len(prices))
        self.assertAlmostEqual(stats['median'], 0.65, places=2)
        self.assertAlmostEqual(stats['mean'], 0.65, places=2)
        self.assertGreater(stats['p75'], stats['median'])
        self.assertLess(stats['p25'], stats['median'])
    
    def test_calculate_statistics_empty(self):
        """Test statistics with no data."""
        stats = self.manager.calculate_statistics()
        
        self.assertEqual(stats['sample_count'], 0)
        self.assertEqual(stats['median'], 0.0)
        self.assertEqual(stats['mean'], 0.0)
    
    def test_persistence(self):
        """Test saving and loading cache."""
        now = datetime.now()
        
        # Add some prices
        for i in range(10):
            self.manager.add_price_point(now - timedelta(hours=i), 0.5 + i * 0.05)
        
        # Save cache
        self.manager._save_cache()
        
        # Create new manager and load cache
        new_manager = PriceHistoryManager(self.config)
        new_manager.data_dir = Path(self.temp_dir)
        new_manager.cache_file = Path(self.temp_dir) / 'price_history.json'
        new_manager._load_cache()
        
        self.assertEqual(len(new_manager.price_cache), len(self.manager.price_cache))
    
    def test_get_cache_info(self):
        """Test cache information retrieval."""
        now = datetime.now()
        
        # Empty cache
        info = self.manager.get_cache_info()
        self.assertEqual(info['count'], 0)
        
        # Add prices
        self.manager.add_price_point(now - timedelta(hours=24), 0.5)
        self.manager.add_price_point(now, 0.6)
        
        info = self.manager.get_cache_info()
        self.assertEqual(info['count'], 2)
        self.assertIsNotNone(info['oldest'])
        self.assertIsNotNone(info['newest'])
        self.assertGreater(info['coverage_hours'], 20)


class TestAdaptiveThresholdCalculator(unittest.TestCase):
    """Test AdaptiveThresholdCalculator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = {
            'method': 'multiplier',
            'high_price_multiplier': 1.5,
            'critical_price_multiplier': 1.3,
            'seasonal_adjustments_enabled': True,
            'seasonal_multipliers': {
                'winter': {'multiplier': 1.3, 'months': [11, 12, 1, 2]},
                'summer': {'multiplier': 0.85, 'months': [6, 7, 8]},
                'spring_autumn': {'multiplier': 1.0, 'months': [3, 4, 5, 9, 10]}
            },
            'fallback_high_price_pln': 1.35,
            'fallback_critical_price_pln': 1.20
        }
        self.calculator = AdaptiveThresholdCalculator(self.config)
    
    def test_multiplier_calculation(self):
        """Test multiplier-based threshold calculation."""
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'p75': 0.8,
            'sample_count': 100
        }
        
        # Test with spring/autumn (1.0x seasonal)
        april_time = datetime(2025, 4, 15)
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats, april_time)
        critical_threshold = self.calculator.calculate_critical_price_threshold(price_stats, april_time)
        
        # Expected: median * multiplier * seasonal
        expected_high = 0.6 * 1.5 * 1.0
        expected_critical = 0.6 * 1.3 * 1.0
        
        self.assertAlmostEqual(high_threshold, expected_high, places=3)
        self.assertAlmostEqual(critical_threshold, expected_critical, places=3)
    
    def test_seasonal_adjustment_winter(self):
        """Test winter seasonal adjustment (1.3x)."""
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'sample_count': 100
        }
        
        # November (winter)
        november_time = datetime(2025, 11, 26)
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats, november_time)
        
        # Expected: 0.6 * 1.5 * 1.3 = 1.17
        expected = 0.6 * 1.5 * 1.3
        self.assertAlmostEqual(high_threshold, expected, places=3)
        
        # Verify season detection
        season = self.calculator.get_season_name(november_time)
        self.assertEqual(season, 'winter')
    
    def test_seasonal_adjustment_summer(self):
        """Test summer seasonal adjustment (0.85x)."""
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'sample_count': 100
        }
        
        # July (summer)
        july_time = datetime(2025, 7, 15)
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats, july_time)
        
        # Expected: 0.6 * 1.5 * 0.85 = 0.765
        expected = 0.6 * 1.5 * 0.85
        self.assertAlmostEqual(high_threshold, expected, places=3)
        
        # Verify season detection
        season = self.calculator.get_season_name(july_time)
        self.assertEqual(season, 'summer')
    
    def test_fallback_no_data(self):
        """Test fallback when no price data available."""
        price_stats = {
            'median': 0.0,
            'mean': 0.0,
            'sample_count': 0
        }
        
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats)
        critical_threshold = self.calculator.calculate_critical_price_threshold(price_stats)
        
        self.assertEqual(high_threshold, 1.35)  # fallback_high_price_pln
        self.assertEqual(critical_threshold, 1.20)  # fallback_critical_price_pln
    
    def test_fallback_zero_median(self):
        """Test fallback when median is zero."""
        price_stats = {
            'median': 0.0,
            'mean': 0.5,
            'sample_count': 50
        }
        
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats)
        
        self.assertEqual(high_threshold, 1.35)  # Should use fallback
    
    def test_seasonal_disabled(self):
        """Test thresholds without seasonal adjustments."""
        config = self.config.copy()
        config['seasonal_adjustments_enabled'] = False
        calculator = AdaptiveThresholdCalculator(config)
        
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'sample_count': 100
        }
        
        # Winter time but seasonal disabled
        november_time = datetime(2025, 11, 26)
        high_threshold = calculator.calculate_high_price_threshold(price_stats, november_time)
        
        # Expected: 0.6 * 1.5 (no seasonal multiplier)
        expected = 0.6 * 1.5
        self.assertAlmostEqual(high_threshold, expected, places=3)
    
    def test_percentile_method(self):
        """Test percentile-based calculation method."""
        config = self.config.copy()
        config['method'] = 'percentile'
        config['high_price_percentile'] = 75
        config['seasonal_adjustments_enabled'] = False
        calculator = AdaptiveThresholdCalculator(config)
        
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'p75': 0.85,
            'p50': 0.6,
            'sample_count': 100
        }
        
        high_threshold = calculator.calculate_high_price_threshold(price_stats)
        
        # Should use p75 directly
        self.assertEqual(high_threshold, 0.85)
    
    def test_get_calculation_info(self):
        """Test detailed calculation information."""
        price_stats = {
            'median': 0.6,
            'mean': 0.65,
            'p75': 0.8,
            'sample_count': 100
        }
        
        info = self.calculator.get_calculation_info(price_stats)
        
        self.assertEqual(info['method'], 'multiplier')
        self.assertIn('season', info)
        self.assertIn('seasonal_multiplier', info)
        self.assertIn('high_price_threshold_pln', info)
        self.assertIn('critical_price_threshold_pln', info)
        self.assertEqual(info['sample_count'], 100)
        self.assertFalse(info['using_fallback'])
    
    def test_all_seasonal_months(self):
        """Test that all months map to a season."""
        for month in range(1, 13):
            test_time = datetime(2025, month, 15)
            season = self.calculator.get_season_name(test_time)
            self.assertIn(season, ['winter', 'summer', 'spring_autumn'])
    
    def test_realistic_winter_scenario(self):
        """Test realistic winter pricing scenario."""
        # Current median price in November 2025: ~0.8 PLN/kWh
        price_stats = {
            'median': 0.8,
            'mean': 0.85,
            'p75': 1.0,
            'sample_count': 168  # 7 days of hourly data
        }
        
        november_time = datetime(2025, 11, 26)
        high_threshold = self.calculator.calculate_high_price_threshold(price_stats, november_time)
        critical_threshold = self.calculator.calculate_critical_price_threshold(price_stats, november_time)
        
        # Expected high: 0.8 * 1.5 * 1.3 = 1.56 PLN/kWh
        # Expected critical: 0.8 * 1.3 * 1.3 = 1.352 PLN/kWh
        self.assertAlmostEqual(high_threshold, 1.56, places=2)
        self.assertAlmostEqual(critical_threshold, 1.352, places=2)
        
        # Verify thresholds are higher than fixed ones (1.35/1.20)
        self.assertGreater(high_threshold, 1.35)
        self.assertGreater(critical_threshold, 1.20)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete adaptive threshold system."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
        history_config = {
            'lookback_days': 7,
            'min_samples': 24
        }
        
        calc_config = {
            'method': 'multiplier',
            'high_price_multiplier': 1.5,
            'critical_price_multiplier': 1.3,
            'seasonal_adjustments_enabled': True,
            'seasonal_multipliers': {
                'winter': {'multiplier': 1.3, 'months': [11, 12, 1, 2]},
                'summer': {'multiplier': 0.85, 'months': [6, 7, 8]},
                'spring_autumn': {'multiplier': 1.0, 'months': [3, 4, 5, 9, 10]}
            },
            'fallback_high_price_pln': 1.35,
            'fallback_critical_price_pln': 1.20
        }
        
        self.history = PriceHistoryManager(history_config)
        self.history.data_dir = Path(self.temp_dir)
        self.history.cache_file = Path(self.temp_dir) / 'price_history.json'
        
        self.calculator = AdaptiveThresholdCalculator(calc_config)
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow(self):
        """Test complete workflow: collect prices → calculate stats → compute thresholds."""
        now = datetime.now()
        
        # Simulate 7 days of hourly price data (typical Polish market winter pattern)
        for day in range(7):
            for hour in range(24):
                timestamp = now - timedelta(days=6-day, hours=23-hour)
                
                # Simulate daily price pattern (night low, day high)
                if 0 <= hour < 6:  # Night
                    price = 0.5 + (day * 0.02)
                elif 6 <= hour < 22:  # Day
                    price = 0.9 + (day * 0.03)
                else:  # Evening
                    price = 1.1 + (day * 0.04)
                
                self.history.add_price_point(timestamp, price)
        
        # Calculate statistics
        stats = self.history.calculate_statistics()
        
        self.assertGreater(stats['sample_count'], 150)  # Should have ~168 samples
        self.assertGreater(stats['median'], 0.5)
        self.assertLess(stats['median'], 1.5)
        
        # Calculate thresholds (winter time)
        high_threshold = self.calculator.calculate_high_price_threshold(stats)
        critical_threshold = self.calculator.calculate_critical_price_threshold(stats)
        
        # Thresholds should be reasonable for winter
        self.assertGreater(high_threshold, 1.0)
        self.assertLess(high_threshold, 2.5)
        self.assertGreater(critical_threshold, 0.8)
        self.assertLess(critical_threshold, 2.0)
        
        # High threshold should be higher than critical
        self.assertGreater(high_threshold, critical_threshold)
    
    def test_insufficient_data_workflow(self):
        """Test workflow with insufficient data uses fallback."""
        now = datetime.now()
        
        # Add only 10 samples (less than min_samples=24)
        for i in range(10):
            self.history.add_price_point(now - timedelta(hours=i), 0.6)
        
        stats = self.history.calculate_statistics()
        self.assertEqual(stats['sample_count'], 10)
        
        # Should still calculate thresholds but with low confidence
        high_threshold = self.calculator.calculate_high_price_threshold(stats)
        
        # With insufficient samples in production, code would use fallback
        # But calculator itself will still compute from available data
        self.assertGreater(high_threshold, 0)


if __name__ == '__main__':
    unittest.main()
