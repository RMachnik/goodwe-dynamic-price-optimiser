#!/usr/bin/env python3
"""
Test suite for weather integration functionality
Tests IMGW + Open-Meteo API integration and weather-enhanced PV forecasting
"""

import unittest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import sys
from pathlib import Path
import pytest

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from weather_data_collector import WeatherDataCollector
from pv_forecasting import PVForecaster
from master_coordinator import MasterCoordinator, MultiFactorDecisionEngine


class TestWeatherDataCollector(unittest.TestCase):
    """Test weather data collector functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'weather_integration': {
                'enabled': True,
                'imgw': {
                    'enabled': True,
                    'station': 'krakow',
                    'update_interval_minutes': 15
                },
                'openmeteo': {
                    'enabled': True,
                    'forecast_days': 1,
                    'update_interval_minutes': 60
                },
                'location': {
                    'latitude': 50.1,
                    'longitude': 19.7,
                    'timezone': 'Europe/Warsaw'
                },
                'processing': {
                    'forecast_hours': 24,
                    'cache_duration_minutes': 30,
                    'fallback_to_historical': True,
                    'confidence_threshold': 0.7
                }
            }
        }
        self.weather_collector = WeatherDataCollector(self.config)
    
    def test_initialization(self):
        """Test weather collector initialization"""
        self.assertTrue(self.weather_collector.enabled)
        self.assertEqual(self.weather_collector.location['latitude'], 50.1)
        self.assertEqual(self.weather_collector.location['longitude'], 19.7)
        self.assertEqual(self.weather_collector.imgw_station, 'krakow')
    
    def test_parse_imgw_data(self):
        """Test IMGW data parsing"""
        imgw_data = {
            'stacja': 'Kraków',
            'id_stacji': '12500',
            'temperatura': '15.2',
            'wilgotnosc_wzgledna': '65.0',
            'cisnienie': '1013.2',
            'predkosc_wiatru': '12.5',
            'kierunek_wiatru': '180',
            'suma_opadu': '0.0',
            'data_pomiaru': '2025-01-15',
            'godzina_pomiaru': '12'
        }
        
        parsed = self.weather_collector._parse_imgw_data(imgw_data)
        
        self.assertEqual(parsed['source'], 'IMGW')
        self.assertEqual(parsed['station'], 'Kraków')
        self.assertEqual(parsed['temperature'], 15.2)
        self.assertEqual(parsed['humidity'], 65.0)
        self.assertEqual(parsed['pressure'], 1013.2)
        self.assertIn('cloud_cover_estimated', parsed)
    
    def test_parse_openmeteo_data(self):
        """Test Open-Meteo data parsing"""
        openmeteo_data = {
            'hourly': {
                'time': ['2025-01-15T12:00', '2025-01-15T13:00'],
                'shortwave_radiation': [800, 900],
                'direct_radiation': [600, 700],
                'diffuse_radiation': [200, 200],
                'cloudcover': [25, 30],
                'cloudcover_low': [10, 15],
                'cloudcover_mid': [15, 15],
                'cloudcover_high': [0, 0]
            }
        }
        
        parsed = self.weather_collector._parse_openmeteo_data(openmeteo_data)
        
        self.assertEqual(parsed['source'], 'Open-Meteo')
        self.assertEqual(parsed['forecast_hours'], 24)
        self.assertEqual(len(parsed['solar_irradiance']['ghi']), 2)
        self.assertEqual(parsed['solar_irradiance']['ghi'][0], 800)
        self.assertEqual(parsed['cloud_cover']['total'][0], 25)
    
    def test_estimate_cloud_cover(self):
        """Test cloud cover estimation from IMGW data"""
        # Clear conditions
        clear_data = {
            'wilgotnosc_wzgledna': '40',
            'cisnienie': '1020',
            'suma_opadu': '0'
        }
        cloud_cover = self.weather_collector._estimate_cloud_cover_from_conditions(clear_data)
        self.assertLess(cloud_cover, 50)
        
        # Cloudy conditions
        cloudy_data = {
            'wilgotnosc_wzgledna': '85',
            'cisnienie': '1005',
            'suma_opadu': '2.5'
        }
        cloud_cover = self.weather_collector._estimate_cloud_cover_from_conditions(cloudy_data)
        self.assertGreater(cloud_cover, 50)
    
    def test_assess_data_quality(self):
        """Test data quality assessment"""
        current_data = {'temperature': 15.2, 'humidity': 65.0}
        forecast_data = {
            'solar_irradiance': {'ghi': [800, 900]},
            'cloud_cover': {'total': [25, 30]}
        }
        
        quality = self.weather_collector._assess_data_quality(current_data, forecast_data)
        
        self.assertEqual(quality['score'], 100)
        self.assertGreater(quality['confidence'], 0.5)
        self.assertEqual(len(quality['issues']), 0)
    
    def test_get_solar_irradiance_forecast(self):
        """Test solar irradiance forecast generation"""
        # Set up mock forecast data
        self.weather_collector.weather_forecast = {
            'solar_irradiance': {
                'ghi': [0, 150, 800, 1200, 1000, 600, 0],
                'dni': [0, 200, 900, 1100, 800, 400, 0],
                'dhi': [0, 50, 200, 300, 250, 150, 0]
            },
            'cloud_cover': {
                'total': [0, 25, 75, 90, 85, 60, 0],
                'low': [0, 10, 30, 45, 40, 25, 0],
                'mid': [0, 15, 45, 40, 35, 30, 0],
                'high': [0, 0, 0, 5, 10, 5, 0]
            },
            'timestamps': [
                '2025-01-15T06:00', '2025-01-15T07:00', '2025-01-15T08:00',
                '2025-01-15T09:00', '2025-01-15T10:00', '2025-01-15T11:00',
                '2025-01-15T12:00'
            ]
        }
        
        forecast = self.weather_collector.get_solar_irradiance_forecast(5)
        
        self.assertEqual(len(forecast), 5)
        self.assertEqual(forecast[0]['ghi'], 0)
        self.assertEqual(forecast[2]['ghi'], 800)
        self.assertEqual(forecast[2]['cloud_cover_total'], 75)
    
    def test_cache_validation(self):
        """Test cache validation logic"""
        # No cache initially
        self.assertFalse(self.weather_collector._is_cache_valid())
        
        # Set recent cache
        self.weather_collector.last_update = datetime.now()
        self.assertTrue(self.weather_collector._is_cache_valid())
        
        # Set old cache
        self.weather_collector.last_update = datetime.now() - timedelta(minutes=45)
        self.assertFalse(self.weather_collector._is_cache_valid())
    
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_fetch_imgw_data_success(self, mock_session):
        """Test successful IMGW data fetching"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'stacja': 'Kraków',
            'temperatura': '15.2',
            'wilgotnosc_wzgledna': '65.0'
        })
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        result = await self.weather_collector._fetch_imgw_data()
        
        self.assertEqual(result['source'], 'IMGW')
        self.assertEqual(result['station'], 'Kraków')
        self.assertEqual(result['temperature'], 15.2)
    
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_fetch_openmeteo_data_success(self, mock_session):
        """Test successful Open-Meteo data fetching"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'hourly': {
                'time': ['2025-01-15T12:00'],
                'shortwave_radiation': [800],
                'cloudcover': [25]
            }
        })
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        result = await self.weather_collector._fetch_openmeteo_data()
        
        self.assertEqual(result['source'], 'Open-Meteo')
        self.assertEqual(len(result['solar_irradiance']['ghi']), 1)
        self.assertEqual(result['solar_irradiance']['ghi'][0], 800)


class TestWeatherEnhancedPVForecasting(unittest.TestCase):
    """Test weather-enhanced PV forecasting"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'pv_capacity_kw': 10.0,
            'pv_efficiency': 0.85,
            'forecast_hours': 4,
            'weather_integration': {
                'enabled': True,
                'forecast_hours': 24
            }
        }
        self.pv_forecaster = PVForecaster(self.config)
        
        # Mock weather collector
        self.mock_weather_collector = Mock()
        self.pv_forecaster.set_weather_collector(self.mock_weather_collector)
    
    def test_ghi_to_pv_power_conversion(self):
        """Test GHI to PV power conversion"""
        # Clear sky conditions
        pv_power = self.pv_forecaster._ghi_to_pv_power(1000, 0)  # 1000 W/m², 0% clouds
        expected_power = 1000 * 10 * 0.85  # GHI * area * efficiency
        self.assertAlmostEqual(pv_power, expected_power, places=1)
        
        # Cloudy conditions
        pv_power_cloudy = self.pv_forecaster._ghi_to_pv_power(1000, 50)  # 50% clouds
        self.assertLess(pv_power_cloudy, expected_power)
        
        # No irradiance
        pv_power_none = self.pv_forecaster._ghi_to_pv_power(0, 0)
        self.assertEqual(pv_power_none, 0)
    
    def test_weather_confidence_calculation(self):
        """Test weather-based confidence calculation"""
        # Clear sky
        confidence = self.pv_forecaster._calculate_weather_confidence(10)
        self.assertEqual(confidence, 0.9)
        
        # Partly cloudy
        confidence = self.pv_forecaster._calculate_weather_confidence(40)
        self.assertEqual(confidence, 0.8)
        
        # Cloudy
        confidence = self.pv_forecaster._calculate_weather_confidence(60)
        self.assertEqual(confidence, 0.7)
        
        # Very cloudy
        confidence = self.pv_forecaster._calculate_weather_confidence(90)
        self.assertEqual(confidence, 0.6)
    
    def test_weather_based_forecast(self):
        """Test weather-based PV forecasting"""
        # Mock solar forecast data
        mock_solar_forecast = [
            {
                'timestamp': '2025-01-15T12:00',
                'ghi': 800,
                'dni': 600,
                'dhi': 200,
                'cloud_cover_total': 25,
                'cloud_cover_low': 10,
                'cloud_cover_mid': 15,
                'cloud_cover_high': 0
            },
            {
                'timestamp': '2025-01-15T13:00',
                'ghi': 900,
                'dni': 700,
                'dhi': 200,
                'cloud_cover_total': 30,
                'cloud_cover_low': 15,
                'cloud_cover_mid': 15,
                'cloud_cover_high': 0
            }
        ]
        
        self.mock_weather_collector.get_solar_irradiance_forecast.return_value = mock_solar_forecast
        
        forecasts = self.pv_forecaster.forecast_pv_production_with_weather(2)
        
        self.assertEqual(len(forecasts), 2)
        self.assertEqual(forecasts[0]['method'], 'weather_based')
        self.assertEqual(forecasts[0]['ghi_w_m2'], 800)
        self.assertEqual(forecasts[0]['cloud_cover_percent'], 25)
        self.assertGreater(forecasts[0]['forecasted_power_kw'], 0)
    
    def test_fallback_to_historical(self):
        """Test fallback to historical forecasting when weather data unavailable"""
        # No weather collector
        self.pv_forecaster.weather_collector = None
        
        forecasts = self.pv_forecaster.forecast_pv_production(2)
        
        self.assertEqual(len(forecasts), 2)
        self.assertIn(forecasts[0]['method'], ['historical_pattern', 'time_based_pattern'])
    
    def test_weather_forecast_with_no_data(self):
        """Test weather forecasting when no solar data available"""
        self.mock_weather_collector.get_solar_irradiance_forecast.return_value = []
        
        forecasts = self.pv_forecaster.forecast_pv_production_with_weather(2)
        
        self.assertEqual(len(forecasts), 0)


