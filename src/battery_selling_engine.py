#!/usr/bin/env python3
"""
Battery Energy Selling Engine for GoodWe Dynamic Price Optimiser

This module implements conservative battery energy selling functionality with:
- 80% minimum SOC to start selling
- 50% safety margin SOC (never discharge below 50%)
- Revenue potential: ~260 PLN/year (conservative estimate)
- Full GoodWe inverter integration support

Usage:
    from battery_selling_engine import BatterySellingEngine
    
    engine = BatterySellingEngine(config)
    decision = await engine.analyze_selling_opportunity(current_data, price_data)
"""

import asyncio
import logging
import traceback
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    import goodwe
    from goodwe import Inverter, InverterError, OperationMode
except ImportError:
    print("Error: goodwe library not found. Install with: pip install goodwe")
    raise

# Import smart timing module
try:
    from battery_selling_timing import (
        BatterySellingTiming, 
        TimingDecision, 
        TimingRecommendation
    )
    TIMING_AVAILABLE = True
except ImportError:
    TIMING_AVAILABLE = False
    logging.warning("Battery selling timing module not available - using basic logic")

# Import price forecast collector
try:
    from pse_price_forecast_collector import PSEPriceForecastCollector
    FORECAST_AVAILABLE = True
except ImportError:
    FORECAST_AVAILABLE = False
    logging.warning("PSE price forecast collector not available - timing features limited")

# Import price spike detector (Phase 4)
try:
    from price_spike_detector import PriceSpikeDetector, SpikeLevel
    SPIKE_DETECTOR_AVAILABLE = True
except ImportError:
    SPIKE_DETECTOR_AVAILABLE = False
    logging.warning("Price spike detector not available - Phase 4 features disabled")

# Import tariff pricing
try:
    from tariff_pricing import TariffPricingCalculator, PriceComponents
    TARIFF_PRICING_AVAILABLE = True
except ImportError:
    TARIFF_PRICING_AVAILABLE = False
    logging.warning("Tariff pricing module not available - using SC-only pricing")


class SellingDecision(Enum):
    """Battery selling decision types"""
    START_SELLING = "start_selling"
    STOP_SELLING = "stop_selling"
    CONTINUE_SELLING = "continue_selling"
    WAIT = "wait"


@dataclass
class SellingOpportunity:
    """Represents a battery selling opportunity"""
    decision: SellingDecision
    confidence: float
    expected_revenue_pln: float
    selling_power_w: int
    estimated_duration_hours: float
    reasoning: str
    safety_checks_passed: bool
    risk_level: str  # "low", "medium", "high"
    # Smart timing fields
    timing_recommendation: Optional[Any] = None  # TimingRecommendation
    should_wait_for_peak: bool = False
    optimal_sell_time: Optional[datetime] = None
    peak_price: Optional[float] = None
    opportunity_cost_pln: float = 0.0


@dataclass
class SellingSession:
    """Represents an active battery selling session"""
    session_id: str
    start_time: datetime
    start_soc: float
    target_soc: float
    selling_power_w: int
    expected_revenue_pln: float
    current_price_pln: float
    status: str  # "active", "completed", "cancelled", "failed"
    safety_margin_soc: float = 50.0


