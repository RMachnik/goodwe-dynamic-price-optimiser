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
        self.high_price_threshold = optimization_rules.get('high_price_threshold_pln', 0.8)  # PLN/kWh
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
        
        # Initialize enhanced aggressive charging module
        try:
            self.enhanced_aggressive = EnhancedAggressiveCharging(self.config)
            logger.info("Enhanced aggressive charging module initialized")
        except Exception as e:
            logger.error(f"Failed to initialize enhanced aggressive charging: {e}")
            self.enhanced_aggressive = None
    
    def _load_config(self):
        """Load configuration from config file"""
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.config = {}
    
    def _load_pricing_config(self):
        """Load electricity pricing configuration from config file"""
        try:
            import yaml
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            pricing_config = config.get('electricity_pricing', {})
            self.sc_component_net = pricing_config.get('sc_component_net', 0.0892)
            self.sc_component_gross = pricing_config.get('sc_component_gross', 0.1097)
            self.minimum_price_floor = pricing_config.get('minimum_price_floor', 0.0050)
            self.charging_threshold_percentile = pricing_config.get('charging_threshold_percentile', 0.25)
            
            logger.info(f"Loaded pricing config: SC component = {self.sc_component_net} PLN/kWh")
            
        except Exception as e:
            logger.warning(f"Failed to load pricing config, using defaults: {e}")
            # Default values from Polish electricity pricing document
            self.sc_component_net = 0.0892
            self.sc_component_gross = 0.1097
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
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch CSDAC price data: {e}")
            return None
    
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
            current_price > self.high_price_threshold):
            return {
                'should_charge': False,
                'reason': f'Critical battery (10%) but high price ({current_price:.3f} PLN/kWh > {self.high_price_threshold} PLN/kWh) - waiting for price drop',
                'priority': 'critical',
                'confidence': 0.9
            }
        
        # Decision logic for critical battery
        if current_price <= self.max_critical_price:
            # Price is acceptable for critical charging
            return {
                'should_charge': True,
                'reason': f'Critical battery ({battery_soc}%) + acceptable price ({current_price:.3f} PLN/kWh ≤ {self.max_critical_price} PLN/kWh)',
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

    def _make_charging_decision(self, battery_soc: int, overproduction: int, grid_power: int,
                              grid_direction: str, current_price: Optional[float],
                              cheapest_price: Optional[float], cheapest_hour: Optional[int],
                              price_data: Optional[Dict] = None) -> Dict[str, any]:
        """Make the final charging decision based on all factors"""
        
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
                
            except Exception as e:
                logger.error(f"Error in enhanced aggressive charging: {e}")
        
        # FALLBACK: Legacy aggressive charging logic
        if self._check_aggressive_cheapest_price_conditions(battery_soc, current_price, cheapest_price, cheapest_hour):
            return {
                'should_charge': True,
                'reason': f'Aggressive charging during cheapest price period (current: {current_price:.3f}, cheapest: {cheapest_price:.3f} PLN/kWh)',
                'priority': 'high',
                'confidence': 0.9
            }
        
        # HIGH: PV overproduction - no need to charge from grid
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
            if current_price and current_price <= self.max_critical_price:
                return {
                    'should_charge': True,
                    'reason': f'Low battery ({battery_soc}%) + high grid consumption ({grid_power}W) + reasonable price ({current_price:.3f} PLN/kWh)',
                    'priority': 'high',
                    'confidence': 0.8
                }
            else:
                # Price is too high or unavailable - wait for better conditions
                if current_price:
                    reason = f'Low battery ({battery_soc}%) + high consumption ({grid_power}W) but price too high ({current_price:.3f} PLN/kWh > {self.max_critical_price} PLN/kWh) - waiting for better price'
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
        
        if self.is_charging:
            logger.info("Already charging, skipping start request")
            return True
        
        # Check price only if not forced to start (e.g., by master coordinator for critical battery)
        if not force_start and not self.should_start_charging(price_data):
            logger.info("Current price is not optimal for charging")
            return False
        
        if force_start:
            logger.info("Starting charging due to emergency battery level (overriding price check)")
        else:
            logger.info("Starting price-based charging...")
        
        # Start fast charging
        if await self.goodwe_charger.start_fast_charging():
            self.is_charging = True
            self.charging_start_time = datetime.now()
            logger.info("Charging started successfully")
            return True
        else:
            logger.error("Failed to start charging")
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
