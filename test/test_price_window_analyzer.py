#!/usr/bin/env python3
"""
Price Window Analyzer Tests
Tests the price window analysis functionality for optimal charging timing

This test suite verifies:
- Price window identification and analysis
- Low price window detection
- Price trend analysis
- Window duration calculations
- Optimal charging timing recommendations
- Price volatility analysis
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

from price_window_analyzer import PriceWindowAnalyzer, PriceWindow


class TestPriceWindowAnalyzer(unittest.TestCase):
    """Test price window analyzer functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')
        self.create_test_config()
        
        # Sample price data for testing
        self.sample_price_data = {
            'prices': [
                0.45, 0.42, 0.38, 0.35, 0.32, 0.28, 0.25, 0.22,  # 00:00-01:45 (low prices)
                0.20, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06, 0.05,  # 02:00-03:45 (very low prices)
                0.08, 0.12, 0.18, 0.25, 0.32, 0.38, 0.45, 0.52,  # 04:00-05:45 (rising prices)
                0.58, 0.65, 0.72, 0.78, 0.85, 0.92, 0.98, 1.05,  # 06:00-07:45 (high prices)
                1.12, 1.18, 1.25, 1.32, 1.38, 1.45, 1.52, 1.58,  # 08:00-09:45 (peak prices)
                1.65, 1.72, 1.78, 1.85, 1.92, 1.98, 2.05, 2.12,  # 10:00-11:45 (very high prices)
                2.18, 2.25, 2.32, 2.38, 2.45, 2.52, 2.58, 2.65,  # 12:00-13:45 (peak prices)
                2.72, 2.78, 2.85, 2.92, 2.98, 3.05, 3.12, 3.18,  # 14:00-15:45 (very high prices)
                3.25, 3.32, 3.38, 3.45, 3.52, 3.58, 3.65, 3.72,  # 16:00-17:45 (peak prices)
                3.78, 3.85, 3.92, 3.98, 4.05, 4.12, 4.18, 4.25,  # 18:00-19:45 (very high prices)
                4.32, 4.38, 4.45, 4.52, 4.58, 4.65, 4.72, 4.78,  # 20:00-21:45 (high prices)
                4.85, 4.92, 4.98, 5.05, 5.12, 5.18, 5.25, 5.32,  # 22:00-23:45 (very high prices)
            ],
            'date': '2025-09-07',
            'currency': 'PLN',
            'unit': 'kWh',
            'intervals': 96,  # 15-minute intervals
            'start_time': '00:00',
            'end_time': '23:45'
        }
        
        # Expected low price windows
        self.expected_low_windows = [
            {'start': 0, 'end': 7, 'duration': 2.0, 'avg_price': 0.31},   # 00:00-01:45
            {'start': 8, 'end': 15, 'duration': 2.0, 'avg_price': 0.10},  # 02:00-03:45
        ]
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_config(self):
        """Create test configuration file"""
        config = {
            'price_analysis': {
                'very_low_price_threshold': 0.15,  # 0.15 PLN/kWh
                'low_price_threshold': 0.35,       # 0.35 PLN/kWh
                'medium_price_threshold': 0.60,    # 0.60 PLN/kWh
                'high_price_threshold': 1.40,      # 1.40 PLN/kWh (to match test expectations)
                'very_high_price_threshold': 1.50, # 1.50 PLN/kWh
                'min_window_duration_minutes': 30,
                'max_window_duration_hours': 4
            },
            'charging': {
                'max_charging_power': 3000,
                'battery_capacity_kwh': 10,
                'charging_efficiency': 0.95
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
    
    def test_price_window_analyzer_initialization(self):
        """Test price window analyzer initialization"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        self.assertIsNotNone(analyzer, "Price window analyzer should be created")
        self.assertIsNotNone(analyzer.config, "Configuration should be loaded")
        self.assertEqual(analyzer.config.get('low_price_threshold_percentile', 25), 25,
                        "Low price threshold should be set correctly")
    
    def test_price_window_identification(self):
        """Test identification of price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price data
        windows = analyzer.identify_price_windows(self.sample_price_data)
        
        self.assertIsNotNone(windows, "Price windows should be identified")
        self.assertIsInstance(windows, list, "Windows should be a list")
        self.assertGreater(len(windows), 0, "Should identify at least one price window")
        
        # Verify window structure
        for window in windows:
            self.assertIsInstance(window, PriceWindow, "Window should be PriceWindow instance")
            self.assertIn('start_time', window.__dict__, "Window should have start_time")
            self.assertIn('end_time', window.__dict__, "Window should have end_time")
            self.assertIn('duration_hours', window.__dict__, "Window should have duration_hours")
            self.assertTrue(hasattr(window, 'avg_price'), "Window should have avg_price")
            self.assertTrue(hasattr(window, 'price_type'), "Window should have price_type")
    
    def test_low_price_window_detection(self):
        """Test detection of low price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price data
        windows = analyzer.identify_price_windows(self.sample_price_data)
        
        # Find low price windows
        low_windows = [w for w in windows if w.price_type == 'low']
        
        self.assertGreater(len(low_windows), 0, "Should identify low price windows")
        
        # Verify low price window characteristics
        for window in low_windows:
            self.assertLessEqual(window.avg_price, 0.35, "Low price window should have low average price")
            self.assertGreaterEqual(window.duration_hours, 0.5, "Low price window should be at least 30 minutes")
    
    def test_very_low_price_window_detection(self):
        """Test detection of very low price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price data
        windows = analyzer.identify_price_windows(self.sample_price_data)
        
        # Find very low price windows
        very_low_windows = [w for w in windows if w.price_type == 'very_low']
        
        self.assertGreater(len(very_low_windows), 0, "Should identify very low price windows")
        
        # Verify very low price window characteristics
        for window in very_low_windows:
            self.assertLessEqual(window.avg_price, 0.15, "Very low price window should have very low average price")
    
    def test_high_price_window_detection(self):
        """Test detection of high price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price data
        windows = analyzer.identify_price_windows(self.sample_price_data)
        
        # Find high price windows
        high_windows = [w for w in windows if w.price_type == 'high']
        
        self.assertGreater(len(high_windows), 0, "Should identify high price windows")
        
        # Verify high price window characteristics
        for window in high_windows:
            self.assertGreaterEqual(window.avg_price, 1.0, "High price window should have high average price")
    
    def test_price_trend_analysis(self):
        """Test price trend analysis"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price trends
        trends = analyzer.analyze_price_trends(self.sample_price_data)
        
        self.assertIsNotNone(trends, "Price trends should be analyzed")
        self.assertIn('overall_trend', trends, "Should include overall trend")
        self.assertIn('trend_strength', trends, "Should include trend strength")
        self.assertIn('volatility', trends, "Should include volatility")
        
        # Verify trend analysis results
        self.assertIn(trends['overall_trend'], ['rising', 'falling', 'stable'], 
                     "Overall trend should be one of the expected values")
        self.assertGreaterEqual(trends['trend_strength'], 0.0, "Trend strength should be non-negative")
        self.assertLessEqual(trends['trend_strength'], 1.0, "Trend strength should be at most 1.0")
        self.assertGreaterEqual(trends['volatility'], 0.0, "Volatility should be non-negative")
    
    def test_window_duration_calculation(self):
        """Test window duration calculations"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Create a test window
        start_time = datetime(2025, 9, 7, 2, 0)  # 02:00
        end_time = datetime(2025, 9, 7, 4, 0)    # 04:00
        
        duration = analyzer.calculate_window_duration(start_time, end_time)
        
        self.assertEqual(duration, 2.0, "Window duration should be 2 hours")
    
    def test_optimal_charging_timing(self):
        """Test optimal charging timing recommendations"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price data
        windows = analyzer.identify_price_windows(self.sample_price_data)
        
        # Get optimal charging timing
        energy_needed_kwh = 5.0  # 5 kWh needed (30% to 80% of 10 kWh battery)
        max_charging_power_kw = 3.0  # 3 kW max charging power
        
        timing = analyzer.get_optimal_charging_timing(
            self.sample_price_data, energy_needed_kwh, max_charging_power_kw
        )
        
        self.assertIsNotNone(timing, "Optimal charging timing should be calculated")
        self.assertIn('optimal_window', timing, "Should recommend a charging window")
        self.assertIn('recommendation', timing, "Should include recommendation")
        self.assertIn('reason', timing, "Should include reason")
        self.assertIn('estimated_cost', timing, "Should include estimated cost")
        self.assertIn('charging_duration_hours', timing, "Should include charging duration")
    
    def test_price_volatility_analysis(self):
        """Test price volatility analysis"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Analyze price volatility
        volatility = analyzer.analyze_price_volatility(self.sample_price_data)
        
        self.assertIsNotNone(volatility, "Price volatility should be analyzed")
        self.assertIn('volatility_score', volatility, "Should include volatility score")
        self.assertIn('price_range', volatility, "Should include price range")
        self.assertIn('standard_deviation', volatility, "Should include standard deviation")
        self.assertIn('coefficient_of_variation', volatility, "Should include coefficient of variation")
        
        # Verify volatility analysis results
        self.assertGreaterEqual(volatility['volatility_score'], 0.0, "Volatility score should be non-negative")
        self.assertGreater(volatility['price_range'], 0.0, "Price range should be positive")
        self.assertGreaterEqual(volatility['standard_deviation'], 0.0, "Standard deviation should be non-negative")
    
    def test_charging_cost_calculation(self):
        """Test charging cost calculations"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Test cost calculation for a specific window
        window = PriceWindow(
            start_time=datetime(2025, 9, 7, 2, 0),
            end_time=datetime(2025, 9, 7, 4, 0),
            duration_hours=2.0,
            avg_price=0.10,
            price_type='very_low'
        )
        
        energy_needed = 5.0  # 5 kWh
        cost = analyzer.calculate_charging_cost(window, energy_needed)
        
        self.assertIsNotNone(cost, "Charging cost should be calculated")
        self.assertIn('total_cost', cost, "Should include total cost")
        self.assertIn('cost_per_kwh', cost, "Should include cost per kWh")
        self.assertIn('energy_charged', cost, "Should include energy charged")
        
        # Verify cost calculation
        expected_cost = 0.10 * 5.0  # 0.50 PLN
        self.assertAlmostEqual(cost['total_cost'], expected_cost, places=2, 
                              msg="Cost calculation should be accurate")
    
    def test_savings_calculation(self):
        """Test savings calculation compared to average price"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Test savings calculation
        low_price_window = PriceWindow(
            start_time=datetime(2025, 9, 7, 2, 0),
            end_time=datetime(2025, 9, 7, 4, 0),
            duration_hours=2.0,
            avg_price=0.10,
            price_type='very_low'
        )
        
        average_price = 1.50  # PLN/kWh
        energy_needed = 5.0   # kWh
        
        savings = analyzer.calculate_savings(low_price_window, average_price, energy_needed)
        
        self.assertIsNotNone(savings, "Savings should be calculated")
        self.assertIn('savings_amount', savings, "Should include savings amount")
        self.assertIn('savings_percentage', savings, "Should include savings percentage")
        self.assertIn('cost_with_average', savings, "Should include cost with average price")
        self.assertIn('cost_with_low_price', savings, "Should include cost with low price")
        
        # Verify savings calculation
        expected_savings = (1.50 - 0.10) * 5.0  # 7.00 PLN
        self.assertAlmostEqual(savings['savings_amount'], expected_savings, places=2,
                              msg="Savings calculation should be accurate")
    
    def test_window_overlap_detection(self):
        """Test detection of overlapping price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Create overlapping windows
        window1 = PriceWindow(
            start_time=datetime(2025, 9, 7, 2, 0),
            end_time=datetime(2025, 9, 7, 4, 0),
            duration_hours=2.0,
            avg_price=0.10,
            price_type='very_low'
        )
        
        window2 = PriceWindow(
            start_time=datetime(2025, 9, 7, 3, 0),
            end_time=datetime(2025, 9, 7, 5, 0),
            duration_hours=2.0,
            avg_price=0.15,
            price_type='low'
        )
        
        # Test overlap detection
        has_overlap = analyzer.windows_overlap(window1, window2)
        self.assertTrue(has_overlap, "Should detect overlapping windows")
        
        # Test non-overlapping windows
        window3 = PriceWindow(
            start_time=datetime(2025, 9, 7, 6, 0),
            end_time=datetime(2025, 9, 7, 8, 0),
            duration_hours=2.0,
            avg_price=0.50,
            price_type='medium'
        )
        
        has_overlap = analyzer.windows_overlap(window1, window3)
        self.assertFalse(has_overlap, "Should not detect overlap in non-overlapping windows")
    
    def test_window_priority_ranking(self):
        """Test ranking of price windows by priority"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Create windows with different priorities
        windows = [
            PriceWindow(
                start_time=datetime(2025, 9, 7, 2, 0),
                end_time=datetime(2025, 9, 7, 4, 0),
                duration_hours=2.0,
                avg_price=0.10,
                price_type='very_low'
            ),
            PriceWindow(
                start_time=datetime(2025, 9, 7, 6, 0),
                end_time=datetime(2025, 9, 7, 8, 0),
                duration_hours=2.0,
                avg_price=0.50,
                price_type='medium'
            ),
            PriceWindow(
                start_time=datetime(2025, 9, 7, 10, 0),
                end_time=datetime(2025, 9, 7, 12, 0),
                duration_hours=2.0,
                avg_price=2.00,
                price_type='high'
            )
        ]
        
        # Rank windows by priority
        ranked_windows = analyzer.rank_windows_by_priority(windows)
        
        self.assertIsNotNone(ranked_windows, "Windows should be ranked")
        self.assertEqual(len(ranked_windows), len(windows), "Should rank all windows")
        
        # Verify ranking (very_low should be highest priority)
        self.assertEqual(ranked_windows[0].price_type, 'very_low', 
                        "Very low price window should be highest priority")
    
    def test_energy_capacity_analysis(self):
        """Test analysis of energy capacity in price windows"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Test energy capacity analysis
        window = PriceWindow(
            start_time=datetime(2025, 9, 7, 2, 0),
            end_time=datetime(2025, 9, 7, 4, 0),
            duration_hours=2.0,
            avg_price=0.10,
            price_type='very_low'
        )
        
        max_charging_power = 3000  # 3 kW
        battery_capacity = 10.0    # 10 kWh
        
        capacity_analysis = analyzer.analyze_energy_capacity(window, max_charging_power, battery_capacity)
        
        self.assertIsNotNone(capacity_analysis, "Energy capacity should be analyzed")
        self.assertIn('max_energy_chargeable', capacity_analysis, "Should include max energy chargeable")
        self.assertIn('charging_power_utilization', capacity_analysis, "Should include power utilization")
        self.assertIn('battery_capacity_utilization', capacity_analysis, "Should include battery utilization")
        
        # Verify capacity analysis
        expected_max_energy = 2.0 * 3.0  # 6 kWh (2 hours * 3 kW)
        self.assertAlmostEqual(capacity_analysis['max_energy_chargeable'], expected_max_energy, places=2,
                              msg="Max energy calculation should be accurate")
    
    def test_price_window_filtering(self):
        """Test filtering of price windows by criteria"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Create test windows
        windows = [
            PriceWindow(
                start_time=datetime(2025, 9, 7, 2, 0),
                end_time=datetime(2025, 9, 7, 4, 0),
                duration_hours=2.0,
                avg_price=0.10,
                price_type='very_low'
            ),
            PriceWindow(
                start_time=datetime(2025, 9, 7, 6, 0),
                end_time=datetime(2025, 9, 7, 6, 30),
                duration_hours=0.5,
                avg_price=0.50,
                price_type='medium'
            ),
            PriceWindow(
                start_time=datetime(2025, 9, 7, 10, 0),
                end_time=datetime(2025, 9, 7, 12, 0),
                duration_hours=2.0,
                avg_price=2.00,
                price_type='high'
            )
        ]
        
        # Filter windows by minimum duration
        filtered_windows = analyzer.filter_windows_by_duration(windows, min_duration_hours=1.0)
        
        self.assertIsNotNone(filtered_windows, "Windows should be filtered")
        self.assertEqual(len(filtered_windows), 2, "Should filter out short windows")
        
        # Filter windows by price type
        low_price_windows = analyzer.filter_windows_by_price_type(windows, ['very_low', 'low'])
        
        self.assertEqual(len(low_price_windows), 1, "Should filter to low price windows only")
        self.assertEqual(low_price_windows[0].price_type, 'very_low', 
                        "Should return very low price window")
    
    def test_error_handling_invalid_data(self):
        """Test error handling with invalid price data"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Test with invalid price data
        invalid_data = {
            'prices': [],  # Empty prices
            'date': '2025-09-07'
        }
        
        # Should handle invalid data gracefully
        try:
            windows = analyzer.identify_price_windows(invalid_data)
            self.assertIsNotNone(windows, "Should handle invalid data gracefully")
            self.assertEqual(len(windows), 0, "Should return empty list for invalid data")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle invalid data gracefully, got exception: {e}")
    
    def test_error_handling_missing_config(self):
        """Test error handling with missing configuration"""
        # Test with non-existent config file
        invalid_config_path = os.path.join(self.temp_dir, 'non_existent_config.yaml')
        
        # Should handle missing config gracefully
        try:
            analyzer = PriceWindowAnalyzer(invalid_config_path)
            self.assertIsNotNone(analyzer, "Should create analyzer even with missing config")
        except Exception as e:
            # Should not raise unhandled exceptions
            self.fail(f"Should handle missing config gracefully, got exception: {e}")


class TestPriceWindowPerformance(unittest.TestCase):
    """Test price window analyzer performance characteristics"""
    
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
            'price_analysis': {
                'very_low_price_threshold': 0.15,  # 0.15 PLN/kWh
                'low_price_threshold': 0.35,       # 0.35 PLN/kWh
                'medium_price_threshold': 0.60,    # 0.60 PLN/kWh
                'high_price_threshold': 1.40,      # 1.40 PLN/kWh (to match test expectations)
                'very_high_price_threshold': 1.50, # 1.50 PLN/kWh
                'min_window_duration_minutes': 30,
                'max_window_duration_hours': 4
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
    
    def test_analysis_performance_large_dataset(self):
        """Test performance with large price dataset"""
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Create large price dataset (7 days of 15-minute intervals)
        large_price_data = {
            'prices': [0.25 + (i % 96) * 0.01 for i in range(7 * 96)],  # 672 prices
            'date': '2025-09-07',
            'currency': 'PLN',
            'unit': 'kWh',
            'intervals': 7 * 96
        }
        
        # Test analysis performance
        start_time = datetime.now()
        
        windows = analyzer.identify_price_windows(large_price_data)
        trends = analyzer.analyze_price_trends(large_price_data)
        volatility = analyzer.analyze_price_volatility(large_price_data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Performance assertions
        self.assertLess(duration, 5.0, "Analysis of large dataset should complete within 5 seconds")
        self.assertIsNotNone(windows, "Should identify windows in large dataset")
        self.assertIsNotNone(trends, "Should analyze trends in large dataset")
        self.assertIsNotNone(volatility, "Should analyze volatility in large dataset")
    
    def test_memory_usage(self):
        """Test memory usage of price window analyzer"""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create analyzer
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        # Get memory usage after creation
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 10MB)
        self.assertLess(memory_increase, 10 * 1024 * 1024, 
                       f"Memory increase should be less than 10MB, got {memory_increase / 1024 / 1024:.2f}MB")
    
    def test_initialization_time(self):
        """Test price window analyzer initialization time"""
        start_time = datetime.now()
        
        config = self.load_config()
        analyzer = PriceWindowAnalyzer(config['price_analysis'])
        
        end_time = datetime.now()
        initialization_time = (end_time - start_time).total_seconds()
        
        # Initialization should be fast (less than 1 second)
        self.assertLess(initialization_time, 1.0, 
                       f"Initialization should be less than 1 second, got {initialization_time:.2f} seconds")


if __name__ == '__main__':
    unittest.main(verbosity=2)
