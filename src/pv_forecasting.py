#!/usr/bin/env python3
"""
PV Production Forecasting Module
Provides PV production predictions for timing-aware charging decisions

This module implements PV production forecasting based on:
- Historical PV production patterns
- Current weather conditions
- Time of day patterns
- Seasonal variations
"""

import json
import logging
import statistics
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import math

logger = logging.getLogger(__name__)

class PVForecaster:
    """PV production forecasting for timing-aware charging decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the PV forecaster"""
        self.config = config
        self.data_dir = Path(config.get('data_directory', 'out/energy_data'))
        self.data_dir.mkdir(exist_ok=True)
        
        # PV system configuration
        self.pv_capacity_kw = config.get('pv_capacity_kw', 10.0)  # Default 10kW system
        self.pv_efficiency = config.get('pv_efficiency', 0.85)  # Default 85% efficiency
        
        # Forecasting parameters
        self.forecast_hours = config.get('forecast_hours', 4)  # Forecast next 4 hours
        self.historical_days = config.get('historical_days', 7)  # Use last 7 days for patterns
        
        # Time-based PV production patterns (typical for Polish climate)
        self.hourly_production_factors = {
            6: 0.0,   # 6 AM - No production
            7: 0.1,   # 7 AM - Very low
            8: 0.3,   # 8 AM - Low
            9: 0.5,   # 9 AM - Medium-low
            10: 0.7,  # 10 AM - Medium
            11: 0.8,  # 11 AM - Medium-high
            12: 0.9,  # 12 PM - High
            13: 1.0,  # 1 PM - Peak
            14: 0.9,  # 2 PM - High
            15: 0.8,  # 3 PM - Medium-high
            16: 0.6,  # 4 PM - Medium
            17: 0.4,  # 5 PM - Medium-low
            18: 0.2,  # 6 PM - Low
            19: 0.0,  # 7 PM - No production
            20: 0.0,  # 8 PM - No production
        }
    
    def forecast_pv_production(self, hours_ahead: int = None) -> List[Dict[str, Any]]:
        """
        Forecast PV production for the next N hours
        
        Args:
            hours_ahead: Number of hours to forecast (default: self.forecast_hours)
            
        Returns:
            List of hourly PV production forecasts
        """
        if hours_ahead is None:
            hours_ahead = self.forecast_hours
            
        logger.info(f"Forecasting PV production for next {hours_ahead} hours")
        
        # Get historical data for pattern analysis
        historical_data = self._load_historical_data()
        
        # Get current conditions
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Generate hourly forecasts
        forecasts = []
        for hour_offset in range(hours_ahead):
            forecast_time = current_time + timedelta(hours=hour_offset)
            forecast_hour = forecast_time.hour
            
            # Calculate forecasted production
            forecasted_production = self._calculate_hourly_production(
                forecast_hour, 
                historical_data,
                hour_offset
            )
            
            forecasts.append({
                'timestamp': forecast_time.isoformat(),
                'hour': forecast_hour,
                'hour_offset': hour_offset,
                'forecasted_power_kw': forecasted_production,
                'forecasted_power_w': forecasted_production * 1000,
                'confidence': self._calculate_confidence(hour_offset, historical_data),
                'method': 'historical_pattern' if historical_data else 'time_based_pattern'
            })
        
        logger.info(f"Generated {len(forecasts)} PV production forecasts")
        return forecasts
    
    def _load_historical_data(self) -> List[Dict[str, Any]]:
        """Load historical PV production data for pattern analysis"""
        historical_data = []
        
        try:
            # Look for historical data files
            for days_back in range(1, self.historical_days + 1):
                date = datetime.now() - timedelta(days=days_back)
                date_str = date.strftime('%Y-%m-%d')
                
                # Look for coordinator state files for this date
                pattern = f"coordinator_state_{date_str.replace('-', '')}_*.json"
                data_files = list(Path('out').glob(pattern))
                
                if data_files:
                    # Load the most recent file for this date
                    latest_file = max(data_files, key=lambda f: f.stat().st_mtime)
                    with open(latest_file, 'r') as f:
                        data = json.load(f)
                        
                        if 'current_data' in data and 'photovoltaic' in data['current_data']:
                            pv_data = data['current_data']['photovoltaic']
                            historical_data.append({
                                'date': date_str,
                                'hour': datetime.fromisoformat(data['timestamp']).hour,
                                'power_kw': pv_data.get('current_power_kw', 0),
                                'daily_production_kwh': pv_data.get('daily_production_kwh', 0),
                                'efficiency_percent': pv_data.get('efficiency_percent', 0)
                            })
            
            logger.info(f"Loaded {len(historical_data)} historical PV data points")
            
        except Exception as e:
            logger.warning(f"Failed to load historical data: {e}")
        
        return historical_data
    
    def _calculate_hourly_production(self, hour: int, historical_data: List[Dict], hour_offset: int) -> float:
        """Calculate forecasted PV production for a specific hour"""
        
        # Base production factor from time of day
        base_factor = self.hourly_production_factors.get(hour, 0.0)
        
        # Adjust based on historical data if available
        if historical_data:
            historical_factor = self._get_historical_factor(hour, historical_data)
            # Blend historical and time-based factors
            adjusted_factor = (base_factor * 0.3) + (historical_factor * 0.7)
        else:
            adjusted_factor = base_factor
        
        # Apply seasonal adjustments (simplified)
        seasonal_factor = self._get_seasonal_factor()
        
        # Calculate final production
        forecasted_production = (
            self.pv_capacity_kw * 
            adjusted_factor * 
            seasonal_factor * 
            self.pv_efficiency
        )
        
        # Reduce confidence for further future predictions
        if hour_offset > 2:
            forecasted_production *= (1.0 - (hour_offset - 2) * 0.1)
        
        return max(0.0, min(forecasted_production, self.pv_capacity_kw))
    
    def _get_historical_factor(self, hour: int, historical_data: List[Dict]) -> float:
        """Get historical production factor for a specific hour"""
        hour_data = [d for d in historical_data if d['hour'] == hour]
        
        if not hour_data:
            return 0.0
        
        # Calculate average production factor for this hour
        total_production = sum(d['power_kw'] for d in hour_data)
        avg_production = total_production / len(hour_data)
        
        # Convert to factor (0.0 to 1.0)
        return min(1.0, avg_production / self.pv_capacity_kw)
    
    def _get_seasonal_factor(self) -> float:
        """Get seasonal adjustment factor"""
        month = datetime.now().month
        
        # Simplified seasonal factors for Polish climate
        seasonal_factors = {
            1: 0.3,   # January - Low
            2: 0.4,   # February - Low
            3: 0.6,   # March - Medium-low
            4: 0.8,   # April - Medium-high
            5: 0.9,   # May - High
            6: 1.0,   # June - Peak
            7: 1.0,   # July - Peak
            8: 0.9,   # August - High
            9: 0.7,   # September - Medium-high
            10: 0.5,  # October - Medium-low
            11: 0.3,  # November - Low
            12: 0.2,  # December - Very low
        }
        
        return seasonal_factors.get(month, 0.7)
    
    def _calculate_confidence(self, hour_offset: int, historical_data: List[Dict]) -> float:
        """Calculate confidence level for the forecast"""
        base_confidence = 0.8
        
        # Reduce confidence for further future predictions
        time_penalty = hour_offset * 0.1
        
        # Increase confidence if we have historical data
        data_bonus = 0.2 if historical_data else 0.0
        
        confidence = base_confidence - time_penalty + data_bonus
        return max(0.1, min(1.0, confidence))
    
    def get_current_pv_capacity(self) -> float:
        """Get current PV production capacity"""
        return self.pv_capacity_kw
    
    def estimate_charging_time_with_pv(self, energy_needed_kwh: float, forecasts: List[Dict]) -> Dict[str, Any]:
        """
        Estimate how long it would take to charge using PV production
        
        Args:
            energy_needed_kwh: Energy needed to charge battery (kWh)
            forecasts: PV production forecasts
            
        Returns:
            Dictionary with charging time estimates
        """
        if not forecasts:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'No PV forecasts available'
            }
        
        # Calculate cumulative energy available from PV
        cumulative_energy = 0.0
        hours_to_charge = 0
        
        for forecast in forecasts:
            pv_power_kw = forecast['forecasted_power_kw']
            
            # Assume we can use 80% of PV power for charging (20% for house consumption)
            available_for_charging = pv_power_kw * 0.8
            
            if available_for_charging > 0:
                cumulative_energy += available_for_charging
                hours_to_charge += 1
                
                if cumulative_energy >= energy_needed_kwh:
                    break
        
        if cumulative_energy >= energy_needed_kwh:
            return {
                'can_charge_with_pv': True,
                'estimated_time_hours': hours_to_charge,
                'total_energy_available_kwh': cumulative_energy,
                'reason': f'PV can provide {cumulative_energy:.1f} kWh in {hours_to_charge} hours'
            }
        else:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'total_energy_available_kwh': cumulative_energy,
                'reason': f'PV can only provide {cumulative_energy:.1f} kWh, need {energy_needed_kwh:.1f} kWh'
            }
    
    def save_forecast_data(self, forecasts: List[Dict], filename: str = None):
        """Save forecast data to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"pv_forecast_{timestamp}.json"
        
        filepath = self.data_dir / filename
        
        forecast_data = {
            'timestamp': datetime.now().isoformat(),
            'forecast_hours': len(forecasts),
            'pv_capacity_kw': self.pv_capacity_kw,
            'forecasts': forecasts
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(forecast_data, f, indent=2)
            logger.info(f"Saved PV forecast data to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save forecast data: {e}")


def create_pv_forecaster(config: Dict[str, Any]) -> PVForecaster:
    """Create a PV forecaster instance"""
    return PVForecaster(config)