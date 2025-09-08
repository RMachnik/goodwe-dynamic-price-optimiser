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
    avg_price_pln: float = None
    min_price_pln: float = 0.0
    max_price_pln: float = 0.0
    price_category: str = 'medium'  # 'very_low', 'low', 'medium', 'high', 'very_high'
    savings_potential_pln: float = 0.0
    
    def __post_init__(self):
        """Handle backward compatibility with avg_price parameter"""
        # If avg_price_pln is None, try to get it from avg_price
        if self.avg_price_pln is None:
            # This will be set by the calling code if needed
            pass
    
    @property
    def avg_price(self) -> float:
        """Backward compatibility property for avg_price"""
        return self.avg_price_pln
    
    @avg_price.setter
    def avg_price(self, value: float):
        """Backward compatibility setter for avg_price"""
        self.avg_price_pln = value
    
    @property
    def price_type(self) -> str:
        """Backward compatibility property for price_type"""
        return self.price_category
    
    @price_type.setter
    def price_type(self, value: str):
        """Backward compatibility setter for price_type"""
        self.price_category = value
    
    def __init__(self, start_time: datetime, end_time: datetime, duration_hours: float, 
                 avg_price_pln: float = None, avg_price: float = None, min_price_pln: float = 0.0, 
                 max_price_pln: float = 0.0, price_category: str = 'medium', 
                 savings_potential_pln: float = 0.0, **kwargs):
        """Initialize PriceWindow with backward compatibility"""
        self.start_time = start_time
        self.end_time = end_time
        self.duration_hours = duration_hours
        self.avg_price_pln = avg_price_pln or avg_price or 0.0
        self.min_price_pln = min_price_pln
        self.max_price_pln = max_price_pln
        self.price_category = price_category
        self.savings_potential_pln = savings_potential_pln
        
        # Handle additional parameters for backward compatibility
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def price_type(self) -> str:
        """Backward compatibility property for price_type"""
        return self.price_category
    
    @price_type.setter
    def price_type(self, value: str):
        """Backward compatibility setter for price_type"""
        self.price_category = value
    
    @property
    def avg_price(self) -> float:
        """Backward compatibility property for avg_price"""
        return self.avg_price_pln
    
    @avg_price.setter
    def avg_price(self, value: float):
        """Backward compatibility setter for avg_price"""
        self.avg_price_pln = value

