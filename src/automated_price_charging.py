#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Enhanced Automated Price-Based Charging System
Integrates Polish electricity market prices with smart charging control
Considers PV overproduction, consumption patterns, and price optimization
"""

import asyncio
import json
import logging
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
from pathlib import Path

# Import the GoodWe fast charging functionality
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger
from enhanced_data_collector import EnhancedDataCollector
from enhanced_aggressive_charging import EnhancedAggressiveCharging
from tariff_pricing import TariffPricingCalculator, PriceComponents
from price_history_manager import PriceHistoryManager
from adaptive_threshold_calculator import AdaptiveThresholdCalculator

# Logging configuration handled by main application
logger = logging.getLogger(__name__)

class AutomatedPriceCharger:
    """Enhanced automated charging system with smart strategy"""
    
    def __init__(self, config_path: str = None):
        """Initialize the automated charger"""
        if config_path is None:
            # Use absolute path to config directory
            current_dir = Path(__file__).parent.parent
            self.config_path = str(current_dir / "config" / "master_coordinator_config.yaml")
        else:
            self.config_path = config_path
        
        # Load configuration first
        self._load_config()
        
        self.goodwe_charger = GoodWeFastCharger(self.config_path)
        self.data_collector = EnhancedDataCollector(self.config_path)
        self.price_api_url = "https://api.raporty.pse.pl/api/csdac-pln"
        self.current_schedule = None
        self.is_charging = False
        self.charging_start_time = None
        self.last_decision_time = None
        self.decision_history = []
        
        # Window commitment mechanism to prevent infinite postponement
        self.committed_window_time = None  # Time we committed to charge
        self.committed_window_price = None  # Price at committed window
        self.window_commitment_timestamp = None  # When commitment was made
        self.window_postponement_count = 0  # Track how many times we've postponed
        self.active_charging_session = False  # Track if we started a charging session
        self.charging_session_start_time = None  # When current session started
        self.charging_session_start_soc = None  # SOC when session started (for dynamic duration)
        
        # Smart charging thresholds
        self.critical_battery_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('critical', 12)  # % - Price-aware charging
        self.emergency_battery_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('emergency', 5)  # % - Always charge regardless of price
        self.low_battery_threshold = 30  # % - Consider charging if below this
        self.medium_battery_threshold = 50  # % - Only charge if conditions are favorable
        self.price_savings_threshold = 0.3  # 30% savings required to wait
        self.overproduction_threshold = 1500  # W - Significant overproduction (increased to allow charging during negative prices)
        self.high_consumption_threshold = 1000  # W - High consumption
        
        # Smart critical charging configuration
        smart_critical_config = self.config.get('timing_awareness', {}).get('smart_critical_charging', {})
        self.smart_critical_enabled = smart_critical_config.get('enabled', True)
        self.max_critical_price = smart_critical_config.get('max_critical_price_pln', 0.35)  # PLN/kWh
        self.max_wait_hours = smart_critical_config.get('max_wait_hours', 6)  # hours
        self.min_price_savings_percent = smart_critical_config.get('min_price_savings_percent', 30)  # %
        self.emergency_override_price = smart_critical_config.get('emergency_override_price', True)
        
        # Advanced optimization rules
        optimization_rules = smart_critical_config.get('optimization_rules', {})
        self.wait_at_10_percent_if_high_price = optimization_rules.get('wait_at_10_percent_if_high_price', True)
        self.high_price_threshold = optimization_rules.get('high_price_threshold_pln', 1.35)  # PLN/kWh - fallback value
        self.proactive_charging_enabled = optimization_rules.get('proactive_charging_enabled', True)
        self.pv_poor_threshold = optimization_rules.get('pv_poor_threshold_w', 200)  # Watts
        self.battery_target_threshold = optimization_rules.get('battery_target_threshold', 80)  # %
        self.weather_improvement_hours = optimization_rules.get('weather_improvement_hours', 6)  # hours
        self.max_proactive_price = optimization_rules.get('max_proactive_price_pln', 0.7)  # PLN/kWh
        
        # Super low price charging rules
        self.super_low_price_enabled = optimization_rules.get('super_low_price_charging_enabled', True)
        self.super_low_price_threshold = optimization_rules.get('super_low_price_threshold_pln', 0.3)  # PLN/kWh
        self.super_low_price_target_soc = optimization_rules.get('super_low_price_target_soc', 100)  # %
        self.super_low_price_min_duration = optimization_rules.get('super_low_price_min_duration_hours', 1.0)  # hours
        
        # PV preference during super low prices
        pv_preference_config = optimization_rules.get('super_low_price_pv_preference', {})
        self.pv_excellent_threshold = pv_preference_config.get('pv_excellent_threshold_w', 3000)  # Watts
        self.weather_stable_threshold = pv_preference_config.get('weather_stable_threshold', 0.8)  # confidence
        self.house_usage_low_threshold = pv_preference_config.get('house_usage_low_threshold_w', 1000)  # Watts
        self.pv_charging_time_limit = pv_preference_config.get('pv_charging_time_limit_hours', 2.0)  # hours
        
        # Interim cost analysis configuration
        interim_cost_config = smart_critical_config.get('interim_cost_analysis', {})
        self.interim_cost_enabled = interim_cost_config.get('enabled', False)
        self.interim_net_savings_threshold = interim_cost_config.get('net_savings_threshold_pln', 0.10)  # PLN
        self.interim_evaluation_window_hours = interim_cost_config.get('evaluation_window_hours', 12)  # hours
        self.interim_time_of_day_adjustment = interim_cost_config.get('time_of_day_adjustment', True)
        self.interim_evening_peak_multiplier = interim_cost_config.get('evening_peak_multiplier', 1.5)
        self.interim_night_discount_multiplier = interim_cost_config.get('night_discount_multiplier', 0.8)
        self.interim_fallback_consumption = interim_cost_config.get('fallback_consumption_kw', 1.25)  # kW
        self.interim_min_historical_hours = interim_cost_config.get('min_historical_hours', 48)  # hours
        self.interim_lookback_days = interim_cost_config.get('lookback_days', 7)  # days

    def _load_config(self) -> None:
        """Load YAML configuration defensively into `self.config`."""
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            self.config = {}
        
        # Window commitment configuration (prevents infinite postponement)
        interim_cfg = self.config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('interim_cost_analysis', {})
        self.window_commitment_enabled = interim_cfg.get('window_commitment_enabled', True)
        self.max_window_postponements = interim_cfg.get('max_window_postponements', 3)
        self.commitment_margin_minutes = interim_cfg.get('commitment_margin_minutes', 30)
        self.min_charging_session_duration = interim_cfg.get('min_charging_session_duration_minutes', 90)
        self.dynamic_protection_duration = interim_cfg.get('dynamic_protection_duration', True)
        self.protection_duration_buffer_percent = interim_cfg.get('protection_duration_buffer_percent', 10)
        self.soc_urgency_thresholds = interim_cfg.get('soc_urgency_thresholds', {
            'critical': 15,  # Below 15%: commit immediately, no more postponements
            'urgent': 20,    # Below 20%: max 1 postponement allowed
            'low': 30        # Below 30%: max 2 postponements allowed
        })
        
        # Partial charging configuration
        smart_critical_config = self.config.get('timing_awareness', {}).get('smart_critical_charging', {})
        partial_charging_config = smart_critical_config.get('partial_charging', {})
        self.partial_charging_enabled = partial_charging_config.get('enabled', False)
        self.partial_safety_margin = partial_charging_config.get('safety_margin_percent', 10) / 100.0  # Convert to fraction
        self.partial_max_sessions_per_day = partial_charging_config.get('max_partial_sessions_per_day', 4)
        self.partial_min_charge_kwh = partial_charging_config.get('min_partial_charge_kwh', 2.0)  # kWh
        self.partial_session_tracking_file = partial_charging_config.get('session_tracking_file', 'out/partial_charging_sessions.json')
        self.partial_daily_reset_hour = partial_charging_config.get('daily_reset_hour', 6)  # 24h format
        self.partial_timezone = partial_charging_config.get('timezone', 'Europe/Warsaw')
        
        # Preventive partial charging configuration (nested in partial_charging)
        self.preventive_partial_enabled = partial_charging_config.get('preventive_enabled', True)
        self.preventive_scan_ahead_hours = partial_charging_config.get('preventive_scan_ahead_hours', 12)
        self.preventive_min_savings_percent = partial_charging_config.get('preventive_min_savings_percent', 30)
        self.preventive_critical_soc_forecast = partial_charging_config.get('preventive_critical_soc_forecast', 15)
        self.preventive_min_high_price_duration_hours = partial_charging_config.get('preventive_min_high_price_duration_hours', 3)
        
        # Import pytz for timezone handling
        try:
            import pytz
            self.warsaw_tz = pytz.timezone(self.partial_timezone)
            logger.info(f"Partial charging timezone set to {self.partial_timezone}")
        except Exception as e:
            logger.warning(f"Failed to load timezone {self.partial_timezone}, using UTC: {e}")
            import pytz
            self.warsaw_tz = pytz.UTC
        
        # Battery capacity for partial charging calculations
        self.battery_capacity_kwh = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)  # kWh
        
        # Log status of features from config
        self.interim_cost_enabled = interim_cfg.get('enabled', False)
        logger.info(f"Interim cost analysis: {'enabled' if self.interim_cost_enabled else 'disabled'}")
        logger.info(f"Partial charging: {'enabled' if self.partial_charging_enabled else 'disabled'} (max {self.partial_max_sessions_per_day} sessions/day)")
        logger.info(f"Preventive partial charging: {'enabled' if self.preventive_partial_enabled else 'disabled'}")
        
        # Load electricity pricing configuration
        self._load_pricing_config()
        
        # Initialize tariff pricing calculator
        try:
            self.tariff_calculator = TariffPricingCalculator(self.config)
            logger.info("Tariff pricing calculator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tariff pricing calculator: {e}")
            self.tariff_calculator = None
        
        # Load aggressive cheapest price charging configuration (legacy)
        self._load_aggressive_cheapest_config()

    def _load_pricing_config(self) -> None:
        """Load tariff/service charge pricing components safely."""
        pricing_cfg = self.config.get('pricing', {})
        tariff_cfg = self.config.get('tariff', {})
        elec_pricing = self.config.get('electricity_pricing', {})
        elec_tariff = self.config.get('electricity_tariff', {})
        
        # Service charge component (SC) net in PLN/kWh - check multiple locations
        sc_candidates = [
            float(elec_pricing.get('sc_component_net', 0.0)),
            float(elec_tariff.get('sc_component_pln_kwh', 0.0)),
            float(tariff_cfg.get('sc_component_net_pln_kwh', 0.0)),
            float(tariff_cfg.get('sc_component_pln_kwh', 0.0)),
            float(pricing_cfg.get('sc_component_net_pln_kwh', 0.0))
        ]
        
        # Use the first non-zero value
        self.sc_component_net = next((x for x in sc_candidates if x != 0.0), 0.0)
        
        # Minimum price floor (Polish regulatory minimum)
        self.minimum_price_floor = float(pricing_cfg.get('minimum_price_floor_pln_kwh', 0.0050))
        
        # Tariff configuration for `TariffPricingCalculator` is already passed via `self.config`
        
        # Initialize enhanced aggressive charging module
        try:
            self.enhanced_aggressive = EnhancedAggressiveCharging(self.config)
            logger.info("Enhanced aggressive charging module initialized")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced aggressive charging: {e}")
            self.enhanced_aggressive = None
        
        # Initialize adaptive price thresholds
        adaptive_config = self.config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('adaptive_thresholds', {})
        self.adaptive_enabled = adaptive_config.get('enabled', False)
        
        if self.adaptive_enabled:
            try:
                self.price_history = PriceHistoryManager(adaptive_config)
                self.threshold_calculator = AdaptiveThresholdCalculator(adaptive_config)
                self.threshold_update_interval = adaptive_config.get('update_interval_hours', 3) * 3600  # Convert to seconds
                self.last_threshold_update = 0
                self.adaptive_high_price_threshold = None
                self.adaptive_critical_price = None
                
                # Load historical data on startup
                loaded_count = self.price_history.load_historical_from_files()
                logger.debug(
                    f"Loaded {loaded_count} historical price points for adaptive thresholds"
                )
                self.minimum_price_floor = 0.0050
                self.charging_threshold_percentile = 0.25
            except Exception as e:
                logger.error(f"Adaptive thresholds initialization failed: {e}")
                self.price_history = None
                self.threshold_calculator = None
                self.threshold_update_interval = adaptive_config.get('update_interval_hours', 3) * 3600
                self.last_threshold_update = 0
                self.adaptive_high_price_threshold = None
                self.adaptive_critical_price = None
                self.minimum_price_floor = 0.0050
                self.charging_threshold_percentile = 0.25
    
    def _load_aggressive_cheapest_config(self):
        """Load aggressive cheapest price charging configuration"""
        try:
            coordinator_config = self.config.get('coordinator', {})
            self.aggressive_cheapest_config = coordinator_config.get('cheapest_price_aggressive_charging', {})
            
            # Set defaults if not configured
            self.aggressive_cheapest_enabled = self.aggressive_cheapest_config.get('enabled', True)
            self.max_price_difference_pln = self.aggressive_cheapest_config.get('max_price_difference_pln', 0.05)
            self.min_battery_soc_for_aggressive = self.aggressive_cheapest_config.get('min_battery_soc_for_aggressive', 30)
            self.max_battery_soc_for_aggressive = self.aggressive_cheapest_config.get('max_battery_soc_for_aggressive', 85)
            self.override_pv_overproduction = self.aggressive_cheapest_config.get('override_pv_overproduction', True)
            self.min_charging_duration_minutes = self.aggressive_cheapest_config.get('min_charging_duration_minutes', 15)
            
            logger.info(f"Aggressive cheapest price charging: {'enabled' if self.aggressive_cheapest_enabled else 'disabled'}")
            
        except Exception as e:
            logger.error(f"Failed to load aggressive cheapest price configuration: {e}")
            self.aggressive_cheapest_config = {}
            self.aggressive_cheapest_enabled = False
    
    def calculate_final_price(self, market_price: float, timestamp: Optional[datetime] = None, kompas_status: Optional[str] = None) -> float:
        """
        Calculate final price using tariff-aware pricing.
        
        Args:
            market_price: Market price in PLN/MWh
            timestamp: Time for the price (used for time-based tariffs)
            kompas_status: Kompas status for G14dynamic
        
        Returns:
            Final price in PLN/MWh (for consistency with existing code)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Use tariff calculator if available
        if self.tariff_calculator:
            # Convert from PLN/MWh to PLN/kWh if needed
            market_price_kwh = market_price / 1000 if market_price > 10 else market_price
            
            components = self.tariff_calculator.calculate_final_price(
                market_price_kwh,
                timestamp,
                kompas_status
            )
            
            # Return in PLN/MWh for consistency with existing code
            return components.final_price * 1000
        else:
            # Fallback to legacy pricing (SC component only)
            logger.warning("Tariff calculator not available, using legacy SC-only pricing")
            final_price = market_price + self.sc_component_net
            return final_price
    
    def apply_minimum_price_floor(self, price: float) -> float:
        """Apply minimum price floor as per Polish regulations"""
        return max(price, self.minimum_price_floor)
    
    def _calculate_interim_cost(self, start_time: datetime, end_time: datetime, price_data: Dict) -> float:
        """
        Calculate the cost of grid consumption during the interim period (waiting time).
        
        This method analyzes historical consumption patterns from the Enhanced Data Collector's
        7-day buffer to estimate grid consumption costs if we wait from start_time to end_time.
        
        Args:
            start_time: Current time (start of interim period)
            end_time: Future time (end of interim period, start of charging window)
            price_data: Dictionary with 'value' list containing price points with 'dtime' and 'csdac_pln'
        
        Returns:
            Estimated grid consumption cost in PLN for the interim period
        """
        if not self.interim_cost_enabled:
            return 0.0
        
        try:
            # Get historical data from Enhanced Data Collector
            historical_data = self.data_collector.historical_data
            
            # Check if we have enough historical data
            if len(historical_data) < self.interim_min_historical_hours * 180:  # 180 = 3600s/hour / 20s/sample
                logger.debug(f"Insufficient historical data ({len(historical_data)} samples, need {self.interim_min_historical_hours * 180}), using fallback consumption")
                # Use fallback consumption rate
                hours_to_wait = (end_time - start_time).total_seconds() / 3600
                
                # Get average price for interim period
                avg_price = self._get_average_price_for_period(start_time, end_time, price_data)
                if avg_price is None:
                    return 0.0
                
                interim_cost = hours_to_wait * self.interim_fallback_consumption * avg_price
                logger.debug(f"Interim cost (fallback): {interim_cost:.2f} PLN ({hours_to_wait:.1f}h × {self.interim_fallback_consumption:.2f} kW × {avg_price:.3f} PLN/kWh)")
                return interim_cost
            
            # Group historical consumption by hour of day (0-23)
            hourly_consumption = {}  # hour -> [consumption_kw_values]
            
            for data_point in historical_data:
                try:
                    # Extract timestamp and consumption
                    timestamp_str = data_point.get('timestamp')
                    if not timestamp_str:
                        continue
                    
                    # Parse timestamp
                    if isinstance(timestamp_str, str):
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = timestamp_str
                    
                    # Get consumption in kW
                    consumption_kw = data_point.get('house_consumption', {}).get('current_power_kw', 0.0)
                    if not isinstance(consumption_kw, (int, float)):
                        continue
                    
                    # Group by hour of day
                    hour = timestamp.hour
                    if hour not in hourly_consumption:
                        hourly_consumption[hour] = []
                    hourly_consumption[hour].append(consumption_kw)
                    
                except Exception as e:
                    logger.debug(f"Error processing historical data point: {e}")
                    continue
            
            # Calculate average consumption for each hour with time-of-day adjustments
            hourly_avg_consumption = {}
            for hour in range(24):
                if hour in hourly_consumption and len(hourly_consumption[hour]) > 0:
                    avg = sum(hourly_consumption[hour]) / len(hourly_consumption[hour])
                    
                    # Apply time-of-day multipliers if enabled
                    if self.interim_time_of_day_adjustment:
                        if 18 <= hour < 22:  # Evening peak (18:00-22:00)
                            avg *= self.interim_evening_peak_multiplier
                        elif hour >= 22 or hour < 6:  # Night (22:00-06:00)
                            avg *= self.interim_night_discount_multiplier
                    
                    hourly_avg_consumption[hour] = avg
                else:
                    # Use fallback for hours with no data
                    hourly_avg_consumption[hour] = self.interim_fallback_consumption
            
            # Calculate interim cost by iterating through each hour in the interim period
            total_cost = 0.0
            current_time = start_time
            
            while current_time < end_time:
                hour = current_time.hour
                
                # Calculate time fraction for this hour (handles partial hours)
                next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                if next_hour > end_time:
                    next_hour = end_time
                
                hour_fraction = (next_hour - current_time).total_seconds() / 3600
                
                # Get consumption for this hour
                consumption_kw = hourly_avg_consumption.get(hour, self.interim_fallback_consumption)
                
                # Get price for this hour
                price_pln_kwh = self._get_price_for_hour(current_time, price_data)
                if price_pln_kwh is None:
                    price_pln_kwh = 0.6  # Fallback price
                
                # Add to total cost
                hour_cost = hour_fraction * consumption_kw * price_pln_kwh
                total_cost += hour_cost
                
                logger.debug(f"Interim hour {current_time.strftime('%H:%M')}: {hour_fraction:.2f}h × {consumption_kw:.2f} kW × {price_pln_kwh:.3f} PLN/kWh = {hour_cost:.2f} PLN")
                
                current_time = next_hour
            
            logger.info(f"Interim cost: {total_cost:.2f} PLN for period {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
            return total_cost
            
        except Exception as e:
            logger.error(f"Error calculating interim cost: {e}")
            return 0.0
    
    def _get_average_price_for_period(self, start_time: datetime, end_time: datetime, price_data: Dict) -> Optional[float]:
        """Get average price for a time period"""
        try:
            if not price_data or 'value' not in price_data:
                return None
            
            prices = []
            for item in price_data['value']:
                try:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    if start_time <= item_time < end_time:
                        # Convert from PLN/MWh to PLN/kWh
                        price_kwh = float(item['csdac_pln']) / 1000
                        prices.append(price_kwh)
                except Exception:
                    continue
            
            if prices:
                return sum(prices) / len(prices)
            return None
            
        except Exception as e:
            logger.error(f"Error getting average price: {e}")
            return None
    
    def _get_price_for_hour(self, target_time: datetime, price_data: Dict) -> Optional[float]:
        """Get price for a specific hour"""
        try:
            if not price_data or 'value' not in price_data:
                return None
            
            # Find price for the target hour
            for item in price_data['value']:
                try:
                    item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    if item_time.hour == target_time.hour and item_time.date() == target_time.date():
                        # Convert from PLN/MWh to PLN/kWh
                        return float(item['csdac_pln']) / 1000
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for hour: {e}")
            return None
    
    def _evaluate_multi_window_with_interim_cost(self, battery_soc_or_data, price_data_or_current_price=None, current_time_or_price_data: Optional[datetime] = None) -> Optional[Dict[str, any]]:
        """
        Evaluate multiple future charging windows considering interim grid consumption costs.
        
        This method finds optimal charging windows within the evaluation period (default 12h)
        and calculates net benefit = charging_savings - interim_grid_cost for each window.
        
        Includes commitment mechanism to prevent infinite postponement.
        
        Supports both calling conventions:
        - New: (data_dict, price_data, current_time)
        - Old: (battery_soc_int, current_price_float, price_data)
        """
        try:
            # Handle both old and new calling conventions
            if isinstance(battery_soc_or_data, dict):
                # New signature: (data, price_data, current_time)
                battery_soc = int(battery_soc_or_data.get('battery', {}).get('soc_percent', 0))
                price_data = price_data_or_current_price
                current_time = current_time_or_price_data if current_time_or_price_data else datetime.now()
                # Derive current_price from price_data for current_time
                current_price = None
                try:
                    if price_data and 'value' in price_data:
                        for item in price_data['value']:
                            ts = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                            if ts == current_time:
                                current_price = float(item['csdac_pln']) / 1000.0
                                break
                    if current_price is None:
                        first = price_data['value'][0]
                        current_price = float(first['csdac_pln']) / 1000.0
                except Exception:
                    current_price = 0.0
            else:
                # Old signature: (battery_soc, current_price, price_data)
                battery_soc = int(battery_soc_or_data)
                current_price = float(price_data_or_current_price) if price_data_or_current_price else 0.0
                price_data = current_time_or_price_data
                current_time = datetime.now()

            evaluation_end = current_time + timedelta(hours=self.interim_evaluation_window_hours)
            evaluation_end = current_time + timedelta(hours=self.interim_evaluation_window_hours)
            
            # Check if we have a committed window that's now in range
            if self.window_commitment_enabled and self.committed_window_time:
                time_to_window = (self.committed_window_time - current_time).total_seconds() / 60
                
                # If we're within commitment margin of the window, charge now
                if 0 <= time_to_window <= self.commitment_margin_minutes:
                    logger.info(f"🎯 Committed window reached at {self.committed_window_time.strftime('%H:%M')} (price: {self.committed_window_price:.3f} PLN/kWh) - charging now")
                    self._start_charging_session(battery_soc)
                    self._clear_window_commitment()
                    return {
                        'should_charge': True,
                        'reason': f"Committed charging window reached ({self.committed_window_time.strftime('%H:%M')})",
                        'priority': 'high',
                        'confidence': 0.9,
                        'charging_session_protected': True
                    }
                
                # If committed window passed, clear it
                elif time_to_window < 0:
                    logger.warning(f"⚠️ Committed window at {self.committed_window_time.strftime('%H:%M')} passed - clearing commitment")
                    self._clear_window_commitment()
            
            # SOC-based urgency: determine max allowed postponements based on battery level
            if self.window_commitment_enabled:
                max_postponements_allowed = self._get_max_postponements_for_soc(battery_soc)
                
                # If we've hit postponement limit, prevent further postponement
                if self.window_postponement_count >= max_postponements_allowed:
                    # Special case: at critical SOC (allowance==0) without a commitment yet, allow evaluation to create one
                    if max_postponements_allowed == 0 and not self.committed_window_time:
                        logger.warning(
                            f"⛔ Max postponements limit at critical SOC {battery_soc}% - selecting and committing best window"
                        )
                        # continue to evaluation to commit the best available window
                    else:
                        logger.warning(
                            f"⛔ Max postponements reached ({self.window_postponement_count}/{max_postponements_allowed}) "
                            f"at SOC {battery_soc}% - forcing charge now"
                        )
                        self._start_charging_session(battery_soc)
                        # Do not clear commitment or reset count here; keep history intact
                        return {
                            'should_charge': True,
                            'reason': f"Max postponements reached at SOC {battery_soc}% - must charge",
                            'priority': 'high',
                            'confidence': 0.85,
                            'charging_session_protected': True
                        }
            
            # Get adaptive critical threshold - windows above this are blocked
            critical_threshold = float(self.get_critical_price_threshold())
            
            # Find all potential charging windows
            windows = []
            
            if not price_data or 'value' not in price_data:
                logger.debug("No price data available for multi-window evaluation")
                return None
            
            critical_mode = (self._get_max_postponements_for_soc(battery_soc) == 0)
            for item in price_data['value']:
                try:
                    window_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    window_price_mwh = float(item['csdac_pln'])
                    window_price_kwh = window_price_mwh / 1000
                    
                    # Skip windows outside evaluation period
                    if window_time <= current_time or window_time > evaluation_end:
                        continue
                    
                    # HARD LIMIT: Skip windows above adaptive critical threshold unless in critical mode
                    if (not critical_mode) and window_price_kwh > critical_threshold:
                        logger.debug(f"Window {window_time.strftime('%H:%M')}: {window_price_kwh:.3f} PLN/kWh > threshold {critical_threshold:.3f} PLN/kWh - BLOCKED")
                        continue
                    
                    # NEW: Check if window is long enough to complete charging
                    required_charging_hours = self._calculate_required_charging_duration(battery_soc) / 60.0
                    
                    # Calculate how long prices stay good (below critical threshold)
                    if critical_mode:
                        window_duration_hours = max(1.0, self._calculate_window_duration(window_time, price_data, critical_threshold))
                    else:
                        window_duration_hours = self._calculate_window_duration(window_time, price_data, critical_threshold)
                    
                    # Skip if window too short to complete charge (relaxed in critical mode)
                    if (not critical_mode) and window_duration_hours < required_charging_hours:
                        logger.debug(
                            f"Window {window_time.strftime('%H:%M')}: duration {window_duration_hours:.1f}h < "
                            f"required {required_charging_hours:.1f}h - TOO SHORT"
                        )
                        continue
                    
                    # Calculate charging savings (vs current price)
                    charge_kwh = 10.0  # Assume 10 kWh charge for calculation
                    charging_savings = (current_price - window_price_kwh) * charge_kwh
                    
                    # Calculate interim cost (grid consumption while waiting)
                    interim_cost = self._calculate_interim_cost(current_time, window_time, price_data)
                    
                    # Calculate net benefit
                    net_benefit = charging_savings - interim_cost
                    
                    windows.append({
                        'time': window_time,
                        'price_kwh': window_price_kwh,
                        'charging_savings': charging_savings,
                        'interim_cost': interim_cost,
                        'net_benefit': net_benefit,
                        'hours_to_wait': (window_time - current_time).total_seconds() / 3600,
                        'window_duration_hours': window_duration_hours,
                        'required_charging_hours': required_charging_hours
                    })
                    
                    logger.info(
                        f"Window {window_time.strftime('%H:%M')}: "
                        f"price={window_price_kwh:.3f} PLN/kWh, "
                        f"duration={window_duration_hours:.1f}h (need {required_charging_hours:.1f}h), "
                        f"savings={charging_savings:.2f} PLN, "
                        f"interim_cost={interim_cost:.2f} PLN, "
                        f"net_benefit={net_benefit:.2f} PLN"
                    )
                    
                except Exception as e:
                    logger.debug(f"Error processing window: {e}")
                    continue
            
            if not windows:
                logger.debug("No valid charging windows found within evaluation period")
                return None
            
            # Sort windows by net benefit (highest first)
            windows.sort(key=lambda w: w['net_benefit'], reverse=True)
            best_window = windows[0]
            
            # At critical SOC (allowance==0), ensure we commit to a window to prevent chasing endlessly improving prices
            max_allowed = self._get_max_postponements_for_soc(battery_soc)
            if self.window_commitment_enabled and max_allowed == 0 and not self.committed_window_time:
                self._commit_to_window(best_window['time'], best_window['price_kwh'])
                logger.info(
                    f"💡 Critical SOC commit: window at {best_window['time'].strftime('%H:%M')} "
                    f"({best_window['price_kwh']:.3f} PLN/kWh, net benefit: {best_window['net_benefit']:.2f} PLN)"
                )

            # Check if best window has positive net benefit above threshold
            if best_window['net_benefit'] > self.interim_net_savings_threshold:
                # Waiting is beneficial - check for partial charging option
                if self.partial_charging_enabled:
                    partial_decision = self._evaluate_partial_charging(
                        battery_soc, best_window, current_time, current_price
                    )
                    if partial_decision:
                        return partial_decision
                
                # Handle window commitment to prevent infinite postponement
                if self.window_commitment_enabled:
                    # If we don't have a committed window yet, or the new window is significantly better
                    if not self.committed_window_time:
                        # First time committing to a window
                        self._commit_to_window(best_window['time'], best_window['price_kwh'])
                        logger.info(
                            f"💡 Committing to window at {best_window['time'].strftime('%H:%M')} "
                            f"({best_window['price_kwh']:.3f} PLN/kWh, net benefit: {best_window['net_benefit']:.2f} PLN)"
                        )
                    elif best_window['time'] != self.committed_window_time:
                        # Window has changed - this is a postponement
                        self.window_postponement_count += 1
                        logger.info(
                            f"📅 Window moved from {self.committed_window_time.strftime('%H:%M')} to {best_window['time'].strftime('%H:%M')} "
                            f"(postponement #{self.window_postponement_count})"
                        )
                        self._commit_to_window(best_window['time'], best_window['price_kwh'])
                
                # Wait for best window (no partial charge needed/possible)
                return {
                    'should_charge': False,
                    'reason': (
                        f"Better window at {best_window['time'].strftime('%H:%M')} "
                        f"({best_window['price_kwh']:.3f} PLN/kWh): "
                        f"net benefit {best_window['net_benefit']:.2f} PLN "
                        f"(savings {best_window['charging_savings']:.2f} PLN - "
                        f"interim cost {best_window['interim_cost']:.2f} PLN)"
                    ),
                    'priority': 'medium',
                    'confidence': 0.8,
                    'next_window': best_window['time'].strftime('%H:%M'),
                    'net_benefit': best_window['net_benefit']
                }
            else:
                # No beneficial window found - charge now
                logger.info(
                    f"Best window net benefit {best_window['net_benefit']:.2f} PLN "
                    f"<= threshold {self.interim_net_savings_threshold} PLN - charging now"
                )
                
                # Keep commitment for tracking; charging now without clearing commitment
                return {
                    'should_charge': True,
                    'reason': (
                        f"No beneficial future window found "
                        f"(best: {best_window['time'].strftime('%H:%M')} "
                        f"with net benefit {best_window['net_benefit']:.2f} PLN) - charge now"
                    ),
                    'priority': 'medium',
                    'confidence': 0.75
                }
            
        except Exception as e:
            logger.error(f"Error in multi-window evaluation: {e}")
            return None
    
    def _commit_to_window(self, window_time: datetime, window_price: float):
        """Commit to charging at a specific window time"""
        self.committed_window_time = window_time
        self.committed_window_price = window_price
        self.window_commitment_timestamp = datetime.now()
    
    def _clear_window_commitment(self):
        """Clear window commitment and reset postponement counter"""
        self.committed_window_time = None
        self.committed_window_price = None
        self.window_commitment_timestamp = None
        self.window_postponement_count = 0
    
    def _get_max_postponements_for_soc(self, battery_soc: int) -> int:
        """
        Determine maximum allowed postponements based on battery SOC level.
        Lower SOC = fewer postponements allowed (more urgency).
        """
        # Treat 'critical' as strictly below threshold to allow urgent at boundary
        if battery_soc < self.soc_urgency_thresholds['critical']:
            return 0  # No postponements - charge immediately
        elif battery_soc < self.soc_urgency_thresholds['urgent']:
            return 1  # Allow only 1 postponement
        elif battery_soc < self.soc_urgency_thresholds['low']:
            return 2  # Allow 2 postponements
        else:
            return self.max_window_postponements  # Normal limit
    
    def _calculate_required_charging_duration(self, current_soc: int, target_soc: int = None) -> float:
        """
        Calculate required charging duration in minutes based on SOC difference.
        
        Args:
            current_soc: Current battery SOC percentage
            target_soc: Target SOC percentage (defaults to fast_charging target_soc)
        
        Returns:
            Required charging duration in minutes
        """
        try:
            # Get target SOC from config if not provided
            if target_soc is None:
                target_soc = self.config.get('fast_charging', {}).get('target_soc', 100)
            
            # Get battery capacity from config
            battery_capacity_kwh = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)
            
            # Get charging power (percentage of max)
            power_percentage = self.config.get('fast_charging', {}).get('power_percentage', 90) / 100.0
            max_charging_power_w = self.config.get('charging', {}).get('max_power', 10000)
            charging_power_kw = (max_charging_power_w * power_percentage) / 1000.0
            
            # Calculate energy needed
            soc_difference = max(0, target_soc - current_soc)
            energy_needed_kwh = (soc_difference / 100.0) * battery_capacity_kwh
            
            # Calculate time needed (hours). Tests expect simple linear model without extra efficiency factor.
            charging_time_hours = energy_needed_kwh / charging_power_kw
            
            # Convert to minutes and add buffer
            charging_time_minutes = charging_time_hours * 60
            buffer_multiplier = 1.0 + (self.protection_duration_buffer_percent / 100.0)
            buffered_time_minutes = charging_time_minutes * buffer_multiplier
            
            # Debug log for required charging time
            logger.debug(
                f"Required charging time: {charging_time_minutes:.1f} min (+{self.protection_duration_buffer_percent}% buffer -> {buffered_time_minutes:.1f} min)"
            )
            return buffered_time_minutes

        except Exception as e:
            logger.error(f"Error calculating required charging duration: {e}")
            return self.min_charging_session_duration

    def _get_consumption_forecast(self) -> float:
            """Return fallback house consumption forecast in kW for interim analysis."""
            return float(self.interim_fallback_consumption)

    def _calculate_window_duration(self, window_start: datetime, price_data: Dict, max_price_kwh: float) -> float:
        """Calculate consecutive hours from `window_start` with price <= `max_price_kwh`.
        Returns duration in hours.
        """
        if not price_data or 'value' not in price_data:
            return 0.0
        # Build map of timestamps to price (kWh)
        prices = {}
        for item in price_data['value']:
            ts = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            prices[ts] = float(item['csdac_pln']) / 1000.0
        # Walk forward hour by hour
        duration = 0.0
        current = window_start
        while True:
            price = prices.get(current)
            if price is None or price > max_price_kwh:
                break
            duration += 1.0
            current += timedelta(hours=1)
        return duration

    def _scan_for_high_prices_ahead(self, current_price: float, price_data: Dict, 
                                     current_time: datetime) -> List[Dict[str, any]]:
        """
        Scan ahead for high-price periods that would force expensive charging.
        
        Args:
            current_price: Current electricity price in PLN/kWh
            price_data: Dictionary with 'value' list containing price points
            current_time: Current datetime
        
        Returns:
            List of high-price periods sorted by start time (soonest first),
            or empty list if none found. Each period: {start, end, avg_price_kwh, duration_hours}
        """
        try:
            # Get adaptive high price threshold
            high_threshold = self.get_high_price_threshold()
            
            # Early exit if current price is already high
            if current_price >= high_threshold:
                logger.debug(f"Preventive scan blocked: current price {current_price:.3f} >= threshold {high_threshold:.3f}")
                return []
            
            if not price_data or 'value' not in price_data:
                logger.debug("Preventive scan: no price data available")
                return []
            
            logger.debug(f"Scanning for high prices ahead (threshold: {high_threshold:.3f} PLN/kWh)...")
            
            # Build list of hourly prices
            scan_end = current_time + timedelta(hours=self.preventive_scan_ahead_hours)
            hourly_prices = []
            
            for item in price_data['value']:
                try:
                    ts = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    if current_time <= ts < scan_end:
                        price_kwh = float(item['csdac_pln']) / 1000.0  # PLN/MWh → PLN/kWh
                        hourly_prices.append({'time': ts, 'price': price_kwh})
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"Skipping malformed price item: {e}")
                    continue
            
            if not hourly_prices:
                logger.debug("Preventive scan: no future prices in scan window")
                return []
            
            # Sort by time
            hourly_prices.sort(key=lambda x: x['time'])
            
            # Group consecutive high-price hours into periods
            periods = []
            current_period = None
            
            for hour in hourly_prices:
                if hour['price'] > high_threshold:
                    if current_period is None:
                        # Start new period
                        current_period = {
                            'start': hour['time'],
                            'end': hour['time'],
                            'prices': [hour['price']]
                        }
                    else:
                        # Extend current period if consecutive
                        if (hour['time'] - current_period['end']).total_seconds() <= 3600:  # Within 1 hour
                            current_period['end'] = hour['time']
                            current_period['prices'].append(hour['price'])
                        else:
                            # Gap detected - save current and start new
                            if len(current_period['prices']) >= self.preventive_min_high_price_duration_hours:
                                periods.append(current_period)
                            current_period = {
                                'start': hour['time'],
                                'end': hour['time'],
                                'prices': [hour['price']]
                            }
                else:
                    # Low price - end current period if exists
                    if current_period is not None:
                        if len(current_period['prices']) >= self.preventive_min_high_price_duration_hours:
                            periods.append(current_period)
                        current_period = None
            
            # Don't forget last period
            if current_period is not None:
                if len(current_period['prices']) >= self.preventive_min_high_price_duration_hours:
                    periods.append(current_period)
            
            # Format results
            results = []
            for period in periods:
                results.append({
                    'start': period['start'],
                    'end': period['end'],
                    'avg_price_kwh': sum(period['prices']) / len(period['prices']),
                    'duration_hours': len(period['prices'])
                })
            
            if results:
                logger.info(f"Found {len(results)} high-price period(s): {results[0]['duration_hours']:.0f}h @{results[0]['avg_price_kwh']:.3f} PLN/kWh starting at {results[0]['start'].strftime('%H:%M')}")
            else:
                logger.debug(f"No high-price periods ≥{self.preventive_min_high_price_duration_hours}h found in next {self.preventive_scan_ahead_hours}h")
            
            return results
            
        except Exception as e:
            logger.error(f"Error scanning for high prices ahead: {e}")
            return []

    def _calculate_battery_drain_forecast(self, current_soc: int, drain_duration_hours: float) -> Dict[str, float]:
        """
        Forecast battery drain during a period of grid consumption.
        
        Args:
            current_soc: Current battery SOC percentage
            drain_duration_hours: Duration of drain period in hours
        
        Returns:
            Dict with predicted_soc (%), energy_deficit_kwh, hours_until_critical
        """
        try:
            # Use conservative consumption estimate with safety margin
            consumption_kw = self.interim_fallback_consumption * (1 + self.partial_safety_margin)
            
            # Calculate energy drain
            energy_drain_kwh = consumption_kw * drain_duration_hours
            
            # Convert to SOC percentage
            drain_percent = (energy_drain_kwh / self.battery_capacity_kwh) * 100
            predicted_soc = max(0, int(current_soc - drain_percent))
            
            # Calculate energy deficit if below critical
            if predicted_soc < self.preventive_critical_soc_forecast:
                energy_deficit_kwh = ((self.preventive_critical_soc_forecast - predicted_soc) / 100.0) * self.battery_capacity_kwh
            else:
                energy_deficit_kwh = 0.0
            
            # Calculate hours until critical
            if drain_percent > 0:
                drain_rate_percent_per_hour = drain_percent / drain_duration_hours
                soc_above_critical = current_soc - self.preventive_critical_soc_forecast
                hours_until_critical = soc_above_critical / drain_rate_percent_per_hour if drain_rate_percent_per_hour > 0 else 999.0
            else:
                hours_until_critical = 999.0
            
            logger.debug(
                f"Drain forecast: {current_soc}% → {predicted_soc}% over {drain_duration_hours:.1f}h "
                f"({drain_percent:.0f}% drain, {energy_deficit_kwh:.1f} kWh deficit)"
            )
            
            return {
                'predicted_soc': predicted_soc,
                'energy_deficit_kwh': energy_deficit_kwh,
                'hours_until_critical': hours_until_critical
            }
            
        except Exception as e:
            logger.error(f"Error calculating battery drain forecast: {e}")
            return {'predicted_soc': current_soc, 'energy_deficit_kwh': 0.0, 'hours_until_critical': 999.0}

    def _start_charging_session(self, start_soc: int) -> None:
        """Start charging session and set protection duration."""
        self.active_charging_session = True
        self.charging_session_start_time = datetime.now()
        self.charging_session_start_soc = int(start_soc)
        if self.dynamic_protection_duration:
            minutes = self._calculate_required_charging_duration(self.charging_session_start_soc)
            self.session_protection_until = self.charging_session_start_time + timedelta(minutes=minutes)
        else:
            self.session_protection_until = self.charging_session_start_time + timedelta(minutes=self.min_charging_session_duration)

    def end_charging_session(self) -> None:
        """End active charging session and clear protection."""
        self.active_charging_session = False
        self.charging_session_start_time = None
        self.charging_session_start_soc = None
        self.session_protection_until = None

    def is_charging_session_protected(self) -> bool:
        """Return True if current time is within session protection window."""
        if not self.active_charging_session or not getattr(self, 'session_protection_until', None):
            return False
        # If dynamic protection is enabled, recompute end time from start time so test time shifts are respected
        if self.dynamic_protection_duration and self.charging_session_start_time is not None:
            minutes = self._calculate_required_charging_duration(self.charging_session_start_soc)
            dynamic_until = self.charging_session_start_time + timedelta(minutes=minutes)
            return datetime.now() <= dynamic_until
        return datetime.now() <= self.session_protection_until

    
    def _evaluate_partial_charging(self, battery_soc: int, best_window: Dict, 
                                  current_time: datetime, current_price: float) -> Optional[Dict[str, any]]:
        """
        Evaluate whether partial charging is beneficial to bridge the gap to the next window.
        
        Args:
            battery_soc: Current battery SOC percentage
            best_window: Dictionary with best future window details
            current_time: Current datetime
            current_price: Current electricity price in PLN/kWh
        
        Returns:
            Charging decision dict if partial charging recommended, None otherwise
        """
        try:
            # Check if current price is below critical threshold
            critical_threshold = self.get_critical_price_threshold()
            if current_price > critical_threshold:
                logger.debug(f"Partial charging blocked: current price {current_price:.3f} > threshold {critical_threshold:.3f}")
                return None
            
            # Calculate how many hours until best window
            hours_to_window = best_window['hours_to_wait']
            
            # Estimate energy consumption until window (using historical averages + safety margin)
            avg_consumption_kw = self.interim_fallback_consumption  # Use fallback as conservative estimate
            required_energy_kwh = hours_to_window * avg_consumption_kw * (1 + self.partial_safety_margin)
            
            # Check if required energy meets minimum
            if required_energy_kwh < self.partial_min_charge_kwh:
                logger.debug(f"Partial charge too small: {required_energy_kwh:.2f} kWh < minimum {self.partial_min_charge_kwh} kWh")
                return None
            
            # Check if we have battery capacity for partial charge
            battery_capacity_kwh = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)
            current_energy_kwh = (battery_soc / 100.0) * battery_capacity_kwh
            required_soc_kwh = current_energy_kwh + required_energy_kwh
            
            if required_soc_kwh > battery_capacity_kwh:
                logger.debug(f"Insufficient battery capacity for partial charge: need {required_soc_kwh:.2f} kWh, have {battery_capacity_kwh} kWh")
                return None
            
            # Check session limits
            if not self._check_partial_session_limits():
                logger.info("Partial charging session limit reached for today")
                return None
            
            # Partial charging is viable
            target_soc = min(100, int((required_soc_kwh / battery_capacity_kwh) * 100))
            
            return {
                'should_charge': True,
                'reason': (
                    f"Partial charge to {target_soc}% "
                    f"({required_energy_kwh:.1f} kWh) to bridge {hours_to_window:.1f}h "
                    f"until better window at {best_window['time'].strftime('%H:%M')} "
                    f"({best_window['price_kwh']:.3f} PLN/kWh)"
                ),
                'priority': 'medium',
                'confidence': 0.7,
                'partial_charge': True,
                'target_soc': target_soc,
                'required_kwh': required_energy_kwh,
                'next_window': best_window['time'].strftime('%H:%M')
            }
            
        except Exception as e:
            logger.error(f"Error evaluating partial charging: {e}")
            return None

    def _evaluate_preventive_partial_charging(self, battery_soc: int, current_price: float,
                                             price_data: Dict, current_time: datetime) -> Optional[Dict[str, any]]:
        """
        Evaluate whether preventive partial charging is beneficial to avoid expensive charging later.
        
        This charges now during cheap period to avoid being forced to charge at expensive
        rates when battery drains during upcoming high-price period.
        
        Args:
            battery_soc: Current battery SOC percentage
            current_price: Current electricity price in PLN/kWh
            price_data: Dictionary with price data
            current_time: Current datetime
        
        Returns:
            Charging decision dict if preventive charging recommended, None otherwise
        """
        try:
            # Early checks
            if not self.preventive_partial_enabled:
                return None
            
            # Check session limits first (before expensive calculations)
            if not self._check_partial_session_limits():
                logger.debug("Preventive charging blocked: session limit reached")
                return None
            
            # Check if current price is below critical threshold
            critical_threshold = self.get_critical_price_threshold()
            if current_price > critical_threshold:
                logger.debug(f"Preventive charging blocked: current price {current_price:.3f} > critical threshold {critical_threshold:.3f}")
                return None
            
            # Only trigger in middle SOC range (30-60%)
            if battery_soc < 30 or battery_soc > 60:
                logger.debug(f"Preventive charging blocked: SOC {battery_soc}% outside range 30-60%")
                return None
            
            # Scan for high-price periods ahead
            high_price_periods = self._scan_for_high_prices_ahead(current_price, price_data, current_time)
            if not high_price_periods:
                logger.debug("Preventive charging: no high-price periods detected")
                return None
            
            # Evaluate soonest high-price period
            period = high_price_periods[0]
            period_start = period['start']
            period_duration = period['duration_hours']
            period_avg_price = period['avg_price_kwh']
            
            # Calculate battery drain during high-price period
            drain_forecast = self._calculate_battery_drain_forecast(battery_soc, period_duration)
            predicted_soc = drain_forecast['predicted_soc']
            energy_deficit_kwh = drain_forecast['energy_deficit_kwh']
            
            # Skip if predicted SOC stays above critical
            if predicted_soc >= self.preventive_critical_soc_forecast:
                logger.debug(
                    f"Preventive charging not needed: predicted SOC {predicted_soc}% >= "
                    f"critical {self.preventive_critical_soc_forecast}%"
                )
                return None
            
            # Calculate energy to add (at least minimum charge)
            energy_to_add_kwh = max(energy_deficit_kwh, self.partial_min_charge_kwh)
            
            # Calculate target SOC
            current_energy_kwh = (battery_soc / 100.0) * self.battery_capacity_kwh
            target_energy_kwh = current_energy_kwh + energy_to_add_kwh
            
            if target_energy_kwh > self.battery_capacity_kwh:
                logger.debug(f"Preventive charging blocked: insufficient capacity ({target_energy_kwh:.1f} > {self.battery_capacity_kwh} kWh)")
                return None
            
            target_soc = min(100, int((target_energy_kwh / self.battery_capacity_kwh) * 100))
            
            # Economic calculation: charge now vs charge later
            charge_now_cost = current_price * energy_to_add_kwh
            charge_later_cost = period_avg_price * energy_deficit_kwh
            
            savings_pln = charge_later_cost - charge_now_cost
            savings_percent = (savings_pln / charge_later_cost * 100) if charge_later_cost > 0 else 0
            
            # Check if savings meet threshold
            if savings_percent < self.preventive_min_savings_percent:
                logger.debug(
                    f"Preventive charging blocked: savings {savings_percent:.0f}% < "
                    f"threshold {self.preventive_min_savings_percent}%"
                )
                return None
            
            # Preventive charging is beneficial
            hours_to_period = (period_start - current_time).total_seconds() / 3600
            
            reason = (
                f"Preventive charging: save {savings_pln:.2f} PLN ({savings_percent:.0f}%) "
                f"by charging now at {current_price:.3f} vs later at {period_avg_price:.3f} PLN/kWh. "
                f"Battery would drop to {predicted_soc}% during {period_duration:.0f}h expensive period "
                f"starting in {hours_to_period:.1f}h at {period_start.strftime('%H:%M')}"
            )
            
            logger.info(f"⚡ {reason}")
            
            return {
                'should_charge': True,
                'reason': reason,
                'priority': 'medium',
                'confidence': 0.75,
                'preventive_partial': True,
                'target_soc': target_soc,
                'required_kwh': energy_to_add_kwh,
                'savings_pln': savings_pln,
                'savings_percent': savings_percent
            }
            
        except Exception as e:
            logger.error(f"Error evaluating preventive partial charging: {e}")
            return None

    def _check_partial_session_limits(self) -> bool:
        """Check if partial charging session limits allow another session today"""
        try:
            import json
            import os
            from pathlib import Path
            
            # Ensure data directory exists
            session_file_path = Path(self.partial_session_tracking_file)
            session_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load session tracking data
            if session_file_path.exists():
                with open(session_file_path, 'r') as f:
                    session_data = json.load(f)
            else:
                session_data = {'sessions': []}
            
            # Get current date in Warsaw timezone
            current_time = datetime.now(self.warsaw_tz)
            current_date = current_time.date()
            
            # Get daily reset hour in Warsaw timezone
            reset_time = current_time.replace(hour=self.partial_daily_reset_hour, minute=0, second=0, microsecond=0)
            if current_time.hour < self.partial_daily_reset_hour:
                # Before reset time, use yesterday's date for comparison
                reset_time = reset_time - timedelta(days=1)
            
            # Filter sessions for current day (after reset time)
            today_sessions = []
            for session in session_data['sessions']:
                try:
                    session_time = datetime.fromisoformat(session['timestamp'])
                    # Make timezone-aware if not already
                    if session_time.tzinfo is None:
                        session_time = self.warsaw_tz.localize(session_time)
                    
                    if session_time >= reset_time:
                        today_sessions.append(session)
                except Exception as e:
                    logger.debug(f"Error parsing session timestamp: {e}")
                    continue
            
            # Check if we've reached the limit
            if len(today_sessions) >= self.partial_max_sessions_per_day:
                logger.info(f"Partial charging limit reached: {len(today_sessions)}/{self.partial_max_sessions_per_day} sessions today")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking partial session limits: {e}")
            # On error, allow charging (fail open)
            return True
    
    def _record_partial_charging_session(self):
        """Record a partial charging session in the tracking file"""
        try:
            import json
            from pathlib import Path
            
            session_file_path = Path(self.partial_session_tracking_file)
            session_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing data
            if session_file_path.exists():
                with open(session_file_path, 'r') as f:
                    session_data = json.load(f)
            else:
                session_data = {'sessions': []}
            
            # Add new session
            current_time = datetime.now(self.warsaw_tz)
            session_data['sessions'].append({
                'timestamp': current_time.isoformat(),
                'date': current_time.date().isoformat()
            })
            
            # Save updated data
            with open(session_file_path, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info(f"Recorded partial charging session at {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
        except Exception as e:
            logger.error(f"Error recording partial charging session: {e}")
        
    async def initialize(self) -> bool:
        """Initialize the system and connect to inverter"""
        logger.info("Initializing automated price-based charging system...")
        
        # Connect to GoodWe inverter
        if not await self.goodwe_charger.connect_inverter():
            logger.error("Failed to connect to GoodWe inverter")
            return False
        
        logger.info("Successfully connected to GoodWe inverter")
        return True
    
    def fetch_today_prices(self) -> Optional[Dict]:
        """Fetch today's electricity prices from Polish market using RCE-PLN API"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            # CSDAC-PLN API uses business_date field for filtering
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{today}'"
            
            logger.info(f"Fetching CSDAC price data for {today}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('value', []))} CSDAC price points")
            
            # Record prices for adaptive threshold calculation
            if self.adaptive_enabled and self.price_history and data:
                try:
                    for item in data.get('value', []):
                        timestamp = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                        price_pln_kwh = float(item['csdac_pln']) / 1000  # Convert MWh to kWh
                        self.price_history.add_price_point(timestamp, price_pln_kwh)
                except Exception as e:
                    logger.debug(f"Failed to record price history: {e}")
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch CSDAC price data: {e}")
            return None
    
    def _update_adaptive_thresholds(self, force: bool = False) -> None:
        """
        Update adaptive thresholds from recent price history.
        
        Args:
            force: Force update regardless of time interval
        """
        if not self.adaptive_enabled:
            return
        
        current_time = time.time()
        if not force and current_time - self.last_threshold_update < self.threshold_update_interval:
            return  # Not time to update yet
        
        try:
            price_stats = self.price_history.calculate_statistics()
            
            if price_stats['sample_count'] < self.price_history.min_samples:
                logger.warning(
                    f"Insufficient price samples ({price_stats['sample_count']}/{self.price_history.min_samples}), "
                    f"using fallback thresholds"
                )
                return  # Keep using fallback or previous thresholds
            
            # Calculate new thresholds
            self.adaptive_high_price_threshold = self.threshold_calculator.calculate_high_price_threshold(price_stats)
            self.adaptive_critical_price = self.threshold_calculator.calculate_critical_price_threshold(price_stats)
            
            self.last_threshold_update = current_time
            
            # Get calculation info for logging
            calc_info = self.threshold_calculator.get_calculation_info(price_stats)
            
            logger.info(
                f"📊 Updated adaptive thresholds: "
                f"high={self.adaptive_high_price_threshold:.3f} PLN/kWh, "
                f"critical={self.adaptive_critical_price:.3f} PLN/kWh "
                f"(season={calc_info['season']}, "
                f"seasonal_mult={calc_info['seasonal_multiplier']:.2f}x, "
                f"median={price_stats['median']:.3f} PLN/kWh, "
                f"samples={price_stats['sample_count']})"
            )
        except Exception as e:
            logger.error(f"Failed to update adaptive thresholds: {e}")
    
    def get_high_price_threshold(self) -> float:
        """
        Get current high price threshold (adaptive or fixed).
        
        Returns:
            High price threshold in PLN/kWh
        """
        # Update thresholds if needed (checks interval internally)
        if self.adaptive_enabled:
            self._update_adaptive_thresholds()
        
        # Return adaptive threshold if available, otherwise fallback to fixed
        if self.adaptive_enabled and self.adaptive_high_price_threshold is not None:
            return self.adaptive_high_price_threshold
        return self.high_price_threshold
    
    def get_critical_price_threshold(self) -> float:
        """
        Get current critical charging price threshold (adaptive or fixed).
        
        Returns:
            Critical price threshold in PLN/kWh
        """
        # Update thresholds if needed (checks interval internally)
        if self.adaptive_enabled:
            self._update_adaptive_thresholds()
        
        # Return adaptive threshold if available, otherwise fallback to fixed
        if self.adaptive_enabled and self.adaptive_critical_price is not None:
            return self.adaptive_critical_price
        return self.max_critical_price
    
    def analyze_charging_windows(self, price_data: Dict, 
                               target_hours: float = 4.0,
                               max_price_threshold: Optional[float] = None) -> List[Dict]:
        """Analyze price data and find optimal charging windows"""
        
        if not price_data or 'value' not in price_data:
            return []
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            # Calculate final prices (market price + SC component + distribution) for threshold calculation
            final_prices = [
                self.calculate_final_price(
                    float(item['csdac_pln']), 
                    datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                ) 
                for item in price_data['value']
            ]
            max_price_threshold = sorted(final_prices)[int(len(final_prices) * self.charging_threshold_percentile)]
        
        target_minutes = int(target_hours * 60)
        window_size = target_minutes // 15  # Number of 15-minute periods
        
        logger.info(f"Finding charging windows of {target_hours}h at max price {max_price_threshold:.2f} PLN/MWh (including tariff pricing)")
        
        charging_windows = []
        
        # Slide through all possible windows
        for i in range(len(price_data['value']) - window_size + 1):
            window_data = price_data['value'][i:i + window_size]
            # Calculate final prices (market price + SC component + distribution) for each window
            window_final_prices = [
                self.calculate_final_price(
                    float(item['csdac_pln']), 
                    datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                ) 
                for item in window_data
            ]
            avg_price = sum(window_final_prices) / len(window_final_prices)
            
            # Check if window meets criteria
            if avg_price <= max_price_threshold:
                start_time = datetime.strptime(window_data[0]['dtime'], '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(window_data[-1]['dtime'], '%Y-%m-%d %H:%M') + timedelta(minutes=15)
                
                # Calculate savings using final prices (market price + SC component + distribution)
                all_final_prices = [
                    self.calculate_final_price(
                        float(item['csdac_pln']), 
                        datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                    ) 
                    for item in price_data['value']
                ]
                overall_avg = sum(all_final_prices) / len(all_final_prices)
                savings = overall_avg - avg_price
                
                window = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_minutes': target_minutes,
                    'avg_price': avg_price,
                    'savings': savings,
                    'savings_percent': (savings / overall_avg) * 100
                }
                charging_windows.append(window)
        
        # Sort by savings (highest first)
        charging_windows.sort(key=lambda x: x['savings'], reverse=True)
        
        logger.info(f"Found {len(charging_windows)} optimal charging windows")
        return charging_windows
    
    def get_current_price(self, price_data: Dict, kompas_status: Optional[str] = None) -> Optional[float]:
        """Get current electricity price including SC component and distribution"""
        if not price_data or 'value' not in price_data:
            return None
        
        now = datetime.now()
        current_time = now.replace(second=0, microsecond=0)
        
        # Find the current 15-minute period
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            if item_time <= current_time < item_time + timedelta(minutes=15):
                market_price_pln_mwh = float(item['csdac_pln'])
                # Calculate final price with tariff-aware pricing
                final_price_pln_mwh = self.calculate_final_price(market_price_pln_mwh, item_time, kompas_status)
                # Return in PLN/MWh for consistency with other methods
                return final_price_pln_mwh
        
        return None
    
    def should_start_charging(self, price_data: Dict, 
                            max_price_threshold: Optional[float] = None,
                            kompas_status: Optional[str] = None) -> bool:
        """Determine if charging should start based on current price"""
        
        current_price = self.get_current_price(price_data, kompas_status)
        if current_price is None:
            logger.warning("Could not determine current price")
            return False
        
        # Calculate price threshold if not provided
        if max_price_threshold is None:
            # Calculate final prices (market price + SC component + distribution) for threshold calculation
            final_prices = [
                self.calculate_final_price(
                    float(item['csdac_pln']), 
                    datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M'),
                    kompas_status
                ) 
                for item in price_data['value']
            ]
            max_price_threshold = sorted(final_prices)[int(len(final_prices) * self.charging_threshold_percentile)]
        
        should_charge = current_price <= max_price_threshold
        
        logger.info(f"Current price: {current_price:.2f} PLN/MWh, Threshold: {max_price_threshold:.2f} PLN/MWh, Should charge: {should_charge}")
        
        return should_charge
    
    def make_smart_charging_decision(self, current_data: Dict, price_data: Dict) -> Dict[str, any]:
        """
        Make intelligent charging decision using smart strategy
        Considers PV overproduction, consumption patterns, and price optimization
        """
        try:
            logger.info("Making smart charging decision...")
            
            # Extract current system state with type conversion
            battery_soc = self._safe_float(current_data.get('battery', {}).get('soc_percent', 0))
            pv_power = self._safe_float(current_data.get('photovoltaic', {}).get('current_power_w', 0))
            house_consumption = self._safe_float(current_data.get('house_consumption', {}).get('current_power_w', 0))
            grid_power = self._safe_float(current_data.get('grid', {}).get('power_w', 0))
            grid_direction = current_data.get('grid', {}).get('flow_direction', 'Unknown')
            
            # Calculate overproduction
            overproduction = pv_power - house_consumption
            
            # Get current and future prices
            current_price, cheapest_price, cheapest_hour = self._analyze_prices(price_data)
            
            # Make charging decision
            decision = self._make_charging_decision(
                battery_soc=battery_soc,
                overproduction=overproduction,
                grid_power=grid_power,
                grid_direction=grid_direction,
                current_price=current_price,
                cheapest_price=cheapest_price,
                cheapest_hour=cheapest_hour,
                price_data=price_data  # Pass full price data for enhanced logic
            )
            
            # Store decision in history
            self.decision_history.append({
                'timestamp': datetime.now(),
                'decision': decision,
                'current_data': current_data
            })
            
            # Keep only last 10 decisions
            if len(self.decision_history) > 10:
                self.decision_history = self.decision_history[-10:]
            
            # Record partial charging session if decision indicates partial charge
            if decision.get('should_charge') and decision.get('partial_charge'):
                self._record_partial_charging_session()
                logger.info(
                    f"Partial charging session recorded: "
                    f"target SOC {decision.get('target_soc', 'unknown')}%, "
                    f"required {decision.get('required_kwh', 'unknown')} kWh, "
                    f"until {decision.get('next_window', 'unknown')}"
                )
            
            logger.info(f"Smart charging decision: {decision['should_charge']} - {decision['reason']}")
            logger.info(f"Priority: {decision['priority']}, Confidence: {decision['confidence']:.1%}")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error making smart charging decision: {e}")
            return {
                'should_charge': False,
                'reason': f'Error in decision making: {e}',
                'priority': 'low',
                'confidence': 0.0
            }
    
    def _analyze_prices(self, price_data: Dict) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        """Analyze current and future prices"""
        try:
            if not price_data or 'value' not in price_data:
                return None, None, None
            
            current_hour = datetime.now().hour
            prices_raw = price_data['value']
            
            # Convert to hourly averages with tariff-aware pricing
            hourly_prices = {}
            for entry in prices_raw:
                hour = int(entry['dtime'].split(' ')[1].split(':')[0])
                market_price_pln_mwh = entry['csdac_pln']  # Already in PLN/MWh
                entry_time = datetime.strptime(entry['dtime'], '%Y-%m-%d %H:%M')
                # Use tariff-aware pricing
                final_price_pln_mwh = self.calculate_final_price(market_price_pln_mwh, entry_time)
                price_pln_kwh = final_price_pln_mwh / 1000  # Convert to PLN/kWh for display
                
                if hour not in hourly_prices:
                    hourly_prices[hour] = []
                hourly_prices[hour].append(price_pln_kwh)
            
            # Calculate average price per hour
            hourly_avg = {}
            for hour, prices in hourly_prices.items():
                hourly_avg[hour] = sum(prices) / len(prices)
            
            # Get current price
            current_price = hourly_avg.get(current_hour)
            
            # Find cheapest price in next 8 hours
            next_hours = [(h, p) for h, p in hourly_avg.items() 
                         if h >= current_hour and h < current_hour + 8]
            
            if next_hours:
                cheapest_hour, cheapest_price = min(next_hours, key=lambda x: x[1])
                return current_price, cheapest_price, cheapest_hour
            
            return current_price, None, None
            
        except Exception as e:
            logger.error(f"Error analyzing prices: {e}")
            return None, None, None
        
        # Decision logic for critical battery
        critical_threshold = self.get_critical_price_threshold()
        if current_price <= critical_threshold:
            # Price is acceptable for critical charging
            return {
                'should_charge': True,
                'reason': f'Critical battery ({battery_soc}%) + acceptable price ({current_price:.3f} PLN/kWh ≤ {critical_threshold:.3f} PLN/kWh)',
                'priority': 'critical',
                'confidence': 0.9
            }
        
        # Enhanced decision logic with weather and PV forecast consideration
        else:
            # Calculate dynamic maximum wait time based on savings and battery level
            max_wait_hours = self._calculate_dynamic_max_wait_hours(savings_percent, battery_soc)
            
            # Check if we should wait for better price
            should_wait_for_price = (hours_to_wait <= max_wait_hours and 
                                   savings_percent >= self.min_price_savings_percent)
            
            # Check if we should wait for PV improvement (weather-aware)
            should_wait_for_pv = self._should_wait_for_pv_improvement_critical(battery_soc, hours_to_wait)
            
            # Decision logic
            if should_wait_for_pv and should_wait_for_price:
                # Both PV and price will improve - wait for the better option
                if hours_to_wait <= 2:  # Price improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Critical battery ({battery_soc}%) but much cheaper price in {hours_to_wait}h ({cheapest_price:.3f} vs {current_price:.3f} PLN/kWh, {savings_percent:.1f}% savings) + PV improving soon',
                        'priority': 'critical',
                        'confidence': 0.8
                    }
                else:  # PV improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Critical battery ({battery_soc}%) but PV production improving soon + good price savings in {hours_to_wait}h ({savings_percent:.1f}% savings)',
                        'priority': 'critical',
                        'confidence': 0.7
                    }
            
            elif should_wait_for_pv:
                # Only PV will improve - wait for PV
                return {
                    'should_charge': False,
                    'reason': f'Critical battery ({battery_soc}%) but PV production improving soon - waiting for free solar charging',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            elif should_wait_for_price:
                # Only price will improve - wait for better price
                return {
                    'should_charge': False,
                    'reason': f'Critical battery ({battery_soc}%) but much cheaper price in {hours_to_wait}h ({cheapest_price:.3f} vs {current_price:.3f} PLN/kWh, {savings_percent:.1f}% savings)',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            else:
                # Neither PV nor price will improve significantly - charge now
                return {
                    'should_charge': True,
                    'reason': f'Critical battery ({battery_soc}%) + high price ({current_price:.3f} PLN/kWh) but waiting {hours_to_wait}h for {savings_percent:.1f}% savings not optimal + no PV improvement expected',
                    'priority': 'critical',
                    'confidence': 0.8
                }

    def _check_proactive_charging_conditions(self, battery_soc: int, overproduction: int, 
                                           current_price: Optional[float], cheapest_price: Optional[float], 
                                           cheapest_hour: Optional[int]) -> Optional[Dict[str, any]]:
        """Check if proactive charging conditions are met"""
        
        # Get current PV power (assuming it's passed as negative overproduction)
        current_pv_power = abs(overproduction) if overproduction < 0 else 0
        
        # Condition 1: PV is poor (below threshold)
        if current_pv_power > self.pv_poor_threshold:
            return None  # PV is good, no need for proactive charging
        
        # Condition 2: Battery is below target threshold
        if battery_soc >= self.battery_target_threshold:
            return None  # Battery is already well charged
        
        # Condition 3: Price is not high (below max proactive price)
        if not current_price or current_price > self.max_proactive_price:
            return None  # Price is too high for proactive charging
        
        # Condition 4: Weather won't improve significantly in next few hours
        # This is a simplified check - in real implementation, you'd check weather forecast
        # For now, we'll assume if PV is poor now, it won't improve much
        weather_will_improve = self._check_weather_improvement()
        if weather_will_improve:
            return None  # Weather will improve, wait for PV
        
        # All conditions met - proactive charging recommended
        return {
            'should_charge': True,
            'reason': f'Proactive charging: PV poor ({current_pv_power}W < {self.pv_poor_threshold}W), battery low ({battery_soc}% < {self.battery_target_threshold}%), price good ({current_price:.3f} PLN/kWh ≤ {self.max_proactive_price} PLN/kWh), weather poor',
            'priority': 'proactive',
            'confidence': 0.8
        }
    
    def _calculate_dynamic_max_wait_hours(self, savings_percent: float, battery_soc: int) -> float:
        """Calculate dynamic maximum wait time based on savings and battery level"""
        # Base wait time from configuration
        base_wait_hours = self.max_wait_hours
        
        # Adjust based on savings percentage
        if savings_percent >= 80:
            # Very high savings - can wait longer
            savings_multiplier = 1.5
        elif savings_percent >= 60:
            # High savings - can wait moderately longer
            savings_multiplier = 1.2
        elif savings_percent >= 40:
            # Medium savings - use base wait time
            savings_multiplier = 1.0
        else:
            # Low savings - reduce wait time
            savings_multiplier = 0.7
        
        # Adjust based on battery level (lower battery = shorter wait)
        if battery_soc <= 8:
            # Very critical - reduce wait time significantly
            battery_multiplier = 0.5
        elif battery_soc <= 10:
            # Critical - reduce wait time moderately
            battery_multiplier = 0.7
        else:
            # Less critical - use full wait time
            battery_multiplier = 1.0
        
        # Calculate final wait time
        max_wait_hours = base_wait_hours * savings_multiplier * battery_multiplier
        
        # Ensure reasonable bounds (1-12 hours)
        return max(1.0, min(12.0, max_wait_hours))
    
    def _should_wait_for_pv_improvement_critical(self, battery_soc: int, hours_to_wait: float) -> bool:
        """Check if we should wait for PV improvement during critical battery levels"""
        try:
            # For very critical battery levels (≤8%), be more conservative
            if battery_soc <= 8:
                return False  # Don't wait for PV at very critical levels
            
            # For critical levels (9-12%), check PV forecast
            if battery_soc <= 12:
                # Check current time - don't wait for PV if it's late in the day
                current_hour = datetime.now().hour
                if current_hour >= 18:  # After 6 PM, don't wait for PV
                    return False
                
                # Check if we're in a period where PV typically improves
                if 6 <= current_hour <= 16:  # Between 6 AM and 4 PM
                    # Try to get weather and PV forecast data if available
                    # This integrates with the existing weather and PV forecast system
                    try:
                        # Check if we have access to weather data and PV forecast
                        # This would be passed from the calling context in a real implementation
                        # For now, use time-based heuristics with some weather awareness
                        
                        # Morning hours (6-12) - PV typically improving significantly
                        if current_hour <= 12:
                            # Check if it's early enough that PV has room to improve
                            if current_hour <= 10:  # Very early morning - high PV improvement potential
                                return True
                            elif current_hour <= 11:  # Late morning - moderate PV improvement potential
                                return True
                            else:  # Noon - PV at or near peak
                                return False
                        
                        # Early afternoon (13-16) - PV might still improve or be stable
                        elif current_hour <= 14:  # Early afternoon - PV might still improve
                            return True
                        else:  # Late afternoon - PV typically declining
                            return False
                    except Exception as e:
                        logger.warning(f"Failed to check weather/PV forecast: {e}")
                        # Fallback to time-based heuristic
                        return current_hour <= 12
                else:
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check PV improvement: {e}")
            return False

    def _check_weather_improvement(self) -> bool:
        """Check if weather will improve in the next few hours"""
        # This is a simplified implementation
        # In a real system, you would:
        # 1. Get weather forecast for next 6 hours
        # 2. Check cloud cover, precipitation, solar irradiance
        # 3. Determine if PV production will improve significantly
        
        # For now, return False (weather won't improve) to enable proactive charging
        # This can be enhanced with actual weather data integration
        return False

    def _check_weather_stability(self) -> bool:
        """Check if weather conditions are stable for PV charging"""
        # This is a simplified implementation
        # In a real system, you would:
        # 1. Get weather forecast for next 2-4 hours
        # 2. Check cloud cover trends (stable vs increasing)
        # 3. Check precipitation probability
        # 4. Check wind conditions (affects PV efficiency)
        
        # For now, return True (weather stable) to enable PV preference
        # This can be enhanced with actual weather data integration
        return True

    def _check_house_usage_low(self) -> bool:
        """Check if house usage is low enough for PV charging"""
        # This is a simplified implementation
        # In a real system, you would:
        # 1. Get current house consumption
        # 2. Check if PV power > house consumption + charging needs
        # 3. Consider forecasted consumption patterns
        
        # For now, return True (house usage low) to enable PV preference
        # This can be enhanced with actual consumption data integration
        return True

    def _check_super_low_price_conditions(self, battery_soc: int, overproduction: int, 
                                         current_price: Optional[float], cheapest_price: Optional[float], 
                                         cheapest_hour: Optional[int]) -> Optional[Dict[str, any]]:
        """Check if super low price charging conditions are met with PV preference logic"""
        
        # Condition 1: Current price is super low
        if not current_price or current_price > self.super_low_price_threshold:
            return None  # Price is not super low
        
        # Condition 2: Battery is not already at target SOC
        if battery_soc >= self.super_low_price_target_soc:
            return None  # Battery is already fully charged
        
        # Condition 3: Super low price period has sufficient duration
        if cheapest_hour:
            hours_to_wait = cheapest_hour - datetime.now().hour
            if hours_to_wait < 0:
                hours_to_wait += 24  # Next day
            
            # Check if super low price period is long enough
            if hours_to_wait < self.super_low_price_min_duration:
                return None  # Super low price period too short
        
        # Get current conditions
        current_pv_power = abs(overproduction) if overproduction < 0 else 0
        battery_capacity = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)
        charging_rate = 3.0  # kW (configurable)
        
        # Calculate energy needed to reach target SOC
        energy_needed = (self.super_low_price_target_soc - battery_soc) / 100 * battery_capacity
        
        # Calculate charging times
        if current_pv_power > 0:
            pv_charging_time = energy_needed / (current_pv_power / 1000)  # Convert W to kW
        else:
            pv_charging_time = float('inf')  # No PV available
        
        grid_charging_time = energy_needed / charging_rate
        
        # NEW LOGIC: Check if PV conditions are excellent for charging
        pv_excellent = current_pv_power >= self.pv_excellent_threshold  # PV power ≥ 3kW
        weather_stable = self._check_weather_stability()  # Weather stability check
        house_usage_low = self._check_house_usage_low()  # House usage check
        
        # Decision logic with PV preference
        if pv_excellent and weather_stable and house_usage_low:
            # PV is excellent, weather is stable, house usage is low - prefer PV charging
            if pv_charging_time <= self.pv_charging_time_limit:
                # PV can charge fully within time limit - use PV charging
                return {
                    'should_charge': True,
                    'reason': f'Super low price ({current_price:.3f} PLN/kWh) + PV excellent ({current_pv_power}W) + weather stable + house usage low - charging from PV to {self.super_low_price_target_soc}%',
                    'priority': 'super_low_price_pv',
                    'confidence': 0.9,
                    'charging_source': 'pv',
                    'target_soc': self.super_low_price_target_soc,
                    'estimated_cost': 0.0,  # PV charging is free
                    'energy_needed': energy_needed,
                    'charging_time_hours': pv_charging_time
                }
            else:
                # PV excellent but takes too long - use grid charging for speed
                return {
                    'should_charge': True,
                    'reason': f'Super low price ({current_price:.3f} PLN/kWh) + PV excellent ({current_pv_power}W) but slow ({pv_charging_time:.1f}h > {self.pv_charging_time_limit}h) - charging from grid to {self.super_low_price_target_soc}%',
                    'priority': 'super_low_price_grid',
                    'confidence': 0.95,
                    'charging_source': 'grid',
                    'target_soc': self.super_low_price_target_soc,
                    'estimated_cost': current_price * energy_needed,
                    'energy_needed': energy_needed,
                    'charging_time_hours': grid_charging_time
                }
        else:
            # PV not excellent or conditions not ideal - use grid charging
            pv_conditions = []
            if not pv_excellent:
                pv_conditions.append(f"PV insufficient ({current_pv_power}W < {self.pv_excellent_threshold}W)")
            if not weather_stable:
                pv_conditions.append("weather unstable")
            if not house_usage_low:
                pv_conditions.append("house usage high")
            
            return {
                'should_charge': True,
                'reason': f'Super low price ({current_price:.3f} PLN/kWh) + {", ".join(pv_conditions)} - charging from grid to {self.super_low_price_target_soc}%',
                'priority': 'super_low_price_grid',
                'confidence': 0.95,
                'charging_source': 'grid',
                'target_soc': self.super_low_price_target_soc,
                'estimated_cost': current_price * energy_needed,
                'energy_needed': energy_needed,
                'charging_time_hours': grid_charging_time
            }

    def _check_aggressive_cheapest_price_conditions(self, battery_soc: int, current_price: Optional[float], 
                                                   cheapest_price: Optional[float], cheapest_hour: Optional[int]) -> bool:
        """Check if aggressive charging conditions are met during cheapest price periods"""
        
        # Check if aggressive cheapest price charging is enabled
        if not self.aggressive_cheapest_enabled:
            return False
        
        # Need price data to make decision
        if not current_price or not cheapest_price:
            return False
        
        # Check if battery SOC is within acceptable range for aggressive charging
        if battery_soc < self.min_battery_soc_for_aggressive or battery_soc > self.max_battery_soc_for_aggressive:
            return False
        
        # Check if current price is close enough to cheapest price
        price_difference = abs(current_price - cheapest_price)
        if price_difference > self.max_price_difference_pln:
            return False
        
        # Check if we're currently at or very close to the cheapest hour
        current_hour = datetime.now().hour
        if cheapest_hour is not None:
            # Allow charging if we're at the cheapest hour or within 1 hour of it
            hour_difference = abs(current_hour - cheapest_hour)
            if hour_difference > 1:
                return False
        
        logger.info(f"Aggressive cheapest price conditions met: SOC={battery_soc}%, current_price={current_price:.3f}, cheapest_price={cheapest_price:.3f} PLN/kWh")
        return True

    def _smart_critical_charging_decision(self, battery_soc: int, current_price: Optional[float],
                                        cheapest_price: Optional[float], cheapest_hour: Optional[int]) -> Dict[str, any]:
        """Smart critical charging decision that considers price, timing, weather, and PV forecast"""
        
        if not self.smart_critical_enabled:
            # Fallback to old behavior if smart critical charging is disabled
            return {
                'should_charge': True,
                'reason': f'Critical battery level ({battery_soc}% < {self.critical_battery_threshold}%) - smart charging disabled',
                'priority': 'critical',
                'confidence': 1.0
            }
        
        # If no price data available, charge immediately for safety
        if not current_price or not cheapest_price or not cheapest_hour:
            return {
                'should_charge': True,
                'reason': f'Critical battery level ({battery_soc}%) - no price data available',
                'priority': 'critical',
                'confidence': 0.8
            }
        
        # Calculate savings and timing
        savings_percent = self._calculate_savings(current_price, cheapest_price)
        hours_to_wait = cheapest_hour - datetime.now().hour
        if hours_to_wait < 0:
            hours_to_wait += 24  # Next day
        
        # OPTIMIZATION RULE 1: At 10% SOC with high price, always wait for price drop
        if (self.wait_at_10_percent_if_high_price and 
            battery_soc == 10 and 
            current_price > self.get_high_price_threshold()):
            high_threshold = self.get_high_price_threshold()
            return {
                'should_charge': False,
                'reason': f'Critical battery (10%) but high price ({current_price:.3f} PLN/kWh > {high_threshold:.3f} PLN/kWh) - waiting for price drop',
                'priority': 'critical',
                'confidence': 0.9
            }
        
        # Decision logic for critical battery
        critical_threshold = self.get_critical_price_threshold()
        if current_price <= critical_threshold:
            # Price is acceptable for critical charging
            return {
                'should_charge': True,
                'reason': f'Critical battery ({battery_soc}%) + acceptable price ({current_price:.3f} PLN/kWh ≤ {critical_threshold:.3f} PLN/kWh)',
                'priority': 'critical',
                'confidence': 0.9
            }
        
        # Enhanced decision logic with weather and PV forecast consideration
        else:
            # Calculate dynamic maximum wait time based on savings and battery level
            max_wait_hours = self._calculate_dynamic_max_wait_hours(savings_percent, battery_soc)
            
            # Check if we should wait for better price
            should_wait_for_price = (hours_to_wait <= max_wait_hours and 
                                   savings_percent >= self.min_price_savings_percent)
            
            # Check if we should wait for PV improvement (weather-aware)
            should_wait_for_pv = self._should_wait_for_pv_improvement_critical(battery_soc, hours_to_wait)
            
            # Decision logic
            if should_wait_for_pv and should_wait_for_price:
                # Both PV and price will improve - wait for the better option
                if hours_to_wait <= 2:  # Price improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Critical battery ({battery_soc}%) but much cheaper price in {hours_to_wait}h ({cheapest_price:.3f} vs {current_price:.3f} PLN/kWh, {savings_percent:.1f}% savings) + PV improving soon',
                        'priority': 'critical',
                        'confidence': 0.8
                    }
                else:  # PV improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Critical battery ({battery_soc}%) but PV production improving soon + good price savings in {hours_to_wait}h ({savings_percent:.1f}% savings)',
                        'priority': 'critical',
                        'confidence': 0.7
                    }
            
            elif should_wait_for_pv:
                # Only PV will improve - wait for PV
                return {
                    'should_charge': False,
                    'reason': f'Critical battery ({battery_soc}%) but PV production improving soon - waiting for free solar charging',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            elif should_wait_for_price:
                # Only price will improve - wait for better price
                return {
                    'should_charge': False,
                    'reason': f'Critical battery ({battery_soc}%) but much cheaper price in {hours_to_wait}h ({cheapest_price:.3f} vs {current_price:.3f} PLN/kWh, {savings_percent:.1f}% savings)',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            else:
                # Neither PV nor price will improve significantly - charge now
                return {
                    'should_charge': True,
                    'reason': f'Critical battery ({battery_soc}%) + high price ({current_price:.3f} PLN/kWh) but waiting {hours_to_wait}h for {savings_percent:.1f}% savings not optimal + no PV improvement expected',
                    'priority': 'critical',
                    'confidence': 0.8
                }

    def _calculate_dynamic_max_wait_hours(self, savings_percent: float, battery_soc: int) -> float:
        """Calculate dynamic maximum wait time based on savings and battery level"""
        # Base wait time from configuration
        base_wait_hours = self.max_wait_hours
        
        # Adjust based on savings percentage
        if savings_percent >= 80:
            savings_multiplier = 1.5
        elif savings_percent >= 60:
            savings_multiplier = 1.2
        elif savings_percent >= 40:
            savings_multiplier = 1.0
        else:
            savings_multiplier = 0.7
        
        # Adjust based on battery level (lower battery = shorter wait)
        if battery_soc <= 8:
            battery_multiplier = 0.5
        elif battery_soc <= 10:
            battery_multiplier = 0.7
        else:
            battery_multiplier = 1.0
        
        # Calculate final wait time
        max_wait_hours = base_wait_hours * savings_multiplier * battery_multiplier
        
        # Ensure reasonable bounds (1-12 hours)
        return max(1.0, min(12.0, max_wait_hours))
    
    def _should_wait_for_pv_improvement_critical(self, battery_soc: int, hours_to_wait: float) -> bool:
        """Check if we should wait for PV improvement during critical battery levels"""
        try:
            # For very critical battery levels (≤8%), be more conservative
            if battery_soc <= 8:
                return False  # Don't wait for PV at very critical levels
            
            # For critical levels (9-12%), check PV forecast
            if battery_soc <= 12:
                # Check current time - don't wait for PV if it's late in the day
                current_hour = datetime.now().hour
                if current_hour >= 18:  # After 6 PM, don't wait for PV
                    return False
                
                # Check if we're in a period where PV typically improves
                if 6 <= current_hour <= 16:  # Between 6 AM and 4 PM
                    # Simple heuristic: assume PV can improve during daylight hours
                    return True
                    
            return False
        except Exception as e:
            logger.error(f"Error checking PV improvement for critical battery: {e}")
            return False

    def _make_charging_decision(self, battery_soc: int, overproduction: int, grid_power: int,
                              grid_direction: str, current_price: Optional[float],
                              cheapest_price: Optional[float], cheapest_hour: Optional[int],
                              price_data: Optional[Dict] = None) -> Dict[str, any]:
        """Make the final charging decision based on all factors"""
        
        # ACTIVE CHARGING: If already charging, check if we should continue or stop
        if self.is_charging:
            # Check if we should stop charging (target SOC reached, price too high, etc.)
            if battery_soc >= 90:  # Near full
                return {
                    'should_charge': False,
                    'reason': f'Battery nearly full ({battery_soc}%) - stop charging',
                    'priority': 'high',
                    'confidence': 0.95
                }
            
            # Check if protected charging session is active
            if self.is_charging_session_protected():
                return {
                    'should_charge': True,
                    'reason': f'Protected charging session active - continue charging (SOC: {battery_soc}%)',
                    'priority': 'high',
                    'confidence': 0.9
                }
            
            # Continue charging if still within reasonable conditions
            return {
                'should_charge': True,
                'reason': f'Charging in progress - continuing (SOC: {battery_soc}%)',
                'priority': 'medium',
                'confidence': 0.8
            }
        
        # EMERGENCY: Battery below emergency threshold - always charge regardless of price
        if battery_soc < self.emergency_battery_threshold:
            return {
                'should_charge': True,
                'reason': f'Emergency battery level ({battery_soc}% < {self.emergency_battery_threshold}%) - charging immediately',
                'priority': 'emergency',
                'confidence': 1.0
            }
        
        # CRITICAL: Battery below critical threshold - smart price-aware charging
        if battery_soc < self.critical_battery_threshold:
            return self._smart_critical_charging_decision(
                battery_soc, current_price, cheapest_price, cheapest_hour
            )
        
        # MULTI-WINDOW INTERIM COST ANALYSIS: Evaluate future charging windows accounting for interim grid costs
        interim_decision = None
        if self.interim_cost_enabled and price_data and current_price:
            interim_decision = self._evaluate_multi_window_with_interim_cost(
                battery_soc, current_price, price_data
            )
            if interim_decision:
                return interim_decision
        
        # PREVENTIVE PARTIAL CHARGING: Charge now during cheap window to avoid expensive charging later
        if (not self.interim_cost_enabled or not interim_decision) and self.preventive_partial_enabled and 30 <= battery_soc <= 60 and price_data and current_price:
            preventive_decision = self._evaluate_preventive_partial_charging(
                battery_soc, current_price, price_data, datetime.now()
            )
            if preventive_decision:
                logger.info(f"⚡ Preventive partial charging triggered: {preventive_decision['reason']}")
                return preventive_decision
        
        # HIGH: PV overproduction - no need to charge from grid (check BEFORE aggressive charging)
        if overproduction > self.overproduction_threshold:
            return {
                'should_charge': False,
                'reason': f'PV overproduction ({overproduction}W > {self.overproduction_threshold}W) - no grid charging needed',
                'priority': 'high',
                'confidence': 0.9
            }

        # ENHANCED AGGRESSIVE CHEAPEST PRICE CHARGING: Use new smart logic
        if self.enhanced_aggressive:
            try:
                # Get price forecast if available
                forecast_data = None
                try:
                    from pse_price_forecast_collector import PSEPriceForecastCollector
                    forecast_collector = PSEPriceForecastCollector(self.config)
                    forecast_points = forecast_collector.fetch_price_forecast()
                    if forecast_points:
                        forecast_data = [{'price': p.forecasted_price_pln, 'time': p.time, 'confidence': p.confidence}
                                       for p in forecast_points]
                except Exception as e:
                    logger.debug(f"Could not fetch forecast data: {e}")

                # Make enhanced aggressive charging decision
                decision = self.enhanced_aggressive.should_charge_aggressively(
                    battery_soc=battery_soc,
                    price_data=price_data if price_data else {'value': []},  # Pass actual price data
                    forecast_data=forecast_data,
                    current_data={'battery': {'soc_percent': battery_soc}}
                )

                if decision.should_charge:
                    return {
                        'should_charge': True,
                        'reason': decision.reason,
                        'priority': decision.priority,
                        'confidence': decision.confidence,
                        'target_soc': decision.target_soc,
                        'price_category': decision.price_category.value
                    }
                else:
                    # Enhanced aggressive returned "don't charge" - respect that decision
                    # This prevents legacy fallback from overriding smart decisions about waiting for better windows
                    # The enhanced logic already considered interim costs, future windows, and percentile analysis
                    logger.debug(f"Enhanced aggressive charging decided not to charge: {decision.reason}")
                    # Continue to evaluate other conditions (critical, super_low_price, etc.) but skip legacy fallback
                    pass

            except Exception as e:
                logger.error(f"Error in enhanced aggressive charging: {e}")

        # FALLBACK: Legacy aggressive charging logic (only if enhanced aggressive is not enabled)
        elif self._check_aggressive_cheapest_price_conditions(battery_soc, current_price, cheapest_price, cheapest_hour):
            return {
                'should_charge': True,
                'reason': f'Aggressive charging during cheapest price period (current: {current_price:.3f}, cheapest: {cheapest_price:.3f} PLN/kWh)',
                'priority': 'high',
                'confidence': 0.9
            }

        # HIGH: PV overproduction - no need to charge from grid (duplicated for fallback)
        if overproduction > self.overproduction_threshold:
            return {
                'should_charge': False,
                'reason': f'PV overproduction ({overproduction}W > {self.overproduction_threshold}W) - no grid charging needed',
                'priority': 'high',
                'confidence': 0.9
            }
        
        # HIGH: Significant grid consumption with low battery - but only if price is reasonable
        if (battery_soc < self.low_battery_threshold and 
            grid_direction == 'Import' and grid_power > self.high_consumption_threshold):
            
            # Check if current price is reasonable for charging
            critical_threshold = self.get_critical_price_threshold()
            if current_price and current_price <= critical_threshold:
                return {
                    'should_charge': True,
                    'reason': f'Low battery ({battery_soc}%) + high grid consumption ({grid_power}W) + reasonable price ({current_price:.3f} PLN/kWh)',
                    'priority': 'high',
                    'confidence': 0.8
                }
            else:
                # Price is too high or unavailable - wait for better conditions
                if current_price:
                    reason = f'Low battery ({battery_soc}%) + high consumption ({grid_power}W) but price too high ({current_price:.3f} PLN/kWh > {critical_threshold:.3f} PLN/kWh) - waiting for better price'
                else:
                    reason = f'Low battery ({battery_soc}%) + high consumption ({grid_power}W) but no price data available - waiting for better conditions'
                
                return {
                    'should_charge': False,
                    'reason': reason,
                    'priority': 'medium',
                    'confidence': 0.7
                }
        
        # OPTIMIZATION RULE 3: Super low price grid charging - always charge fully from grid during super low prices
        if self.super_low_price_enabled:
            super_low_decision = self._check_super_low_price_conditions(
                battery_soc, overproduction, current_price, cheapest_price, cheapest_hour
            )
            if super_low_decision:
                return super_low_decision
        
        # OPTIMIZATION RULE 2: Proactive charging when PV is poor, weather won't improve, battery <80%, and price is not high
        if self.proactive_charging_enabled:
            proactive_decision = self._check_proactive_charging_conditions(
                battery_soc, overproduction, current_price, cheapest_price, cheapest_hour
            )
            if proactive_decision:
                return proactive_decision
        
        # MEDIUM: Price analysis
        if current_price and cheapest_price and cheapest_hour:
            savings_percent = self._calculate_savings(current_price, cheapest_price)
            
            # Wait for much better price
            if savings_percent > (self.price_savings_threshold * 100):
                return {
                    'should_charge': False,
                    'reason': f'Much cheaper price available in {cheapest_hour}:00 ({cheapest_price:.3f} vs {current_price:.3f} PLN/kWh, {savings_percent:.1f}% savings)',
                    'priority': 'medium',
                    'confidence': 0.7
                }
            
            # Charge now if price is good enough
            if savings_percent < (self.price_savings_threshold * 50):  # Less than 15% savings
                if battery_soc < self.medium_battery_threshold:
                    return {
                        'should_charge': True,
                        'reason': f'Good price ({current_price:.3f} PLN/kWh) + medium battery ({battery_soc}%)',
                        'priority': 'medium',
                        'confidence': 0.6
                    }
        
        # DEFAULT: Wait for better conditions
        return {
            'should_charge': False,
            'reason': 'Wait for better conditions (PV overproduction, lower prices, or higher consumption)',
            'priority': 'low',
            'confidence': 0.4
        }
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float, handling strings and None"""
        if value is None:
            return 0.0
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0
    
    def _calculate_savings(self, current_price: float, cheapest_price: float) -> float:
        """Calculate potential savings percentage"""
        if not current_price or not cheapest_price or current_price == 0:
            return 0.0
        return ((current_price - cheapest_price) / current_price) * 100
    
    async def start_price_based_charging(self, price_data: Dict, force_start: bool = False) -> bool:
        """Start charging based on current electricity price or force start"""
        
        # Get current battery SOC for logging
        try:
            battery_data = await self.goodwe_charger.get_battery_data()
            battery_soc = battery_data.get('soc_percent', 'Unknown')
        except Exception:
            battery_soc = 'Unknown'
        
        if self.is_charging:
            logger.info(f"Already charging at SOC {battery_soc}%, skipping start request")
            return True
        
        # Check price only if not forced to start (e.g., by master coordinator for critical battery)
        if not force_start and not self.should_start_charging(price_data):
            logger.info(f"🚫 Charging blocked: Current price is not optimal (SOC: {battery_soc}%)")
            logger.info(f"   Reason: Price threshold not met - waiting for better pricing conditions")
            return False
        
        if force_start:
            logger.info(f"⚡ Starting charging due to validated decision (SOC: {battery_soc}%, overriding price check)")
        else:
            logger.info(f"⚡ Starting price-based charging at SOC {battery_soc}%...")
        
        # Start fast charging
        if await self.goodwe_charger.start_fast_charging():
            self.is_charging = True
            self.charging_start_time = datetime.now()
            logger.info(f"✅ Charging started successfully at SOC {battery_soc}%")
            return True
        else:
            logger.error(f"❌ Failed to start charging at SOC {battery_soc}%")
            return False
    
    async def stop_price_based_charging(self) -> bool:
        """Stop price-based charging"""
        
        if not self.is_charging:
            logger.info("Not currently charging")
            return True
        
        logger.info("Stopping price-based charging...")
        
        if await self.goodwe_charger.stop_fast_charging():
            self.is_charging = False
            charging_duration = None
            if self.charging_start_time:
                charging_duration = datetime.now() - self.charging_start_time
            
            # End the protected charging session
            self.end_charging_session()
            
            logger.info("Price-based charging stopped")
            if charging_duration:
                logger.info(f"Total charging time: {charging_duration}")
            
            return True
        else:
            logger.error("Failed to stop price-based charging")
            return False
    
    async def schedule_charging_for_today(self, max_charging_hours: float = 4.0):
        """Schedule charging for today's optimal window based on known prices"""
        
        logger.info("Scheduling charging for today's optimal window")
        
        # Fetch today's price data once
        price_data = self.fetch_today_prices()
        if not price_data:
            logger.error("Failed to fetch price data for scheduling")
            return False
        
        # Find optimal charging windows
        charging_windows = self.analyze_charging_windows(price_data, max_charging_hours)
        if not charging_windows:
            logger.warning("No optimal charging windows found for today")
            return False
        
        # Get the best window
        best_window = charging_windows[0]
        start_time_str = best_window['start_time']
        end_time_str = best_window['end_time']
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S').time()
        
        logger.info(f"Optimal charging window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        logger.info(f"Average price: {best_window['avg_price']:.2f} PLN/MWh")
        logger.info(f"Savings: {best_window['savings_per_mwh']:.2f} PLN/MWh")
        
        # Schedule the charging
        await self._execute_scheduled_charging(start_time, end_time, max_charging_hours)
        return True
    
    async def _execute_scheduled_charging(self, start_time: datetime.time, end_time: datetime.time, max_charging_hours: float):
        """Execute scheduled charging for the specified time window"""
        
        logger.info(f"Starting scheduled charging from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
        
        try:
            while True:
                now = datetime.now()
                current_time = now.time()
                
                # Check if we're in the charging window
                if start_time <= current_time <= end_time:
                    if not self.is_charging:
                        logger.info(f"Starting charging at {current_time.strftime('%H:%M')} (scheduled window)")
                        await self.start_price_based_charging(None)  # No need for price data
                
                # Check if we should stop charging
                elif self.is_charging:
                    if current_time > end_time:
                        logger.info(f"Stopping charging at {current_time.strftime('%H:%M')} (end of scheduled window)")
                        await self.stop_price_based_charging()
                        break
                
                # Monitor charging status if active
                if self.is_charging:
                    # Check if we've been charging too long
                    if self.charging_start_time:
                        charging_duration = now - self.charging_start_time
                        if charging_duration.total_seconds() > max_charging_hours * 3600:
                            logger.info(f"Maximum charging time ({max_charging_hours}h) reached, stopping")
                            await self.stop_price_based_charging()
                            break
                    
                    # Check battery SoC
                    status = await self.goodwe_charger.get_charging_status()
                    if 'error' not in status:
                        battery_soc = status.get('current_battery_soc', 0)
                        target_soc = status.get('target_soc_percentage', 0)
                        logger.info(f"Charging in progress: Battery {battery_soc}% / Target {target_soc}%")
                        
                        # Check if target reached
                        if battery_soc >= target_soc:
                            logger.info("Target SoC reached, stopping charging")
                            await self.stop_price_based_charging()
                            break
                
                # Wait 1 minute before next check
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("Scheduled charging interrupted by user")
            if self.is_charging:
                await self.stop_price_based_charging()
        except Exception as e:
            logger.error(f"Scheduled charging error: {e}")
            if self.is_charging:
                await self.stop_price_based_charging()
    
    async def schedule_charging_for_tomorrow(self, max_charging_hours: float = 4.0):
        """Schedule charging for tomorrow's optimal window"""
        
        logger.info("Scheduling charging for tomorrow's optimal window")
        
        # Get tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Fetch tomorrow's price data
        price_data = self.fetch_price_data_for_date(tomorrow_str)
        if not price_data:
            logger.error(f"Failed to fetch price data for {tomorrow_str}")
            return False
        
        # Find optimal charging windows for tomorrow
        charging_windows = self.analyze_charging_windows(price_data, max_charging_hours)
        if not charging_windows:
            logger.warning(f"No optimal charging windows found for {tomorrow_str}")
            return False
        
        # Get the best window
        best_window = charging_windows[0]
        start_time_str = best_window['start_time']
        end_time_str = best_window['end_time']
        
        # Parse times
        start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S').time()
        end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S').time()
        
        logger.info(f"Tomorrow's optimal charging window: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        logger.info(f"Average price: {best_window['avg_price']:.2f} PLN/MWh")
        logger.info(f"Savings: {best_window['savings_per_mwh']:.2f} PLN/MWh")
        
        # Schedule the charging for tomorrow
        await self._execute_scheduled_charging(start_time, end_time, max_charging_hours)
        return True
    
    def fetch_price_data_for_date(self, date_str: str) -> Dict:
        """Fetch price data for a specific date"""
        try:
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{date_str}'"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch price data for {date_str}: {e}")
            return None
    
    def print_daily_schedule(self, price_data: Dict):
        """Print today's charging schedule"""
        if not price_data or 'value' not in price_data:
            print("No price data available")
            return
        
        print("\n" + "="*80)
        print("TODAY'S ELECTRICITY PRICE SCHEDULE (Tariff-Aware)")
        print("="*80)
        if self.tariff_calculator:
            tariff_info = self.tariff_calculator.get_tariff_info()
            print(f"Tariff: {tariff_info['tariff_type'].upper()}")
            print(f"SC Component: {tariff_info['sc_component']} PLN/kWh (Składnik cenotwórczy)")
            print(f"Distribution: {tariff_info['distribution_type']}")
        else:
            print(f"SC Component: {self.sc_component_net} PLN/kWh (Legacy)")
        print("="*80)
        
        # Group prices by hour for better readability
        hourly_prices = {}
        for item in price_data['value']:
            time_str = item['dtime']
            hour = time_str.split(' ')[1][:5]  # Extract HH:MM
            market_price = float(item['csdac_pln'])
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            final_price = self.calculate_final_price(market_price, item_time)
            
            if hour not in hourly_prices:
                hourly_prices[hour] = {'market': [], 'final': []}
            hourly_prices[hour]['market'].append(market_price)
            hourly_prices[hour]['final'].append(final_price)
        
        # Print hourly summary
        for hour in sorted(hourly_prices.keys()):
            market_prices = hourly_prices[hour]['market']
            final_prices = hourly_prices[hour]['final']
            avg_market_price = sum(market_prices) / len(market_prices)
            avg_final_price = sum(final_prices) / len(final_prices)
            min_final_price = min(final_prices)
            max_final_price = max(final_prices)
            
            # Color coding based on final price (with SC component)
            if avg_final_price <= 300:
                price_indicator = "🟢 LOW"
            elif avg_final_price <= 500:
                price_indicator = "🟡 MEDIUM"
            else:
                price_indicator = "🔴 HIGH"
            
            print(f"{hour:5} | Market: {avg_market_price:6.1f} | Final: {avg_final_price:6.1f} PLN/MWh | Range: {min_final_price:6.1f}-{max_final_price:6.1f} | {price_indicator}")
        
        # Find optimal charging windows
        charging_windows = self.analyze_charging_windows(price_data, target_hours=4.0)
        
        if charging_windows:
            print(f"\n🎯 OPTIMAL CHARGING WINDOWS (4h duration):")
            for i, window in enumerate(charging_windows[:3], 1):  # Show top 3
                print(f"  {i}. {window['start_time'].strftime('%H:%M')} - {window['end_time'].strftime('%H:%M')} "
                      f"| Avg: {window['avg_price']:.1f} PLN/MWh | Savings: {window['savings_percent']:.1f}%")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Automated Price-Based Charging System for GoodWe Inverter',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in interactive mode (default)
  python automated_price_charging.py
  
  # Schedule charging for today's optimal window
  python automated_price_charging.py --schedule-today
  
  # Schedule charging for tomorrow's optimal window
  python automated_price_charging.py --schedule-tomorrow
  
  # Show current status and exit
  python automated_price_charging.py --status
  
  # Start charging now if price is optimal
  python automated_price_charging.py --start-now
  
  # Stop charging if active
  python automated_price_charging.py --stop
  
  # Use custom config file
  python automated_price_charging.py --config my_config.yaml --schedule-today
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/master_coordinator_config.yaml',
        help='Configuration file path (default: config/master_coordinator_config.yaml)'
    )
    
    parser.add_argument(
        '--schedule-today', '-m',
        action='store_true',
        help='Schedule charging for today\'s optimal window'
    )
    
    parser.add_argument(
        '--schedule-tomorrow', '-M',
        action='store_true',
        help='Schedule charging for tomorrow\'s optimal window'
    )
    
    parser.add_argument(
        '--start-now', '-s',
        action='store_true',
        help='Start charging now if price is optimal'
    )
    
    parser.add_argument(
        '--stop', '-x',
        action='store_true',
        help='Stop charging if active'
    )
    
    parser.add_argument(
        '--status', '-t',
        action='store_true',
        help='Show current status and exit'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode with menu (default is non-interactive)'
    )
    
    return parser.parse_args()

async def main():
    """Main function"""
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Configuration
    config_file = args.config
    
    if not Path(config_file).exists():
        print(f"Configuration file {config_file} not found!")
        print("Please ensure the GoodWe inverter configuration is set up first.")
        return
    
    # Initialize automated charger
    charger = AutomatedPriceCharger(config_file)
    
    if not await charger.initialize():
        print("Failed to initialize automated charger")
        return
    
    # Get today's price data and show schedule
    print("Fetching today's electricity prices...")
    price_data = charger.fetch_today_prices()
    
    if not price_data:
        print("Failed to fetch price data. Check your internet connection.")
        return
    
    charger.print_daily_schedule(price_data)
    
    # Handle command-line arguments
    if args.schedule_today:
        print("\n🚀 Scheduling charging for today's optimal window...")
        print("Press Ctrl+C to stop scheduled charging")
        await charger.schedule_charging_for_today(max_charging_hours=4.0)
        return
        
    elif args.schedule_tomorrow:
        print("\n🚀 Scheduling charging for tomorrow's optimal window...")
        print("Press Ctrl+C to stop scheduled charging")
        await charger.schedule_charging_for_tomorrow(max_charging_hours=4.0)
        return
        
    elif args.start_now:
        print("\n🔌 Starting charging now if price is optimal...")
        if await charger.start_price_based_charging(price_data):
            print("✅ Charging started based on current prices!")
        else:
            print("❌ Could not start charging (check logs for details)")
        return
        
    elif args.stop:
        print("\n⏹️ Stopping charging if active...")
        if await charger.stop_price_based_charging():
            print("✅ Charging stopped!")
        else:
            print("❌ Could not stop charging (check logs for details)")
        return
        
    elif args.status:
        print("\n📊 Current Status:")
        status = await charger.goodwe_charger.get_charging_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        return
    
    # If no specific action requested, show analysis and exit (non-interactive by default)
    if args.interactive:
        print("\n" + "="*60)
        print("AUTOMATED CHARGING OPTIONS:")
        print("1. Schedule charging for today's optimal window")
        print("2. Schedule charging for tomorrow's optimal window")
        print("3. Show current status")
        print("4. Start charging now (if price is optimal)")
        print("5. Stop charging (if active)")
        print("6. Exit")
        
        while True:
            try:
                choice = input("\nEnter your choice (1-6): ").strip()
                
                if choice == "1":
                    print("Scheduling charging for today's optimal window...")
                    print("Press Ctrl+C to stop scheduled charging")
                    await charger.schedule_charging_for_today(max_charging_hours=4.0)
                    break
                    
                elif choice == "2":
                    print("Scheduling charging for tomorrow's optimal window...")
                    print("Press Ctrl+C to stop scheduled charging")
                    await charger.schedule_charging_for_tomorrow(max_charging_hours=4.0)
                    break
                    
                elif choice == "3":
                    status = await charger.goodwe_charger.get_charging_status()
                    print("\nCurrent Status:")
                    for key, value in status.items():
                        print(f"  {key}: {value}")
                        
                elif choice == "4":
                    if await charger.start_price_based_charging(price_data):
                        print("✅ Charging started based on current prices!")
                    else:
                        print("❌ Could not start charging (check logs for details)")
                        
                elif choice == "5":
                    if await charger.stop_price_based_charging():
                        print("✅ Charging stopped!")
                    else:
                        print("❌ Could not stop charging (check logs for details)")
                        
                elif choice == "6":
                    print("Exiting...")
                    break
                    
                else:
                    print("Invalid choice. Please enter 1-6.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        print("\n" + "="*60)
        print("AUTOMATED CHARGING ANALYSIS COMPLETE")
        print("="*60)
        print("Use --help to see available command-line options for automation.")
        print("Example: python automated_price_charging.py --schedule-today")
        print("Example: python automated_price_charging.py --schedule-tomorrow")
        print("Example: python automated_price_charging.py --start-now")
        print("Example: python automated_price_charging.py --status")
        print("Example: python automated_price_charging.py --interactive")

if __name__ == "__main__":
    asyncio.run(main())