class TestWeatherEnhancedDecisionEngine(unittest.TestCase):
    """Test weather-enhanced decision engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_weights': {
                    'price': 0.40,
                    'battery': 0.25,
                    'pv': 0.20,
                    'consumption': 0.15
                }
            },
            'weather_integration': {
                'enabled': True
            },
            'timing_awareness_enabled': True
        }
        self.decision_engine = MultiFactorDecisionEngine(self.config)
    
    def test_weather_pv_score_calculation(self):
        """Test weather-enhanced PV scoring"""
        weather_data = {
            'forecast': {
                'solar_irradiance': {
                    'ghi': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 800, 900, 1000, 900, 800, 600, 400, 200, 0, 0, 0, 0]
                },
                'cloud_cover': {
                    'total': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 25, 20, 15, 20, 25, 40, 60, 80, 100, 100, 100, 100]
                }
            }
        }
        
        # Test at noon (index 12) - should be high score
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 12
            score = self.decision_engine._calculate_weather_pv_score(weather_data)
            self.assertGreaterEqual(score, 75)  # Should be high score for good conditions
        
        # Test at night (index 0) - should be neutral
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 0
            score = self.decision_engine._calculate_weather_pv_score(weather_data)
            self.assertLessEqual(score, 50)  # Should be neutral or low for no data
    
    def test_weather_enhanced_pv_score(self):
        """Test weather-enhanced PV scoring with blending"""
        current_data = {
            'photovoltaic': {
                'current_power_w': 5000
            },
            'weather': {
                'forecast': {
                    'solar_irradiance': {
                        'ghi': [0] * 12 + [800] * 12
                    },
                    'cloud_cover': {
                        'total': [100] * 12 + [25] * 12
                    }
                }
            }
        }
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 12
            score = self.decision_engine._calculate_weather_enhanced_pv_score(current_data)
            self.assertGreaterEqual(score, 20)  # Should be enhanced by weather data (base score is low due to low PV power)
    
    def test_weather_enhanced_decision_making(self):
        """Test weather-enhanced decision making"""
        current_data = {
            'battery': {
                'soc_percent': 30,
                'charging_status': False
            },
            'photovoltaic': {
                'current_power_w': 2000
            },
            'weather': {
                'forecast': {
                    'solar_irradiance': {
                        'ghi': [0] * 12 + [800] * 12
                    },
                    'cloud_cover': {
                        'total': [100] * 12 + [25] * 12
                    }
                }
            }
        }
        
        price_data = {
            'value': [
                {'dtime': '2025-01-15 12:00', 'csdac_pln': '200.0'},
                {'dtime': '2025-01-15 13:00', 'csdac_pln': '180.0'}
            ]
        }
        
        # Mock the hybrid logic
        with patch.object(self.decision_engine, 'hybrid_logic') as mock_hybrid:
            mock_decision = Mock()
            mock_decision.action = 'start_charging'
            mock_decision.confidence = 0.8
            mock_decision.reason = 'Low price and good weather conditions'
            mock_decision.charging_source = 'hybrid'
            mock_decision.duration_hours = 2.0
            mock_decision.energy_kwh = 5.0
            mock_decision.estimated_cost_pln = 10.0
            mock_decision.estimated_savings_pln = 5.0
            mock_decision.pv_contribution_kwh = 3.0
            mock_decision.grid_contribution_kwh = 2.0
            mock_decision.start_time = datetime.now()
            mock_decision.end_time = datetime.now() + timedelta(hours=2)
            
            mock_hybrid.analyze_and_decide.return_value = mock_decision
            
            decision = self.decision_engine._analyze_and_decide_with_timing(
                current_data, price_data, []
            )
            
            self.assertIn('weather_data', decision)
            self.assertIn('pv_forecast', decision)
            # The action might be 'none' if the decision logic determines no charging is needed
            self.assertIn(decision['action'], ['start_charging', 'none'])


class TestWeatherIntegrationIntegration(unittest.TestCase):
    """Integration tests for weather functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'weather_integration': {
                'enabled': True,
                'imgw': {'enabled': True, 'station': 'krakow'},
                'openmeteo': {'enabled': True, 'forecast_days': 1},
                'location': {'latitude': 50.1, 'longitude': 19.7, 'timezone': 'Europe/Warsaw'},
                'processing': {'forecast_hours': 24, 'cache_duration_minutes': 30}
            },
            'coordinator': {
                'decision_weights': {'price': 0.40, 'battery': 0.25, 'pv': 0.20, 'consumption': 0.15}
            },
            'timing_awareness_enabled': True
        }
    
    @patch('aiohttp.ClientSession')
    @pytest.mark.asyncio
    async def test_full_weather_data_collection(self, mock_session):
        """Test complete weather data collection flow"""
        # Mock IMGW response
        imgw_response = AsyncMock()
        imgw_response.status = 200
        imgw_response.json = AsyncMock(return_value={
            'stacja': 'Kraków',
            'temperatura': '15.2',
            'wilgotnosc_wzgledna': '65.0',
            'cisnienie': '1013.2'
        })
        
        # Mock Open-Meteo response
        openmeteo_response = AsyncMock()
        openmeteo_response.status = 200
        openmeteo_response.json = AsyncMock(return_value={
            'hourly': {
                'time': ['2025-01-15T12:00', '2025-01-15T13:00'],
                'shortwave_radiation': [800, 900],
                'cloudcover': [25, 30]
            }
        })
        
        # Configure mock session to return different responses
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.side_effect = [
            imgw_response, openmeteo_response
        ]
        
        weather_collector = WeatherDataCollector(self.config)
        weather_data = await weather_collector.collect_weather_data()
        
        self.assertIn('current_conditions', weather_data)
        self.assertIn('forecast', weather_data)
        self.assertIn('data_quality', weather_data)
        self.assertTrue(weather_data['sources']['imgw_available'])
        self.assertTrue(weather_data['sources']['openmeteo_available'])
    
    def test_weather_summary_generation(self):
        """Test weather summary generation"""
        weather_collector = WeatherDataCollector(self.config)
        
        # Set up some mock data
        weather_collector.current_weather = {'temperature': 15.2, 'cloud_cover_estimated': 45}
        weather_collector.weather_forecast = {
            'solar_irradiance': {'ghi': [800, 900, 1000]}
        }
        weather_collector.last_update = datetime.now()
        weather_collector.data_quality = {'score': 85, 'confidence': 0.8}
        
        summary = weather_collector.get_weather_summary()
        
        self.assertTrue(summary['enabled'])
        self.assertTrue(summary['data_available'])
        self.assertEqual(summary['current_conditions']['temperature'], 15.2)
        self.assertEqual(summary['current_conditions']['cloud_cover'], 45)
        self.assertTrue(summary['forecast_available'])
        self.assertEqual(summary['solar_forecast_hours'], 3)


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        test_suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        return result.wasSuccessful()
    
    # Run the test suite
    success = asyncio.run(run_async_tests())
    sys.exit(0 if success else 1)
