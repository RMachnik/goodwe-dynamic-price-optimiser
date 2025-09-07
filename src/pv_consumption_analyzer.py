#!/usr/bin/env python3
"""
PV vs Consumption Analysis Module
Implements intelligent analysis of PV production vs house consumption for optimal charging decisions

This module provides:
- Real-time power balance monitoring
- Power deficit calculation (consumption - PV)
- Smart charging source selection (PV vs Grid)
- Timing-aware charging decisions
- Weather-enhanced consumption forecasting
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PowerBalance:
    """Represents the power balance analysis"""
    pv_power_w: float
    consumption_power_w: float
    net_power_w: float  # PV - Consumption (positive = excess, negative = deficit)
    battery_power_w: float
    grid_power_w: float
    timestamp: datetime
    confidence: float

@dataclass
class ChargingRecommendation:
    """Represents a charging recommendation based on power balance analysis"""
    should_charge: bool
    charging_source: str  # 'pv', 'grid', 'hybrid', 'none'
    priority: str  # 'critical', 'high', 'medium', 'low'
    reason: str
    estimated_duration_hours: float
    energy_needed_kwh: float
    confidence: float
    pv_available_kwh: float
    grid_needed_kwh: float

class PVConsumptionAnalyzer:
    """Analyzes PV production vs house consumption for optimal charging decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the PV vs consumption analyzer"""
        self.config = config
        
        # System configuration
        self.battery_capacity_kwh = config.get('timing_awareness', {}).get('battery_capacity_kwh', 10.0)
        self.charging_rate_kw = config.get('timing_awareness', {}).get('charging_rate_kw', 3.0)
        self.pv_capacity_kw = config.get('timing_awareness', {}).get('pv_capacity_kw', 10.0)
        
        # Analysis thresholds
        self.pv_overproduction_threshold_w = config.get('pv_consumption_analysis', {}).get('pv_overproduction_threshold_w', 500)
        self.consumption_forecast_hours = config.get('pv_consumption_analysis', {}).get('consumption_forecast_hours', 4)
        self.min_charging_duration_hours = config.get('timing_awareness', {}).get('min_charging_duration_hours', 0.25)
        
        # Night charging strategy configuration
        self.night_charging_enabled = config.get('pv_consumption_analysis', {}).get('night_charging_enabled', True)
        self.night_hours = config.get('pv_consumption_analysis', {}).get('night_hours', [22, 23, 0, 1, 2, 3, 4, 5])  # 10 PM to 6 AM
        self.high_price_threshold_percentile = config.get('pv_consumption_analysis', {}).get('high_price_threshold_percentile', 0.75)  # 75th percentile
        self.poor_pv_threshold_percentile = config.get('pv_consumption_analysis', {}).get('poor_pv_threshold_percentile', 0.25)  # 25th percentile
        self.min_night_charging_soc = config.get('pv_consumption_analysis', {}).get('min_night_charging_soc', 30.0)  # Don't charge if SOC > 30%
        self.max_night_charging_soc = config.get('pv_consumption_analysis', {}).get('max_night_charging_soc', 80.0)  # Charge up to 80% at night
        
        # Historical data for consumption forecasting
        self.consumption_history = []
        self.max_history_days = 7
    
    def analyze_power_balance(self, current_data: Dict[str, Any]) -> PowerBalance:
        """Analyze current power balance between PV, consumption, and battery"""
        try:
            # Extract current power values
            pv_data = current_data.get('photovoltaic', {})
            consumption_data = current_data.get('consumption', {})
            battery_data = current_data.get('battery', {})
            grid_data = current_data.get('grid', {})
            
            # Current power values (in Watts)
            pv_power_w = pv_data.get('current_power_w', 0)
            consumption_power_w = consumption_data.get('current_power_w', 0)
            battery_power_w = battery_data.get('current_power_w', 0)
            grid_power_w = grid_data.get('current_power_w', 0)
            
            # Calculate net power (PV - Consumption)
            net_power_w = pv_power_w - consumption_power_w
            
            # Calculate confidence based on data availability
            confidence = self._calculate_data_confidence(current_data)
            
            power_balance = PowerBalance(
                pv_power_w=pv_power_w,
                consumption_power_w=consumption_power_w,
                net_power_w=net_power_w,
                battery_power_w=battery_power_w,
                grid_power_w=grid_power_w,
                timestamp=datetime.now(),
                confidence=confidence
            )
            
            logger.debug(f"Power balance: PV={pv_power_w}W, Consumption={consumption_power_w}W, Net={net_power_w}W")
            return power_balance
            
        except Exception as e:
            logger.error(f"Failed to analyze power balance: {e}")
            return PowerBalance(0, 0, 0, 0, 0, datetime.now(), 0.0)
    
    def should_charge_from_pv(self, power_balance: PowerBalance, battery_soc: float) -> bool:
        """Determine if we should charge from PV based on power balance"""
        # Don't charge if PV is not producing excess power
        if power_balance.net_power_w < self.pv_overproduction_threshold_w:
            return False
        
        # Don't charge if battery is already full
        if battery_soc >= 95:
            return False
        
        # Charge if we have excess PV and battery needs charging
        return True
    
    def should_charge_from_grid(self, power_balance: PowerBalance, battery_soc: float, 
                               price_data: Dict, weather_data: Optional[Dict] = None) -> bool:
        """Determine if we should charge from grid based on power balance and conditions"""
        # Don't charge if battery is full
        if battery_soc >= 95:
            return False
        
        # Don't charge if we have excess PV (prefer PV charging)
        if power_balance.net_power_w > self.pv_overproduction_threshold_w:
            return False
        
        # Check if we're in a low price window
        if not self._is_low_price_window(price_data):
            return False
        
        # Check weather conditions if available
        if weather_data and not self._is_good_charging_weather(weather_data):
            return False
        
        return True
    
    def analyze_charging_timing(self, power_balance: PowerBalance, battery_soc: float,
                               pv_forecast: List[Dict], price_data: Dict,
                               weather_data: Optional[Dict] = None) -> ChargingRecommendation:
        """Analyze optimal charging timing considering PV forecast and price windows"""
        try:
            # Calculate energy needed
            target_soc = 60.0  # Target SOC percentage
            energy_needed_kwh = (target_soc - battery_soc) / 100 * self.battery_capacity_kwh
            
            if energy_needed_kwh <= 0:
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason='Battery already at target SOC',
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=1.0,
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Analyze PV forecast for next few hours
            pv_available_kwh = self._calculate_pv_availability(pv_forecast, energy_needed_kwh)
            
            # Check if we're in a low price window
            is_low_price = self._is_low_price_window(price_data)
            price_window_duration = self._get_price_window_duration(price_data)
            
            # Determine charging strategy
            if pv_available_kwh >= energy_needed_kwh:
                # PV can handle all charging needs
                return ChargingRecommendation(
                    should_charge=True,
                    charging_source='pv',
                    priority='high',
                    reason='Sufficient PV available for charging',
                    estimated_duration_hours=energy_needed_kwh / (self.charging_rate_kw * 0.8),  # Assume 80% efficiency
                    energy_needed_kwh=energy_needed_kwh,
                    confidence=0.8,
                    pv_available_kwh=pv_available_kwh,
                    grid_needed_kwh=0
                )
            
            elif is_low_price and price_window_duration >= self.min_charging_duration_hours:
                # Low price window - use hybrid charging
                grid_needed_kwh = energy_needed_kwh - pv_available_kwh
                return ChargingRecommendation(
                    should_charge=True,
                    charging_source='hybrid',
                    priority='critical',
                    reason=f'Low price window ({price_window_duration:.1f}h) - hybrid charging to capture savings',
                    estimated_duration_hours=min(price_window_duration, energy_needed_kwh / self.charging_rate_kw),
                    energy_needed_kwh=energy_needed_kwh,
                    confidence=0.9,
                    pv_available_kwh=pv_available_kwh,
                    grid_needed_kwh=grid_needed_kwh
                )
            
            elif pv_available_kwh > 0:
                # Some PV available, but not enough - wait for better conditions
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='pv',
                    priority='medium',
                    reason='Insufficient PV for full charging, waiting for better conditions',
                    estimated_duration_hours=0,
                    energy_needed_kwh=energy_needed_kwh,
                    confidence=0.6,
                    pv_available_kwh=pv_available_kwh,
                    grid_needed_kwh=energy_needed_kwh - pv_available_kwh
                )
            
            else:
                # No PV available, wait for low price or PV
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason='No PV available and not in low price window',
                    estimated_duration_hours=0,
                    energy_needed_kwh=energy_needed_kwh,
                    confidence=0.7,
                    pv_available_kwh=0,
                    grid_needed_kwh=energy_needed_kwh
                )
                
        except Exception as e:
            logger.error(f"Failed to analyze charging timing: {e}")
            return ChargingRecommendation(
                should_charge=False,
                charging_source='none',
                priority='low',
                reason=f'Analysis error: {e}',
                estimated_duration_hours=0,
                energy_needed_kwh=0,
                confidence=0.0,
                pv_available_kwh=0,
                grid_needed_kwh=0
            )
    
    def forecast_consumption(self, hours_ahead: int = 4) -> List[Dict]:
        """Forecast house consumption for next N hours using historical patterns"""
        try:
            if not self.consumption_history:
                logger.warning("No consumption history available for forecasting")
                return []
            
            # Get current time
            current_time = datetime.now()
            forecasts = []
            
            for hour_offset in range(hours_ahead):
                forecast_time = current_time + timedelta(hours=hour_offset)
                forecast_hour = forecast_time.hour
                
                # Calculate average consumption for this hour from historical data
                historical_consumption = self._get_historical_consumption_for_hour(forecast_hour)
                
                forecasts.append({
                    'timestamp': forecast_time.isoformat(),
                    'hour': forecast_hour,
                    'hour_offset': hour_offset,
                    'forecasted_consumption_w': historical_consumption,
                    'confidence': self._calculate_consumption_confidence(),
                    'method': 'historical_average'
                })
            
            logger.debug(f"Generated {len(forecasts)} consumption forecasts")
            return forecasts
            
        except Exception as e:
            logger.error(f"Failed to forecast consumption: {e}")
            return []
    
    def update_consumption_history(self, current_data: Dict[str, Any]):
        """Update consumption history with current data"""
        try:
            consumption_data = current_data.get('consumption', {})
            current_consumption_w = consumption_data.get('current_power_w', 0)
            
            if current_consumption_w > 0:  # Only record positive consumption
                self.consumption_history.append({
                    'timestamp': datetime.now(),
                    'consumption_w': current_consumption_w,
                    'hour': datetime.now().hour
                })
                
                # Keep only last 7 days of data
                cutoff_time = datetime.now() - timedelta(days=self.max_history_days)
                self.consumption_history = [
                    entry for entry in self.consumption_history 
                    if entry['timestamp'] > cutoff_time
                ]
                
        except Exception as e:
            logger.error(f"Failed to update consumption history: {e}")
    
    def _calculate_data_confidence(self, current_data: Dict[str, Any]) -> float:
        """Calculate confidence in current data quality"""
        confidence = 0.0
        
        # Check if we have PV data
        if current_data.get('photovoltaic', {}).get('current_power_w', 0) > 0:
            confidence += 0.3
        
        # Check if we have consumption data
        if current_data.get('consumption', {}).get('current_power_w', 0) > 0:
            confidence += 0.3
        
        # Check if we have battery data
        if current_data.get('battery', {}).get('soc_percent', 0) > 0:
            confidence += 0.2
        
        # Check if we have grid data
        if current_data.get('grid', {}).get('current_power_w', 0) is not None:
            confidence += 0.2
        
        return min(1.0, confidence)
    
    def _is_low_price_window(self, price_data: Dict) -> bool:
        """Check if we're currently in a low price window"""
        try:
            if not price_data or 'value' not in price_data:
                return False
            
            # Get current time and find matching price
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Find the closest price point
            for price_point in price_data['value']:
                price_time = datetime.strptime(price_point['dtime'], '%Y-%m-%d %H:%M')
                if price_time.hour == current_hour and abs(price_time.minute - current_minute) <= 15:
                    # Calculate final price (market + SC component)
                    market_price = float(price_point['csdac_pln'])
                    sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
                    final_price = market_price + (sc_component * 1000)  # Convert to PLN/MWh
                    
                    # Check if price is low (below 25th percentile)
                    all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
                    threshold = sorted(all_prices)[int(len(all_prices) * 0.25)]
                    
                    return final_price <= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check low price window: {e}")
            return False
    
    def _get_price_window_duration(self, price_data: Dict) -> float:
        """Get duration of current low price window in hours"""
        try:
            if not price_data or 'value' not in price_data:
                return 0.0
            
            # Calculate threshold
            sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
            all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
            threshold = sorted(all_prices)[int(len(all_prices) * 0.25)]
            
            # Find current position and count consecutive low prices
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            duration_hours = 0.0
            
            for price_point in price_data['value']:
                price_time = datetime.strptime(price_point['dtime'], '%Y-%m-%d %H:%M')
                if price_time.hour >= current_hour:
                    market_price = float(price_point['csdac_pln'])
                    final_price = market_price + (sc_component * 1000)
                    
                    if final_price <= threshold:
                        duration_hours += 0.25  # 15-minute intervals
                    else:
                        break
            
            return duration_hours
            
        except Exception as e:
            logger.error(f"Failed to get price window duration: {e}")
            return 0.0
    
    def _is_good_charging_weather(self, weather_data: Dict) -> bool:
        """Check if weather conditions are good for charging"""
        try:
            if not weather_data or 'forecast' not in weather_data:
                return True  # Default to good if no weather data
            
            forecast = weather_data['forecast']
            cloud_cover = forecast.get('cloud_cover', {}).get('total', [])
            
            if not cloud_cover:
                return True
            
            # Get current hour's cloud cover
            current_hour = datetime.now().hour
            if current_hour < len(cloud_cover):
                current_cloud_cover = cloud_cover[current_hour]
                # Good charging weather if cloud cover is less than 75%
                return current_cloud_cover < 75
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check weather conditions: {e}")
            return True
    
    def _calculate_pv_availability(self, pv_forecast: List[Dict], energy_needed_kwh: float) -> float:
        """Calculate how much PV energy will be available for charging"""
        try:
            if not pv_forecast:
                return 0.0
            
            total_pv_energy_kwh = 0.0
            
            for forecast in pv_forecast:
                pv_power_kw = forecast.get('forecasted_power_kw', 0)
                # Assume 15-minute intervals, so 0.25 hours per forecast
                pv_energy_kwh = pv_power_kw * 0.25
                total_pv_energy_kwh += pv_energy_kwh
                
                # Stop if we have enough energy
                if total_pv_energy_kwh >= energy_needed_kwh:
                    break
            
            return min(total_pv_energy_kwh, energy_needed_kwh)
            
        except Exception as e:
            logger.error(f"Failed to calculate PV availability: {e}")
            return 0.0
    
    def _get_historical_consumption_for_hour(self, hour: int) -> float:
        """Get average historical consumption for a specific hour"""
        try:
            if not self.consumption_history:
                return 0.0
            
            # Filter data for the specific hour
            hour_data = [entry for entry in self.consumption_history if entry['hour'] == hour]
            
            if not hour_data:
                return 0.0
            
            # Calculate average consumption
            total_consumption = sum(entry['consumption_w'] for entry in hour_data)
            return total_consumption / len(hour_data)
            
        except Exception as e:
            logger.error(f"Failed to get historical consumption for hour {hour}: {e}")
            return 0.0
    
    def _calculate_consumption_confidence(self) -> float:
        """Calculate confidence in consumption forecast"""
        if not self.consumption_history:
            return 0.0
        
        # More data = higher confidence
        data_points = len(self.consumption_history)
        if data_points >= 100:  # 7 days * 24 hours * ~6 data points per hour
            return 0.9
        elif data_points >= 50:
            return 0.7
        elif data_points >= 20:
            return 0.5
        else:
            return 0.3
    
    def analyze_night_charging_strategy(self, battery_soc: float, pv_forecast: List[Dict], 
                                       price_data: Dict, weather_data: Optional[Dict] = None) -> ChargingRecommendation:
        """
        Analyze if we should charge at night for high price day preparation.
        
        Strategy: Charge at night during low prices if:
        1. We're in night hours
        2. Current price is low
        3. Tomorrow's PV forecast is poor
        4. Tomorrow has high price periods
        5. Battery SOC is below threshold
        """
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            
            # Check if we're in night hours
            if not self._is_night_time(current_hour):
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason='Not in night hours for night charging strategy',
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=1.0,
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Check if night charging is enabled
            if not self.night_charging_enabled:
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason='Night charging strategy disabled',
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=1.0,
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Check if battery SOC is too high for night charging
            if battery_soc > self.min_night_charging_soc:
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason=f'Battery SOC ({battery_soc:.1f}%) too high for night charging (max: {self.min_night_charging_soc}%)',
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=1.0,
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Check if current price is low
            if not self._is_low_price_window(price_data):
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason='Current price not low enough for night charging',
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=0.8,
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Analyze tomorrow's conditions
            tomorrow_analysis = self._analyze_tomorrow_conditions(pv_forecast, price_data, weather_data)
            
            if not tomorrow_analysis['should_prepare']:
                return ChargingRecommendation(
                    should_charge=False,
                    charging_source='none',
                    priority='low',
                    reason=tomorrow_analysis['reason'],
                    estimated_duration_hours=0,
                    energy_needed_kwh=0,
                    confidence=tomorrow_analysis['confidence'],
                    pv_available_kwh=0,
                    grid_needed_kwh=0
                )
            
            # Calculate energy needed for night charging
            target_soc = self.max_night_charging_soc
            energy_needed_kwh = (target_soc - battery_soc) / 100 * self.battery_capacity_kwh
            
            # Calculate charging duration
            charging_duration_hours = min(
                energy_needed_kwh / self.charging_rate_kw,
                self._get_remaining_night_hours(current_hour)
            )
            
            return ChargingRecommendation(
                should_charge=True,
                charging_source='grid',
                priority='critical',
                reason=f"Night charging for high price day preparation: {tomorrow_analysis['reason']}",
                estimated_duration_hours=charging_duration_hours,
                energy_needed_kwh=energy_needed_kwh,
                confidence=tomorrow_analysis['confidence'],
                pv_available_kwh=0,
                grid_needed_kwh=energy_needed_kwh
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze night charging strategy: {e}")
            return ChargingRecommendation(
                should_charge=False,
                charging_source='none',
                priority='low',
                reason=f'Night charging analysis error: {e}',
                estimated_duration_hours=0,
                energy_needed_kwh=0,
                confidence=0.0,
                pv_available_kwh=0,
                grid_needed_kwh=0
            )
    
    def analyze_battery_discharge_strategy(self, battery_soc: float, current_data: Dict,
                                          pv_forecast: List[Dict], price_data: Dict) -> Dict[str, Any]:
        """
        Analyze when to discharge battery during high price periods.
        
        Strategy: Discharge battery when:
        1. We're in high price period
        2. PV production is insufficient
        3. Battery has sufficient charge
        4. It's not night time (preserve night charge)
        """
        try:
            current_time = datetime.now()
            current_hour = current_time.hour
            
            # Don't discharge during night hours (preserve night charge)
            if self._is_night_time(current_hour):
                return {
                    'should_discharge': False,
                    'reason': 'Night hours - preserving battery charge',
                    'confidence': 1.0
                }
            
            # Check if we're in high price period
            if not self._is_high_price_window(price_data):
                return {
                    'should_discharge': False,
                    'reason': 'Not in high price period',
                    'confidence': 0.8
                }
            
            # Check if battery has sufficient charge
            if battery_soc < 40.0:  # Don't discharge if battery is low
                return {
                    'should_discharge': False,
                    'reason': f'Battery SOC too low ({battery_soc:.1f}%) for discharge',
                    'confidence': 0.9
                }
            
            # Check if PV production is insufficient
            power_balance = self.analyze_power_balance(current_data)
            if power_balance.net_power_w > 0:  # PV is producing excess
                return {
                    'should_discharge': False,
                    'reason': 'PV producing excess power - no need to discharge battery',
                    'confidence': 0.8
                }
            
            # Calculate discharge power needed
            consumption_power_w = power_balance.consumption_power_w
            pv_power_w = power_balance.pv_power_w
            deficit_power_w = consumption_power_w - pv_power_w
            
            # Only discharge if we have a significant deficit
            if deficit_power_w < 500:  # Less than 500W deficit
                return {
                    'should_discharge': False,
                    'reason': 'Insufficient power deficit for battery discharge',
                    'confidence': 0.7
                }
            
            return {
                'should_discharge': True,
                'discharge_power_w': min(deficit_power_w, self.charging_rate_kw * 1000),  # Max discharge rate
                'reason': f'High price period with {deficit_power_w}W power deficit - discharging battery',
                'confidence': 0.9,
                'estimated_savings_pln': self._calculate_discharge_savings(deficit_power_w, price_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze battery discharge strategy: {e}")
            return {
                'should_discharge': False,
                'reason': f'Discharge analysis error: {e}',
                'confidence': 0.0
            }
    
    def _is_night_time(self, hour: int) -> bool:
        """Check if current hour is in night hours"""
        return hour in self.night_hours
    
    def _is_high_price_window(self, price_data: Dict) -> bool:
        """Check if we're currently in a high price window"""
        try:
            if not price_data or 'value' not in price_data:
                return False
            
            # Get current time and find matching price
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            # Find the closest price point
            for price_point in price_data['value']:
                price_time = datetime.strptime(price_point['dtime'], '%Y-%m-%d %H:%M')
                if price_time.hour == current_hour and abs(price_time.minute - current_minute) <= 15:
                    # Calculate final price (market + SC component)
                    market_price = float(price_point['csdac_pln'])
                    sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
                    final_price = market_price + (sc_component * 1000)  # Convert to PLN/MWh
                    
                    # Check if price is high (above 75th percentile)
                    all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
                    threshold = sorted(all_prices)[int(len(all_prices) * self.high_price_threshold_percentile)]
                    
                    return final_price >= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check high price window: {e}")
            return False
    
    def _analyze_tomorrow_conditions(self, pv_forecast: List[Dict], price_data: Dict, 
                                   weather_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze tomorrow's conditions to determine if night charging is beneficial"""
        try:
            # Analyze PV forecast for tomorrow
            tomorrow_pv_analysis = self._analyze_tomorrow_pv_forecast(pv_forecast)
            
            # Analyze price forecast for tomorrow
            tomorrow_price_analysis = self._analyze_tomorrow_price_forecast(price_data)
            
            # Combine analysis
            should_prepare = (
                tomorrow_pv_analysis['is_poor_pv'] and 
                tomorrow_price_analysis['has_high_prices'] and
                tomorrow_pv_analysis['confidence'] > 0.6 and
                tomorrow_price_analysis['confidence'] > 0.6
            )
            
            if should_prepare:
                reason = f"Poor PV forecast ({tomorrow_pv_analysis['avg_pv_kw']:.1f}kW avg) + high prices ({tomorrow_price_analysis['high_price_hours']}h)"
                confidence = min(tomorrow_pv_analysis['confidence'], tomorrow_price_analysis['confidence'])
            else:
                if not tomorrow_pv_analysis['is_poor_pv']:
                    reason = f"Good PV forecast expected ({tomorrow_pv_analysis['avg_pv_kw']:.1f}kW avg)"
                elif not tomorrow_price_analysis['has_high_prices']:
                    reason = f"Low prices expected tomorrow ({tomorrow_price_analysis['high_price_hours']}h high price hours)"
                else:
                    reason = "Insufficient forecast confidence for night charging"
                confidence = 0.5
            
            return {
                'should_prepare': should_prepare,
                'reason': reason,
                'confidence': confidence,
                'pv_analysis': tomorrow_pv_analysis,
                'price_analysis': tomorrow_price_analysis
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze tomorrow's conditions: {e}")
            return {
                'should_prepare': False,
                'reason': f'Tomorrow analysis error: {e}',
                'confidence': 0.0
            }
    
    def _analyze_tomorrow_pv_forecast(self, pv_forecast: List[Dict]) -> Dict[str, Any]:
        """Analyze tomorrow's PV forecast to determine if it's poor"""
        try:
            if not pv_forecast:
                return {
                    'is_poor_pv': False,
                    'avg_pv_kw': 0.0,
                    'confidence': 0.0,
                    'reason': 'No PV forecast available'
                }
            
            # Calculate average PV power for tomorrow (assuming forecast covers next 24h)
            total_pv_power = 0.0
            valid_forecasts = 0
            
            for forecast in pv_forecast:
                pv_power_kw = forecast.get('forecasted_power_kw', 0)
                if pv_power_kw > 0:
                    total_pv_power += pv_power_kw
                    valid_forecasts += 1
            
            if valid_forecasts == 0:
                return {
                    'is_poor_pv': True,
                    'avg_pv_kw': 0.0,
                    'confidence': 0.8,
                    'reason': 'No PV production forecasted'
                }
            
            avg_pv_kw = total_pv_power / valid_forecasts
            
            # Consider poor PV if average is below 25th percentile of system capacity
            poor_pv_threshold = self.pv_capacity_kw * (self.poor_pv_threshold_percentile / 100)
            is_poor_pv = avg_pv_kw < poor_pv_threshold
            
            confidence = min(0.9, valid_forecasts / 24)  # More forecasts = higher confidence
            
            return {
                'is_poor_pv': is_poor_pv,
                'avg_pv_kw': avg_pv_kw,
                'confidence': confidence,
                'reason': f'Average PV: {avg_pv_kw:.1f}kW (threshold: {poor_pv_threshold:.1f}kW)'
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze tomorrow PV forecast: {e}")
            return {
                'is_poor_pv': False,
                'avg_pv_kw': 0.0,
                'confidence': 0.0,
                'reason': f'PV forecast analysis error: {e}'
            }
    
    def _analyze_tomorrow_price_forecast(self, price_data: Dict) -> Dict[str, Any]:
        """Analyze tomorrow's price forecast to determine if there are high prices"""
        try:
            if not price_data or 'value' not in price_data:
                return {
                    'has_high_prices': False,
                    'high_price_hours': 0,
                    'confidence': 0.0,
                    'reason': 'No price data available'
                }
            
            # Calculate price threshold
            sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
            all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
            high_price_threshold = sorted(all_prices)[int(len(all_prices) * self.high_price_threshold_percentile)]
            
            # Count high price hours for tomorrow (assuming data covers next 24h)
            high_price_hours = 0
            total_hours = 0
            
            current_time = datetime.now()
            tomorrow_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            for price_point in price_data['value']:
                price_time = datetime.strptime(price_point['dtime'], '%Y-%m-%d %H:%M')
                
                # Check if this price point is for tomorrow
                if price_time >= tomorrow_start and price_time < tomorrow_start + timedelta(days=1):
                    market_price = float(price_point['csdac_pln'])
                    final_price = market_price + (sc_component * 1000)
                    
                    if final_price >= high_price_threshold:
                        high_price_hours += 1
                    total_hours += 1
            
            has_high_prices = high_price_hours >= 4  # At least 4 hours of high prices
            
            confidence = min(0.9, total_hours / 24)  # More data = higher confidence
            
            return {
                'has_high_prices': has_high_prices,
                'high_price_hours': high_price_hours,
                'confidence': confidence,
                'reason': f'{high_price_hours} hours of high prices (threshold: {high_price_threshold:.0f} PLN/MWh)'
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze tomorrow price forecast: {e}")
            return {
                'has_high_prices': False,
                'high_price_hours': 0,
                'confidence': 0.0,
                'reason': f'Price forecast analysis error: {e}'
            }
    
    def _get_remaining_night_hours(self, current_hour: int) -> float:
        """Get remaining night hours for charging"""
        try:
            # Find current position in night hours
            if current_hour not in self.night_hours:
                return 0.0
            
            # Calculate remaining night hours
            remaining_hours = 0.0
            for hour in self.night_hours:
                if hour >= current_hour:
                    remaining_hours += 1.0
                elif hour < current_hour and hour < 6:  # Next day's early morning hours
                    remaining_hours += 1.0
            
            return min(remaining_hours, 8.0)  # Max 8 hours of night charging
            
        except Exception as e:
            logger.error(f"Failed to calculate remaining night hours: {e}")
            return 0.0
    
    def _calculate_discharge_savings(self, deficit_power_w: float, price_data: Dict) -> float:
        """Calculate estimated savings from battery discharge during high price period"""
        try:
            if not price_data or 'value' not in price_data:
                return 0.0
            
            # Get current high price
            current_time = datetime.now()
            current_hour = current_time.hour
            current_minute = current_time.minute
            
            for price_point in price_data['value']:
                price_time = datetime.strptime(price_point['dtime'], '%Y-%m-%d %H:%M')
                if price_time.hour == current_hour and abs(price_time.minute - current_minute) <= 15:
                    market_price = float(price_point['csdac_pln'])
                    sc_component = self.config.get('electricity_pricing', {}).get('sc_component_pln_kwh', 0.0892)
                    current_price = market_price + (sc_component * 1000)
                    
                    # Calculate average price for comparison
                    all_prices = [float(p['csdac_pln']) + (sc_component * 1000) for p in price_data['value']]
                    avg_price = sum(all_prices) / len(all_prices)
                    
                    # Calculate savings per kWh
                    savings_per_kwh = (current_price - avg_price) / 1000  # Convert to PLN/kWh
                    
                    # Calculate energy saved (assuming 1 hour of discharge)
                    energy_saved_kwh = (deficit_power_w / 1000) * 1.0  # 1 hour
                    
                    return savings_per_kwh * energy_saved_kwh
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate discharge savings: {e}")
            return 0.0
