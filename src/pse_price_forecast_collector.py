#!/usr/bin/env python3
"""
PSE Price Forecast Collector
Collects price forecasts from PSE API (price-fcst endpoint)

This module fetches electricity price forecasts from the Polish Power System Operator (PSE)
to enable earlier and more accurate charging decisions before the daily CSDAC publication at 12:42.
"""

import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)

@dataclass
class PriceForecastPoint:
    """Represents a single price forecast point"""
    time: datetime
    forecasted_price_pln: float  # Forecasted price in PLN/MWh
    confidence: float = 1.0  # Confidence level (0.0-1.0)
    forecast_type: str = 'intraday'  # Type of forecast
    period: str = ''  # OREB period identifier

class PSEPriceForecastCollector:
    """Collects and manages electricity price forecasts from PSE API"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the forecast collector"""
        self.config = config
        
        # Extract PSE price forecast configuration
        forecast_config = config.get('pse_price_forecast', {})
        
        self.enabled = forecast_config.get('enabled', True)
        # Use energy-prices endpoint which includes CSDAC day-ahead forecasts
        # The price-fcst endpoint only has near-real-time historical data
        self.api_url = forecast_config.get('api_url', 'https://api.raporty.pse.pl/api/energy-prices')
        self.update_interval_minutes = forecast_config.get('update_interval_minutes', 60)
        self.forecast_hours_ahead = forecast_config.get('forecast_hours_ahead', 24)
        self.confidence_threshold = forecast_config.get('confidence_threshold', 0.7)
        
        # Decision rules
        decision_rules = forecast_config.get('decision_rules', {})
        self.wait_for_better_price_enabled = decision_rules.get('wait_for_better_price_enabled', True)
        self.min_savings_to_wait_percent = decision_rules.get('min_savings_to_wait_percent', 15)
        self.max_wait_time_hours = decision_rules.get('max_wait_time_hours', 4)
        self.prefer_forecast_over_current = decision_rules.get('prefer_forecast_over_current', True)
        
        # Fallback configuration
        fallback_config = forecast_config.get('fallback', {})
        self.use_csdac_if_unavailable = fallback_config.get('use_csdac_if_unavailable', True)
        self.retry_attempts = fallback_config.get('retry_attempts', 3)
        self.retry_delay_seconds = fallback_config.get('retry_delay_seconds', 60)
        
        # Cache
        self.forecast_cache: List[PriceForecastPoint] = []
        self.last_update_time: Optional[datetime] = None
        self.last_fetch_success: bool = False
        self.consecutive_failures: int = 0
        
        logger.info(f"PSE Price Forecast Collector initialized (enabled: {self.enabled})")
    
    def fetch_price_forecast(self, hours_ahead: int = None) -> List[PriceForecastPoint]:
        """
        Fetch price forecasts from PSE API
        
        Args:
            hours_ahead: Number of hours to forecast (default: from config)
            
        Returns:
            List of PriceForecastPoint objects
        """
        if not self.enabled:
            logger.debug("Price forecast collection is disabled")
            return []
        
        # Check if cache is still valid
        if self._is_cache_valid():
            logger.debug("Using cached forecast data")
            return self.forecast_cache
        
        hours_ahead = hours_ahead or self.forecast_hours_ahead
        
        # Try to fetch new data with retry logic
        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"Fetching price forecast from PSE API (attempt {attempt + 1}/{self.retry_attempts})")
                
                # Build API URL with date filter to get current/future data
                # PSE API defaults to old data without filtering
                # Request data from today onwards to cover current and next days
                today = datetime.now().strftime('%Y-%m-%d')
                
                # Simple filter - API doesn't support $top with $filter
                api_url_with_filter = f"{self.api_url}?$filter=business_date ge '{today}'"
                
                logger.debug(f"API URL: {api_url_with_filter}")
                
                # Fetch data from API
                response = requests.get(api_url_with_filter, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                # Log diagnostic info about received data
                raw_count = len(data.get('value', []))
                if raw_count > 0:
                    first_date = data['value'][0].get('dtime', 'unknown')
                    last_date = data['value'][-1].get('dtime', 'unknown')
                    logger.debug(f"Received {raw_count} raw records from API (dates: {first_date} to {last_date})")
                else:
                    logger.warning("API returned empty data set")
                
                forecast_points = self._parse_forecast_data(data, hours_ahead)
                
                if forecast_points:
                    # Update cache
                    self.forecast_cache = forecast_points
                    self.last_update_time = datetime.now()
                    self.last_fetch_success = True
                    self.consecutive_failures = 0
                    
                    logger.info(f"Successfully fetched {len(forecast_points)} forecast points")
                    return forecast_points
                else:
                    if raw_count > 0:
                        logger.warning(f"API returned {raw_count} records but none were future forecasts within {hours_ahead}h window")
                    else:
                        logger.warning("No forecast data received from API (empty response)")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to fetch forecast data (attempt {attempt + 1}): {e}")
                self.consecutive_failures += 1
                
                if attempt < self.retry_attempts - 1:
                    logger.info(f"Retrying in {self.retry_delay_seconds} seconds...")
                    time.sleep(self.retry_delay_seconds)
            except Exception as e:
                logger.error(f"Unexpected error fetching forecast: {e}")
                self.consecutive_failures += 1
                break
        
        # All attempts failed
        self.last_fetch_success = False
        logger.warning(f"Failed to fetch forecast after {self.retry_attempts} attempts")
        
        # Return cached data if available
        if self.forecast_cache:
            logger.info("Using stale cached forecast data as fallback")
            return self.forecast_cache
        
        return []
    
    def _parse_forecast_data(self, data: Dict, hours_ahead: int) -> List[PriceForecastPoint]:
        """
        Parse forecast data from PSE API response
        
        Args:
            data: API response data
            hours_ahead: Number of hours to include in forecast
            
        Returns:
            List of PriceForecastPoint objects
        """
        forecast_points = []
        current_time = datetime.now()
        cutoff_time = current_time + timedelta(hours=hours_ahead)
        
        # Statistics for logging
        total_records = 0
        past_records = 0
        beyond_window_records = 0
        parse_errors = 0
        
        try:
            # PSE API returns data in 'value' field
            for item in data.get('value', []):
                total_records += 1
                
                # Parse timestamp (format: "2024-06-14 00:15:00")
                time_str = item.get('dtime')
                if not time_str:
                    parse_errors += 1
                    continue
                
                # Handle different timestamp formats
                try:
                    if ':' in time_str and time_str.count(':') == 2:
                        # Format: "2024-06-14 00:15:00"
                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Format: "2025-10-14 14:00"
                        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                except ValueError as e:
                    logger.error(f"Error parsing timestamp '{time_str}': {e}")
                    parse_errors += 1
                    continue
                
                # Only include forecasts within the time window
                # Allow a small lookback (30 minutes) to account for publication delays
                # PSE publishes forecasts with a delay, so recent past forecasts are still useful
                lookback_minutes = 30
                earliest_time = current_time - timedelta(minutes=lookback_minutes)
                
                if dt < earliest_time:
                    past_records += 1
                    continue
                if dt > cutoff_time:
                    beyond_window_records += 1
                    continue
                
                # Extract forecasted price
                # For energy-prices endpoint, try CSDAC first (day-ahead price), then CEN
                forecasted_price = item.get('csdac_pln') or item.get('cen_cost')
                if forecasted_price is None:
                    continue
                
                forecasted_price = float(forecasted_price)
                period = item.get('period', '')
                
                # Determine forecast type based on available data
                forecast_type = 'day_ahead' if item.get('csdac_pln') is not None else 'intraday'
                
                # Create forecast point
                forecast_point = PriceForecastPoint(
                    time=dt,
                    forecasted_price_pln=forecasted_price,
                    confidence=1.0,  # PSE forecasts are considered high confidence
                    forecast_type=forecast_type,
                    period=period
                )
                
                forecast_points.append(forecast_point)
            
            # Sort by time
            forecast_points.sort(key=lambda x: x.time)
            
            # Log parsing statistics
            logger.info(f"Parsed {len(forecast_points)} usable forecast points from {total_records} total records")
            if past_records > 0 or beyond_window_records > 0 or parse_errors > 0:
                logger.debug(f"Filtering stats: {past_records} past, {beyond_window_records} beyond {hours_ahead}h window, {parse_errors} parse errors")
            
        except Exception as e:
            logger.error(f"Error parsing forecast data: {e}")
            return []
        
        return forecast_points
    
    def get_forecast_for_time(self, target_time: datetime) -> Optional[float]:
        """
        Get forecasted price for a specific time
        
        Args:
            target_time: Target datetime
            
        Returns:
            Forecasted price in PLN/MWh or None if not available
        """
        if not self.forecast_cache:
            return None
        
        # Find closest forecast point
        closest_point = None
        min_time_diff = timedelta(hours=999)
        
        for point in self.forecast_cache:
            time_diff = abs(point.time - target_time)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_point = point
        
        # Only return if within 30 minutes of target time
        if closest_point and min_time_diff <= timedelta(minutes=30):
            return closest_point.forecasted_price_pln
        
        return None
    
    def is_forecast_available(self) -> bool:
        """
        Check if forecast data is available
        
        Returns:
            True if forecast data is available and valid
        """
        return bool(self.forecast_cache) and self._is_cache_valid()
    
    def get_forecast_confidence(self) -> float:
        """
        Get overall confidence level of current forecasts
        
        Returns:
            Confidence level (0.0-1.0)
        """
        if not self.forecast_cache:
            return 0.0
        
        # Base confidence on data freshness and success rate
        freshness_factor = 1.0
        if self.last_update_time:
            age_minutes = (datetime.now() - self.last_update_time).total_seconds() / 60
            freshness_factor = max(0.0, 1.0 - (age_minutes / (self.update_interval_minutes * 2)))
        
        # Reduce confidence based on consecutive failures
        failure_factor = max(0.0, 1.0 - (self.consecutive_failures * 0.2))
        
        return min(1.0, freshness_factor * failure_factor)
    
    def should_wait_for_better_price(self, current_price: float, current_time: datetime = None) -> Dict[str, Any]:
        """
        Determine if we should wait for a better price based on forecasts
        
        Args:
            current_price: Current electricity price in PLN/MWh
            current_time: Current time (default: now)
            
        Returns:
            Dictionary with decision and reasoning
        """
        if not self.wait_for_better_price_enabled:
            return {
                'should_wait': False,
                'reason': 'Wait for better price feature is disabled',
                'better_price_time': None,
                'expected_savings_percent': 0.0
            }
        
        if not self.is_forecast_available():
            return {
                'should_wait': False,
                'reason': 'No forecast data available',
                'better_price_time': None,
                'expected_savings_percent': 0.0
            }
        
        current_time = current_time or datetime.now()
        max_wait_time = current_time + timedelta(hours=self.max_wait_time_hours)
        
        # Find the best price within the wait window
        best_price = None
        best_price_time = None
        
        for point in self.forecast_cache:
            if current_time < point.time <= max_wait_time:
                if best_price is None or point.forecasted_price_pln < best_price:
                    best_price = point.forecasted_price_pln
                    best_price_time = point.time
        
        if best_price is None:
            return {
                'should_wait': False,
                'reason': 'No forecast data within wait window',
                'better_price_time': None,
                'expected_savings_percent': 0.0
            }
        
        # Calculate potential savings
        # Guard against division by zero or non-positive current price
        if current_price is None or current_price <= 0:
            return {
                'should_wait': False,
                'reason': 'Invalid or non-positive current price; cannot compute savings',
                'better_price_time': best_price_time,
                'expected_savings_percent': 0.0,
                'current_price': current_price,
                'forecasted_price': best_price
            }

        savings_percent = ((current_price - best_price) / current_price) * 100
        
        if savings_percent >= self.min_savings_to_wait_percent:
            wait_hours = (best_price_time - current_time).total_seconds() / 3600
            return {
                'should_wait': True,
                'reason': f'Better price expected in {wait_hours:.1f}h (savings: {savings_percent:.1f}%)',
                'better_price_time': best_price_time,
                'expected_savings_percent': savings_percent,
                'current_price': current_price,
                'forecasted_price': best_price,
                'wait_hours': wait_hours
            }
        
        return {
            'should_wait': False,
            'reason': f'Potential savings ({savings_percent:.1f}%) below threshold ({self.min_savings_to_wait_percent}%)',
            'better_price_time': best_price_time,
            'expected_savings_percent': savings_percent,
            'current_price': current_price,
            'forecasted_price': best_price
        }
    
    def get_forecast_statistics(self) -> Dict[str, Any]:
        """
        Get statistical summary of current forecasts
        
        Returns:
            Dictionary with forecast statistics
        """
        if not self.forecast_cache:
            return {
                'available': False,
                'count': 0
            }
        
        prices = [p.forecasted_price_pln for p in self.forecast_cache]
        
        return {
            'available': True,
            'count': len(self.forecast_cache),
            'min_price': min(prices),
            'max_price': max(prices),
            'avg_price': statistics.mean(prices),
            'median_price': statistics.median(prices),
            'time_range': {
                'start': self.forecast_cache[0].time.isoformat(),
                'end': self.forecast_cache[-1].time.isoformat()
            },
            'confidence': self.get_forecast_confidence(),
            'last_update': self.last_update_time.isoformat() if self.last_update_time else None,
            'consecutive_failures': self.consecutive_failures
        }
    
    def _is_cache_valid(self) -> bool:
        """
        Check if cached forecast data is still valid
        
        Returns:
            True if cache is valid
        """
        if not self.forecast_cache or not self.last_update_time:
            return False
        
        age_minutes = (datetime.now() - self.last_update_time).total_seconds() / 60
        return age_minutes < self.update_interval_minutes
    
    def clear_cache(self):
        """Clear cached forecast data"""
        self.forecast_cache = []
        self.last_update_time = None
        logger.info("Forecast cache cleared")

