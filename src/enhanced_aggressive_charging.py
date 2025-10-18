#!/usr/bin/env python3
"""
Enhanced Aggressive Charging Module

This module implements improved aggressive charging logic that:
- Uses percentage-based price thresholds (not fixed PLN amounts)
- Analyzes historical price percentiles (only charge at truly cheap prices)
- Detects continuous cheap price periods (not just ±1 hour)
- Integrates with PSE D+1 forecast (checks tomorrow's prices)
- Implements price categories (super_cheap, very_cheap, cheap, moderate)
- Coordinates with battery selling (reserves capacity for selling opportunities)
- Compares to median/average prices (not just cheapest)
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from tariff_pricing import TariffPricingCalculator, PriceComponents

logger = logging.getLogger(__name__)


class PriceCategory(Enum):
    """Price category classification"""
    SUPER_CHEAP = "super_cheap"      # < 0.20 PLN/kWh
    VERY_CHEAP = "very_cheap"        # 0.20-0.30 PLN/kWh
    CHEAP = "cheap"                  # 0.30-0.40 PLN/kWh
    MODERATE = "moderate"            # 0.40-0.60 PLN/kWh
    EXPENSIVE = "expensive"          # 0.60-0.80 PLN/kWh
    VERY_EXPENSIVE = "very_expensive" # > 0.80 PLN/kWh


@dataclass
class PriceAnalysis:
    """Comprehensive price analysis"""
    current_price: float
    cheapest_price: float
    cheapest_hour: int
    median_price: float
    average_price: float
    percentile_25th: float
    percentile_75th: float
    current_percentile: float  # Where current price ranks (0-100)
    category: PriceCategory
    is_historically_cheap: bool  # Is in bottom 25% of prices
    is_below_median: bool
    is_near_cheapest: bool  # Within threshold of cheapest


@dataclass
class ChargingPeriod:
    """Represents a continuous cheap charging period"""
    start_hour: int
    end_hour: int
    duration_hours: float
    avg_price: float
    min_price: float
    category: PriceCategory


@dataclass
class ChargingDecision:
    """Enhanced charging decision with detailed reasoning"""
    should_charge: bool
    reason: str
    priority: str  # 'emergency', 'high', 'medium', 'low'
    confidence: float
    target_soc: int  # Target SOC for this charging session
    estimated_duration_hours: float
    price_category: PriceCategory
    opportunity_cost: float  # Cost of charging now vs waiting


class EnhancedAggressiveCharging:
    """Enhanced aggressive charging logic"""
    
    def __init__(self, config: Dict):
        """Initialize enhanced aggressive charging"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        aggressive_config = config.get('coordinator', {}).get('cheapest_price_aggressive_charging', {})
        
        self.enabled = aggressive_config.get('enabled', True)
        
        # Percentage-based thresholds (not fixed PLN amounts)
        self.price_threshold_percent = aggressive_config.get('price_threshold_percent', 10)  # Within 10% of cheapest
        
        # Price category thresholds (PLN/kWh)
        self.super_cheap_threshold = aggressive_config.get('super_cheap_threshold', 0.20)
        self.very_cheap_threshold = aggressive_config.get('very_cheap_threshold', 0.30)
        self.cheap_threshold = aggressive_config.get('cheap_threshold', 0.40)
        self.moderate_threshold = aggressive_config.get('moderate_threshold', 0.60)
        self.expensive_threshold = aggressive_config.get('expensive_threshold', 0.80)
        
        # Target SOC by price category
        self.super_cheap_target_soc = aggressive_config.get('super_cheap_target_soc', 100)
        self.very_cheap_target_soc = aggressive_config.get('very_cheap_target_soc', 90)
        self.cheap_target_soc = aggressive_config.get('cheap_target_soc', 80)
        
        # Battery selling coordination
        self.coordinate_with_selling = aggressive_config.get('coordinate_with_selling', True)
        self.min_selling_reserve_percent = aggressive_config.get('min_selling_reserve_percent', 5)
        
        # Historical price analysis
        self.use_percentile_analysis = aggressive_config.get('use_percentile_analysis', True)
        self.percentile_threshold = aggressive_config.get('percentile_threshold', 25)  # Bottom 25%
        
        # Forecast integration
        self.use_d1_forecast = aggressive_config.get('use_d1_forecast', True)
        self.min_tomorrow_price_diff_percent = aggressive_config.get('min_tomorrow_price_diff_percent', 30)
        
        # SOC ranges
        self.min_battery_soc_for_aggressive = aggressive_config.get('min_battery_soc_for_aggressive', 30)
        self.max_battery_soc_for_aggressive = aggressive_config.get('max_battery_soc_for_aggressive', 85)
        
        # Battery selling integration
        battery_selling_config = config.get('battery_selling', {})
        self.battery_selling_enabled = battery_selling_config.get('enabled', False)
        self.min_selling_soc = battery_selling_config.get('min_battery_soc', 80)
        
        # Initialize tariff pricing calculator
        try:
            self.tariff_calculator = TariffPricingCalculator(config)
            self.logger.info("Tariff pricing calculator initialized for enhanced aggressive charging")
        except Exception as e:
            self.logger.error(f"Failed to initialize tariff calculator: {e}")
            self.tariff_calculator = None
        
        self.logger.info(f"Enhanced Aggressive Charging initialized (enabled: {self.enabled})")
        self.logger.info(f"  - Price threshold: {self.price_threshold_percent}% of cheapest")
        self.logger.info(f"  - Percentile analysis: {'enabled' if self.use_percentile_analysis else 'disabled'}")
        self.logger.info(f"  - D+1 forecast: {'enabled' if self.use_d1_forecast else 'disabled'}")
        self.logger.info(f"  - Battery selling coordination: {'enabled' if self.coordinate_with_selling else 'disabled'}")
    
    def analyze_prices(self, price_data: Dict, forecast_data: Optional[List[Dict]] = None) -> PriceAnalysis:
        """Comprehensive price analysis"""
        try:
            # Extract current and cheapest prices
            current_price = self._extract_current_price(price_data)
            cheapest_price, cheapest_hour = self._extract_cheapest_price(price_data)
            
            if not current_price or not cheapest_price:
                return None
            
            # Extract all today's prices for statistical analysis
            all_prices = self._extract_all_prices(price_data)
            
            if len(all_prices) < 10:  # Need sufficient data
                return None
            
            # Calculate statistics
            median_price = statistics.median(all_prices)
            average_price = statistics.mean(all_prices)
            sorted_prices = sorted(all_prices)
            percentile_25th = sorted_prices[int(len(sorted_prices) * 0.25)]
            percentile_75th = sorted_prices[int(len(sorted_prices) * 0.75)]
            
            # Determine current price percentile rank
            rank = sum(1 for p in all_prices if p <= current_price)
            current_percentile = (rank / len(all_prices)) * 100
            
            # Classify price category
            category = self._classify_price_category(current_price)
            
            # Determine if historically cheap
            is_historically_cheap = current_price <= percentile_25th
            
            # Determine if below median
            is_below_median = current_price <= median_price
            
            # Determine if near cheapest (percentage-based)
            price_threshold = cheapest_price * (1 + self.price_threshold_percent / 100)
            is_near_cheapest = current_price <= price_threshold
            
            analysis = PriceAnalysis(
                current_price=current_price,
                cheapest_price=cheapest_price,
                cheapest_hour=cheapest_hour,
                median_price=median_price,
                average_price=average_price,
                percentile_25th=percentile_25th,
                percentile_75th=percentile_75th,
                current_percentile=current_percentile,
                category=category,
                is_historically_cheap=is_historically_cheap,
                is_below_median=is_below_median,
                is_near_cheapest=is_near_cheapest
            )
            
            self.logger.debug(f"Price analysis: current={current_price:.3f}, median={median_price:.3f}, "
                            f"percentile={current_percentile:.1f}%, category={category.value}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing prices: {e}")
            return None
    
    def detect_charging_periods(self, price_data: Dict) -> List[ChargingPeriod]:
        """Detect continuous cheap charging periods"""
        try:
            periods = []
            
            # Extract hourly prices
            hourly_prices = self._extract_hourly_prices(price_data)
            
            if not hourly_prices:
                return periods
            
            # Find continuous cheap periods
            current_period_start = None
            current_period_prices = []
            
            for hour, price in sorted(hourly_prices.items()):
                category = self._classify_price_category(price)
                
                # Start new period if price is cheap enough
                if category in [PriceCategory.SUPER_CHEAP, PriceCategory.VERY_CHEAP, PriceCategory.CHEAP]:
                    if current_period_start is None:
                        current_period_start = hour
                        current_period_prices = [price]
                    else:
                        # Continue current period
                        current_period_prices.append(price)
                else:
                    # End current period
                    if current_period_start is not None and len(current_period_prices) >= 2:
                        # Period must be at least 2 hours
                        period = ChargingPeriod(
                            start_hour=current_period_start,
                            end_hour=hour - 1,
                            duration_hours=len(current_period_prices),
                            avg_price=statistics.mean(current_period_prices),
                            min_price=min(current_period_prices),
                            category=self._classify_price_category(min(current_period_prices))
                        )
                        periods.append(period)
                    
                    current_period_start = None
                    current_period_prices = []
            
            # Handle period that extends to end of day
            if current_period_start is not None and len(current_period_prices) >= 2:
                period = ChargingPeriod(
                    start_hour=current_period_start,
                    end_hour=23,
                    duration_hours=len(current_period_prices),
                    avg_price=statistics.mean(current_period_prices),
                    min_price=min(current_period_prices),
                    category=self._classify_price_category(min(current_period_prices))
                )
                periods.append(period)
            
            self.logger.debug(f"Detected {len(periods)} charging periods")
            for period in periods:
                self.logger.debug(f"  Period: {period.start_hour:02d}:00-{period.end_hour:02d}:00, "
                                f"avg={period.avg_price:.3f}, category={period.category.value}")
            
            return periods
            
        except Exception as e:
            self.logger.error(f"Error detecting charging periods: {e}")
            return []
    
    def should_charge_aggressively(self, battery_soc: int, price_data: Dict, 
                                   forecast_data: Optional[List[Dict]] = None,
                                   current_data: Optional[Dict] = None) -> ChargingDecision:
        """Main decision method for aggressive charging"""
        try:
            # Check if enabled
            if not self.enabled:
                return ChargingDecision(
                    should_charge=False,
                    reason="Enhanced aggressive charging disabled",
                    priority='low',
                    confidence=0.0,
                    target_soc=battery_soc,
                    estimated_duration_hours=0.0,
                    price_category=PriceCategory.MODERATE,
                    opportunity_cost=0.0
                )
            
            # Check SOC range
            if battery_soc < self.min_battery_soc_for_aggressive or battery_soc > self.max_battery_soc_for_aggressive:
                return ChargingDecision(
                    should_charge=False,
                    reason=f"Battery SOC {battery_soc}% outside aggressive charging range ({self.min_battery_soc_for_aggressive}-{self.max_battery_soc_for_aggressive}%)",
                    priority='low',
                    confidence=0.0,
                    target_soc=battery_soc,
                    estimated_duration_hours=0.0,
                    price_category=PriceCategory.MODERATE,
                    opportunity_cost=0.0
                )
            
            # Analyze current prices
            price_analysis = self.analyze_prices(price_data, forecast_data)
            
            if not price_analysis:
                return ChargingDecision(
                    should_charge=False,
                    reason="Insufficient price data for analysis",
                    priority='low',
                    confidence=0.0,
                    target_soc=battery_soc,
                    estimated_duration_hours=0.0,
                    price_category=PriceCategory.MODERATE,
                    opportunity_cost=0.0
                )
            
            # Rule 1: Only charge if price is historically cheap (bottom 25%)
            if self.use_percentile_analysis and not price_analysis.is_historically_cheap:
                return ChargingDecision(
                    should_charge=False,
                    reason=f"Price {price_analysis.current_price:.3f} PLN/kWh not historically cheap ({price_analysis.current_percentile:.1f}th percentile, need <{self.percentile_threshold}%)",
                    priority='low',
                    confidence=0.0,
                    target_soc=battery_soc,
                    estimated_duration_hours=0.0,
                    price_category=price_analysis.category,
                    opportunity_cost=0.0
                )
            
            # Rule 2: Check if we're in a cheap charging period
            charging_periods = self.detect_charging_periods(price_data)
            current_hour = datetime.now().hour
            
            in_cheap_period = False
            current_period = None
            
            for period in charging_periods:
                if period.start_hour <= current_hour <= period.end_hour:
                    in_cheap_period = True
                    current_period = period
                    break
            
            if not in_cheap_period:
                # Check if cheap period is coming soon (within 1 hour)
                upcoming_period = None
                for period in charging_periods:
                    if 0 <= period.start_hour - current_hour <= 1:
                        upcoming_period = period
                        break
                
                if upcoming_period:
                    return ChargingDecision(
                        should_charge=False,
                        reason=f"Cheap period starting soon at {upcoming_period.start_hour:02d}:00 (avg {upcoming_period.avg_price:.3f} PLN/kWh) - wait",
                        priority='low',
                        confidence=0.8,
                        target_soc=battery_soc,
                        estimated_duration_hours=0.0,
                        price_category=price_analysis.category,
                        opportunity_cost=0.0
                    )
                
                return ChargingDecision(
                    should_charge=False,
                    reason=f"Not in cheap charging period (current hour {current_hour:02d}:00, price {price_analysis.current_price:.3f} PLN/kWh)",
                    priority='low',
                    confidence=0.0,
                    target_soc=battery_soc,
                    estimated_duration_hours=0.0,
                    price_category=price_analysis.category,
                    opportunity_cost=0.0
                )
            
            # Rule 3: Check tomorrow's forecast if available
            if self.use_d1_forecast and forecast_data:
                tomorrow_analysis = self._analyze_tomorrow_prices(forecast_data)
                if tomorrow_analysis:
                    # If tomorrow has significantly cheaper prices, wait
                    savings_percent = ((price_analysis.current_price - tomorrow_analysis['min_price']) / 
                                     price_analysis.current_price) * 100
                    
                    if savings_percent >= self.min_tomorrow_price_diff_percent:
                        return ChargingDecision(
                            should_charge=False,
                            reason=f"Tomorrow has much cheaper prices (min {tomorrow_analysis['min_price']:.3f} vs current {price_analysis.current_price:.3f}, {savings_percent:.1f}% savings) - wait",
                            priority='low',
                            confidence=0.9,
                            target_soc=battery_soc,
                            estimated_duration_hours=0.0,
                            price_category=price_analysis.category,
                            opportunity_cost=(price_analysis.current_price - tomorrow_analysis['min_price']) * 10  # Assume 10kWh charging
                        )
            
            # Rule 4: Determine target SOC based on price category and battery selling
            target_soc = self._calculate_target_soc(price_analysis, battery_soc)
            
            # Rule 5: Make final decision
            if price_analysis.category == PriceCategory.SUPER_CHEAP:
                # Super cheap prices - definitely charge
                return ChargingDecision(
                    should_charge=True,
                    reason=f"SUPER CHEAP price {price_analysis.current_price:.3f} PLN/kWh (< {self.super_cheap_threshold}) - charge to {target_soc}%",
                    priority='high',
                    confidence=0.95,
                    target_soc=target_soc,
                    estimated_duration_hours=self._estimate_charging_time(battery_soc, target_soc),
                    price_category=price_analysis.category,
                    opportunity_cost=0.0
                )
            
            elif price_analysis.category == PriceCategory.VERY_CHEAP:
                # Very cheap prices - charge if below median
                if price_analysis.is_below_median:
                    return ChargingDecision(
                        should_charge=True,
                        reason=f"VERY CHEAP price {price_analysis.current_price:.3f} PLN/kWh (< {self.very_cheap_threshold}, below median {price_analysis.median_price:.3f}) - charge to {target_soc}%",
                        priority='high',
                        confidence=0.85,
                        target_soc=target_soc,
                        estimated_duration_hours=self._estimate_charging_time(battery_soc, target_soc),
                        price_category=price_analysis.category,
                        opportunity_cost=0.0
                    )
            
            elif price_analysis.category == PriceCategory.CHEAP:
                # Cheap prices - charge if historically cheap and near cheapest
                if price_analysis.is_historically_cheap and price_analysis.is_near_cheapest:
                    return ChargingDecision(
                        should_charge=True,
                        reason=f"CHEAP price {price_analysis.current_price:.3f} PLN/kWh (historically cheap, {price_analysis.current_percentile:.1f}th percentile) - charge to {target_soc}%",
                        priority='medium',
                        confidence=0.75,
                        target_soc=target_soc,
                        estimated_duration_hours=self._estimate_charging_time(battery_soc, target_soc),
                        price_category=price_analysis.category,
                        opportunity_cost=0.0
                    )
            
            # Default: Don't charge
            return ChargingDecision(
                should_charge=False,
                reason=f"Price {price_analysis.current_price:.3f} PLN/kWh ({price_analysis.category.value}, {price_analysis.current_percentile:.1f}th percentile) not cheap enough for aggressive charging",
                priority='low',
                confidence=0.7,
                target_soc=battery_soc,
                estimated_duration_hours=0.0,
                price_category=price_analysis.category,
                opportunity_cost=0.0
            )
            
        except Exception as e:
            self.logger.error(f"Error in aggressive charging decision: {e}")
            return ChargingDecision(
                should_charge=False,
                reason=f"Error in decision logic: {e}",
                priority='low',
                confidence=0.0,
                target_soc=battery_soc,
                estimated_duration_hours=0.0,
                price_category=PriceCategory.MODERATE,
                opportunity_cost=0.0
            )
    
    def _classify_price_category(self, price: float) -> PriceCategory:
        """Classify price into category"""
        if price < self.super_cheap_threshold:
            return PriceCategory.SUPER_CHEAP
        elif price < self.very_cheap_threshold:
            return PriceCategory.VERY_CHEAP
        elif price < self.cheap_threshold:
            return PriceCategory.CHEAP
        elif price < self.moderate_threshold:
            return PriceCategory.MODERATE
        elif price < self.expensive_threshold:
            return PriceCategory.EXPENSIVE
        else:
            return PriceCategory.VERY_EXPENSIVE
    
    def _calculate_target_soc(self, price_analysis: PriceAnalysis, current_soc: int) -> int:
        """Calculate target SOC based on price category and battery selling"""
        # Base target on price category
        if price_analysis.category == PriceCategory.SUPER_CHEAP:
            base_target = self.super_cheap_target_soc
        elif price_analysis.category == PriceCategory.VERY_CHEAP:
            base_target = self.very_cheap_target_soc
        elif price_analysis.category == PriceCategory.CHEAP:
            base_target = self.cheap_target_soc
        else:
            base_target = current_soc  # Don't charge
        
        # Adjust for battery selling if enabled
        if self.coordinate_with_selling and self.battery_selling_enabled:
            # If battery selling is enabled, target at least min_selling_soc for selling opportunities
            if base_target < self.min_selling_soc:
                base_target = self.min_selling_soc
                self.logger.debug(f"Adjusted target SOC to {base_target}% for battery selling opportunities")
        
        return min(base_target, 100)  # Cap at 100%
    
    def _estimate_charging_time(self, current_soc: int, target_soc: int) -> float:
        """Estimate charging time in hours"""
        # Assume 20kWh battery, 3kW charging rate
        battery_capacity_kwh = 20.0
        charging_rate_kw = 3.0
        
        soc_increase = target_soc - current_soc
        energy_needed_kwh = (soc_increase / 100) * battery_capacity_kwh
        charging_time_hours = energy_needed_kwh / charging_rate_kw
        
        return max(0.25, charging_time_hours)  # Minimum 15 minutes
    
    def _extract_current_price(self, price_data: Dict, kompas_status: Optional[str] = None) -> Optional[float]:
        """Extract current price from price data with tariff-aware pricing"""
        try:
            if 'value' in price_data:
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
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting current price: {e}")
            return None
    
    def _extract_cheapest_price(self, price_data: Dict, kompas_status: Optional[str] = None) -> Tuple[Optional[float], Optional[int]]:
        """Extract cheapest price and hour with tariff-aware pricing"""
        try:
            if 'value' in price_data:
                prices = []
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
                    
                    market_price = float(item.get('csdac_pln', 0))
                    
                    if self.tariff_calculator:
                        # Use tariff-aware pricing
                        market_price_kwh = market_price / 1000
                        components = self.tariff_calculator.calculate_final_price(
                            market_price_kwh, item_time, kompas_status
                        )
                        final_price = components.final_price
                    else:
                        # Fallback: SC component only
                        final_price = (market_price + 89.2) / 1000  # PLN/kWh
                    
                    prices.append((final_price, item_time.hour))
                
                if prices:
                    cheapest_price, cheapest_hour = min(prices, key=lambda x: x[0])
                    return cheapest_price, cheapest_hour
            
            return None, None
        except Exception as e:
            self.logger.error(f"Error extracting cheapest price: {e}")
            return None, None
    
    def _extract_all_prices(self, price_data: Dict, kompas_status: Optional[str] = None) -> List[float]:
        """Extract all prices for statistical analysis with tariff-aware pricing"""
        try:
            prices = []
            if 'value' in price_data:
                for item in price_data['value']:
                    market_price = float(item.get('csdac_pln', 0))
                    item_time_str = item.get('dtime', '')
                    
                    if self.tariff_calculator and item_time_str:
                        try:
                            if ':' in item_time_str and item_time_str.count(':') == 2:
                                item_time = datetime.strptime(item_time_str, '%Y-%m-%d %H:%M:%S')
                            else:
                                item_time = datetime.strptime(item_time_str, '%Y-%m-%d %H:%M')
                            
                            market_price_kwh = market_price / 1000
                            components = self.tariff_calculator.calculate_final_price(
                                market_price_kwh, item_time, kompas_status
                            )
                            final_price = components.final_price
                        except (ValueError, Exception) as e:
                            # Fallback if datetime parsing fails
                            final_price = (market_price + 89.2) / 1000
                    else:
                        # Fallback: SC component only
                        final_price = (market_price + 89.2) / 1000  # PLN/kWh
                    
                    prices.append(final_price)
            return prices
        except Exception as e:
            self.logger.error(f"Error extracting all prices: {e}")
            return []
    
    def _extract_hourly_prices(self, price_data: Dict) -> Dict[int, float]:
        """Extract prices by hour"""
        try:
            hourly_prices = {}
            if 'value' in price_data:
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
                    
                    hour = item_time.hour
                    market_price = float(item.get('csdac_pln', 0))
                    final_price = (market_price + 89.2) / 1000  # PLN/kWh
                    
                    # Use minimum price for each hour if multiple entries
                    if hour not in hourly_prices or final_price < hourly_prices[hour]:
                        hourly_prices[hour] = final_price
            
            return hourly_prices
        except Exception as e:
            self.logger.error(f"Error extracting hourly prices: {e}")
            return {}
    
    def _analyze_tomorrow_prices(self, forecast_data: List[Dict]) -> Optional[Dict]:
        """Analyze tomorrow's forecasted prices"""
        try:
            if not forecast_data:
                return None
            
            # Extract prices from forecast
            prices = []
            for point in forecast_data:
                price = point.get('price', point.get('forecasted_price_pln', 0))
                if price > 0:
                    prices.append(price / 1000 if price > 10 else price)  # Handle PLN/MWh vs PLN/kWh
            
            if not prices:
                return None
            
            return {
                'min_price': min(prices),
                'median_price': statistics.median(prices),
                'avg_price': statistics.mean(prices)
            }
        except Exception as e:
            self.logger.error(f"Error analyzing tomorrow prices: {e}")
            return None