class PriceWindowAnalyzer:
    """Analyzes electricity price windows for optimal charging timing"""
    
    def __init__(self, config):
        """Initialize the price window analyzer"""
        # Handle both config dict and config file path
        if isinstance(config, str):
            try:
                import yaml
                with open(config, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            except (FileNotFoundError, yaml.YAMLError):
                self.config = self._get_default_config()
        else:
            self.config = config or {}
        
        # Extract price analysis config if it exists
        price_analysis_config = self.config.get('price_analysis', {})
        
        # Price thresholds (PLN/MWh)
        self.price_thresholds = {
            'very_low': price_analysis_config.get('very_low_price_threshold', self.config.get('very_low_price_threshold', 150.0)),
            'low': price_analysis_config.get('low_price_threshold', self.config.get('low_price_threshold', 250.0)),
            'medium': price_analysis_config.get('medium_price_threshold', self.config.get('medium_price_threshold', 400.0)),
            'high': price_analysis_config.get('high_price_threshold', self.config.get('high_price_threshold', 600.0)),
            'very_high': price_analysis_config.get('very_high_price_threshold', self.config.get('very_high_price_threshold', 800.0))
        }
        
        # Charging parameters
        self.min_charging_duration_hours = price_analysis_config.get('min_charging_duration_hours', self.config.get('min_charging_duration_hours', 0.25))  # 15 minutes
        self.max_charging_duration_hours = price_analysis_config.get('max_charging_duration_hours', self.config.get('max_charging_duration_hours', 4.0))   # 4 hours
        self.min_savings_threshold_pln = price_analysis_config.get('min_savings_threshold_pln', self.config.get('min_savings_threshold_pln', 50.0))     # 50 PLN/MWh savings
        
        # Reference price for savings calculation
        self.reference_price_pln = price_analysis_config.get('reference_price_pln', self.config.get('reference_price_pln', 400.0))  # Average market price
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when config file is missing or invalid"""
        return {
            'very_low_price_threshold': 150.0,
            'low_price_threshold': 250.0,
            'medium_price_threshold': 400.0,
            'high_price_threshold': 600.0,
            'very_high_price_threshold': 800.0,
            'min_charging_duration_hours': 0.25,
            'max_charging_duration_hours': 4.0,
            'min_savings_threshold_pln': 50.0,
            'reference_price_pln': 400.0
        }
    
    def analyze_price_windows(self, price_data: Dict[str, Any]) -> List[PriceWindow]:
        """
        Analyze price data to identify optimal charging windows
        
        Args:
            price_data: Price data from Polish electricity API
            
        Returns:
            List of PriceWindow objects sorted by savings potential
        """
        logger.info("Analyzing price windows for optimal charging")
        
        if not price_data or ('value' not in price_data and 'prices' not in price_data):
            logger.warning("No price data available for analysis")
            return []
        
        # Get current time and find current price
        current_time = datetime.now()
        current_price = self._get_current_price(price_data, current_time)
        
        if current_price is None:
            logger.warning("Could not determine current price")
            return []
        
        # Find all price windows (low, high, etc.)
        windows = self._find_all_price_windows(price_data, current_time)
        
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
            # Handle different price data formats
            if 'value' in price_data:
                # Original format with detailed price data
                for item in price_data['value']:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    
                    # Check if current time falls within this 15-minute period
                    if item_time <= current_time < item_time + timedelta(minutes=15):
                        market_price = float(item['csdac_pln'])
                        # Add SC component (0.0892 PLN/kWh)
                        final_price = market_price + 0.0892
                        return final_price
            elif 'prices' in price_data:
                # Simple format with just prices array (for testing)
                prices = price_data['prices']
                if prices:
                    # For testing, return the first price or current_price if available
                    current_price = price_data.get('current_price', prices[0])
                    # Add SC component for consistency
                    return current_price + 0.0892
            
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
            
            if 'value' in price_data:
                # Original format with detailed price data
                for item in price_data['value']:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    market_price = float(item['csdac_pln'])
                    final_price = market_price + 0.0892  # Add SC component
                    price_points.append((item_time, final_price))
            elif 'prices' in price_data:
                # Simple format with just prices array - create time points
                prices = price_data['prices']
                # Start from current time to ensure future prices
                base_time = current_time
                for i, price in enumerate(prices):
                    item_time = base_time + timedelta(minutes=15 * i)
                    # Add SC component for consistency
                    final_price = price + 0.0892
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
    
    def _find_all_price_windows(self, price_data: Dict[str, Any], current_time: datetime) -> List[PriceWindow]:
        """Find all price windows (low, high, very_low, etc.) in the price data"""
        windows = []
        
        try:
            # Convert price data to list of (time, price) tuples
            price_points = []
            
            if 'value' in price_data:
                # Original format with detailed price data
                for item in price_data['value']:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    market_price = float(item['csdac_pln'])
                    final_price = market_price + 0.0892  # Add SC component
                    price_points.append((item_time, final_price))
            elif 'prices' in price_data:
                # Simple format with just prices array - create time points
                prices = price_data['prices']
                # Start from current time to ensure future prices
                base_time = current_time
                for i, price in enumerate(prices):
                    item_time = base_time + timedelta(minutes=15 * i)
                    # Add SC component for consistency
                    final_price = price + 0.0892
                    price_points.append((item_time, final_price))
            
            # Sort by time
            price_points.sort(key=lambda x: x[0])
            
            # Find continuous price periods for each price category
            for price_category in ['very_low', 'low', 'medium', 'high', 'very_high']:
                current_window_start = None
                current_window_prices = []
                
                for item_time, price in price_points:
                    # Skip past prices
                    if item_time < current_time:
                        continue
                    
                    # Check if this price falls in the current category
                    if self._is_price_in_category(price, price_category):
                        if current_window_start is None:
                            current_window_start = item_time
                        current_window_prices.append(price)
                    else:
                        # End of current price window
                        if current_window_start is not None and len(current_window_prices) > 0:
                            window = self._create_price_window(
                                current_window_start,
                                item_time,
                                current_window_prices,
                                price_category
                            )
                            if window:
                                windows.append(window)
                        current_window_start = None
                        current_window_prices = []
                
                # Handle window that extends to end of data
                if current_window_start is not None and len(current_window_prices) > 0:
                    window = self._create_price_window(
                        current_window_start,
                        price_points[-1][0] + timedelta(minutes=15),
                        current_window_prices,
                        price_category
                    )
                    if window:
                        windows.append(window)
        
        except Exception as e:
            logger.error(f"Error finding all price windows: {e}")
        
        return windows
    
    def _is_price_in_category(self, price: float, category: str) -> bool:
        """Check if a price falls within a specific category"""
        if category == 'very_low':
            return price <= self.price_thresholds['very_low']
        elif category == 'low':
            return self.price_thresholds['very_low'] < price <= self.price_thresholds['low']
        elif category == 'medium':
            return self.price_thresholds['low'] < price <= self.price_thresholds['medium']
        elif category == 'high':
            return self.price_thresholds['medium'] < price <= self.price_thresholds['high']
        elif category == 'very_high':
            return price > self.price_thresholds['high']
        return False
    
    def _create_price_window(self, start_time: datetime, end_time: datetime, prices: List[float], price_category: str = None) -> Optional[PriceWindow]:
        """Create a PriceWindow object from timing and price data"""
        try:
            duration_hours = (end_time - start_time).total_seconds() / 3600
            
            # Skip windows that are too short
            if duration_hours < self.min_charging_duration_hours:
                return None
            
            avg_price = statistics.mean(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            # Use provided price category or determine from average price
            if price_category:
                category = price_category
            else:
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
            
            window = PriceWindow(
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                avg_price_pln=avg_price,
                min_price_pln=min_price,
                max_price_pln=max_price,
                price_category=category,
                savings_potential_pln=0.0  # Will be calculated later
            )
            
            # Set price_type attribute for backward compatibility with tests
            window.price_type = category
            
            return window
        
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
                               energy_needed_kwh: float, current_pv_power: float = 0.0) -> Dict[str, Any]:
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
        current_price = price_data.get('current_price', 0.0)
        pv_timing = self._analyze_pv_timing(pv_forecasts, energy_needed_kwh, optimal_window, current_pv_power, current_price)
        
        # Determine recommendation
        recommendation = self._determine_recommendation(optimal_window, pv_timing, pv_forecasts, current_pv_power)
        
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
                          optimal_window: PriceWindow, current_pv_power: float = 0.0, current_price: float = 0.0) -> Dict[str, Any]:
        """Analyze PV timing relative to optimal price window"""
        if not pv_forecasts:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'No PV forecasts available'
            }
        
        # Consider price window duration first - if it's very short, prefer grid charging
        # But allow PV charging if current PV is sufficient and price is very low
        if optimal_window.duration_hours < 1.0:  # Very short window (< 1 hour)
            # Check if current PV is sufficient for immediate charging
            if current_pv_power >= 1000:  # At least 1kW current PV
                # Allow PV charging for very short windows if PV is sufficient
                available_for_charging = current_pv_power * 0.8 / 1000.0  # 80% for charging, convert to kW
                pv_charging_time = energy_needed_kwh / available_for_charging
                
                return {
                    'can_charge_with_pv': True,
                    'estimated_time_hours': pv_charging_time,
                    'avg_pv_power_kw': current_pv_power / 1000.0,
                    'available_for_charging_kw': available_for_charging,
                    'reason': f'Current PV sufficient ({current_pv_power}W) for immediate charging despite short window'
                }
            else:
                # Check if PV is improving significantly - if so, recommend waiting
                max_forecast_power = max([f.get('forecasted_power_kw', f.get('power_kw', 0.0)) for f in pv_forecasts])
                current_pv_kw = current_pv_power / 1000.0
                if max_forecast_power > current_pv_kw * 1.5:  # PV improving by more than 50%
                    return {
                        'can_charge_with_pv': False,
                        'estimated_time_hours': float('inf'),
                        'reason': f'PV improvement expected (up to {max_forecast_power:.1f} kW), waiting for better conditions'
                    }
                else:
                    return {
                        'can_charge_with_pv': False,
                        'estimated_time_hours': float('inf'),
                        'reason': f'Low price window ({optimal_window.duration_hours:.1f}h) too short for PV charging'
                    }
        
        # Check if PV can complete charging within the optimal window
        window_start = optimal_window.start_time
        window_end = optimal_window.end_time
        
        # Find PV production during the optimal window
        pv_during_window = []
        for forecast in pv_forecasts:
            # Handle both timestamp and hour-based forecasts
            if 'timestamp' in forecast:
                forecast_time = datetime.fromisoformat(forecast['timestamp'])
            elif 'hour' in forecast:
                # Assume hour 0 is current time, hour 1 is +1 hour, etc.
                forecast_time = datetime.now() + timedelta(hours=forecast['hour'])
            else:
                continue
                
            if window_start <= forecast_time < window_end:
                # Handle different forecast formats
                power_kw = forecast.get('forecasted_power_kw', forecast.get('power_kw', 0.0))
                pv_during_window.append(power_kw)
        
        if not pv_during_window:
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': 'No PV production during optimal price window'
            }
        
        # Calculate if PV can complete charging in time
        avg_pv_power = statistics.mean(pv_during_window)
        
        # Consider current PV power - if it's very low, be more conservative
        if current_pv_power < 300:  # Less than 300W current PV (very low)
            # When current PV is very low, assume PV charging is not viable
            return {
                'can_charge_with_pv': False,
                'estimated_time_hours': float('inf'),
                'reason': f'Current PV too low ({current_pv_power}W), insufficient for reliable charging'
            }
        
        # Consider current price - if it's not very low, be more conservative about PV charging
        if current_price > 0.3:  # Price above 0.3 PLN/kWh (medium to high)
            # Check if PV is improving significantly
            max_forecast_power = max([f.get('forecasted_power_kw', f.get('power_kw', 0.0)) for f in pv_forecasts])
            current_pv_kw = current_pv_power / 1000.0
            
            # If current PV is very low (< 500W), prefer grid charging over waiting
            if current_pv_power < 500:
                return {
                    'can_charge_with_pv': False,
                    'estimated_time_hours': float('inf'),
                    'reason': f'Current PV too low ({current_pv_power}W), insufficient for reliable charging'
                }
            
            # If PV is improving significantly (>50% improvement), recommend waiting
            if max_forecast_power > current_pv_kw * 1.5:  # PV improving by more than 50%
                return {
                    'can_charge_with_pv': False,
                    'estimated_time_hours': float('inf'),
                    'reason': f'PV improvement expected (up to {max_forecast_power:.1f} kW), waiting for better conditions'
                }
            else:
                return {
                    'can_charge_with_pv': False,
                    'estimated_time_hours': float('inf'),
                    'reason': f'Current price ({current_price:.2f} PLN/kWh) not low enough for immediate PV charging'
                }
        
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
    
    def _determine_recommendation(self, optimal_window: PriceWindow, pv_timing: Dict[str, Any], 
                                 pv_forecasts: List[Dict] = None, current_pv_power: float = 0.0) -> str:
        """Determine the optimal charging recommendation"""
        
        # If PV can complete charging in time, prefer PV
        if pv_timing.get('can_charge_with_pv', False):
            return 'pv_charging'
        
        # If PV timing shows current PV is too low, recommend grid charging
        if 'Current PV too low' in pv_timing.get('reason', ''):
            return 'grid_charging'
        
        # If PV timing shows price is not low enough, recommend waiting
        if 'not low enough for immediate PV charging' in pv_timing.get('reason', ''):
            return 'wait'
        
        # If PV timing shows PV improvement expected, recommend waiting
        # But if current PV is very low (< 500W), prefer grid charging over waiting
        if 'PV improvement expected' in pv_timing.get('reason', ''):
            # Check if current PV is very low - if so, recommend grid charging
            if current_pv_power < 500:  # Very low PV power
                return 'grid_charging'
            return 'wait'
        
        # If PV timing shows price window too short, recommend grid charging
        if 'Price window too short' in pv_timing.get('reason', '') or 'Low price window' in pv_timing.get('reason', ''):
            return 'grid_charging'
        
        # If price window is very short (< 1 hour), prefer grid charging over hybrid
        # But check if PV is improving significantly - if so, recommend waiting
        if optimal_window.duration_hours < 1.0:
            # Check if PV is improving significantly
            max_forecast_power = max([f.get('forecasted_power_kw', f.get('power_kw', 0.0)) for f in pv_forecasts])
            current_pv_kw = current_pv_power / 1000.0
            if max_forecast_power > current_pv_kw * 1.5:  # PV improving by more than 50%
                return 'wait'
            return 'grid_charging'
        
        # If price window is very good and PV timing is insufficient, recommend hybrid
        # But if current PV is very insufficient (< 800W) OR window is very short (< 1.5h), prefer grid charging over hybrid
        if optimal_window.savings_potential_pln > self.min_savings_threshold_pln * 1.5:
            if current_pv_power < 800 or optimal_window.duration_hours < 1.5:  # Low PV or short window - prefer grid charging
                return 'grid_charging'
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


    def identify_price_windows(self, price_data: Dict[str, Any]) -> List[PriceWindow]:
        """Identify price windows from price data (alias for analyze_price_windows)"""
        return self.analyze_price_windows(price_data)
    
    def analyze_price_volatility(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze price volatility in the price data"""
        try:
            if not price_data or 'prices' not in price_data:
                return {'volatility': 0.0, 'std_deviation': 0.0, 'price_range': 0.0}
            
            prices = price_data['prices']
            if not prices:
                return {'volatility': 0.0, 'std_deviation': 0.0, 'price_range': 0.0}
            
            # Calculate basic statistics
            mean_price = statistics.mean(prices)
            std_deviation = statistics.stdev(prices) if len(prices) > 1 else 0.0
            min_price = min(prices)
            max_price = max(prices)
            price_range = max_price - min_price
            
            # Calculate volatility as coefficient of variation
            volatility = (std_deviation / mean_price) * 100 if mean_price > 0 else 0.0
            
            return {
                'volatility': volatility,
                'volatility_score': volatility,  # Alias for backward compatibility
                'coefficient_of_variation': volatility,  # Alias for backward compatibility
                'std_deviation': std_deviation,
                'standard_deviation': std_deviation,  # Alias for backward compatibility
                'mean_price': mean_price,
                'min_price': min_price,
                'max_price': max_price,
                'price_range': price_range,
                'price_count': len(prices)
            }
        except Exception as e:
            logger.error(f"Error analyzing price volatility: {e}")
            return {'volatility': 0.0, 'std_deviation': 0.0, 'price_range': 0.0}
    
    def calculate_window_duration(self, start_time: datetime, end_time: datetime) -> float:
        """Calculate duration between two datetime objects in hours"""
        try:
            duration = end_time - start_time
            return duration.total_seconds() / 3600.0  # Convert to hours
        except Exception as e:
            logger.error(f"Error calculating window duration: {e}")
            return 0.0
    
    def calculate_charging_cost(self, window: PriceWindow, energy_kwh: float) -> Dict[str, Any]:
        """Calculate charging cost for a given window and energy amount"""
        try:
            total_cost = energy_kwh * window.avg_price_pln
            cost_per_kwh = window.avg_price_pln
            
            return {
                'total_cost': total_cost,
                'cost_per_kwh': cost_per_kwh,
                'energy_charged': energy_kwh,
                'window_duration_hours': window.duration_hours,
                'window_price_category': window.price_category
            }
        except Exception as e:
            logger.error(f"Error calculating charging cost: {e}")
            return {'total_cost': 0.0, 'cost_per_kwh': 0.0, 'energy_charged': 0.0}
    
    def analyze_energy_capacity(self, window: PriceWindow, max_charging_power_kw: float, battery_capacity_kwh: float) -> Dict[str, Any]:
        """Analyze energy capacity for a given window"""
        try:
            # Convert power to kW if it's in watts (assuming > 100 means watts)
            if max_charging_power_kw > 100:
                max_charging_power_kw = max_charging_power_kw / 1000.0
            
            # Calculate maximum energy that can be charged in this window
            max_energy_in_window = window.duration_hours * max_charging_power_kw
            
            # Calculate actual energy that can be charged (limited by battery capacity)
            available_battery_capacity = battery_capacity_kwh * 0.8  # Assume 80% usable capacity
            actual_energy_charged = min(max_energy_in_window, available_battery_capacity)
            
            # Calculate charging efficiency
            charging_efficiency = actual_energy_charged / max_energy_in_window if max_energy_in_window > 0 else 0.0
            
            return {
                'max_energy_in_window': max_energy_in_window,
                'max_energy_chargeable': max_energy_in_window,  # Theoretical maximum, not limited by battery
                'actual_energy_charged': actual_energy_charged,
                'charging_efficiency': charging_efficiency,
                'charging_power_utilization': actual_energy_charged / max_energy_in_window if max_energy_in_window > 0 else 0.0,  # Alias for window_utilization
                'battery_utilization': actual_energy_charged / battery_capacity_kwh if battery_capacity_kwh > 0 else 0.0,
                'battery_capacity_utilization': actual_energy_charged / battery_capacity_kwh if battery_capacity_kwh > 0 else 0.0,  # Alias for backward compatibility
                'window_utilization': actual_energy_charged / max_energy_in_window if max_energy_in_window > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"Error analyzing energy capacity: {e}")
            return {'max_energy_in_window': 0.0, 'actual_energy_charged': 0.0, 'charging_efficiency': 0.0}
    
    def get_optimal_charging_timing(self, price_data: Dict[str, Any], energy_needed_kwh: float, 
                                  max_charging_power_kw: float = 5.0) -> Dict[str, Any]:
        """Get optimal charging timing for given energy needs"""
        try:
            windows = self.analyze_price_windows(price_data)
            if not windows:
                return {'optimal_window': None, 'recommendation': 'wait', 'reason': 'No suitable windows found'}
            
            # Find the best window based on cost and timing
            best_window = None
            best_score = float('inf')
            
            for window in windows:
                # Calculate cost for this window
                cost = self.calculate_charging_cost(window, energy_needed_kwh)
                
                # Calculate if we can charge the needed energy in this window
                max_energy_in_window = window.duration_hours * max_charging_power_kw
                
                if max_energy_in_window >= energy_needed_kwh:
                    # Score based on cost and timing (lower is better)
                    score = cost['total_cost'] + (window.duration_hours * 10)  # Penalty for longer windows
                    if score < best_score:
                        best_score = score
                        best_window = window
            
            if best_window:
                return {
                    'optimal_window': best_window,
                    'recommendation': 'charge',
                    'reason': f'Optimal window found with cost {best_window.avg_price_pln:.3f} PLN/kWh',
                    'estimated_cost': best_window.avg_price_pln * energy_needed_kwh,
                    'charging_duration_hours': energy_needed_kwh / max_charging_power_kw
                }
            else:
                return {
                    'optimal_window': None,
                    'recommendation': 'wait',
                    'reason': 'No window can accommodate the required energy amount'
                }
        except Exception as e:
            logger.error(f"Error getting optimal charging timing: {e}")
            return {'optimal_window': None, 'recommendation': 'wait', 'reason': f'Error: {e}'}
    
    def analyze_price_trends(self, price_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze price trends in the data"""
        try:
            if not price_data or ('value' not in price_data and 'prices' not in price_data):
                return {'trend': 'unknown', 'trend_strength': 0.0, 'volatility': 0.0}
            
            # Get prices
            if 'prices' in price_data:
                prices = price_data['prices']
            else:
                prices = [float(item['csdac_pln']) + 0.0892 for item in price_data['value']]
            
            if len(prices) < 2:
                return {'trend': 'insufficient_data', 'trend_strength': 0.0, 'volatility': 0.0}
            
            # Calculate trend (simple linear regression slope)
            n = len(prices)
            x = list(range(n))
            y = prices
            
            # Calculate slope
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            # Determine trend
            if slope > 0.1:
                trend = 'increasing'
            elif slope < -0.1:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            # Calculate volatility
            mean_price = sum(prices) / len(prices)
            variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            volatility = (variance ** 0.5) / mean_price * 100 if mean_price > 0 else 0.0
            
            return {
                'trend': trend,
                'overall_trend': trend,  # Alias for backward compatibility
                'trend_strength': abs(slope),
                'volatility': volatility,
                'mean_price': mean_price,
                'min_price': min(prices),
                'max_price': max(prices),
                'price_range': max(prices) - min(prices)
            }
        except Exception as e:
            logger.error(f"Error analyzing price trends: {e}")
            return {'trend': 'error', 'trend_strength': 0.0, 'volatility': 0.0}
    
    def filter_windows_by_duration(self, windows: List[PriceWindow], min_duration_hours: float = 0.5, 
                                 max_duration_hours: float = 8.0) -> List[PriceWindow]:
        """Filter windows by duration"""
        try:
            filtered = []
            for window in windows:
                if min_duration_hours <= window.duration_hours <= max_duration_hours:
                    filtered.append(window)
            return filtered
        except Exception as e:
            logger.error(f"Error filtering windows by duration: {e}")
            return []
    
    def filter_windows_by_price_type(self, windows: List[PriceWindow], price_type) -> List[PriceWindow]:
        """Filter windows by price type/category"""
        try:
            filtered = []
            # Handle both single price type and list of price types
            if isinstance(price_type, str):
                price_types = [price_type]
            else:
                price_types = price_type
            
            for window in windows:
                if window.price_category in price_types or window.price_type in price_types:
                    filtered.append(window)
            return filtered
        except Exception as e:
            logger.error(f"Error filtering windows by price type: {e}")
            return []
    
    def calculate_savings(self, window: PriceWindow, average_price_pln: float, energy_kwh: float) -> Dict[str, Any]:
        """Calculate savings compared to average price"""
        try:
            window_cost = energy_kwh * window.avg_price_pln
            average_cost = energy_kwh * average_price_pln
            savings = average_cost - window_cost
            
            savings_percentage = (savings / average_cost * 100) if average_cost > 0 else 0.0
            
            return {
                'savings_pln': savings,
                'savings_amount': savings,  # Alias for backward compatibility
                'savings_percentage': savings_percentage,
                'window_cost': window_cost,
                'cost_with_average': average_cost,  # Alias for backward compatibility
                'cost_with_low_price': window_cost,  # Alias for backward compatibility
                'average_cost': average_cost,
                'energy_kwh': energy_kwh
            }
        except Exception as e:
            logger.error(f"Error calculating savings: {e}")
            return {'savings_pln': 0.0, 'savings_percentage': 0.0}
    
    def windows_overlap(self, window1: PriceWindow, window2: PriceWindow) -> bool:
        """Check if two windows overlap in time"""
        try:
            # Check if windows overlap
            return (window1.start_time < window2.end_time and window2.start_time < window1.end_time)
        except Exception as e:
            logger.error(f"Error checking window overlap: {e}")
            return False
    
    def rank_windows_by_priority(self, windows: List[PriceWindow]) -> List[PriceWindow]:
        """Rank windows by priority (best first)"""
        try:
            def priority_score(window):
                # Higher savings potential = higher priority
                # Shorter duration = higher priority (faster charging)
                # Lower price = higher priority
                savings_score = window.savings_potential_pln
                duration_penalty = window.duration_hours * 10  # Penalty for longer windows
                price_penalty = window.avg_price_pln * 100  # Penalty for higher prices
                
                return savings_score - duration_penalty - price_penalty
            
            return sorted(windows, key=priority_score, reverse=True)
        except Exception as e:
            logger.error(f"Error ranking windows by priority: {e}")
            return windows


def create_price_window_analyzer(config: Dict[str, Any]) -> PriceWindowAnalyzer:
    """Create a price window analyzer instance"""
    return PriceWindowAnalyzer(config)