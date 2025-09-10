#!/usr/bin/env python3
"""
PV Trend Analyzer Module
Analyzes PV production trends and forecasts to optimize charging decisions

This module provides:
- PV production trend analysis (increasing/decreasing/stable)
- Weather-based PV production predictions
- Smart timing recommendations (wait vs charge now)
- Integration with weather forecasts and price windows
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)

@dataclass
class PVTrendAnalysis:
    """Represents PV trend analysis results"""
    trend_direction: str  # 'increasing', 'decreasing', 'stable'
    trend_strength: float  # 0.0 to 1.0 (how strong the trend is)
    current_pv_kw: float
    forecasted_pv_kw: float  # Average for next 1-2 hours
    peak_pv_kw: float  # Peak production in forecast window
    confidence: float  # Confidence in the trend analysis
    time_to_peak_hours: float  # Hours until peak production
    weather_factor: float  # Weather impact on production (0.0 to 1.0)
    recommendation: str  # 'wait_for_pv', 'charge_now', 'hybrid_approach'

@dataclass
class TimingRecommendation:
    """Represents timing recommendation for charging decisions"""
    should_wait: bool
    wait_reason: str
    estimated_wait_time_hours: float
    expected_pv_improvement_kw: float
    confidence: float
    alternative_action: str  # What to do if not waiting

class PVTrendAnalyzer:
    """Analyzes PV production trends for optimal charging decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the PV trend analyzer"""
        self.config = config
        
        # PV system configuration
        self.pv_capacity_kw = config.get('timing_awareness', {}).get('pv_capacity_kw', 10.0)
        self.charging_rate_kw = config.get('timing_awareness', {}).get('charging_rate_kw', 3.0)
        
        # Trend analysis parameters
        self.forecast_hours = config.get('timing_awareness', {}).get('forecast_hours', 4)
        self.trend_analysis_hours = config.get('weather_aware_decisions', {}).get('trend_analysis_hours', 2)
        self.min_trend_confidence = config.get('weather_aware_decisions', {}).get('min_trend_confidence', 0.6)
        
        # Weather integration
        self.weather_enabled = config.get('weather_integration', {}).get('enabled', True)
        self.weather_impact_threshold = config.get('weather_aware_decisions', {}).get('weather_impact_threshold', 0.3)
        
        # Timing thresholds
        self.max_wait_time_hours = config.get('weather_aware_decisions', {}).get('max_wait_time_hours', 2.0)
        self.min_pv_improvement_kw = config.get('weather_aware_decisions', {}).get('min_pv_improvement_kw', 1.0)
    
    def analyze_pv_trend(self, current_data: Dict[str, Any], pv_forecast: List[Dict], 
                        weather_data: Optional[Dict] = None) -> PVTrendAnalysis:
        """
        Analyze PV production trend and provide recommendations
        
        Args:
            current_data: Current system data
            pv_forecast: PV production forecast
            weather_data: Weather data for enhanced analysis
            
        Returns:
            PVTrendAnalysis with trend information and recommendations
        """
        try:
            logger.info("Analyzing PV production trend")
            
            # Extract current PV production
            current_pv_kw = current_data.get('photovoltaic', {}).get('current_power_kw', 0)
            current_consumption_kw = current_data.get('house_consumption', {}).get('current_power_kw', 0)
            
            # Analyze PV forecast trends
            trend_direction, trend_strength = self._analyze_forecast_trend(pv_forecast)
            
            # Calculate forecasted PV production for next 1-2 hours
            forecasted_pv_kw = self._calculate_forecasted_pv(pv_forecast, self.trend_analysis_hours)
            peak_pv_kw = self._find_peak_pv_production(pv_forecast, self.trend_analysis_hours)
            time_to_peak_hours = self._calculate_time_to_peak(pv_forecast, self.trend_analysis_hours)
            
            # Analyze weather impact
            weather_factor = self._analyze_weather_impact(weather_data, pv_forecast)
            
            # Calculate confidence in trend analysis
            confidence = self._calculate_trend_confidence(pv_forecast, weather_data, trend_strength)
            
            # Generate recommendation
            recommendation = self._generate_trend_recommendation(
                current_pv_kw, forecasted_pv_kw, peak_pv_kw, time_to_peak_hours,
                trend_direction, trend_strength, confidence, weather_factor
            )
            
            return PVTrendAnalysis(
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                current_pv_kw=current_pv_kw,
                forecasted_pv_kw=forecasted_pv_kw,
                peak_pv_kw=peak_pv_kw,
                confidence=confidence,
                time_to_peak_hours=time_to_peak_hours,
                weather_factor=weather_factor,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze PV trend: {e}")
            return PVTrendAnalysis(
                trend_direction='stable',
                trend_strength=0.0,
                current_pv_kw=0.0,
                forecasted_pv_kw=0.0,
                peak_pv_kw=0.0,
                confidence=0.0,
                time_to_peak_hours=0.0,
                weather_factor=0.0,
                recommendation='charge_now'
            )
    
    def analyze_timing_recommendation(self, trend_analysis: PVTrendAnalysis, 
                                    price_data: Dict, battery_soc: float,
                                    current_consumption_kw: float) -> TimingRecommendation:
        """
        Analyze timing recommendation based on PV trend and other factors
        
        Args:
            trend_analysis: PV trend analysis results
            price_data: Current electricity price data
            battery_soc: Current battery state of charge
            current_consumption_kw: Current house consumption
            
        Returns:
            TimingRecommendation with wait/charge decision
        """
        try:
            logger.info("Analyzing timing recommendation based on PV trend")
            
            # Calculate current power balance
            current_net_power = trend_analysis.current_pv_kw - current_consumption_kw
            forecasted_net_power = trend_analysis.forecasted_pv_kw - current_consumption_kw
            
            # Check if we should wait for PV improvement
            should_wait = self._should_wait_for_pv_improvement(
                trend_analysis, current_net_power, forecasted_net_power, 
                price_data, battery_soc
            )
            
            if should_wait:
                wait_reason = self._generate_wait_reason(trend_analysis, current_net_power, forecasted_net_power)
                estimated_wait_time = min(trend_analysis.time_to_peak_hours, self.max_wait_time_hours)
                expected_improvement = max(0, trend_analysis.peak_pv_kw - trend_analysis.current_pv_kw)
                confidence = trend_analysis.confidence
                alternative_action = 'charge_from_grid'
            else:
                wait_reason = self._generate_charge_reason(trend_analysis, current_net_power, price_data, battery_soc)
                estimated_wait_time = 0.0
                expected_improvement = 0.0
                confidence = 1.0 - trend_analysis.confidence  # Higher confidence in not waiting
                alternative_action = 'wait_for_pv'
            
            return TimingRecommendation(
                should_wait=should_wait,
                wait_reason=wait_reason,
                estimated_wait_time_hours=estimated_wait_time,
                expected_pv_improvement_kw=expected_improvement,
                confidence=confidence,
                alternative_action=alternative_action
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze timing recommendation: {e}")
            return TimingRecommendation(
                should_wait=False,
                wait_reason=f'Analysis error: {e}',
                estimated_wait_time_hours=0.0,
                expected_pv_improvement_kw=0.0,
                confidence=0.0,
                alternative_action='charge_now'
            )
    
    def _analyze_forecast_trend(self, pv_forecast: List[Dict]) -> Tuple[str, float]:
        """Analyze the trend direction and strength from PV forecast"""
        if not pv_forecast or len(pv_forecast) < 2:
            return 'stable', 0.0
        
        # Get PV power values for trend analysis
        pv_powers = [forecast.get('forecasted_power_kw', 0) for forecast in pv_forecast[:self.trend_analysis_hours]]
        
        if len(pv_powers) < 2:
            return 'stable', 0.0
        
        # Calculate trend using linear regression slope
        n = len(pv_powers)
        x_values = list(range(n))
        y_values = pv_powers
        
        # Calculate slope (trend direction and strength)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # Determine trend direction and strength
        if slope > 0.1:  # Increasing trend
            trend_direction = 'increasing'
            trend_strength = min(1.0, abs(slope) / 1.0)  # Normalize to 0-1, more sensitive
        elif slope < -0.1:  # Decreasing trend
            trend_direction = 'decreasing'
            trend_strength = min(1.0, abs(slope) / 1.0)  # Normalize to 0-1, more sensitive
        else:  # Stable trend
            trend_direction = 'stable'
            trend_strength = 0.0
        
        return trend_direction, trend_strength
    
    def _calculate_forecasted_pv(self, pv_forecast: List[Dict], hours: int) -> float:
        """Calculate average PV production for next N hours"""
        if not pv_forecast:
            return 0.0
        
        # Get forecasts for the specified number of hours
        relevant_forecasts = pv_forecast[:hours]
        if not relevant_forecasts:
            return 0.0
        
        # Calculate average PV production
        total_pv = sum(forecast.get('forecasted_power_kw', 0) for forecast in relevant_forecasts)
        return total_pv / len(relevant_forecasts)
    
    def _find_peak_pv_production(self, pv_forecast: List[Dict], hours: int) -> float:
        """Find peak PV production in the forecast window"""
        if not pv_forecast:
            return 0.0
        
        # Get forecasts for the specified number of hours
        relevant_forecasts = pv_forecast[:hours]
        if not relevant_forecasts:
            return 0.0
        
        # Find maximum PV production
        return max(forecast.get('forecasted_power_kw', 0) for forecast in relevant_forecasts)
    
    def _calculate_time_to_peak(self, pv_forecast: List[Dict], hours: int) -> float:
        """Calculate time until peak PV production"""
        if not pv_forecast:
            return 0.0
        
        # Get forecasts for the specified number of hours
        relevant_forecasts = pv_forecast[:hours]
        if not relevant_forecasts:
            return 0.0
        
        # Find peak production and its time
        peak_pv = 0.0
        time_to_peak = 0.0
        
        for i, forecast in enumerate(relevant_forecasts):
            pv_power = forecast.get('forecasted_power_kw', 0)
            if pv_power > peak_pv:
                peak_pv = pv_power
                time_to_peak = i * 0.25  # Assuming 15-minute intervals
        
        return time_to_peak
    
    def _analyze_weather_impact(self, weather_data: Optional[Dict], pv_forecast: List[Dict]) -> float:
        """Analyze weather impact on PV production"""
        if not weather_data or not pv_forecast:
            return 0.5  # Neutral impact if no weather data
        
        try:
            # Get current weather conditions
            current_conditions = weather_data.get('current_conditions', {})
            forecast_data = weather_data.get('forecast', {})
            
            # Analyze cloud cover impact
            cloud_cover_impact = self._analyze_cloud_cover_impact(current_conditions, forecast_data)
            
            # Analyze solar irradiance trends
            irradiance_impact = self._analyze_irradiance_trends(pv_forecast)
            
            # Combine weather factors
            weather_factor = (cloud_cover_impact + irradiance_impact) / 2.0
            
            return max(0.0, min(1.0, weather_factor))
            
        except Exception as e:
            logger.error(f"Failed to analyze weather impact: {e}")
            return 0.5
    
    def _analyze_cloud_cover_impact(self, current_conditions: Dict, forecast_data: Dict) -> float:
        """Analyze cloud cover impact on PV production"""
        try:
            # Get current cloud cover
            current_cloud_cover = current_conditions.get('cloud_cover', 50)  # Default 50%
            
            # Get forecast cloud cover
            forecast_cloud_cover = forecast_data.get('cloud_cover', {}).get('total', [])
            
            if not forecast_cloud_cover:
                return 0.5  # Neutral if no forecast data
            
            # Calculate average forecast cloud cover for next 2 hours
            forecast_avg = sum(forecast_cloud_cover[:8]) / min(8, len(forecast_cloud_cover))  # 8 * 15min = 2h
            
            # Calculate impact (lower cloud cover = higher impact factor)
            current_impact = 1.0 - (current_cloud_cover / 100.0)
            forecast_impact = 1.0 - (forecast_avg / 100.0)
            
            # Return improvement factor
            return max(0.0, min(1.0, forecast_impact - current_impact + 0.5))
            
        except Exception as e:
            logger.error(f"Failed to analyze cloud cover impact: {e}")
            return 0.5
    
    def _analyze_irradiance_trends(self, pv_forecast: List[Dict]) -> float:
        """Analyze solar irradiance trends from PV forecast"""
        if not pv_forecast:
            return 0.5
        
        try:
            # Get irradiance values from forecast
            irradiance_values = [forecast.get('ghi_w_m2', 0) for forecast in pv_forecast[:8]]  # Next 2 hours
            
            if len(irradiance_values) < 2:
                return 0.5
            
            # Calculate trend
            current_irradiance = irradiance_values[0]
            avg_forecast_irradiance = sum(irradiance_values[1:]) / (len(irradiance_values) - 1)
            
            # Calculate improvement factor
            if current_irradiance == 0:
                return 0.5  # Neutral if no current irradiance
            
            improvement_factor = avg_forecast_irradiance / current_irradiance
            return max(0.0, min(1.0, improvement_factor))
            
        except Exception as e:
            logger.error(f"Failed to analyze irradiance trends: {e}")
            return 0.5
    
    def _calculate_trend_confidence(self, pv_forecast: List[Dict], weather_data: Optional[Dict], 
                                  trend_strength: float) -> float:
        """Calculate confidence in trend analysis"""
        confidence = 0.5  # Base confidence
        
        # Increase confidence based on trend strength
        confidence += trend_strength * 0.3
        
        # Increase confidence if we have weather data
        if weather_data:
            confidence += 0.2
        
        # Increase confidence based on forecast quality
        if pv_forecast:
            forecast_confidence = statistics.mean([f.get('confidence', 0.5) for f in pv_forecast[:4]])
            confidence += forecast_confidence * 0.2
        
        return max(0.0, min(1.0, confidence))
    
    def _generate_trend_recommendation(self, current_pv_kw: float, forecasted_pv_kw: float,
                                     peak_pv_kw: float, time_to_peak_hours: float,
                                     trend_direction: str, trend_strength: float,
                                     confidence: float, weather_factor: float) -> str:
        """Generate trend-based recommendation"""
        
        # Strong increasing trend with good confidence
        if (trend_direction == 'increasing' and trend_strength > 0.6 and 
            confidence > self.min_trend_confidence and 
            peak_pv_kw > current_pv_kw + self.min_pv_improvement_kw):
            return 'wait_for_pv'
        
        # Strong decreasing trend
        elif (trend_direction == 'decreasing' and trend_strength > 0.6 and 
              confidence > self.min_trend_confidence):
            return 'charge_now'
        
        # Good weather conditions with moderate improvement
        elif (weather_factor > 0.7 and peak_pv_kw > current_pv_kw + self.min_pv_improvement_kw and
              time_to_peak_hours <= self.max_wait_time_hours):
            return 'hybrid_approach'
        
        # Default recommendation
        else:
            return 'charge_now'
    
    def _should_wait_for_pv_improvement(self, trend_analysis: PVTrendAnalysis, 
                                      current_net_power: float, forecasted_net_power: float,
                                      price_data: Dict, battery_soc: float) -> bool:
        """Determine if we should wait for PV improvement"""
        
        # For critical battery levels, still consider PV forecast but with stricter conditions
        if battery_soc <= 12:  # Critical battery threshold (updated from config)
            # Only wait if PV improvement is very significant and very soon
            if (trend_analysis.trend_direction == 'increasing' and 
                trend_analysis.time_to_peak_hours <= 1.0 and  # Must be within 1 hour
                trend_analysis.peak_pv_kw >= 2.0 and  # Must reach at least 2kW
                trend_analysis.confidence >= 0.8):  # High confidence required
                return True
            return False
        
        # Don't wait if we already have significant PV overproduction
        if current_net_power > 1.0:  # 1kW overproduction threshold
            return False
        
        # Don't wait if trend confidence is too low
        if trend_analysis.confidence < self.min_trend_confidence:
            return False
        
        # Don't wait if improvement is too small
        pv_improvement = trend_analysis.peak_pv_kw - trend_analysis.current_pv_kw
        if pv_improvement < self.min_pv_improvement_kw:
            return False
        
        # Don't wait if it takes too long
        if trend_analysis.time_to_peak_hours > self.max_wait_time_hours:
            return False
        
        # Don't wait if we're in a very low price window (charge now)
        if self._is_very_low_price_window(price_data):
            return False
        
        # Wait if we have an increasing trend with reasonable conditions
        if (trend_analysis.trend_direction == 'increasing' and 
            trend_analysis.trend_strength > 0.3 and  # More lenient threshold
            trend_analysis.weather_factor > 0.3):    # More lenient threshold
            return True
        
        return False
    
    def _is_very_low_price_window(self, price_data: Dict) -> bool:
        """Check if we're in a very low price window"""
        try:
            if not price_data or 'value' not in price_data:
                return False
            
            # Get current price
            current_time = datetime.now()
            current_hour = current_time.hour
            
            for price_point in price_data['value']:
                # Handle different timestamp formats
                dtime_str = price_point['dtime']
                try:
                    if 'T' in dtime_str:
                        # ISO format: '2025-09-07T12:00:00'
                        price_time = datetime.fromisoformat(dtime_str)
                    else:
                        # Standard format: '2025-09-07 12:00'
                        price_time = datetime.strptime(dtime_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    # Try alternative formats
                    try:
                        price_time = datetime.strptime(dtime_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        # Skip this price point if we can't parse it
                        continue
                if price_time.hour == current_hour:
                    # Handle both 'csdac_pln' and 'price' field names
                    if 'csdac_pln' in price_point:
                        market_price = float(price_point['csdac_pln'])
                        sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
                        final_price = market_price + (sc_component * 1000)
                        
                        # Very low price threshold (10th percentile)
                        all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
                    else:
                        # For test data with 'price' field
                        final_price = float(price_point['price'])
                        all_prices = [float(p['price']) for p in price_data['value']]
                    
                    very_low_threshold = sorted(all_prices)[int(len(all_prices) * 0.1)]
                    return final_price <= very_low_threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check very low price window: {e}")
            return False
    
    def _generate_wait_reason(self, trend_analysis: PVTrendAnalysis, 
                            current_net_power: float, forecasted_net_power: float) -> str:
        """Generate reason for waiting"""
        pv_improvement = trend_analysis.peak_pv_kw - trend_analysis.current_pv_kw
        
        if trend_analysis.trend_direction == 'increasing':
            return f"PV production increasing by {pv_improvement:.1f}kW in {trend_analysis.time_to_peak_hours:.1f}h"
        elif trend_analysis.weather_factor > 0.7:
            return f"Weather conditions improving, PV will increase by {pv_improvement:.1f}kW"
        else:
            return f"PV production expected to improve by {pv_improvement:.1f}kW"
    
    def _generate_charge_reason(self, trend_analysis: PVTrendAnalysis, 
                              current_net_power: float, price_data: Dict, battery_soc: float) -> str:
        """Generate reason for charging now"""
        if battery_soc <= 20:
            return "Critical battery level - charging immediately"
        elif trend_analysis.trend_direction == 'decreasing':
            return "PV production decreasing - charge now before it gets worse"
        elif self._is_very_low_price_window(price_data):
            return "Very low electricity prices - charge now to capture savings"
        elif current_net_power > 0.5:
            return "PV overproduction - no grid charging needed"
        else:
            return "No significant PV improvement expected - charge now"
