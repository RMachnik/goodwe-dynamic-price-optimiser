#!/usr/bin/env python3
"""
Tests for Weather-Aware Decision System
Verifies that the system correctly uses weather forecasts and PV trends to make smart charging decisions
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MultiFactorDecisionEngine
from pv_trend_analyzer import PVTrendAnalyzer


class TestWeatherAwareDecisions(unittest.TestCase):
    """Test weather-aware decision making in the enhanced system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_interval_minutes': 15,
                'health_check_interval_minutes': 5
            },
            'timing_awareness_enabled': True,  # Enable timing awareness for weather tests
            'weather_integration': {
                'enabled': True
            },
            'weather_aware_decisions': {
                'enabled': True,
                'trend_analysis_hours': 2,
                'min_trend_confidence': 0.6,
                'weather_impact_threshold': 0.3,
                'max_wait_time_hours': 2.0,
                'min_pv_improvement_kw': 1.0
            },
            'timing_awareness': {
                'pv_capacity_kw': 10.0,
                'charging_rate_kw': 3.0,
                'battery_capacity_kwh': 10.0
            },
            'battery_management': {
                'soc_thresholds': {
                    'critical': 12  # Use same threshold as main config
                }
            }
        }
        self.decision_engine = MultiFactorDecisionEngine(self.config)
        
        # Initialize PV consumption analyzer (normally done in MasterCoordinator)
        from pv_consumption_analyzer import PVConsumptionAnalyzer
        self.decision_engine.pv_consumption_analyzer = PVConsumptionAnalyzer(self.config)
        
        # Set up mock weather collector for PV forecaster
        mock_weather_collector = Mock()
        # Mock the get_solar_irradiance_forecast method to return test data
        mock_weather_collector.get_solar_irradiance_forecast.return_value = [
            {
                'timestamp': '2025-09-07T12:00:00',
                'ghi': 800,  # High solar irradiance
                'dni': 900,
                'dhi': 100,
                'cloud_cover_total': 20,  # Low cloud cover
                'cloud_cover_low': 10,
                'cloud_cover_mid': 5,
                'cloud_cover_high': 5
            },
            {
                'timestamp': '2025-09-07T13:00:00',
                'ghi': 900,  # Even higher solar irradiance
                'dni': 1000,
                'dhi': 100,
                'cloud_cover_total': 10,  # Very low cloud cover
                'cloud_cover_low': 5,
                'cloud_cover_mid': 3,
                'cloud_cover_high': 2
            }
        ]
        self.decision_engine.pv_forecaster.set_weather_collector(mock_weather_collector)
        
        # Mock price data with current time
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = (current_time.minute // 15) * 15  # Round to nearest 15 minutes
        current_date = current_time.strftime('%Y-%m-%d')
        
        self.mock_price_data = {
            'value': [
                {
                    'dtime': f'{current_date} {current_hour:02d}:{current_minute:02d}',
                    'csdac_pln': 1100.0,  # Price above 10th percentile (1089.2)
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 1) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 800.0,  # Even higher price
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 2) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 1000.0,  # Very high price
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 3) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 1200.0,  # Extremely high price
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 4) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 1400.0,  # Even higher
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 5) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 1600.0,  # Even higher
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 6) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 1800.0,  # Even higher
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 7) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 2000.0,  # Even higher
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 8) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 2200.0,  # Even higher
                    'business_date': current_date
                },
                {
                    'dtime': f'{current_date} {(current_hour + 9) % 24:02d}:{current_minute:02d}',
                    'csdac_pln': 2400.0,  # Even higher
                    'business_date': current_date
                }
            ]
        }
    
    def test_pv_trend_analyzer_initialization(self):
        """Test that PV trend analyzer is properly initialized"""
        self.assertIsNotNone(self.decision_engine.pv_trend_analyzer)
        self.assertIsInstance(self.decision_engine.pv_trend_analyzer, PVTrendAnalyzer)
    
    def test_weather_aware_decision_with_increasing_pv_trend(self):
        """Test decision making when PV production is increasing"""
        # Scenario: PV production is increasing, should wait for better conditions
        current_data = {
            'battery': {
                'soc_percent': 40,  # Medium battery level
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_kw': 1.0,  # Low current PV
                'current_power_w': 1000
            },
            'house_consumption': {
                'current_power_kw': 1.5,  # Higher consumption
                'current_power_w': 1500
            },
            'weather': {
                'current_conditions': {
                    'cloud_cover': 30  # Low cloud cover
                },
                'forecast': {
                    'cloud_cover': {
                        'total': [25, 20, 15, 10, 5, 0, 0, 0]  # Decreasing cloud cover
                    }
                }
            }
        }
        
        # Mock PV forecast showing increasing trend
        with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production_with_weather') as mock_forecast:
            mock_forecast.return_value = [
                {'forecasted_power_kw': 1.0, 'ghi_w_m2': 400, 'confidence': 0.8, 'timestamp': '2025-09-07T12:00:00'},
                {'forecasted_power_kw': 2.0, 'ghi_w_m2': 600, 'confidence': 0.8, 'timestamp': '2025-09-07T12:15:00'},
                {'forecasted_power_kw': 3.0, 'ghi_w_m2': 800, 'confidence': 0.8, 'timestamp': '2025-09-07T12:30:00'},
                {'forecasted_power_kw': 4.0, 'ghi_w_m2': 1000, 'confidence': 0.8, 'timestamp': '2025-09-07T12:45:00'},
                {'forecasted_power_kw': 5.0, 'ghi_w_m2': 1200, 'confidence': 0.8, 'timestamp': '2025-09-07T13:00:00'},
                {'forecasted_power_kw': 6.0, 'ghi_w_m2': 1400, 'confidence': 0.8, 'timestamp': '2025-09-07T13:15:00'},
                {'forecasted_power_kw': 7.0, 'ghi_w_m2': 1600, 'confidence': 0.8, 'timestamp': '2025-09-07T13:30:00'},
                {'forecasted_power_kw': 8.0, 'ghi_w_m2': 1800, 'confidence': 0.8, 'timestamp': '2025-09-07T13:45:00'}
            ]
            
            decision = self.decision_engine.analyze_and_decide(
                current_data,
                self.mock_price_data,
                []
            )
            
            # Should include weather-aware analysis
            self.assertIn('weather_aware_analysis', decision)
            weather_analysis = decision['weather_aware_analysis']
            
            # Check PV trend analysis
            pv_trend = weather_analysis['pv_trend']
            self.assertEqual(pv_trend['trend_direction'], 'increasing')
            self.assertGreaterEqual(pv_trend['trend_strength'], 0.3)  # More realistic expectation
            self.assertGreater(pv_trend['peak_pv_kw'], pv_trend['current_pv_kw'])
            
            # Check timing recommendation
            timing_rec = weather_analysis['timing_recommendation']
            self.assertTrue(timing_rec['should_wait'])
            self.assertIn('increasing', timing_rec['wait_reason'])
            self.assertGreater(timing_rec['expected_pv_improvement_kw'], 0)
    
    def test_weather_aware_decision_with_decreasing_pv_trend(self):
        """Test decision making when PV production is decreasing"""
        # Scenario: PV production is decreasing, should charge now
        current_data = {
            'battery': {
                'soc_percent': 40,
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_kw': 5.0,  # High current PV
                'current_power_w': 5000
            },
            'house_consumption': {
                'current_power_kw': 1.5,
                'current_power_w': 1500
            },
            'weather': {
                'current_conditions': {
                    'cloud_cover': 20  # Low cloud cover
                },
                'forecast': {
                    'cloud_cover': {
                        'total': [30, 40, 50, 60, 70, 80, 90, 95]  # Increasing cloud cover
                    }
                }
            }
        }
        
        # Mock PV forecast showing decreasing trend
        with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production_with_weather') as mock_forecast:
            mock_forecast.return_value = [
                {'forecasted_power_kw': 5.0, 'ghi_w_m2': 1000, 'confidence': 0.8, 'timestamp': '2025-09-07T12:00:00'},
                {'forecasted_power_kw': 4.0, 'ghi_w_m2': 800, 'confidence': 0.8, 'timestamp': '2025-09-07T12:15:00'},
                {'forecasted_power_kw': 3.0, 'ghi_w_m2': 600, 'confidence': 0.8, 'timestamp': '2025-09-07T12:30:00'},
                {'forecasted_power_kw': 2.0, 'ghi_w_m2': 400, 'confidence': 0.8, 'timestamp': '2025-09-07T12:45:00'},
                {'forecasted_power_kw': 1.0, 'ghi_w_m2': 200, 'confidence': 0.8, 'timestamp': '2025-09-07T13:00:00'},
                {'forecasted_power_kw': 0.5, 'ghi_w_m2': 100, 'confidence': 0.8, 'timestamp': '2025-09-07T13:15:00'},
                {'forecasted_power_kw': 0.2, 'ghi_w_m2': 50, 'confidence': 0.8, 'timestamp': '2025-09-07T13:30:00'},
                {'forecasted_power_kw': 0.1, 'ghi_w_m2': 25, 'confidence': 0.8, 'timestamp': '2025-09-07T13:45:00'}
            ]
            
            decision = self.decision_engine.analyze_and_decide(
                current_data,
                self.mock_price_data,
                []
            )
            
            # Check PV trend analysis
            weather_analysis = decision['weather_aware_analysis']
            pv_trend = weather_analysis['pv_trend']
            self.assertEqual(pv_trend['trend_direction'], 'decreasing')
            self.assertGreaterEqual(pv_trend['trend_strength'], 0.3)  # More realistic expectation
            
            # Check timing recommendation
            timing_rec = weather_analysis['timing_recommendation']
            self.assertFalse(timing_rec['should_wait'])
            self.assertIn('decreasing', timing_rec['wait_reason'])
    
    def test_weather_aware_decision_critical_battery_override(self):
        """Test that critical battery level overrides weather recommendations"""
        # Scenario: Critical battery but PV production increasing
        current_data = {
            'battery': {
                'soc_percent': 18,  # Critical battery level (below 20% threshold)
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_kw': 1.0,
                'current_power_w': 1000
            },
            'house_consumption': {
                'current_power_kw': 1.5,
                'current_power_w': 1500
            },
            'weather': {
                'current_conditions': {
                    'cloud_cover': 30
                },
                'forecast': {
                    'cloud_cover': {
                        'total': [25, 20, 15, 10, 5, 0, 0, 0]  # Decreasing cloud cover
                    }
                }
            }
        }
        
        # Mock PV forecast showing increasing trend
        with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production_with_weather') as mock_forecast:
            mock_forecast.return_value = [
                {'forecasted_power_kw': 1.0, 'ghi_w_m2': 400, 'confidence': 0.8, 'timestamp': '2025-09-07T12:00:00'},
                {'forecasted_power_kw': 2.0, 'ghi_w_m2': 600, 'confidence': 0.8, 'timestamp': '2025-09-07T12:15:00'},
                {'forecasted_power_kw': 3.0, 'ghi_w_m2': 800, 'confidence': 0.8, 'timestamp': '2025-09-07T12:30:00'},
                {'forecasted_power_kw': 4.0, 'ghi_w_m2': 1000, 'confidence': 0.8, 'timestamp': '2025-09-07T12:45:00'}
            ]
            
            decision = self.decision_engine.analyze_and_decide(
                current_data,
                self.mock_price_data,
                []
            )
            
            # Should start charging despite PV trend recommendation to wait
            self.assertEqual(decision['action'], 'start_charging')
            
            # Weather analysis should still show wait recommendation
            weather_analysis = decision['weather_aware_analysis']
            timing_rec = weather_analysis['timing_recommendation']
            self.assertTrue(timing_rec['should_wait'])  # Trend analysis says wait
            # But action overrides due to critical battery
    
    def test_weather_aware_decision_without_weather_data(self):
        """Test decision making when weather data is not available"""
        # Scenario: No weather data, should fall back to normal decision making
        current_data = {
            'battery': {
                'soc_percent': 40,
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_kw': 2.0,
                'current_power_w': 2000
            },
            'house_consumption': {
                'current_power_kw': 1.5,
                'current_power_w': 1500
            }
            # No weather data
        }
        
        # Mock PV forecast without weather data
        with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production_with_weather') as mock_forecast:
            mock_forecast.return_value = [
                {'forecasted_power_kw': 2.0, 'confidence': 0.6, 'timestamp': '2025-09-07T12:00:00'},
                {'forecasted_power_kw': 2.2, 'confidence': 0.6, 'timestamp': '2025-09-07T12:15:00'},
                {'forecasted_power_kw': 2.4, 'confidence': 0.6, 'timestamp': '2025-09-07T12:30:00'},
                {'forecasted_power_kw': 2.6, 'confidence': 0.6, 'timestamp': '2025-09-07T12:45:00'}
            ]
            
            decision = self.decision_engine.analyze_and_decide(
                current_data,
                self.mock_price_data,
                []
            )
            
            # Should still include weather-aware analysis but with lower confidence
            self.assertIn('weather_aware_analysis', decision)
            weather_analysis = decision['weather_aware_analysis']
            
            # PV trend should still be analyzed but with lower confidence
            pv_trend = weather_analysis['pv_trend']
            self.assertLess(pv_trend['confidence'], 0.8)  # Lower confidence without weather data
    
    def test_pv_trend_analyzer_standalone(self):
        """Test PV trend analyzer functionality independently"""
        analyzer = PVTrendAnalyzer(self.config)
        
        # Test data
        current_data = {
            'photovoltaic': {'current_power_kw': 2.0},
            'house_consumption': {'current_power_kw': 1.5}
        }
        
        pv_forecast = [
            {'forecasted_power_kw': 2.0, 'ghi_w_m2': 600, 'confidence': 0.8},
            {'forecasted_power_kw': 3.0, 'ghi_w_m2': 800, 'confidence': 0.8},
            {'forecasted_power_kw': 4.0, 'ghi_w_m2': 1000, 'confidence': 0.8},
            {'forecasted_power_kw': 5.0, 'ghi_w_m2': 1200, 'confidence': 0.8}
        ]
        
        weather_data = {
            'current_conditions': {'cloud_cover': 30},
            'forecast': {'cloud_cover': {'total': [25, 20, 15, 10]}}
        }
        
        # Test trend analysis
        trend_analysis = analyzer.analyze_pv_trend(current_data, pv_forecast, weather_data)
        
        self.assertEqual(trend_analysis.trend_direction, 'increasing')
        self.assertGreaterEqual(trend_analysis.trend_strength, 0.3)  # More realistic expectation
        self.assertGreater(trend_analysis.peak_pv_kw, trend_analysis.current_pv_kw)
        self.assertGreaterEqual(trend_analysis.confidence, 0.3)  # More realistic expectation
        
        # Test timing recommendation
        timing_rec = analyzer.analyze_timing_recommendation(
            trend_analysis, self.mock_price_data, 40, 1.5
        )
        
        self.assertTrue(timing_rec.should_wait)
        self.assertIn('increasing', timing_rec.wait_reason)
        self.assertGreater(timing_rec.expected_pv_improvement_kw, 0)
    
    def test_weather_aware_decision_with_very_low_prices(self):
        """Test that very low prices override wait recommendations"""
        # Scenario: Very low prices but PV production increasing
        current_time = datetime.now()
        current_hour = current_time.hour
        current_minute = (current_time.minute // 15) * 15  # Round to nearest 15 minutes
        current_date = current_time.strftime('%Y-%m-%d')
        
        very_low_price_data = {
            'value': [
                {
                    'dtime': f'{current_date} {current_hour:02d}:{current_minute:02d}',
                    'csdac_pln': 100.0,  # Very low price
                    'business_date': current_date
                }
            ]
        }
        
        current_data = {
            'battery': {
                'soc_percent': 40,
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_kw': 1.0,
                'current_power_w': 1000
            },
            'house_consumption': {
                'current_power_kw': 1.5,
                'current_power_w': 1500
            },
            'weather': {
                'current_conditions': {
                    'cloud_cover': 30
                },
                'forecast': {
                    'cloud_cover': {
                        'total': [25, 20, 15, 10, 5, 0, 0, 0]  # Decreasing cloud cover
                    }
                }
            }
        }
        
        # Mock PV forecast showing increasing trend
        with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production_with_weather') as mock_forecast:
            mock_forecast.return_value = [
                {'forecasted_power_kw': 1.0, 'ghi_w_m2': 400, 'confidence': 0.8, 'timestamp': '2025-09-07T12:00:00'},
                {'forecasted_power_kw': 2.0, 'ghi_w_m2': 600, 'confidence': 0.8, 'timestamp': '2025-09-07T12:15:00'},
                {'forecasted_power_kw': 3.0, 'ghi_w_m2': 800, 'confidence': 0.8, 'timestamp': '2025-09-07T12:30:00'},
                {'forecasted_power_kw': 4.0, 'ghi_w_m2': 1000, 'confidence': 0.8, 'timestamp': '2025-09-07T12:45:00'}
            ]
            
            decision = self.decision_engine.analyze_and_decide(
                current_data,
                very_low_price_data,
                []
            )
            
            # Should charge now despite PV trend due to very low prices
            self.assertEqual(decision['action'], 'start_charging')
            
            # Weather analysis should show wait recommendation but action overrides
            weather_analysis = decision['weather_aware_analysis']
            timing_rec = weather_analysis['timing_recommendation']
            self.assertFalse(timing_rec['should_wait'])  # Overridden by very low prices
            self.assertIn('Very low electricity prices', timing_rec['wait_reason'])


if __name__ == '__main__':
    unittest.main()
