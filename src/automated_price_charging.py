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
from pathlib import Path

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    import requests  # Fallback to sync requests

# Import the GoodWe fast charging functionality
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger
from enhanced_data_collector import EnhancedDataCollector
from tariff_pricing import TariffPricingCalculator, PriceComponents
from price_history_manager import PriceHistoryManager
from adaptive_threshold_calculator import AdaptiveThresholdCalculator

# Logging configuration handled by main application
logger = logging.getLogger(__name__)

class AutomatedPriceCharger:
    """Enhanced automated charging system with smart strategy"""
    
    def __init__(self, config_path: str = None):
        """Initialize the automated charger"""
        # Support both dict config and file path
        if isinstance(config_path, dict):
            # Direct config dict provided (used in tests)
            self.config_path = None
            self.config = config_path
            # Extract config values without loading from file
            self._extract_config_values()
            # Pass dict to dependencies
            config_for_deps = self.config
        else:
            # File path provided or use default
            if config_path is None:
                # Use absolute path to config directory
                current_dir = Path(__file__).parent.parent
                self.config_path = str(current_dir / "config" / "master_coordinator_config.yaml")
            else:
                self.config_path = config_path
            
            # Load configuration first (also calls _extract_config_values)
            self._load_config()
            # Pass path to dependencies
            config_for_deps = self.config_path
        
        self.goodwe_charger = GoodWeFastCharger(config_for_deps)
        self.data_collector = EnhancedDataCollector(config_for_deps)
        # Get price API URL from config with fallback
        self.price_api_url = self.config.get('price_analysis', {}).get('api_url', 'https://api.raporty.pse.pl/api/csdac-pln')
        self.current_schedule = None
        self.is_charging = False
        self.charging_start_time = None
        self.charging_stop_time = None  # Track when charging stopped for flip-flop protection
        self.last_decision_time = None
        self.decision_history = []
        
        # Price scan cache for opportunistic tier
        self._price_scan_cache = {}  # Cache for _find_cheapest_price_next_hours
        self._price_scan_cache_timestamp = None  # Cache invalidation tracking
        
        # PV forecaster for weather-aware decisions (set by MasterCoordinator)
        self.pv_forecaster = None
        
        # Session tracking for hysteresis
        self.active_charging_session = None
        self.session_start_time = None
        self.session_start_soc = None
        self.last_full_charge_soc = None  # Track last "full" charge level
        self.daily_session_count = 0
        self.last_session_reset = datetime.now().date()

    def set_pv_forecaster(self, pv_forecaster) -> None:
        """Set PV forecaster for weather-aware charging decisions.
        
        Args:
            pv_forecaster: PVForecaster instance with weather collector configured
        """
        self.pv_forecaster = pv_forecaster
        logger.info("PV forecaster set for weather-aware charging decisions")

    def _load_config(self) -> None:
        """Load YAML configuration defensively into `self.config`."""
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            self.config = {}
        
        # Extract config values
        self._extract_config_values()
    
    def _extract_config_values(self) -> None:
        """Extract configuration values from self.config dict."""
        # Smart charging thresholds
        self.critical_battery_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('critical', 12)  # % - Price-aware charging
        self.emergency_battery_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('emergency', 5)  # % - Always charge regardless of price
        self.low_battery_threshold = 30  # % - Consider charging if below this
        self.medium_battery_threshold = 50  # % - Only charge if conditions are favorable
        self.price_savings_threshold = 0.3  # 30% savings required to wait
        self.overproduction_threshold = 1500  # W - Significant overproduction
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
        
        # OPPORTUNISTIC tier pre-peak charging rules
        self.opportunistic_pre_peak_enabled = optimization_rules.get('opportunistic_pre_peak_enabled', True)
        self.evening_peak_hours = optimization_rules.get('evening_peak_hours', [17, 18, 19, 20, 21, 22])
        self.opportunistic_pre_peak_threshold = optimization_rules.get('opportunistic_pre_peak_threshold', 0.9)  # PLN/kWh
        self.evening_price_multiplier = optimization_rules.get('evening_price_multiplier', 1.1)
        self.opportunistic_pre_peak_min_soc = optimization_rules.get('opportunistic_pre_peak_min_soc', 20)  # %
        
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
        
        # Simple charging configuration (December 2024)
        self.flip_flop_protection_minutes = smart_critical_config.get('flip_flop_protection_minutes', 15)
        self.opportunistic_tolerance_percent = smart_critical_config.get('opportunistic_tolerance_percent', 15) / 100.0
        
        # Battery capacity for calculations
        self.battery_capacity_kwh = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)  # kWh
        
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
        
        # Load charging hysteresis configuration (battery longevity)
        self._load_hysteresis_config()

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
    
    def _load_hysteresis_config(self):
        """Load charging hysteresis configuration for battery longevity"""
        try:
            battery_config = self.config.get('battery_management', {})
            hysteresis_config = battery_config.get('charging_hysteresis', {})
            
            # Set defaults if not configured
            self.hysteresis_enabled = hysteresis_config.get('enabled', False)
            
            # Normal tier thresholds (SOC 40-100%)
            self.normal_start_threshold = hysteresis_config.get('normal_start_threshold', 85)
            self.normal_stop_threshold = hysteresis_config.get('normal_stop_threshold', 95)
            self.normal_target_soc = hysteresis_config.get('normal_target_soc', 95)
            
            # Opportunistic tier thresholds (SOC 15-40%)
            self.opportunistic_start_threshold = hysteresis_config.get('opportunistic_start_threshold', 70)
            self.opportunistic_stop_threshold = hysteresis_config.get('opportunistic_stop_threshold', 85)
            
            # Session management
            self.min_session_duration_minutes = hysteresis_config.get('min_session_duration_minutes', 30)
            self.min_discharge_depth_percent = hysteresis_config.get('min_discharge_depth_percent', 10)
            self.max_sessions_per_day = hysteresis_config.get('max_sessions_per_day', 4)
            
            # Override settings
            self.override_on_emergency = hysteresis_config.get('override_on_emergency', True)
            self.override_on_critical = hysteresis_config.get('override_on_critical', True)
            
            logger.info(f"Charging hysteresis: {'enabled' if self.hysteresis_enabled else 'disabled'} "
                       f"(start: {self.normal_start_threshold}%, stop: {self.normal_stop_threshold}%, "
                       f"max sessions: {self.max_sessions_per_day}/day)")
            
        except Exception as e:
            logger.error(f"Failed to load hysteresis configuration: {e}")
            self.hysteresis_enabled = False
    
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
            # Always convert from PLN/MWh to PLN/kWh (removal of unreliable heuristic)
            market_price_kwh = market_price / 1000
            
            components = self.tariff_calculator.calculate_final_price(
                market_price_kwh,
                timestamp,
                kompas_status
            )
            
            logger.info(f"calculate_final_price: market={market_price:.2f} PLN/MWh ({market_price_kwh:.4f} PLN/kWh), timestamp={timestamp.strftime('%Y-%m-%d %H:%M')}, components.final_price={components.final_price:.4f} PLN/kWh")
            
            # Return in PLN/MWh for consistency with existing code
            return components.final_price * 1000
        else:
            # Fallback to legacy pricing (SC component only)
            logger.warning("Tariff calculator not available, using legacy SC-only pricing")
            # Convert SC component from PLN/kWh to PLN/MWh
            final_price = market_price + (self.sc_component_net * 1000)
            return final_price
    
    def apply_minimum_price_floor(self, price: float) -> float:
        """Apply minimum price floor as per Polish regulations"""
        return max(price, self.minimum_price_floor)
        
    async def initialize(self) -> bool:
        """Initialize the system and connect to inverter"""
        logger.info("Initializing automated price-based charging system...")
        
        # Connect to GoodWe inverter
        if not await self.goodwe_charger.connect_inverter():
            logger.error("Failed to connect to GoodWe inverter")
            return False
        
        logger.info("Successfully connected to GoodWe inverter")
        return True
    
    async def fetch_today_prices(self) -> Optional[Dict]:
        """Fetch today's electricity prices from Polish market using RCE-PLN API (async)"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            # CSDAC-PLN API uses business_date field for filtering
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{today}'"
            
            logger.info(f"Fetching CSDAC price data for {today}")
            
            # Use aiohttp if available, otherwise fallback to requests
            if AIOHTTP_AVAILABLE:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        response.raise_for_status()
                        data = await response.json()
            else:
                import requests
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
        
        logger.info(f"get_current_price: Looking for period matching {current_time.strftime('%Y-%m-%d %H:%M')}")
        
        # 1. Try to find the exact 15-minute period match
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            period_end = item_time + timedelta(minutes=15)
            if item_time <= current_time < period_end:
                market_price_pln_mwh = float(item['csdac_pln'])
                final_price_pln_mwh = self.calculate_final_price(market_price_pln_mwh, item_time, kompas_status)
                logger.info(f"get_current_price: EXACT MATCH {item['dtime']} -> Final: {final_price_pln_mwh:.2f} PLN/MWh")
                return final_price_pln_mwh
                
        # 2. Fallback: Try to find any price for the same hour if 15-minute match failed
        # This is vital for hourly data where only 00:00, 01:00, etc. records exist
        current_hour = now.hour
        current_date = now.date()
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            if item_time.hour == current_hour and item_time.date() == current_date:
                market_price_pln_mwh = float(item['csdac_pln'])
                final_price_pln_mwh = self.calculate_final_price(market_price_pln_mwh, item_time, kompas_status)
                logger.info(f"get_current_price: HOURLY FALLBACK MATCH {item['dtime']} for hour {current_hour} -> Final: {final_price_pln_mwh:.2f} PLN/MWh")
                return final_price_pln_mwh
        
        logger.warning(f"get_current_price: No matching period found for {current_time}")
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
                'reason': f'Low battery ({battery_soc}%) - charging at {current_price:.2f} PLN',
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
                        'reason': f'Low battery ({battery_soc}%) - waiting {hours_to_wait:.0f}h for cheaper price + solar',
                        'priority': 'critical',
                        'confidence': 0.8
                    }
                else:  # PV improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Low battery ({battery_soc}%) - solar improving soon',
                        'priority': 'critical',
                        'confidence': 0.7
                    }
            
            elif should_wait_for_pv:
                # Only PV will improve - wait for PV
                return {
                    'should_charge': False,
                    'reason': f'Low battery ({battery_soc}%) - waiting for free solar',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            elif should_wait_for_price:
                # Only price will improve - wait for better price
                return {
                    'should_charge': False,
                    'reason': f'Low battery ({battery_soc}%) - waiting {hours_to_wait:.0f}h for {savings_percent:.0f}% cheaper price',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            else:
                # Neither PV nor price will improve significantly - charge now
                return {
                    'should_charge': True,
                    'reason': f'Low battery ({battery_soc}%) - charging now (no better option soon)',
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
            'reason': f'No solar, battery low ({battery_soc}%), good price - charging',
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
        """Check if weather will improve in the next few hours using PV forecast.
        
        Returns:
            True if weather/PV is expected to improve significantly, False otherwise.
            On API failure or missing forecaster, returns False (conservative: assume no improvement).
        """
        try:
            if not self.pv_forecaster:
                logger.debug("No PV forecaster available - assuming weather won't improve")
                return False
            
            # Get weather-based PV forecast for next 6 hours
            forecasts = self.pv_forecaster.forecast_pv_production_with_weather(self.weather_improvement_hours)
            
            if not forecasts:
                logger.debug("No PV forecast data available - assuming weather won't improve")
                return False
            
            # Check if PV production is expected to improve significantly
            # Compare first hour forecast to average of remaining hours
            if len(forecasts) < 2:
                return False
            
            current_pv = forecasts[0].get('forecasted_power_kw', 0)
            future_pv_values = [f.get('forecasted_power_kw', 0) for f in forecasts[1:]]
            
            if not future_pv_values:
                return False
            
            avg_future_pv = sum(future_pv_values) / len(future_pv_values)
            
            # Weather improves if future PV is at least 50% higher than current
            # and future PV is above 1 kW (meaningful production)
            improvement_threshold = 1.5
            min_meaningful_pv_kw = 1.0
            
            if avg_future_pv > current_pv * improvement_threshold and avg_future_pv >= min_meaningful_pv_kw:
                logger.info(f"Weather expected to improve: current PV={current_pv:.1f}kW, future avg={avg_future_pv:.1f}kW")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Failed to check weather improvement: {e} - assuming no improvement")
            return False

    def _check_weather_stability(self) -> bool:
        """Check if weather conditions are stable for PV charging using PV forecast.
        
        Returns:
            True if weather is stable (low variance in cloud cover), False otherwise.
            On API failure or missing forecaster, returns True (optimistic for PV preference).
        """
        try:
            if not self.pv_forecaster:
                logger.debug("No PV forecaster available - assuming weather is stable")
                return True
            
            # Get weather-based PV forecast for next 4 hours
            forecasts = self.pv_forecaster.forecast_pv_production_with_weather(4)
            
            if not forecasts:
                logger.debug("No PV forecast data available - assuming weather is stable")
                return True
            
            # Check cloud cover stability
            cloud_covers = [f.get('cloud_cover_percent', 50) for f in forecasts]
            
            if not cloud_covers:
                return True
            
            # Weather is unstable if cloud cover varies by more than 30% between hours
            max_cloud = max(cloud_covers)
            min_cloud = min(cloud_covers)
            cloud_variance = max_cloud - min_cloud
            
            # Also check confidence levels
            confidences = [f.get('confidence', 0.5) for f in forecasts]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
            
            # Weather is stable if variance is low AND confidence is reasonable
            stability_threshold = 30  # percent cloud cover variance
            min_confidence = 0.6
            
            is_stable = cloud_variance <= stability_threshold and avg_confidence >= min_confidence
            
            if not is_stable:
                logger.debug(f"Weather unstable: cloud variance={cloud_variance}%, confidence={avg_confidence:.2f}")
            
            return is_stable
            
        except Exception as e:
            logger.warning(f"Failed to check weather stability: {e} - assuming stable")
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
                    'reason': f'Very cheap ({current_price:.2f} PLN) + great solar - charging from PV',
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
                    'reason': f'Very cheap ({current_price:.2f} PLN) - fast grid charge (PV too slow)',
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
                pv_conditions.append("low solar")
            if not weather_stable:
                pv_conditions.append("cloudy")
            if not house_usage_low:
                pv_conditions.append("high usage")
            
            return {
                'should_charge': True,
                'reason': f'Very cheap ({current_price:.2f} PLN) - grid charging ({{", ".join(pv_conditions)}})',
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
                'reason': f'Low battery ({battery_soc}%) - charging immediately',
                'priority': 'critical',
                'confidence': 1.0
            }
        
        # If no price data available, charge immediately for safety
        if not current_price or not cheapest_price or not cheapest_hour:
            return {
                'should_charge': True,
                'reason': f'Low battery ({battery_soc}%) - no price data, charging now',
                'priority': 'critical',
                'confidence': 0.8
            }
        
        # Calculate savings and timing
        savings_percent = self._calculate_savings(current_price, cheapest_price)
        hours_to_wait = cheapest_hour - datetime.now().hour
        if hours_to_wait < 0:
            hours_to_wait += 24  # Next day
        
        # OPTIMIZATION RULE 1: At 10% SOC with high price, always wait for price drop
        # Also wait if fixed threshold exceeded or it's a high price for critical charging
        high_threshold = self.get_high_price_threshold()
        is_high_price = current_price > high_threshold
        
        if self.wait_at_10_percent_if_high_price and battery_soc == 10 and is_high_price:
            return {
                'should_charge': False,
                'reason': f'Low battery (10%) but price too high ({current_price:.3f} > {high_threshold:.3f}) - waiting for drop',
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
                        'reason': f'Low battery ({battery_soc}%) - cheaper price in {hours_to_wait:.0f}h + solar coming',
                        'priority': 'critical',
                        'confidence': 0.8
                    }
                else:  # PV improvement is sooner
                    return {
                        'should_charge': False,
                        'reason': f'Low battery ({battery_soc}%) - solar production improving soon',
                        'priority': 'critical',
                        'confidence': 0.7
                    }
            
            elif should_wait_for_pv:
                # Only PV will improve - wait for PV
                return {
                    'should_charge': False,
                    'reason': f'Low battery ({battery_soc}%) - waiting for solar',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            elif should_wait_for_price:
                # Only price will improve - wait for better price
                return {
                    'should_charge': False,
                    'reason': f'Low battery ({battery_soc}%) - {savings_percent:.0f}% cheaper price in {hours_to_wait:.0f}h',
                    'priority': 'critical',
                    'confidence': 0.7
                }
            
            else:
                # Neither PV nor price will improve significantly - charge now
                return {
                    'should_charge': True,
                    'reason': f'Low battery ({battery_soc}%) - charging (no better option)',
                    'priority': 'critical',
                    'confidence': 0.8
                }

    def _calculate_dynamic_max_wait_hours(self, savings_percent: float, battery_soc: int) -> float:
        """Calculate dynamic maximum wait time based on savings and battery level"""
        # Base wait time from configuration
        base_wait_hours = self.max_wait_hours
        
        # Adjust based on savings percentage
        if savings_percent >= 80:
            savings_multiplier = 2.0  # Increased from 1.5 to allow longer wait for huge savings
        elif savings_percent >= 60:
            savings_multiplier = 1.6  # Increased from 1.2
        elif savings_percent >= 40:
            savings_multiplier = 1.2  # Increased from 1.0
        else:
            savings_multiplier = 0.8  # Slight increase from 0.7
        
        # Adjust based on battery level (lower battery = shorter wait)
        # For high savings (>=60%), be more willing to wait even at 9-10% SOC
        if battery_soc <= 8:
            battery_multiplier = 0.5
        elif battery_soc <= 10:
            # At 9-10% with high savings (>=60%), use full or near-full base time
            if savings_percent >= 70:
                battery_multiplier = 1.2  # Boost wait if savings are excellent
            elif savings_percent >= 50:
                battery_multiplier = 1.0
            else:
                battery_multiplier = 0.7
        else:
            battery_multiplier = 1.0
        
        # Calculate final wait time
        max_wait_hours = base_wait_hours * savings_multiplier * battery_multiplier
        
        # Boost for extreme savings
        if savings_percent >= 85:
            max_wait_hours += 2.0
        
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

    def _is_approaching_evening_peak(self) -> Tuple[bool, float]:
        """
        Check if current time is approaching evening peak (before 16:00).
        
        Returns:
            Tuple of (is_approaching, hours_until_peak)
            - is_approaching: True if before 16:00 and evening peak will occur
            - hours_until_peak: Hours until evening peak starts (17:00)
        """
        now = datetime.now()
        current_hour = now.hour
        
        # Check if before the cutoff (16:00)
        if current_hour < 16:
            # Calculate hours until evening peak starts
            evening_peak_start = min(self.evening_peak_hours) if self.evening_peak_hours else 17
            hours_until_peak = evening_peak_start - current_hour - (now.minute / 60.0)
            return True, max(0, hours_until_peak)
        
        return False, 0.0
    
    def _get_evening_peak_forecast(self, price_data: Dict) -> Optional[Dict[str, float]]:
        """
        Get evening peak price forecast from price_data.
        
        Args:
            price_data: Dictionary with 'value' list containing price points
        
        Returns:
            Dict with {'avg': float, 'max': float, 'min': float} in PLN/kWh, or None if no data
        """
        if not price_data or 'value' not in price_data:
            return None
        
        try:
            evening_prices = []
            
            # Extract prices for evening peak hours
            for hour in self.evening_peak_hours:
                for period in price_data['value']:
                    dt_str = period.get('dtime', '')
                    # Match hour in datetime string (supports both formats)
                    if f'T{hour:02d}:' in dt_str or f' {hour:02d}:' in dt_str:
                        # Calculate final price with tariff
                        market_price_mwh = float(period['csdac_pln'])
                        dt = datetime.fromisoformat(dt_str.replace('Z', ''))
                        final_price_mwh = self.calculate_final_price(market_price_mwh, dt)
                        final_price_kwh = final_price_mwh / 1000
                        evening_prices.append(final_price_kwh)
            
            if not evening_prices:
                return None
            
            return {
                'avg': sum(evening_prices) / len(evening_prices),
                'max': max(evening_prices),
                'min': min(evening_prices)
            }
        except Exception as e:
            logger.error(f"Error getting evening peak forecast: {e}")
            return None
    
    

    def _find_cheapest_price_next_hours(self, hours: int, price_data: Dict) -> Optional[float]:
        """
        Find cheapest price in the next N hours with 5-minute caching.
        
        Args:
            hours: Number of hours to scan ahead
            price_data: Dictionary with 'value' list containing price points
        
        Returns:
            Cheapest price in PLN/kWh, or None if no data available
        """
        try:
            # Check cache validity (5-minute expiration)
            cache_key = hours
            now = datetime.now()
            
            if (self._price_scan_cache_timestamp and 
                cache_key in self._price_scan_cache and
                (now - self._price_scan_cache_timestamp) < timedelta(minutes=5)):
                logger.debug(f"Cache hit for cheapest_price_next_{hours}h: {self._price_scan_cache[cache_key]:.3f} PLN/kWh")
                return self._price_scan_cache[cache_key]
            
            # Cache miss or expired - scan prices
            if not price_data or 'value' not in price_data:
                return None
            
            scan_end = now + timedelta(hours=hours)
            prices = []
            
            for item in price_data.get('value', []):
                try:
                    dtime = datetime.fromisoformat(item['dtime'].replace('Z', '+00:00'))
                    if now <= dtime <= scan_end:
                        price_kwh = self.calculate_final_price(float(item['csdac_pln']), dtime) / 1000
                        prices.append(price_kwh)
                except (KeyError, ValueError, TypeError):
                    continue
            
            if not prices:
                return None
            
            cheapest = min(prices)
            
            # Update cache
            self._price_scan_cache[cache_key] = cheapest
            self._price_scan_cache_timestamp = now
            
            logger.debug(f"Cheapest price next {hours}h: {cheapest:.3f} PLN/kWh")
            return cheapest
            
        except Exception as e:
            logger.error(f"Error finding cheapest price: {e}")
            return None
    
    def _is_price_cheap_for_normal_tier(self, current_price: float, current_soc: int, price_data: Dict) -> bool:
        """
        Determine if price is cheap enough for Normal tier (50%+ SOC) using percentile logic.
        
        Uses 40th/60th percentiles from last 24 hours. Charges if:
        - Price ≤ 40th percentile, OR
        - Price ≤ 60th percentile AND SOC < 85%
        
        Falls back to "cheapest_next_24h × 1.10" if adaptive thresholds disabled or no data.
        
        Args:
            current_price: Current price in PLN/kWh
            current_soc: Current battery SOC percentage
            price_data: Price data dictionary
        
        Returns:
            True if price is cheap enough to charge
        """
        try:
            # Null checks for price history manager
            if not self.adaptive_enabled or not self.price_history:
                logger.debug("Adaptive thresholds disabled, using fallback for Normal tier")
                cheapest_24h = self._find_cheapest_price_next_hours(24, price_data)
                if cheapest_24h is None:
                    return False
                return current_price <= cheapest_24h * 1.10
            
            # Get recent prices from last 24 hours
            recent_prices = self.price_history.get_recent_prices(hours=24)
            
            if not recent_prices or len(recent_prices) < 10:  # Need minimum data points
                logger.debug(f"Insufficient price history ({len(recent_prices) if recent_prices else 0} points), using fallback")
                cheapest_24h = self._find_cheapest_price_next_hours(24, price_data)
                if cheapest_24h is None:
                    return False
                return current_price <= cheapest_24h * 1.10
            
            # Calculate percentiles using numpy
            import numpy as np
            p40 = np.percentile(recent_prices, 40)
            p60 = np.percentile(recent_prices, 60)
            
            # Decision logic
            if current_price <= p40:
                logger.debug(f"Normal tier: price {current_price:.3f} ≤ p40 {p40:.3f} → CHARGE")
                return True
            elif current_price <= p60 and current_soc < 85:
                logger.debug(f"Normal tier: price {current_price:.3f} ≤ p60 {p60:.3f} AND SOC {current_soc}% < 85% → CHARGE")
                return True
            else:
                logger.debug(f"Normal tier: price {current_price:.3f} > thresholds (p40={p40:.3f}, p60={p60:.3f}) → WAIT")
                return False
            
        except Exception as e:
            logger.error(f"Error in Normal tier price check: {e}")
            # Fallback on error
            try:
                cheapest_24h = self._find_cheapest_price_next_hours(24, price_data)
                if cheapest_24h is None:
                    return False
                return current_price <= cheapest_24h * 1.10
            except:
                return False

    def _normal_tier_with_hysteresis(self, battery_soc: int, current_price: float,
                                     cheapest_price: Optional[float], cheapest_hour: Optional[int],
                                     price_data: Dict) -> Dict[str, any]:
        """Normal tier charging with hysteresis to reduce cycles and protect battery longevity"""
        
        # Reset daily session count if new day
        today = datetime.now().date()
        if today != self.last_session_reset:
            self.daily_session_count = 0
            self.last_session_reset = today
            logger.info(f"Reset daily session count for {today}")
        
        # Check if we're in an active charging session
        if self.active_charging_session:
            return self._handle_active_session(battery_soc)
        
        # Check if we've exceeded max sessions per day
        if self.daily_session_count >= self.max_sessions_per_day:
            return {
                'should_charge': False,
                'reason': f'NORMAL tier: Max sessions ({self.max_sessions_per_day}) reached today - protecting battery',
                'priority': 'low',
                'confidence': 0.9
            }
        
        # Check if battery has discharged enough to warrant recharging
        if self.last_full_charge_soc is not None:
            discharge_depth = self.last_full_charge_soc - battery_soc
            if discharge_depth < self.min_discharge_depth_percent:
                return {
                    'should_charge': False,
                    'reason': f'NORMAL tier: Insufficient discharge ({discharge_depth}% < {self.min_discharge_depth_percent}%) - protecting battery',
                    'priority': 'low',
                    'confidence': 0.8
                }
        
        # Check if SOC is below start threshold
        if battery_soc >= self.normal_start_threshold:
            return {
                'should_charge': False,
                'reason': f'NORMAL tier: Battery OK ({battery_soc}%) - above start threshold ({self.normal_start_threshold}%)',
                'priority': 'low',
                'confidence': 0.7
            }
        
        # SOC is below start threshold - check if price is good
        if not self._is_price_cheap_for_normal_tier(current_price, battery_soc, price_data):
            return {
                'should_charge': False,
                'reason': f'NORMAL tier: Battery low ({battery_soc}%) but price not cheap enough ({current_price:.2f} PLN)',
                'priority': 'low',
                'confidence': 0.7
            }
        
        # Start new charging session
        self.active_charging_session = True
        self.session_start_time = datetime.now()
        self.session_start_soc = battery_soc
        self.daily_session_count += 1
        
        logger.info(f"🔋 Starting charging session #{self.daily_session_count} (SOC: {battery_soc}% → target: {self.normal_target_soc}%)")
        
        return {
            'should_charge': True,
            'reason': f'NORMAL tier: Good price ({current_price:.2f} PLN) - starting session #{self.daily_session_count}',
            'priority': 'low',
            'confidence': 0.8,
            'target_soc': self.normal_target_soc,
            'session_number': self.daily_session_count
        }

    def _handle_active_session(self, battery_soc: int) -> Dict[str, any]:
        """Handle decision during active charging session"""
        
        # Check if we've reached target SOC
        if battery_soc >= self.normal_stop_threshold:
            # End session
            self.active_charging_session = None
            self.last_full_charge_soc = battery_soc
            
            logger.info(f"✅ Charging session complete (SOC: {self.session_start_soc}% → {battery_soc}%)")
            
            return {
                'should_charge': False,
                'reason': f'NORMAL tier: Target SOC reached ({battery_soc}% >= {self.normal_stop_threshold}%)',
                'priority': 'low',
                'confidence': 0.95
            }
        
        # Check minimum session duration
        if self.session_start_time:
            session_duration_minutes = (datetime.now() - self.session_start_time).seconds / 60
            
            if session_duration_minutes < self.min_session_duration_minutes:
                # Continue charging (prevent flapping)
                return {
                    'should_charge': True,
                    'reason': f'NORMAL tier: Continuing session (min duration: {self.min_session_duration_minutes}min)',
                    'priority': 'low',
                    'confidence': 0.9,
                    'target_soc': self.normal_target_soc
                }
        
        # Session long enough, but not at target - continue charging
        return {
            'should_charge': True,
            'reason': f'NORMAL tier: Charging to target ({battery_soc}% → {self.normal_target_soc}%)',
            'priority': 'low',
            'confidence': 0.85,
            'target_soc': self.normal_target_soc
        }

    def _make_charging_decision(self, battery_soc: int, overproduction: int, grid_power: int,
                              grid_direction: str, current_price: Optional[float],
                              cheapest_price: Optional[float], cheapest_hour: Optional[int],
                              price_data: Optional[Dict] = None) -> Dict[str, any]:
        """
        Make the final charging decision using 4-tier SOC-based logic.
        
        Tiers:
        1. Emergency (<5%): Always charge immediately
        2. Critical (5-12%): Use _smart_critical_charging_decision() with adaptive thresholds
        3. Opportunistic (12-50%): Charge if current_price ≤ cheapest_next_12h × 1.15
        4. Normal (50%+): Charge if price ≤ 40th percentile OR (≤60th percentile AND SOC < 85%)
        
        Includes bidirectional flip-flop protection (15 minutes).
        """
        
        # ACTIVE CHARGING: If already charging, check if we should continue or stop
        if self.is_charging:
            # Bidirectional flip-flop: prevent stop within 15 minutes of start
            if self.charging_start_time:
                minutes_since_start = (datetime.now() - self.charging_start_time).total_seconds() / 60
                if minutes_since_start < self.flip_flop_protection_minutes:
                    return {
                        'should_charge': True,
                        'reason': f'Flip-flop protection: charging started {minutes_since_start:.1f} min ago (continue)',
                        'priority': 'high',
                        'confidence': 0.95
                    }
            
            # Check if we should stop charging (target SOC reached, etc.)
            if battery_soc >= 90:  # Near full
                return {
                    'should_charge': False,
                    'reason': f'Battery nearly full ({battery_soc}%) - stop charging',
                    'priority': 'high',
                    'confidence': 0.95
                }
            
            # Check if current price is too high for continuing (except if emergency)
            if battery_soc > 5 and current_price and current_price > self.get_high_price_threshold():
                return {
                    'should_charge': False,
                    'reason': f'Charging in progress but price spiked ({current_price:.3f} > {self.get_high_price_threshold():.3f}) - pausing',
                    'priority': 'medium',
                    'confidence': 0.8
                }
            
            # Continue charging if still within reasonable conditions
            return {
                'should_charge': True,
                'reason': f'Charging in progress - continuing (SOC: {battery_soc}%)',
                'priority': 'medium',
                'confidence': 0.8
            }
        
        # BIDIRECTIONAL FLIP-FLOP: Prevent start within 15 minutes of stop
        if self.charging_stop_time:
            minutes_since_stop = (datetime.now() - self.charging_stop_time).total_seconds() / 60
            if minutes_since_stop < self.flip_flop_protection_minutes:
                return {
                    'should_charge': False,
                    'reason': f'Flip-flop protection: charging stopped {minutes_since_stop:.1f} min ago (wait)',
                    'priority': 'low',
                    'confidence': 0.95
                }
        
        # CHECK PROACTIVE CHARGING: Before tier logic, check if proactive conditions override normal rules
        if self.proactive_charging_enabled:
            proactive_decision = self._check_proactive_charging_conditions(
                battery_soc, overproduction, current_price, cheapest_price, cheapest_hour
            )
            if proactive_decision:
                return proactive_decision
        
        # TIER 1 - EMERGENCY (<5%): Always charge immediately
        if battery_soc < self.emergency_battery_threshold:
            return {
                'should_charge': True,
                'reason': f'EMERGENCY tier: battery {battery_soc}% < {self.emergency_battery_threshold}% - charge immediately regardless of price',
                'priority': 'emergency',
                'confidence': 1.0
            }
        
        # TIER 2 - CRITICAL (5-12%): Smart price-aware charging with adaptive thresholds
        if battery_soc < self.critical_battery_threshold:
            decision = self._smart_critical_charging_decision(
                battery_soc, current_price, cheapest_price, cheapest_hour
            )
            # Add tier label to reason
            decision['reason'] = f"CRITICAL tier: {decision['reason']}"
            return decision
        
        # TIER 3 - OPPORTUNISTIC (12-50%): Charge if price within 15% of cheapest in next 12h
        # WITH time-of-day awareness: charge before evening peak if forecast shows higher prices
        if battery_soc < 50:
            if not current_price or not price_data:
                return {
                    'should_charge': False,
                    'reason': 'OPPORTUNISTIC tier: no price data available',
                    'priority': 'low',
                    'confidence': 0.3
                }
            
            cheapest_next_12h = self._find_cheapest_price_next_hours(12, price_data)
            if cheapest_next_12h is None:
                return {
                    'should_charge': False,
                    'reason': 'No price forecast available - waiting',
                    'priority': 'low',
                    'confidence': 0.3
                }
            
            threshold = cheapest_next_12h * (1 + self.opportunistic_tolerance_percent)
            
            # PRE-PEAK CHARGING LOGIC: Check if we should charge before evening peak
            if (self.opportunistic_pre_peak_enabled and 
                battery_soc >= self.opportunistic_pre_peak_min_soc and
                current_price <= self.opportunistic_pre_peak_threshold):
                
                is_approaching, hours_until = self._is_approaching_evening_peak()
                
                if is_approaching:
                    evening_forecast = self._get_evening_peak_forecast(price_data)
                    
                    if evening_forecast:
                        evening_avg = evening_forecast['avg']
                        
                        # Check if evening prices will be significantly higher (>10% of current)
                        if evening_avg > current_price * self.evening_price_multiplier:
                            return {
                                'should_charge': True,
                                'reason': f'Charging before evening peak ({hours_until:.0f}h away) - price will rise to ~{evening_avg:.2f} PLN',
                                'priority': 'medium',
                                'confidence': 0.75
                            }
                        else:
                            logger.debug(f"OPPORTUNISTIC pre-peak: evening avg {evening_avg:.3f} not significantly higher than current {current_price:.3f} (threshold {current_price * self.evening_price_multiplier:.3f})")
                    else:
                        logger.warning("OPPORTUNISTIC pre-peak: evening forecast unavailable, using normal logic")
            
            # NORMAL LOGIC: Use 15% tolerance threshold
            if current_price <= threshold:
                return {
                    'should_charge': True,
                    'reason': f'OPPORTUNISTIC tier: Near best price today ({current_price:.2f} PLN) - charging now',
                    'priority': 'medium',
                    'confidence': 0.75
                }
            else:
                return {
                    'should_charge': False,
                    'reason': f'OPPORTUNISTIC tier: Cheaper price coming ({cheapest_next_12h:.2f} PLN) - waiting',
                    'priority': 'low',
                    'confidence': 0.7
                }
        
        # TIER 4 - NORMAL (50%+): Charge if price very cheap (percentile-based)
        # WITH HYSTERESIS: Reduce charging sessions for battery longevity
        if not current_price or not price_data:
            return {
                'should_charge': False,
                'reason': 'NORMAL tier: no price data available',
                'priority': 'low',
                'confidence': 0.3
            }
        
        # Use hysteresis logic if enabled
        if self.hysteresis_enabled:
            return self._normal_tier_with_hysteresis(
                battery_soc, current_price, cheapest_price, cheapest_hour, price_data
            )
        
        # Legacy logic (no hysteresis)
        if self._is_price_cheap_for_normal_tier(current_price, battery_soc, price_data):
            return {
                'should_charge': True,
                'reason': f'NORMAL tier: Good price ({current_price:.2f} PLN) - topping up battery',
                'priority': 'low',
                'confidence': 0.65
            }
        else:
            return {
                'should_charge': False,
                'reason': f'NORMAL tier: Battery OK ({battery_soc}%), waiting for better price',
                'priority': 'low',
                'confidence': 0.6
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
            self.charging_stop_time = datetime.now()  # Track stop time for flip-flop protection
            charging_duration = None
            if self.charging_start_time:
                charging_duration = self.charging_stop_time - self.charging_start_time
            
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
    
    async def fetch_price_data_for_date(self, date_str: str) -> Dict:
        """Fetch price data for a specific date (async)"""
        try:
            url = f"{self.price_api_url}?$filter=business_date%20eq%20'{date_str}'"
            
            # Use aiohttp if available, otherwise fallback to requests
            if AIOHTTP_AVAILABLE:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response.raise_for_status()
                        return await response.json()
            else:
                import requests
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