class BatterySellingEngine:
    """Conservative battery energy selling engine with safety-first approach"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the battery selling engine with configuration"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Extract battery selling configuration
        selling_config = config.get('battery_selling', {})
        
        # Conservative safety parameters (from project plan analysis)
        self.min_selling_soc = selling_config.get('min_battery_soc', 80.0)  # 80% minimum SOC (default)
        self.safety_margin_soc = selling_config.get('safety_margin_soc', 50.0)  # 50% safety margin
        # Selling thresholds
        self.min_selling_price_pln = selling_config.get('min_selling_price_pln', 0.50)  # 0.50 PLN/kWh
        
        # Revenue factor (e.g., 0.8 for 80% return)
        self.revenue_factor = selling_config.get('revenue_factor', 1.0)
        
        self.max_daily_cycles = selling_config.get('max_daily_cycles', 2)  # Max 2 cycles per day
        self.peak_hours = selling_config.get('peak_hours', [17, 18, 19, 20, 21])  # 5-9 PM
        self.grid_export_limit_w = selling_config.get('grid_export_limit_w', 5000)  # 5kW max export
        self.battery_dod_limit = selling_config.get('battery_dod_limit', 50)  # 50% max discharge
        
        # Phase 2: Dynamic SOC thresholds based on price magnitude
        smart_timing_config = selling_config.get('smart_timing', {})
        dynamic_soc_config = smart_timing_config.get('dynamic_soc_thresholds', {})
        self.dynamic_soc_enabled = dynamic_soc_config.get('enabled', False)
        self.super_premium_price_threshold = dynamic_soc_config.get('super_premium_price_threshold', 1.2)
        self.super_premium_min_soc = dynamic_soc_config.get('super_premium_min_soc', 70)
        self.premium_price_threshold = dynamic_soc_config.get('premium_price_threshold', 0.9)
        self.premium_min_soc = dynamic_soc_config.get('premium_min_soc', 75)
        self.very_high_price_threshold = dynamic_soc_config.get('very_high_price_threshold', 0.8)
        self.very_high_min_soc = dynamic_soc_config.get('very_high_min_soc', 60)
        self.high_price_threshold = dynamic_soc_config.get('high_price_threshold', 0.7)
        self.high_min_soc = dynamic_soc_config.get('high_min_soc', 80)
        self.require_peak_hours = dynamic_soc_config.get('require_peak_hours', True)
        self.require_recharge_forecast = dynamic_soc_config.get('require_recharge_forecast', True)
        
        # Phase 3: Risk-adjusted safety margin
        risk_margin_config = smart_timing_config.get('risk_adjusted_safety_margin', {})
        self.risk_adjusted_margin_enabled = risk_margin_config.get('enabled', False)
        self.conservative_margin_soc = risk_margin_config.get('conservative_margin', 55)  # High risk
        self.moderate_margin_soc = risk_margin_config.get('moderate_margin', 50)  # Medium risk
        self.aggressive_margin_soc = risk_margin_config.get('aggressive_margin', 48)  # Low risk
        self.evening_hours_start = risk_margin_config.get('evening_hours_start', 18)
        self.evening_hours_end = risk_margin_config.get('evening_hours_end', 22)
        self.min_forecast_confidence_aggressive = risk_margin_config.get('min_forecast_confidence_aggressive', 0.8)
        
        # Battery specifications - read from config
        self.battery_capacity_kwh = config.get('battery_management', {}).get('capacity_kwh', 20.0)
        self.discharge_efficiency = 0.95  # 95% efficiency
        self.usable_energy_per_cycle = self.battery_capacity_kwh * (self.min_selling_soc - self.safety_margin_soc) / 100
        self.net_sellable_energy = round(self.usable_energy_per_cycle * self.discharge_efficiency, 2)
        
        # Default DOD for normal operation (restore after selling)
        critical_soc = config.get('battery_management', {}).get('soc_thresholds', {}).get('critical', 10)
        self.default_dod = 100 - critical_soc
        
        # Session tracking
        self.active_sessions: List[SellingSession] = []
        self.daily_cycles = 0
        self.last_cycle_reset = datetime.now().date()
        
        # Smart timing engine (if available)
        self.timing_engine = None
        self.forecast_collector = None
        if TIMING_AVAILABLE:
            try:
                self.timing_engine = BatterySellingTiming(config)
                self.logger.info("Smart timing engine initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize timing engine: {e}")
        
        # Price forecast collector (if available)
        if FORECAST_AVAILABLE:
            try:
                self.forecast_collector = PSEPriceForecastCollector(config)
                self.logger.info("Price forecast collector initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize forecast collector: {e}")
        
        # Tariff pricing calculator (if available)
        self.tariff_calculator = None
        if TARIFF_PRICING_AVAILABLE:
            try:
                self.tariff_calculator = TariffPricingCalculator(config)
                self.logger.info("Tariff pricing calculator initialized for battery selling")
            except Exception as e:
                self.logger.warning(f"Failed to initialize tariff calculator: {e}")
        
        # Phase 4: Price spike detector
        self.spike_detector = None
        if SPIKE_DETECTOR_AVAILABLE:
            try:
                self.spike_detector = PriceSpikeDetector(config)
                self.logger.info("Price spike detector initialized (Phase 4)")
            except Exception as e:
                self.logger.warning(f"Failed to initialize spike detector: {e}")
        
        # Phase 4: Negative price strategy
        negative_price_config = smart_timing_config.get('negative_price_strategy', {})
        self.negative_price_enabled = negative_price_config.get('enabled', False)
        self.negative_price_threshold = negative_price_config.get('negative_price_threshold', 0.05)
        self.spike_sell_min_soc = negative_price_config.get('spike_sell_min_soc', 60)
        self.allow_sell_below_min_soc = negative_price_config.get('allow_sell_below_min_soc', True)
        
        # Phase 4: Kompas integration
        kompas_config = smart_timing_config.get('kompas_integration', {})
        self.kompas_enabled = kompas_config.get('enabled', False)
        self.s4_extreme_sell = kompas_config.get('s4_extreme_sell', True)
        self.s4_min_soc = kompas_config.get('s4_min_soc', 60)
        self.s4_ignore_forecast = kompas_config.get('s4_ignore_forecast', True)
        
        # Initialize consumption forecasting for sell-then-buy prevention
        self.consumption_forecaster = None
        self.sell_then_buy_enabled = config.get('battery_selling', {}).get('sell_then_buy_prevention', {}).get('enabled', False)  # Disabled by default for backward compatibility
        self.future_analysis_hours = config.get('battery_selling', {}).get('sell_then_buy_prevention', {}).get('analysis_hours', 12)
        self.min_savings_ratio = config.get('battery_selling', {}).get('sell_then_buy_prevention', {}).get('min_savings_ratio', 1.5)  # Revenue/cost ratio
        
        # Protection mechanisms (Phase: Buy-back protection)
        self.emergency_sell_threshold = config.get('battery_selling', {}).get('emergency_sell_price_threshold', 1.50)
        self.max_soc_drop_per_session = config.get('battery_selling', {}).get('max_soc_drop_per_session', 20)
        self.max_soc_drop_per_day = config.get('battery_selling', {}).get('max_soc_drop_per_day', 40)
        self.profit_margin_multiplier = config.get('battery_selling', {}).get('min_profit_margin_multiplier', 1.5)
        self.daily_tracking_file = Path(config.get('battery_selling', {}).get('daily_tracking_file', 'data/daily_soc_drops.json'))
        self.daily_soc_drop_tracking = self._load_daily_tracking()

        try:
            from pv_consumption_analyzer import PVConsumptionAnalyzer
            consumption_config = config.get('pv_consumption', {})
            self.consumption_forecaster = PVConsumptionAnalyzer(config)
            self.logger.info("Consumption forecaster initialized for sell-then-buy prevention")
        except Exception as e:
            self.logger.warning(f"Could not initialize consumption forecaster: {e}. Sell-then-buy prevention will use basic heuristics.")

        self.logger.info(f"Battery Selling Engine initialized with conservative parameters:")
        self.logger.info(f"  - Min selling SOC: {self.min_selling_soc}% (default)")
        self.logger.info(f"  - Safety margin SOC: {self.safety_margin_soc}%")
        self.logger.info(f"  - Min selling price: {self.min_selling_price_pln} PLN/kWh")
        self.logger.info(f"  - Usable energy per cycle: {self.usable_energy_per_cycle:.2f} kWh")
        self.logger.info(f"  - Net sellable energy: {self.net_sellable_energy:.2f} kWh")
        self.logger.info(f"  - Smart timing: {'Enabled' if self.timing_engine else 'Disabled'}")
        self.logger.info(f"  - Tariff pricing: {'Enabled' if self.tariff_calculator else 'SC-only'}")
        self.logger.info(f"  - Sell-then-buy prevention: {'Enabled' if self.sell_then_buy_enabled else 'Disabled'}")
        self.logger.info(f"  - Emergency sell threshold: {self.emergency_sell_threshold:.2f} PLN/kWh")
        self.logger.info(f"  - Max SOC drop per session: {self.max_soc_drop_per_session}%")
        self.logger.info(f"  - Max SOC drop per day: {self.max_soc_drop_per_day}%")
        self.logger.info(f"  - Phase 2 Dynamic SOC: {'Enabled' if self.dynamic_soc_enabled else 'Disabled'}")
        if self.dynamic_soc_enabled:
            self.logger.info(f"    * Super premium (>{self.super_premium_price_threshold} PLN/kWh): {self.super_premium_min_soc}% SOC")
            self.logger.info(f"    * Premium ({self.premium_price_threshold}-{self.super_premium_price_threshold} PLN/kWh): {self.premium_min_soc}% SOC")
            self.logger.info(f"    * Very high ({self.very_high_price_threshold}-{self.premium_price_threshold} PLN/kWh): {self.very_high_min_soc}% SOC")
            self.logger.info(f"    * High ({self.high_price_threshold}-{self.very_high_price_threshold} PLN/kWh): {self.high_min_soc}% SOC")
    
    def _reset_daily_cycles(self):
        """Reset daily cycle counter if new day"""
        today = datetime.now().date()
        if today != self.last_cycle_reset:
            self.daily_cycles = 0
            self.last_cycle_reset = today
            self.logger.info("Daily cycle counter reset for new day")
    
    def _load_daily_tracking(self) -> Dict[str, float]:
        """Load daily SOC drop tracking from file, clean old data (>7 days)"""
        try:
            if not self.daily_tracking_file.exists():
                self.logger.info("Daily tracking file does not exist, starting fresh")
                return {}
            
            with open(self.daily_tracking_file, 'r') as f:
                data = json.load(f)
            
            # Clean old entries (>7 days)
            cutoff_date = datetime.now().date() - timedelta(days=7)
            cleaned_data = {
                date_str: value 
                for date_str, value in data.items()
                if datetime.strptime(date_str, '%Y-%m-%d').date() >= cutoff_date
            }
            
            if len(cleaned_data) < len(data):
                self.logger.info(f"Cleaned {len(data) - len(cleaned_data)} old tracking entries")
            
            return cleaned_data
        except Exception as e:
            self.logger.warning(f"Failed to load daily tracking: {e}, starting fresh")
            return {}
    
    def _save_daily_tracking(self):
        """Atomically save daily SOC drop tracking to file"""
        try:
            # Ensure directory exists
            self.daily_tracking_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first, then atomic rename
            temp_file = self.daily_tracking_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.daily_soc_drop_tracking, f, indent=2)
            
            temp_file.replace(self.daily_tracking_file)
            self.logger.debug("Daily tracking saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save daily tracking: {e}")
    
    def _get_today_soc_drop(self) -> float:
        """Get total SOC drop for today"""
        today_str = datetime.now().strftime('%Y-%m-%d')
        return self.daily_soc_drop_tracking.get(today_str, 0.0)
    
    def _is_peak_hour(self) -> bool:
        """Check if current hour is a peak selling hour"""
        current_hour = datetime.now().hour
        return current_hour in self.peak_hours
    
    def _is_night_time(self) -> bool:
        """Check if current time is during night hours"""
        current_hour = datetime.now().hour
        return current_hour in [22, 23, 0, 1, 2, 3, 4, 5]  # 10 PM to 6 AM
    
    def _get_dynamic_min_soc(self, current_price: float, price_forecast: Optional[List[Dict[str, Any]]] = None) -> float:
        """
        Phase 2: Calculate dynamic minimum SOC based on price magnitude
        
        Args:
            current_price: Current electricity price (PLN/kWh)
            price_forecast: Optional price forecast for recharge opportunity check
            
        Returns:
            Minimum SOC threshold for current price level
        """
        if not self.dynamic_soc_enabled:
            return self.min_selling_soc  # Return default 80%
        
        # Safety check: Only allow lower SOC during peak hours if configured
        if self.require_peak_hours and not self._is_peak_hour():
            return self.min_selling_soc  # Use default 80% outside peak hours
        
        # Check for recharge opportunity in forecast if required
        # Smart approach: For premium prices (top tier), recharge opportunity is advisory (not blocking)
        # For lower prices, it's required for safety
        is_premium_price = current_price >= self.premium_price_threshold
        
        if self.require_recharge_forecast:
            if not price_forecast:
                # No forecast available
                if is_premium_price:
                    # Premium prices: allow selling without forecast (advisory only)
                    self.logger.info(f"Premium price {current_price:.3f} PLN/kWh - allowing dynamic SOC without forecast (advisory)")
                else:
                    # Lower prices: require forecast for safety
                    self.logger.warning(f"Dynamic SOC requires recharge forecast but none available - using default {self.min_selling_soc}% SOC")
                    return self.min_selling_soc  # Use default 80% - conservative
            
            has_recharge_opportunity = self._check_recharge_opportunity(price_forecast, current_price)
            if not has_recharge_opportunity:
                if is_premium_price:
                    # Premium prices: allow selling without recharge opportunity (advisory only)
                    self.logger.info(f"Premium price {current_price:.3f} PLN/kWh - allowing dynamic SOC without recharge opportunity (advisory, would prefer price < {current_price * 0.7:.3f} PLN/kWh)")
                else:
                    # Lower prices: require recharge opportunity for safety
                    self.logger.warning(f"Dynamic SOC requires recharge opportunity (price < {current_price * 0.7:.3f} PLN/kWh) in next 12h but none found - using default {self.min_selling_soc}% SOC")
                    return self.min_selling_soc  # Use default 80% if no recharge opportunity
        
        # Dynamic SOC thresholds based on price magnitude
        if current_price >= self.super_premium_price_threshold:
            # Super premium prices (>1.2 PLN/kWh) - allow selling from 70%
            self.logger.info(f"Super premium price {current_price:.3f} PLN/kWh detected - min SOC: {self.super_premium_min_soc}%")
            return self.super_premium_min_soc
        elif current_price >= self.premium_price_threshold:
            # Premium prices (0.9-1.2 PLN/kWh) - allow selling from 75%
            self.logger.info(f"Premium price {current_price:.3f} PLN/kWh detected - min SOC: {self.premium_min_soc}%")
            return self.premium_min_soc
        elif current_price >= self.very_high_price_threshold:
            # Very high prices (0.8-0.9 PLN/kWh) - allow selling from 60%
            self.logger.info(f"Very high price {current_price:.3f} PLN/kWh detected - min SOC: {self.very_high_min_soc}%")
            return self.very_high_min_soc
        elif current_price >= self.high_price_threshold:
            # High prices (0.7-0.8 PLN/kWh) - standard 80%
            return self.high_min_soc
        else:
            # Normal prices - standard 80%
            return self.min_selling_soc
    
    def _get_risk_adjusted_safety_margin(self, forecast_confidence: float = 0.7) -> float:
        """
        Calculate risk-adjusted safety margin based on multiple factors
        
        Phase 3 Feature: Adjusts safety margin (48-50-55%) based on:
        - Forecast confidence (higher confidence = lower margin)
        - Time of day (evening hours = higher margin for house usage)
        - Historical selling success
        
        Args:
            forecast_confidence: Confidence in price forecast (0-1)
            
        Returns:
            Safety margin SOC percentage (48-55%)
        """
        if not self.risk_adjusted_margin_enabled:
            return self.safety_margin_soc  # Default 50%
        
        # Factor 1: Time of day
        current_hour = datetime.now().hour
        is_evening = self.evening_hours_start <= current_hour <= self.evening_hours_end
        
        # Factor 2: Forecast confidence
        high_confidence = forecast_confidence >= self.min_forecast_confidence_aggressive
        
        # Decision matrix for safety margin
        if is_evening:
            # Conservative during evening (preserve for house usage)
            margin = self.conservative_margin_soc  # 55%
            reason = "evening hours"
        elif high_confidence:
            # Aggressive with high confidence
            margin = self.aggressive_margin_soc  # 48%
            reason = "high forecast confidence"
        else:
            # Moderate in other cases
            margin = self.moderate_margin_soc  # 50%
            reason = "moderate conditions"
        
        if margin != self.safety_margin_soc:
            self.logger.info(f"Risk-adjusted safety margin: {margin}% ({reason}, confidence: {forecast_confidence:.2f})")
        
        return margin
    
    def _check_recharge_opportunity(self, price_forecast: List[Dict[str, Any]], current_price: float) -> bool:
        """
        Check if there's a recharge opportunity (lower price) in the forecast
        
        Args:
            price_forecast: List of forecast price points
            current_price: Current price to compare against
            
        Returns:
            True if there's a lower price period within 12h for recharging
        """
        try:
            if not price_forecast:
                return False
                
            current_time = datetime.now()
            recharge_window_end = current_time + timedelta(hours=12)
            
            # Look for prices significantly lower than current (at least 30% lower for recharge)
            recharge_price_threshold = current_price * 0.7
            
            for forecast_point in price_forecast:
                if not isinstance(forecast_point, dict):
                    continue
                    
                point_time = forecast_point.get('time')
                if isinstance(point_time, str):
                    try:
                        point_time = datetime.fromisoformat(point_time.replace('Z', '+00:00'))
                    except (ValueError, AttributeError):
                        continue
                
                # Skip if no valid time or beyond window
                if not point_time:
                    continue
                    
                # Only check time comparison if point_time is a datetime object
                try:
                    if point_time > recharge_window_end:
                        continue
                except TypeError:
                    # Skip if comparison fails
                    continue
                
                price = forecast_point.get('price', forecast_point.get('forecasted_price_pln', 0))
                if price > 0 and price <= recharge_price_threshold:
                    self.logger.info(f"Recharge opportunity found: {price:.3f} PLN/kWh (threshold: {recharge_price_threshold:.3f})")
                    return True
            
            self.logger.info("No recharge opportunity found in 12h forecast")
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking recharge opportunity: {e}")
            return False  # Conservative: no recharge opportunity if error
    
    def _calculate_expected_revenue(self, current_price_pln: float, selling_duration_hours: float) -> float:
        """Calculate expected revenue from selling session"""
        selling_power_kw = self.grid_export_limit_w / 1000
        energy_sold_kwh = selling_power_kw * selling_duration_hours * self.discharge_efficiency
        # Apply revenue factor (e.g., 0.8 for 80% return)
        return energy_sold_kwh * current_price_pln * self.revenue_factor
    
    def _check_safety_conditions(self, current_data: Dict[str, Any], forecast_confidence: float = 0.7) -> Tuple[bool, str]:
        """
        Check if it's safe to start/continue selling
        
        Phase 3: Now uses risk-adjusted safety margin if enabled
        """
        try:
            # Extract current system data
            battery_soc = current_data.get('battery', {}).get('soc_percent', 0)
            battery_temp = current_data.get('battery', {}).get('temperature', 0)
            grid_voltage = current_data.get('grid', {}).get('voltage', 0)
            
            # Phase 3: Get risk-adjusted safety margin if enabled
            effective_safety_margin = self._get_risk_adjusted_safety_margin(forecast_confidence)
            
            # Safety check 1: Battery SOC above safety margin
            if battery_soc <= effective_safety_margin:
                return False, f"Battery SOC {battery_soc}% below safety margin {effective_safety_margin}%"
            
            # Safety check 2: Battery temperature within limits
            if battery_temp > 50:  # GoodWe Lynx-D max operating temp
                return False, f"Battery temperature {battery_temp}°C too high (max 50°C)"
            
            if battery_temp < -20:  # GoodWe Lynx-D min operating temp
                return False, f"Battery temperature {battery_temp}°C too low (min -20°C)"
            
            # Safety check 3: Grid voltage within limits
            if grid_voltage > 0 and not (200 <= grid_voltage <= 250):
                return False, f"Grid voltage {grid_voltage}V outside safe range (200-250V)"
            
            # Safety check 4: Daily cycle limit
            self._reset_daily_cycles()
            if self.daily_cycles >= self.max_daily_cycles:
                return False, f"Daily cycle limit reached ({self.daily_cycles}/{self.max_daily_cycles})"
            
            # Safety check 5: Not during night hours (preserve night charge)
            current_hour = datetime.now().hour
            if current_hour in [22, 23, 0, 1, 2, 3, 4, 5]:  # 10 PM to 6 AM
                return False, f"Night hours - preserving battery charge (hour {current_hour})"
            
            return True, "All safety conditions passed"
            
        except Exception as e:
            self.logger.error(f"Error checking safety conditions: {e}")
            return False, f"Safety check error: {e}"

    def _analyze_sell_then_buy_risk(self, current_data: Dict[str, Any], price_data: Dict[str, Any],
                                   price_forecast: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Analyze "sell-then-buy" risk to prevent net financial loss

        This critical function prevents the system from selling battery energy when:
        - Future consumption might force buying back at higher prices
        - Opportunity cost of selling > guaranteed cost of buying back later
        - Would create energy deficit that exceeds safety margins

        Returns:
            dict with 'safe_to_sell' (bool) and 'reason' (str)
        """
        if not self.sell_then_buy_enabled:
            return {'safe_to_sell': True, 'reason': 'Sell-then-buy prevention disabled'}

        try:
            current_soc = current_data.get('battery', {}).get('soc_percent', 0)
            current_price_pln = price_data.get('current_price_pln', 0)

            # 1. FORECAST FUTURE CONSUMPTION NEEDS
            future_consumption_kwh = self._forecast_future_consumption(current_data)
            self.logger.debug(f"Future {self.future_analysis_hours}h consumption forecast: {future_consumption_kwh:.2f} kWh")

            # 2. CALCULATE ENERGY AVAILABILITY AFTER POTENTIAL SELLING
            # Calculate maximum sellable energy
            max_sellable_energy_kwh = (current_soc - self.safety_margin_soc) / 100 * self.battery_capacity_kwh * self.discharge_efficiency

            # Be more reasonable about how much energy we'll actually sell
            # Only consider energy deficit if future consumption would consume >60% of available capacity
            energy_deficit_kwh = max(0, future_consumption_kwh - (max_sellable_energy_kwh * 0.4))  # Leave 40% buffer

            # 3. CALCULATE BUYING COST IF WE NEED TO CHARGE BACK
            buy_back_cost_pln = 0.0
            if energy_deficit_kwh > 0:
                # Find highest price in forecast for buying (conservative approach)
                max_future_price_pln = self._find_max_future_price(price_forecast, current_price_pln)
                buy_back_cost_pln = energy_deficit_kwh * max_future_price_pln
                self.logger.debug(f"Energy deficit: {energy_deficit_kwh:.2f} kWh, buy-back cost at {max_future_price_pln:.3f} PLN/kWh: {buy_back_cost_pln:.2f} PLN")

            # 4. CALCULATE SELLING REVENUE (EXPECTED FROM CURRENT OPPORTUNITY)
            # Assume we'd sell 80% of available energy (conservative estimate)
            selling_revenue_pln = max_sellable_energy_kwh * 0.8 * current_price_pln
            self.logger.debug(f"Selling revenue estimate: {selling_revenue_pln:.2f} PLN")

            # 5. OPPORTUNITY COST ANALYSIS
            # Is revenue from selling > cost of buying back later?
            net_profit_pln = selling_revenue_pln - buy_back_cost_pln
            savings_ratio = selling_revenue_pln / buy_back_cost_pln if buy_back_cost_pln > 0 else float('inf')

            self.logger.debug(f"Net profit analysis: Revenue {selling_revenue_pln:.2f} - Cost {buy_back_cost_pln:.2f} = {net_profit_pln:.2f} PLN (ratio: {savings_ratio:.2f})")

            # 6. DECISION MATRIX
            # Only block selling in extreme scenarios where we'd lose significant money
            if energy_deficit_kwh > (max_sellable_energy_kwh * 0.5):  # Would use >50% of sellable energy
                return {
                    'safe_to_sell': False,
                    'reason': f"Would create very large energy deficit ({energy_deficit_kwh:.1f} kWh > 50% of sellable capacity)"
                }

            if buy_back_cost_pln > (selling_revenue_pln * 1.5):  # Would more than double our costs
                return {
                    'safe_to_sell': False,
                    'reason': f"Buy-back cost {buy_back_cost_pln:.2f} PLN > 1.5x selling revenue {selling_revenue_pln:.1f} PLN (unacceptable cost)"
                }

            # For normal cases with reasonable ratios, allow selling
            # The prevention is more informational than blocking in most cases

            # 7. SAFE TO SELL - returns default success
            return {
                'safe_to_sell': True,
                'reason': f"Safe opportunity (revenue: {selling_revenue_pln:.1f} PLN, deficit cost: {buy_back_cost_pln:.1f} PLN, ratio: {savings_ratio:.1f})"
            }

        except Exception as e:
            self.logger.error(f"Error in sell-then-buy risk analysis: {e}")
            # Conservative: prevent selling if analysis fails
            return {
                'safe_to_sell': False,
                'reason': 'Analysis error - blocking sale for safety'
            }

    def _forecast_future_consumption(self, current_data: Dict[str, Any]) -> float:
        """
        Forecast future consumption for the analysis period

        Uses consumption analyzer if available, otherwise fallbacks to heuristics
        """
        try:
            if self.consumption_forecaster:
                # Use advanced consumption forecasting
                forecasts = self.consumption_forecaster.forecast_consumption(hours_ahead=self.future_analysis_hours)
                if forecasts:
                    # Sum forecasted consumption over the analysis period
                    total_consumption = sum(f.get('consumption_forecast_kwh', 0) for f in forecasts)
                    return total_consumption

            # Fallback: Use heuristic-based forecasting
            current_consumption = current_data.get('consumption', {}).get('power_w', 0) / 1000  # Convert to kW
            current_hour = datetime.now().hour

            # Base consumption patterns by time of day (kWh per hour)
            if 0 <= current_hour <= 5:  # Night
                base_hourly_consumption = 0.5
            elif 6 <= current_hour <= 11:  # Morning
                base_hourly_consumption = 1.0
            elif 12 <= current_hour <= 17:  # Afternoon/Evening
                base_hourly_consumption = 1.5
            else:  # Evening/Night
                base_hourly_consumption = 1.2

            # Scale by current consumption (if reading is available)
            if current_consumption > 0:
                scaling_factor = current_consumption / base_hourly_consumption
                base_hourly_consumption *= min(scaling_factor, 2.0)  # Cap scaling

            # Calculate total consumption for analysis period
            total_consumption = base_hourly_consumption * self.future_analysis_hours

            return total_consumption

        except Exception as e:
            self.logger.error(f"Error forecasting consumption: {e}")
            # Conservative fallback: assume high consumption
            return 2.0 * self.future_analysis_hours  # 2 kWh per hour

    def _find_max_future_price(self, price_forecast: Optional[List[Dict[str, Any]]], current_price_pln: float) -> float:
        """
        Find the maximum price we might need to pay for buying energy back

        Uses forecast data if available, otherwise makes conservative assumptions
        """
        try:
            max_price = current_price_pln  # At least current price

            if price_forecast:
                for forecast_point in price_forecast:
                    if isinstance(forecast_point, dict):
                        # Check different price field names
                        price = (forecast_point.get('price') or
                               forecast_point.get('forecasted_price_pln', 0) / 1000 or  # Convert PLN/MWh to PLN/kWh if needed
                               forecast_point.get('value', 0))

                        if price > 0:
                            max_price = max(max_price, price)

            # Conservative: add 25% buffer for price volatility
            max_price *= 1.25

            return max_price

        except Exception as e:
            self.logger.error(f"Error finding max future price: {e}")
            # Very conservative: assume prices could double
            return current_price_pln * 2.0

    def _analyze_selling_opportunity(self, current_data: Dict[str, Any], price_data: Dict[str, Any],
                                     price_forecast: Optional[List[Dict[str, Any]]] = None) -> SellingOpportunity:
        """Analyze if there's a good opportunity to sell battery energy (Phase 2: with dynamic SOC)"""
        try:
            # Extract current system data
            battery_soc = current_data.get('battery', {}).get('soc_percent', 0)
            pv_power = current_data.get('pv', {}).get('power_w', 0)
            consumption = current_data.get('consumption', {}).get('power_w', 0)
            current_price_pln = price_data.get('current_price_pln', 0)
            
            # EMERGENCY MODE: Bypass protections for extremely high prices
            emergency_mode = current_price_pln >= self.emergency_sell_threshold
            if emergency_mode:
                self.logger.info(
                    f"⚡ EMERGENCY SELL MODE: Price {current_price_pln:.3f} PLN/kWh exceeds threshold "
                    f"{self.emergency_sell_threshold:.2f} — bypassing buy-back and profit protections for optimal revenue"
                )

            # Check safety conditions first
            safety_ok, safety_reason = self._check_safety_conditions(current_data)
            if not safety_ok:
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"Safety check failed: {safety_reason}",
                    safety_checks_passed=False,
                    risk_level="high"
                )
            
            # Check daily cumulative SOC drop limit
            today_drop = self._get_today_soc_drop()
            if today_drop >= self.max_soc_drop_per_day:
                self.logger.info(
                    f"🛡️ BLOCKED: Daily SOC drop limit reached — used {today_drop:.1f}% of "
                    f"{self.max_soc_drop_per_day}% maximum (protects battery health)"
                )
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"Daily SOC drop limit reached: {today_drop:.1f}% of {self.max_soc_drop_per_day}% max",
                    safety_checks_passed=True,
                    risk_level="high"
                )

            # CRITICAL: Check "sell-then-buy" prevention before proceeding (skip in emergency mode)
            if not emergency_mode:
                sell_then_buy_analysis = self._analyze_sell_then_buy_risk(current_data, price_data, price_forecast)
                if not sell_then_buy_analysis.get('safe_to_sell', True):
                    self.logger.info(
                        f"🛡️ BLOCKED: Sell-then-buy protection — {sell_then_buy_analysis.get('reason', 'Risk detected')} | "
                        f"Current: {current_price_pln:.3f} PLN/kWh"
                    )
                    return SellingOpportunity(
                        decision=SellingDecision.WAIT,
                        confidence=0.0,
                        expected_revenue_pln=0.0,
                        selling_power_w=0,
                        estimated_duration_hours=0.0,
                        reasoning=f"Sell-then-buy prevention: {sell_then_buy_analysis.get('reason', 'Risk detected')}",
                        safety_checks_passed=True,
                        risk_level="high"
                    )
            else:
                self.logger.info("⚡ Emergency mode: Skipping sell-then-buy analysis (price justifies risk)")
            
            
            # Phase 2: Get dynamic minimum SOC based on price magnitude
            min_soc_required = self._get_dynamic_min_soc(current_price_pln, price_forecast)
            
            # Check minimum SOC requirement (now dynamic)
            if battery_soc < min_soc_required:
                # Provide detailed reasoning about why dynamic SOC wasn't used
                if self.dynamic_soc_enabled and min_soc_required == self.min_selling_soc:
                    # Dynamic SOC is enabled but we're using default - explain why
                    reason_parts = []
                    if self.require_peak_hours and not self._is_peak_hour():
                        reason_parts.append("outside peak hours (17-21)")
                    if self.require_recharge_forecast:
                        if not price_forecast:
                            reason_parts.append("no price forecast available")
                        elif not self._check_recharge_opportunity(price_forecast, current_price_pln):
                            recharge_threshold = current_price_pln * 0.7
                            reason_parts.append(f"no recharge opportunity (need price < {recharge_threshold:.3f} PLN/kWh in next 12h)")
                    reason_suffix = f" - using default {min_soc_required}% because: {', '.join(reason_parts)}" if reason_parts else ""
                else:
                    reason_suffix = ""
                
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"Battery SOC {battery_soc}% below minimum threshold {min_soc_required}% (price: {current_price_pln:.3f} PLN/kWh){reason_suffix}",
                    safety_checks_passed=True,
                    risk_level="low"
                )
            
            # Check minimum selling price
            if current_price_pln < self.min_selling_price_pln:
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"Current price {current_price_pln:.3f} PLN/kWh below minimum {self.min_selling_price_pln} PLN/kWh",
                    safety_checks_passed=True,
                    risk_level="low"
                )
            
            # Check profit margin (skip in emergency mode)
            if not emergency_mode:
                min_profitable_price = self.min_selling_price_pln * self.profit_margin_multiplier
                if current_price_pln < min_profitable_price:
                    self.logger.info(
                        f"🛡️ BLOCKED: Insufficient profit margin — Price {current_price_pln:.3f} < "
                        f"{min_profitable_price:.3f} PLN/kWh ({self.profit_margin_multiplier}x threshold)"
                    )
                    return SellingOpportunity(
                        decision=SellingDecision.WAIT,
                        confidence=0.0,
                        expected_revenue_pln=0.0,
                        selling_power_w=0,
                        estimated_duration_hours=0.0,
                        reasoning=f"Price {current_price_pln:.3f} below profitable threshold {min_profitable_price:.3f} PLN/kWh",
                        safety_checks_passed=True,
                        risk_level="medium"
                    )
            
            
            # Check if PV is insufficient (prefer PV over battery)
            if pv_power >= consumption:
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"PV power {pv_power}W sufficient for consumption {consumption}W - no need to sell battery",
                    safety_checks_passed=True,
                    risk_level="low"
                )
            
            # Calculate selling parameters
            power_deficit = consumption - pv_power
            # For selling, we want to export max allowed power, not just cover deficit
            selling_power_w = self.grid_export_limit_w
            
            # Calculate duration based on available energy
            available_energy_kwh = (battery_soc - self.safety_margin_soc) / 100 * self.battery_capacity_kwh
            estimated_duration_hours = available_energy_kwh / (selling_power_w / 1000)
            
            # Apply SOC drop limits (per session and daily)
            today_drop = self._get_today_soc_drop()
            remaining_daily = self.max_soc_drop_per_day - today_drop
            max_allowed_soc_drop = min(
                battery_soc - self.safety_margin_soc,  # Available above safety margin
                self.max_soc_drop_per_session,          # Per-session limit
                remaining_daily                         # Remaining daily budget
            )
            
            if max_allowed_soc_drop <= 0:
                self.logger.info(
                    f"🛡️ BLOCKED: No SOC drop budget remaining (session: {self.max_soc_drop_per_session}%, "
                    f"daily remaining: {remaining_daily:.1f}%)"
                )
                return SellingOpportunity(
                    decision=SellingDecision.WAIT,
                    confidence=0.0,
                    expected_revenue_pln=0.0,
                    selling_power_w=0,
                    estimated_duration_hours=0.0,
                    reasoning=f"SOC drop budget exhausted (daily remaining: {remaining_daily:.1f}%)",
                    safety_checks_passed=True,
                    risk_level="medium"
                )
            
            # Cap energy to allowed SOC drop
            max_allowed_energy_kwh = (max_allowed_soc_drop / 100) * self.battery_capacity_kwh
            if available_energy_kwh > max_allowed_energy_kwh:
                available_energy_kwh = max_allowed_energy_kwh
                estimated_duration_hours = available_energy_kwh / (selling_power_w / 1000)
                self.logger.info(
                    f"🛡️ LIMITING SALE: Capping to {max_allowed_soc_drop:.1f}% SOC drop | "
                    f"Session limit: {self.max_soc_drop_per_session}%, Daily remaining: {remaining_daily:.1f}%"
                )
            
            # Calculate expected revenue
            expected_revenue = self._calculate_expected_revenue(current_price_pln, estimated_duration_hours)
            
            # Calculate confidence based on multiple factors
            confidence = self._calculate_confidence(battery_soc, current_price_pln, power_deficit)
            
            # Determine risk level
            risk_level = self._assess_risk_level(battery_soc, current_price_pln, estimated_duration_hours)
            
            # Make decision
            if confidence >= 0.7 and expected_revenue >= 1.0:  # At least 1 PLN revenue
                decision = SellingDecision.START_SELLING
                reasoning = f"Good selling opportunity: {battery_soc}% SOC, {current_price_pln:.3f} PLN/kWh, {expected_revenue:.2f} PLN revenue"
                
                # Prefix with emergency indicator if in emergency mode
                if emergency_mode:
                    reasoning = f"⚡ EMERGENCY: {reasoning}"
            else:
                decision = SellingDecision.WAIT
                reasoning = f"Not optimal: confidence {confidence:.2f}, revenue {expected_revenue:.2f} PLN"
            
            return SellingOpportunity(
                decision=decision,
                confidence=confidence,
                expected_revenue_pln=expected_revenue,
                selling_power_w=selling_power_w,
                estimated_duration_hours=estimated_duration_hours,
                reasoning=reasoning,
                safety_checks_passed=True,
                risk_level=risk_level
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing selling opportunity: {e}")
            return SellingOpportunity(
                decision=SellingDecision.WAIT,
                confidence=0.0,
                expected_revenue_pln=0.0,
                selling_power_w=0,
                estimated_duration_hours=0.0,
                reasoning=f"Analysis error: {e}",
                safety_checks_passed=False,
                risk_level="high"
            )
    
    def _calculate_confidence(self, battery_soc: float, current_price_pln: float, power_deficit: float) -> float:
        """Calculate confidence score for selling decision"""
        confidence = 0.0
        
        # SOC factor (higher SOC = higher confidence)
        soc_factor = min(battery_soc / 100, 1.0)
        confidence += soc_factor * 0.3
        
        # Price factor (higher price = higher confidence)
        price_factor = min(current_price_pln / 1.0, 1.0)  # Normalize to 1.0 PLN/kWh
        confidence += price_factor * 0.3
        
        # Power deficit factor (higher deficit = higher confidence)
        deficit_factor = min(power_deficit / 2000, 1.0)  # Normalize to 2kW deficit
        confidence += deficit_factor * 0.2
        
        # Peak hour factor
        peak_factor = 0.1 if self._is_peak_hour() else 0.0
        confidence += peak_factor
        
        # Safety margin factor (more margin = higher confidence)
        margin_delta = self.min_selling_soc - self.safety_margin_soc
        if margin_delta <= 0:
            # When min_selling equals safety margin, avoid division by zero
            margin_factor = 1.0 if battery_soc >= self.min_selling_soc else 0.0
        else:
            margin_factor = (battery_soc - self.safety_margin_soc) / margin_delta
        margin_factor = max(0.0, min(margin_factor, 1.0))
        confidence += margin_factor * 0.1
        
        return min(confidence, 1.0)
    
    def _assess_risk_level(self, battery_soc: float, current_price_pln: float, duration_hours: float) -> str:
        """Assess risk level of selling opportunity"""
        risk_score = 0
        
        # SOC risk (lower SOC = higher risk)
        if battery_soc < 85:
            risk_score += 1
        if battery_soc < 75:
            risk_score += 1
        
        # Price risk (lower price = higher risk)
        if current_price_pln < 0.6:
            risk_score += 1
        if current_price_pln < 0.4:
            risk_score += 1
        
        # Duration risk (longer duration = higher risk)
        if duration_hours > 2:
            risk_score += 1
        if duration_hours > 4:
            risk_score += 1
        
        # Determine risk level
        if risk_score <= 1:
            return "low"
        elif risk_score <= 3:
            return "medium"
        else:
            return "high"
    
    async def analyze_selling_opportunity(self, current_data: Dict[str, Any], price_data: Dict[str, Any]) -> SellingOpportunity:
        """Main method to analyze selling opportunity with smart timing (Phase 2: with dynamic SOC)"""
        # Phase 2: Get price forecast for dynamic SOC calculation
        price_forecast = await self._get_price_forecast()
        
        # Run basic analysis with forecast for dynamic SOC
        basic_opportunity = self._analyze_selling_opportunity(current_data, price_data, price_forecast)
        
        # If timing engine not available or basic analysis says WAIT, return immediately
        if not self.timing_engine or basic_opportunity.decision == SellingDecision.WAIT:
            return basic_opportunity
        
        # If basic analysis says START_SELLING, check if we should wait for better price
        if basic_opportunity.decision == SellingDecision.START_SELLING:
            try:
                # Get price forecast
                price_forecast = await self._get_price_forecast()
                
                if price_forecast:
                    # Get current price in PLN/kWh
                    current_price_pln = price_data.get('current_price_pln', 0)
                    if not current_price_pln:
                        # Try to extract from price_data
                        current_price_pln = self._extract_current_price(price_data)
                    
                    # Get forecast confidence
                    forecast_confidence = self.forecast_collector.get_forecast_confidence() if self.forecast_collector else 0.8
                    
                    # Analyze timing
                    timing_rec = self.timing_engine.analyze_selling_timing(
                        current_price=current_price_pln,
                        price_forecast=price_forecast,
                        current_data=current_data,
                        forecast_confidence=forecast_confidence
                    )
                    
                    # Update opportunity with timing recommendation
                    basic_opportunity.timing_recommendation = timing_rec
                    basic_opportunity.opportunity_cost_pln = timing_rec.opportunity_cost_pln
                    
                    # If timing says WAIT, update decision
                    if timing_rec.decision in [TimingDecision.WAIT_FOR_PEAK, TimingDecision.WAIT_FOR_HIGHER]:
                        basic_opportunity.decision = SellingDecision.WAIT
                        basic_opportunity.reasoning = f"Smart timing: {timing_rec.reasoning}"
                        basic_opportunity.should_wait_for_peak = True
                        basic_opportunity.optimal_sell_time = timing_rec.sell_time
                        basic_opportunity.peak_price = timing_rec.peak_info.peak_price if timing_rec.peak_info else None
                        basic_opportunity.confidence = timing_rec.confidence
                        
                        self.logger.info(f"Smart timing: Waiting for better price. {timing_rec.reasoning}")
                    
                    # If timing says NO_OPPORTUNITY, update decision
                    elif timing_rec.decision == TimingDecision.NO_OPPORTUNITY:
                        basic_opportunity.decision = SellingDecision.WAIT
                        basic_opportunity.reasoning = f"Smart timing: {timing_rec.reasoning}"
                        basic_opportunity.confidence = timing_rec.confidence
                        
                        self.logger.info(f"Smart timing: No good opportunity. {timing_rec.reasoning}")
                    
                    # If timing says SELL_NOW, keep the START_SELLING decision
                    else:
                        basic_opportunity.reasoning += f" | Smart timing: {timing_rec.reasoning}"
                        basic_opportunity.confidence = max(basic_opportunity.confidence, timing_rec.confidence)
                        
                        self.logger.info(f"Smart timing: Confirmed sell now. {timing_rec.reasoning}")
                        
            except Exception as e:
                self.logger.error(f"Error in smart timing analysis: {e}")
                # Fall back to basic analysis
        
        return basic_opportunity
    
    async def _get_price_forecast(self) -> List[Dict[str, Any]]:
        """Get price forecast data"""
        if not self.forecast_collector:
            return []
        
        try:
            # Fetch forecast
            forecast_points = self.forecast_collector.fetch_price_forecast()
            
            # Convert to format expected by timing engine
            forecast_data = []
            for point in forecast_points:
                forecast_data.append({
                    'time': point.time.isoformat(),
                    'price': point.forecasted_price_pln / 1000,  # Convert PLN/MWh to PLN/kWh
                    'forecasted_price_pln': point.forecasted_price_pln,
                    'confidence': point.confidence
                })
            
            return forecast_data
            
        except Exception as e:
            self.logger.error(f"Error fetching price forecast: {e}")
            return []
    
    def _extract_current_price(self, price_data: Dict[str, Any], kompas_status: Optional[str] = None) -> float:
        """Extract current price from price_data with tariff-aware pricing"""
        try:
            # Try different price data formats
            if 'current_price_pln' in price_data:
                return price_data['current_price_pln']
            
            if 'value' in price_data:
                # CSDAC format - find current time period
                current_time = datetime.now()
                for item in price_data['value']:
                    item_time_str = item.get('dtime', '')
                    if not item_time_str:
                        continue
                    
                    try:
                        if ':' in item_time_str and item_time_str.count(':') == 2:
                            item_time = datetime.strptime(item_time_str, '%Y-%m-%d %H:%M:%S')
                        else:
                            item_time = datetime.strptime(item_time_str, '%Y-%m-%d %H:%M')
                    except ValueError:
                        continue
                    
                    if item_time <= current_time < item_time + timedelta(minutes=15):
                        market_price = float(item.get('csdac_pln', 0))
                        
                        if self.tariff_calculator:
                            # Use tariff-aware pricing
                            market_price_kwh = market_price / 1000
                            components = self.tariff_calculator.calculate_final_price(
                                market_price_kwh, item_time, kompas_status
                            )
                            return components.final_price
                        else:
                            # Fallback: SC component only
                            return (market_price + 89.2) / 1000  # Convert to PLN/kWh
            
            # Default fallback
            return self.min_selling_price_pln
            
        except Exception as e:
            self.logger.error(f"Error extracting current price: {e}")
            return self.min_selling_price_pln
    
    async def ensure_safe_state(self, inverter: Inverter) -> bool:
        """Ensure inverter is in safe state (General mode, no export, default DOD) on startup"""
        try:
            self.logger.info(f"Ensuring inverter is in safe state (General mode, DOD {self.default_dod}%)...")
            await inverter.set_operation_mode(OperationMode.GENERAL)
            await inverter.set_grid_export_limit(0)
            await inverter.set_ongrid_battery_dod(self.default_dod)
            return True
        except Exception as e:
            self.logger.error(f"Failed to ensure safe state: {e}")
            return False

    async def start_selling_session(self, inverter: Inverter, opportunity: SellingOpportunity) -> bool:
        """Start a battery selling session using GoodWe inverter"""
        try:
            if opportunity.decision != SellingDecision.START_SELLING:
                self.logger.warning("Cannot start selling session - decision is not START_SELLING")
                return False
            
            if not opportunity.safety_checks_passed:
                self.logger.error("Cannot start selling session - safety checks failed")
                return False
            
            # Create selling session
            session = SellingSession(
                session_id=f"selling_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                start_time=datetime.now(),
                start_soc=0,  # Will be updated from inverter
                target_soc=self.safety_margin_soc,
                selling_power_w=opportunity.selling_power_w,
                expected_revenue_pln=opportunity.expected_revenue_pln,
                current_price_pln=0,  # Will be updated
                status="active"
            )
            
            # Get current SOC for tracking
            try:
                current_soc = await inverter.get_battery_soc()
                session.start_soc = current_soc
            except Exception as e:
                self.logger.warning(f"Could not get battery SOC: {e}")
                session.start_soc = 0
            
            # Set inverter to eco_discharge mode
            # Note: ECO_DISCHARGE mode expects power in % (0-100), not Watts
            # We set 100% here and rely on set_grid_export_limit to cap the actual export
            await inverter.set_operation_mode(
                OperationMode.ECO_DISCHARGE,
                100,  # Power limit % (100% = max discharge)
                int(self.safety_margin_soc)  # Min SOC (safety margin) (ensure int)
            )
            
            # Enable grid export
            await inverter.set_grid_export_limit(int(opportunity.selling_power_w))
            await inverter.set_ongrid_battery_dod(self.battery_dod_limit)
            
            # Add to active sessions
            self.active_sessions.append(session)
            self.daily_cycles += 1
            
            self.logger.info(f"Started selling session {session.session_id}:")
            self.logger.info(f"  - Selling power: {opportunity.selling_power_w}W")
            self.logger.info(f"  - Expected revenue: {opportunity.expected_revenue_pln:.2f} PLN")
            self.logger.info(f"  - Estimated duration: {opportunity.estimated_duration_hours:.1f} hours")
            self.logger.info(f"  - Safety margin SOC: {self.safety_margin_soc}%")
            
            return True
            
        except InverterError as e:
            self.logger.error(f"GoodWe inverter error starting selling session: {e}")
            self.logger.error(traceback.format_exc())
            return False
        except Exception as e:
            self.logger.error(f"Error starting selling session: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def stop_selling_session(self, inverter: Inverter, session_id: str) -> bool:
        """Stop a battery selling session"""
        try:
            # Find the session
            session = next((s for s in self.active_sessions if s.session_id == session_id), None)
            if not session:
                self.logger.warning(f"Selling session {session_id} not found")
                return False
            
            # Set inverter back to general mode
            await inverter.set_operation_mode(OperationMode.GENERAL)
            
            # Disable grid export
            await inverter.set_grid_export_limit(0)
            
            # Restore default DOD
            await inverter.set_ongrid_battery_dod(self.default_dod)
            
            # Update session status
            session.status = "completed"
            
            # Track SOC drop for daily limit enforcement
            try:
                end_soc = await inverter.get_battery_soc()
                if session.start_soc > 0:  # Only track if we have valid start SOC
                    soc_drop = session.start_soc - end_soc
                    if soc_drop > 0:  # Only track actual drops
                        today_str = datetime.now().strftime('%Y-%m-%d')
                        self.daily_soc_drop_tracking[today_str] = self.daily_soc_drop_tracking.get(today_str, 0.0) + soc_drop
                        self._save_daily_tracking()
                        self.logger.info(
                            f"Session {session_id} SOC drop: {soc_drop:.1f}% "
                            f"(daily total: {self.daily_soc_drop_tracking[today_str]:.1f}%)"
                        )
            except Exception as e:
                self.logger.warning(f"Could not track SOC drop: {e}")
            
            # Remove from active sessions
            self.active_sessions = [s for s in self.active_sessions if s.session_id != session_id]
            
            self.logger.info(f"Stopped selling session {session_id}")
            return True
            
        except InverterError as e:
            self.logger.error(f"GoodWe inverter error stopping selling session: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error stopping selling session: {e}")
            return False
    
    async def update_active_sessions(self, inverter: Inverter, current_data: Dict[str, Any]) -> List[str]:
        """Update active sessions and stop completed ones"""
        completed_sessions = []
        # Create a copy of active_sessions to iterate over
        for session in list(self.active_sessions):
            # Check if target SOC reached
            current_soc = current_data.get('battery', {}).get('soc_percent', 0)
            # Add small buffer (1%) to ensure we stop when we hit the target
            if current_soc <= session.target_soc + 1.0:
                self.logger.info(f"Session {session.session_id} target SOC reached ({current_soc}% <= {session.target_soc + 1.0}%)")
                await self.stop_selling_session(inverter, session.session_id)
                completed_sessions.append(session.session_id)
        return completed_sessions

    def get_selling_status(self) -> Dict[str, Any]:
        """Get current selling status and statistics"""
        self._reset_daily_cycles()
        
        return {
            "active_sessions": len(self.active_sessions),
            "daily_cycles": self.daily_cycles,
            "max_daily_cycles": self.max_daily_cycles,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "start_time": s.start_time.isoformat(),
                    "status": s.status,
                    "selling_power_w": s.selling_power_w,
                    "expected_revenue_pln": s.expected_revenue_pln
                }
                for s in self.active_sessions
            ],
            "configuration": {
                "min_selling_soc": self.min_selling_soc,
                "safety_margin_soc": self.safety_margin_soc,
                "min_selling_price_pln": self.min_selling_price_pln,
                "grid_export_limit_w": self.grid_export_limit_w,
                "usable_energy_per_cycle_kwh": self.usable_energy_per_cycle,
                "net_sellable_energy_kwh": self.net_sellable_energy
            }
        }
    
    def get_revenue_estimate(self) -> Dict[str, Any]:
        """Get revenue estimation based on conservative parameters"""
        # Conservative daily revenue estimate
        daily_revenue = self.net_sellable_energy * 0.25  # 0.25 PLN/kWh average price spread
        monthly_revenue = daily_revenue * 30
        annual_revenue = daily_revenue * 365
        
        return {
            "daily_revenue_pln": round(daily_revenue, 2),
            "monthly_revenue_pln": round(monthly_revenue, 2),
            "annual_revenue_pln": round(annual_revenue, 2),
            "cycles_per_day": self.max_daily_cycles,
            "energy_per_cycle_kwh": self.net_sellable_energy,
            "average_price_spread_pln": 0.25,
            "note": "Conservative estimates based on 80% min SOC, 50% safety margin"
        }
