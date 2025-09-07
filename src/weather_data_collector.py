#!/usr/bin/env python3
"""
Weather Data Collector for GoodWe Enhanced Energy Management System
Integrates IMGW (current conditions) + Open-Meteo (forecasts) for optimal PV forecasting

This module provides:
- Real-time weather conditions from IMGW (official Polish weather service)
- 24-hour weather forecasts from Open-Meteo (solar irradiance + cloud cover)
- Hybrid data collection with fallback mechanisms
- Weather-aware PV production forecasting
"""

import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class WeatherDataCollector:
    """Hybrid weather data collector using IMGW + Open-Meteo APIs"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize weather data collector"""
        self.config = config
        self.weather_config = config.get('weather_integration', {})
        
        # Location configuration (Mników, Małopolska, Poland)
        self.location = {
            'latitude': self.weather_config.get('location', {}).get('latitude', 50.1),
            'longitude': self.weather_config.get('location', {}).get('longitude', 19.7),
            'timezone': self.weather_config.get('location', {}).get('timezone', 'Europe/Warsaw')
        }
        
        # API endpoints
        self.imgw_station = self.weather_config.get('imgw', {}).get('station', 'krakow')
        self.imgw_endpoint = f"https://danepubliczne.imgw.pl/api/data/synop/station/{self.imgw_station}"
        self.openmeteo_endpoint = "https://api.open-meteo.com/v1/forecast"
        
        # Configuration
        self.enabled = self.weather_config.get('enabled', True)
        self.update_interval_minutes = self.weather_config.get('openmeteo', {}).get('update_interval_minutes', 60)
        self.cache_duration_minutes = self.weather_config.get('processing', {}).get('cache_duration_minutes', 30)
        
        # Data cache
        self.current_weather = {}
        self.weather_forecast = {}
        self.last_update = None
        self.data_quality = {}
        
        # Error tracking
        self.imgw_errors = 0
        self.openmeteo_errors = 0
        self.max_errors = 5
        
    async def collect_weather_data(self) -> Dict[str, Any]:
        """Collect comprehensive weather data from both APIs"""
        if not self.enabled:
            logger.info("Weather data collection disabled")
            return {}
        
        try:
            logger.info("Collecting weather data from IMGW and Open-Meteo APIs")
            
            # Check if we have recent cached data
            if self._is_cache_valid():
                logger.debug("Using cached weather data")
                return self._get_cached_data()
            
            # Collect data from both APIs in parallel
            current_task = asyncio.create_task(self._fetch_imgw_data())
            forecast_task = asyncio.create_task(self._fetch_openmeteo_data())
            
            current_data, forecast_data = await asyncio.gather(
                current_task, forecast_task, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(current_data, Exception):
                logger.error(f"IMGW API error: {current_data}")
                current_data = {}
                self.imgw_errors += 1
            
            if isinstance(forecast_data, Exception):
                logger.error(f"Open-Meteo API error: {forecast_data}")
                forecast_data = {}
                self.openmeteo_errors += 1
            
            # Combine data
            weather_data = {
                'current_conditions': current_data,
                'forecast': forecast_data,
                'timestamp': datetime.now().isoformat(),
                'data_quality': self._assess_data_quality(current_data, forecast_data),
                'location': self.location,
                'sources': {
                    'imgw_available': bool(current_data),
                    'openmeteo_available': bool(forecast_data)
                }
            }
            
            # Update cache
            self.current_weather = current_data
            self.weather_forecast = forecast_data
            self.last_update = datetime.now()
            self.data_quality = weather_data['data_quality']
            
            logger.info(f"Weather data collected - IMGW: {bool(current_data)}, Open-Meteo: {bool(forecast_data)}")
            return weather_data
            
        except Exception as e:
            logger.error(f"Failed to collect weather data: {e}")
            return {}
    
    async def _fetch_imgw_data(self) -> Dict[str, Any]:
        """Fetch current weather conditions from IMGW"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(self.imgw_endpoint) as response:
                    if response.status == 200:
                        data = await response.json()
                        parsed_data = self._parse_imgw_data(data)
                        logger.debug(f"IMGW data fetched successfully from station {self.imgw_station}")
                        return parsed_data
                    else:
                        logger.warning(f"IMGW API returned status {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Failed to fetch IMGW data: {e}")
            raise
    
    async def _fetch_openmeteo_data(self) -> Dict[str, Any]:
        """Fetch weather forecast from Open-Meteo"""
        try:
            params = {
                'latitude': self.location['latitude'],
                'longitude': self.location['longitude'],
                'hourly': 'shortwave_radiation,direct_radiation,diffuse_radiation,cloudcover,cloudcover_low,cloudcover_mid,cloudcover_high',
                'forecast_days': 1,  # 1 day forecast for D+1 planning
                'timezone': self.location['timezone']
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(self.openmeteo_endpoint, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        parsed_data = self._parse_openmeteo_data(data)
                        logger.debug(f"Open-Meteo data fetched successfully for {self.location['latitude']}, {self.location['longitude']}")
                        return parsed_data
                    else:
                        logger.warning(f"Open-Meteo API returned status {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"Failed to fetch Open-Meteo data: {e}")
            raise
    
    def _parse_imgw_data(self, data: Dict) -> Dict[str, Any]:
        """Parse IMGW API response"""
        if not data:
            return {}
        
        try:
            return {
                'source': 'IMGW',
                'station': data.get('stacja', 'Unknown'),
                'station_id': data.get('id_stacji', 'Unknown'),
                'temperature': float(data.get('temperatura', 0)),
                'humidity': float(data.get('wilgotnosc_wzgledna', 0)),
                'pressure': float(data.get('cisnienie', 0)),
                'wind_speed': float(data.get('predkosc_wiatru', 0)),
                'wind_direction': float(data.get('kierunek_wiatru', 0)),
                'precipitation': float(data.get('suma_opadu', 0)),
                'cloud_cover_estimated': self._estimate_cloud_cover_from_conditions(data),
                'timestamp': data.get('data_pomiaru', '') + ' ' + data.get('godzina_pomiaru', '00') + ':00'
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing IMGW data: {e}")
            return {}
    
    def _parse_openmeteo_data(self, data: Dict) -> Dict[str, Any]:
        """Parse Open-Meteo API response"""
        if not data or 'hourly' not in data:
            return {}
        
        try:
            hourly = data['hourly']
            
            return {
                'source': 'Open-Meteo',
                'forecast_hours': 24,  # 1 day forecast
                'solar_irradiance': {
                    'ghi': hourly.get('shortwave_radiation', []),  # Global Horizontal Irradiance (W/m²)
                    'dni': hourly.get('direct_radiation', []),     # Direct Normal Irradiance (W/m²)
                    'dhi': hourly.get('diffuse_radiation', [])     # Diffuse Horizontal Irradiance (W/m²)
                },
                'cloud_cover': {
                    'total': hourly.get('cloudcover', []),         # Total cloud cover (%)
                    'low': hourly.get('cloudcover_low', []),       # Low cloud cover (%)
                    'mid': hourly.get('cloudcover_mid', []),       # Mid cloud cover (%)
                    'high': hourly.get('cloudcover_high', [])      # High cloud cover (%)
                },
                'timestamps': hourly.get('time', [])
            }
        except (KeyError, TypeError) as e:
            logger.error(f"Error parsing Open-Meteo data: {e}")
            return {}
    
    def _estimate_cloud_cover_from_conditions(self, imgw_data: Dict) -> float:
        """Estimate cloud cover from IMGW conditions"""
        try:
            humidity = float(imgw_data.get('wilgotnosc_wzgledna', 50))
            pressure = float(imgw_data.get('cisnienie', 1013))
            precipitation = float(imgw_data.get('suma_opadu', 0))
            
            # Basic cloud cover estimation based on meteorological conditions
            cloud_cover = 0
            
            # Precipitation indicates clouds
            if precipitation > 0:
                cloud_cover += 60
            
            # High humidity and low pressure indicate clouds
            if humidity > 80:
                cloud_cover += 30
            elif humidity > 60:
                cloud_cover += 15
            
            if pressure < 1010:
                cloud_cover += 20
            elif pressure < 1015:
                cloud_cover += 10
            
            # Cap at 100%
            return min(100, cloud_cover)
            
        except (ValueError, TypeError):
            return 50  # Default moderate cloud cover
    
    def _assess_data_quality(self, current_data: Dict, forecast_data: Dict) -> Dict[str, Any]:
        """Assess quality of collected weather data"""
        quality_score = 0
        issues = []
        confidence = 0.0
        
        # Check current conditions data
        if current_data:
            quality_score += 50
            if current_data.get('temperature', 0) != 0:
                confidence += 0.3
            if current_data.get('humidity', 0) != 0:
                confidence += 0.2
        else:
            issues.append("No current weather data from IMGW")
        
        # Check forecast data
        if forecast_data:
            quality_score += 50
            solar_data = forecast_data.get('solar_irradiance', {})
            if solar_data.get('ghi') and len(solar_data['ghi']) > 0:
                confidence += 0.3
            if forecast_data.get('cloud_cover', {}).get('total') and len(forecast_data['cloud_cover']['total']) > 0:
                confidence += 0.2
        else:
            issues.append("No forecast data from Open-Meteo")
        
        # Check error rates
        if self.imgw_errors > self.max_errors:
            issues.append(f"IMGW API has {self.imgw_errors} consecutive errors")
            quality_score -= 20
        
        if self.openmeteo_errors > self.max_errors:
            issues.append(f"Open-Meteo API has {self.openmeteo_errors} consecutive errors")
            quality_score -= 20
        
        return {
            'score': max(0, quality_score),
            'confidence': min(1.0, confidence),
            'issues': issues,
            'imgw_errors': self.imgw_errors,
            'openmeteo_errors': self.openmeteo_errors
        }
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self.last_update:
            return False
        
        cache_age = datetime.now() - self.last_update
        return cache_age.total_seconds() < (self.cache_duration_minutes * 60)
    
    def _get_cached_data(self) -> Dict[str, Any]:
        """Get cached weather data"""
        return {
            'current_conditions': self.current_weather,
            'forecast': self.weather_forecast,
            'timestamp': self.last_update.isoformat() if self.last_update else datetime.now().isoformat(),
            'data_quality': self.data_quality,
            'location': self.location,
            'sources': {
                'imgw_available': bool(self.current_weather),
                'openmeteo_available': bool(self.weather_forecast)
            },
            'cached': True
        }
    
    def get_solar_irradiance_forecast(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """Get solar irradiance forecast for next N hours"""
        if not self.weather_forecast or 'solar_irradiance' not in self.weather_forecast:
            logger.warning("No solar irradiance forecast data available")
            return []
        
        solar_data = self.weather_forecast['solar_irradiance']
        timestamps = self.weather_forecast.get('timestamps', [])
        cloud_data = self.weather_forecast.get('cloud_cover', {})
        
        forecast = []
        for i in range(min(hours_ahead, len(timestamps))):
            if i < len(timestamps) and i < len(solar_data['ghi']):
                forecast.append({
                    'timestamp': timestamps[i],
                    'ghi': solar_data['ghi'][i] if i < len(solar_data['ghi']) else 0,  # W/m²
                    'dni': solar_data['dni'][i] if i < len(solar_data['dni']) else 0,  # W/m²
                    'dhi': solar_data['dhi'][i] if i < len(solar_data['dhi']) else 0,  # W/m²
                    'cloud_cover_total': cloud_data['total'][i] if i < len(cloud_data['total']) else 0,
                    'cloud_cover_low': cloud_data['low'][i] if i < len(cloud_data['low']) else 0,
                    'cloud_cover_mid': cloud_data['mid'][i] if i < len(cloud_data['mid']) else 0,
                    'cloud_cover_high': cloud_data['high'][i] if i < len(cloud_data['high']) else 0
                })
        
        logger.debug(f"Generated {len(forecast)} hours of solar irradiance forecast")
        return forecast
    
    def get_current_cloud_cover(self) -> float:
        """Get current cloud cover percentage"""
        if self.current_weather:
            return self.current_weather.get('cloud_cover_estimated', 0)
        return 0
    
    def get_current_temperature(self) -> float:
        """Get current temperature in Celsius"""
        if self.current_weather:
            return self.current_weather.get('temperature', 0)
        return 0
    
    def is_weather_data_available(self) -> bool:
        """Check if weather data is available and of good quality"""
        if not self.enabled:
            return False
        
        if not self._is_cache_valid():
            return False
        
        quality = self.data_quality.get('score', 0)
        return quality >= 50  # At least 50% data quality
    
    def get_weather_summary(self) -> Dict[str, Any]:
        """Get a summary of current weather conditions"""
        summary = {
            'enabled': self.enabled,
            'data_available': self.is_weather_data_available(),
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'data_quality': self.data_quality,
            'current_conditions': {
                'temperature': self.get_current_temperature(),
                'cloud_cover': self.get_current_cloud_cover()
            },
            'forecast_available': bool(self.weather_forecast),
            'solar_forecast_hours': len(self.weather_forecast.get('solar_irradiance', {}).get('ghi', [])) if self.weather_forecast else 0
        }
        
        return summary


def create_weather_collector(config: Dict[str, Any]) -> WeatherDataCollector:
    """Create a weather data collector instance"""
    return WeatherDataCollector(config)
