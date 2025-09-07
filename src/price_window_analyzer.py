#!/usr/bin/env python3
"""
Price Window Analysis Module
Analyzes electricity price windows for optimal charging timing

This module implements price window analysis to identify:
- Low price windows and their duration
- Optimal charging windows
- Price trend analysis
- Timing-aware charging decisions
"""

import json
import logging
import statistics
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PriceWindow:
    """Represents a price window with timing information"""
    start_time: datetime
    end_time: datetime
    duration_hours: float
    avg_price_pln: float
    min_price_pln: float
    max_price_pln: float
    price_category: str  # 'very_low', 'low', 'medium', 'high', 'very_high'
    savings_potential_pln: float

class PriceWindowAnalyzer:
    """Analyzes electricity price windows for optimal charging timing"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the price window analyzer"""
        self.config = config
        
        # Price thresholds (PLN/MWh)
        self.price_thresholds = {
            'very_low': config.get('very_low_price_threshold', 150.0),
            'low': config.get('low_price_threshold', 250.0),
            'medium': config.get('medium_price_threshold', 400.0),
            'high': config.get('high_price_threshold', 600.0),
            'very_high': config.get('very_high_price_threshold', 800.0)
        }
        
        # Charging parameters
        self.min_charging_duration_hours = config.get('min_charging_duration_hours', 0.25)  # 15 minutes
        self.max_charging_duration_hours = config.get('max_charging_duration_hours', 4.0)   # 4 hours
        self.min_savings_threshold_pln = config.get('min_savings_threshold_pln', 50.0)     # 50 PLN/MWh savings
        
        # Reference price for savings calculation
        self.reference_price_pln = config.get('reference_price_pln', 400.0)  # Average market price
    
    def analyze_price_windows(self, price_data: Dict[str, Any]) -> List[PriceWindow]:
        """
        Analyze price data to identify optimal charging windows
        
        Args:
            price_data: Price data from Polish electricity API
            
        Returns:
            List of PriceWindow objects sorted by savings potential
        """
        logger.info("Analyzing price windows for optimal charging")
        
        if not price_data or 'value' not in price_data:
            logger.warning("No price data available for analysis")
            return []
        
        # Get current time and find current price
        current_time = datetime.now()
        current_price = self._get_current_price(price_data, current_time)
        
        if current_price is None:
            logger.warning("Could not determine current price")
            return []
        
        # Find all low price windows
        windows = self._find_low_price_windows(price_data, current_time)
        
        # Calculate savings potential for each window
        for window in windows:
            window.savings_potential_pln = self._calculate_savings_potential(window)
        
        # Sort by savings potential (highest first)
        windows.sort(key=lambda w: w.savings_potential_pln, reverse=True)
        
        logger.info(f"Found {len(windows)} price windows for analysis")
        return windows
    
    def _get_current_price(self, price_data: Dict[str, Any], current_time: datetime) -> Optional[float]:
        """Get current electricity price"""
        try:
            for item in price_data['value']:
                item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                
                # Check if current time falls within this 15-minute period
                if item_time <= current_time < item_time + timedelta(minutes=15):
                    market_price = float(item['csdac_pln'])
                    # Add SC component (0.0892 PLN/kWh)
                    final_price = market_price + 0.0892
                    return final_price
            
            logger.warning("Current time not found in price data")
            return None
            
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return None
    
    def _find_low_price_windows(self, price_data: Dict[str, Any], current_time: datetime) -> List[PriceWindow]:
        """Find all low price windows in the price data"""
        windows = []
        
        try:
            # Convert price data to list of (time, price) tuples
            price_points = []
            for item in price_data['value']:
                item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                market_price = float(item['csdac_pln'])
                final_price = market_price + 0.0892  # Add SC component
                price_points.append((item_time, final_price))
            
            # Sort by time
            price_points.sort(key=lambda x: x[0])
            
            # Find continuous low price periods
            current_window_start = None
            current_window_prices = []
            
            for item_time, price in price_points:
                # Skip past prices
                if item_time < current_time:
                    continue
                
                # Check if this is a low price
                if price <= self.price_thresholds['low']:
                    if current_window_start is None:
                        current_window_start = item_time
                    current_window_prices.append(price)
                else:
                    # End of low price window
                    if current_window_start is not None and len(current_window_prices) > 0:
                        window = self._create_price_window(
                            current_window_start,
                            item_time,
                            current_window_prices
                        )
                        if window:
                            windows.append(window)
                    
                    current_window_start = None
                    current_window_prices = []
            
            # Handle case where low price window extends to end of data
            if current_window_start is not None and len(current_window_prices) > 0:
                window = self._create_price_window(
                    current_window_start,
                    price_points[-1][0] + timedelta(minutes=15),
                    current_window_prices
                )
                if window:
                    windows.append(window)
        
        except Exception as e:
            logger.error(f"Error finding low price windows: {e}")
        
        return windows
    
    def _create_price_window(self, start_time: datetime, end_time: datetime, prices: List[float]) -> Optional[PriceWindow]:
        """Create a PriceWindow object from timing and price data"""
        try:
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Skip windows that are too short
            if duration_hours < self.min_charging_duration_hours:
                return None
            
            avg_price = statistics.mean(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            # Determine price category
            if avg_price <= self.price_thresholds['very_low']:
                category = 'very_low'
            elif avg_price <= self.price_thresholds['low']:
                category = 'low'
            elif avg_price <= self.price_thresholds['medium']:
                category = 'medium'
            elif avg_price <= self.price_thresholds['high']:
                category = 'high'
            else:
                category = 'very_high'
            
            return PriceWindow(
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                avg_price_pln=avg_price,
                min_price_pln=min_price,
                max_price_pln=max_price,
                price_category=category,
                savings_potential_pln=0.0  # Will be calculated later
            )
        
        except Exception as e:
            logger.error(f"Error creating price window: {e}")
            return None
    
    def _calculate_savings_potential(self, window: PriceWindow) -> float:
        """Calculate savings potential for a price window"""
        # Calculate savings per MWh compared to reference price
        savings_per_mwh = self.reference_price_pln - window.avg_price_pln
        
        # Weight by duration (longer windows are more valuable)
        duration_weight = min(1.0, window.duration_hours / 2.0)  # Cap at 2 hours
        
        # Weight by price category (very low prices are more valuable)
        category_weights = {
            'very_low': 1.5,
            'low': 1.2,
            'medium': 1.0,
            'high': 0.8,
            'very_high': 0.5
        }
        category_weight = category_weights.get(window.price_category, 1.0)
        
        # Calculate total savings potential
        total_savings = savings_per_mwh * duration_weight * category_weight
        
        return max(0.0, total_savings)
    
    def get_optimal_charging_window(self, price_data: Dict[str, Any], energy_needed_kwh: float) -> Optional[PriceWindow]:
        """
        Get the optimal charging window for a given energy requirement
        
        Args:
            price_data: Price data from Polish electricity API
            energy_needed_kwh: Energy needed to charge battery (kWh)
            
        Returns:
            Optimal PriceWindow or None if no suitable window found
        """
        logger.info(f"Finding optimal charging window for {energy_needed_kwh:.1f} kWh")
        
        # Analyze all price windows
        windows = self.analyze_price_windows(price_data)
        
        if not windows:
            logger.warning("No price windows found")
            return None
        
        # Estimate charging time needed
        charging_rate_kw = self.config.get('charging_rate_kw', 3.0)  # Default 3kW charging
        charging_time_hours = energy_needed_kwh / charging_rate_kw
        
        logger.info(f"Estimated charging time: {charging_time_hours:.1f} hours")
        
        # Find the best window that can accommodate the charging time
        for window in windows:
            # Check if window is long enough for charging
            if window.duration_hours >= charging_time_hours:
                # Check if savings are significant
                if window.savings_potential_pln >= self.min_savings_threshold_pln:
                    logger.info(f"Found optimal window: {window.start_time.strftime('%H:%M')} - {window.end_time.strftime('%H:%M')}, "
                              f"duration: {window.duration_hours:.1f}h, savings: {window.savings_potential_pln:.1f} PLN/MWh")
                    return window
        
        # If no window is long enough, find the best available window
        if windows:
            best_window = windows[0]
            logger.info(f"No window long enough for full charging, using best available: "
                      f"{best_window.start_time.strftime('%H:%M')} - {best_window.end_time.strftime('%H:%M')}")
            return best_window
        
        logger.warning("No suitable charging window found")
        return None
    
    def analyze_timing_vs_price(self, price_data: Dict[str, Any], pv_forecasts: List[Dict], 
                               energy_needed_kwh: float) -> Dict[str, Any]:
        """
        Analyze timing vs price to determine optimal charging strategy
        
        Args:
            price_data: Price data from Polish electricity API
            pv_forecasts: PV production forecasts
            energy_needed_kwh: Energy needed to charge battery (kWh)
            
        Returns:
            Dictionary with timing analysis and recommendations
        """
        logger.info("Analyzing timing vs price for optimal charging strategy")
        
        # Get optimal price window
        optimal_window = self.get_optimal_charging_window(price_data, energy_needed_kwh)
        
        if not optimal_window:
            return {
                'recommendation': 'wait',
                'reason': 'No suitable price window found',
                'optimal_window': None,
                'pv_timing': None,
                'hybrid_recommended': False
            }
        
        # Analyze PV timing
        pv_timing = self._analyze_pv_timing(pv_forecasts, energy_needed_kwh, optimal_window)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(optimal_window, pv_timing)
        
        return {
            'recommendation': recommendation,
            'reason': self._get_recommendation_reason(recommendation, optimal_window, pv_timing),
            'optimal_window': {
                'start_time': optimal_window.start_time.isoformat(),
                'end_time': optimal_window.end_time.isoformat(),
                'duration_hours': optimal_window.duration_hours,
                'avg_price_pln': optimal_window.avg_price_pln,
                'savings_potential_pln': optimal_window.savings_potential_pln
            },
            'pv_timing': pv_timing,
            'hybrid_recommended': recommendation == 'hybrid_charging'
        }
    
    def _analyze_pv_timing(self, pv_forecasts: List[Dict], energy_needed_kwh: float, 
                          optimal_window: PriceWindow) -> Dict[str, Any]:
        """Analyze PV timing relative to optimal price window"""
        if not pv_forecasts:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'No PV forecasts available'
            }
        
        # Calculate PV charging time
        charging_rate_kw = self.config.get('charging_rate_kw', 3.0)
        charging_time_hours = energy_needed_kwh / charging_rate_kw
        
        # Check if PV can complete charging within the optimal window
        window_start = optimal_window.start_time
        window_end = optimal_window.end_time
        
        # Find PV production during the optimal window
        pv_during_window = []
        for forecast in pv_forecasts:
            forecast_time = datetime.fromisoformat(forecast['timestamp'])
            if window_start <= forecast_time < window_end:
                pv_during_window.append(forecast['forecasted_power_kw'])
        
        if not pv_during_window:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'No PV production during optimal price window'
            }
        
        # Calculate if PV can complete charging in time
        avg_pv_power = statistics.mean(pv_during_window)
        available_for_charging = avg_pv_power * 0.8  # 80% for charging, 20% for house
        
        if available_for_charging > 0:
            pv_charging_time = energy_needed_kwh / available_for_charging
            can_complete_in_time = pv_charging_time <= optimal_window.duration_hours
            
            return {
                'can_charge_with_pv': can_complete_in_time,
                'estimated_time_hours': pv_charging_time,
                'avg_pv_power_kw': avg_pv_power,
                'available_for_charging_kw': available_for_charging,
                'reason': f'PV can provide {available_for_charging:.1f} kW, charging time: {pv_charging_time:.1f}h'
            }
        else:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'Insufficient PV production during optimal window'
            }
    
    def _determine_recommendation(self, optimal_window: PriceWindow, pv_timing: Dict[str, Any]) -> str:
        """Determine the optimal charging recommendation"""
        
        # If PV can complete charging in time, prefer PV
        if pv_timing.get('can_charge_with_pv', False):
            return 'pv_charging'
        
        # If price window is very good and PV timing is insufficient, recommend hybrid
        if optimal_window.savings_potential_pln > self.min_savings_threshold_pln * 1.5:
            return 'hybrid_charging'
        
        # If price window is good but not great, wait for better conditions
        if optimal_window.savings_potential_pln > self.min_savings_threshold_pln:
            return 'wait_for_better_timing'
        
        # Otherwise, wait
        return 'wait'
    
    def _get_recommendation_reason(self, recommendation: str, optimal_window: PriceWindow, 
                                  pv_timing: Dict[str, Any]) -> str:
        """Get human-readable reason for the recommendation"""
        
        if recommendation == 'pv_charging':
            return f"PV can complete charging in {pv_timing['estimated_time_hours']:.1f}h during low price window"
        
        elif recommendation == 'hybrid_charging':
            return f"Low price window ({optimal_window.duration_hours:.1f}h) shorter than PV charging time ({pv_timing['estimated_time_hours']:.1f}h), use grid charging to capture savings"
        
        elif recommendation == 'wait_for_better_timing':
            return f"Price window available but PV timing insufficient, waiting for better conditions"
        
        else:  # wait
            return "No optimal charging conditions found, waiting for better timing"


def create_price_window_analyzer(config: Dict[str, Any]) -> PriceWindowAnalyzer:
    """Create a price window analyzer instance"""
    return PriceWindowAnalyzer(config)