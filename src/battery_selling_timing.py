#!/usr/bin/env python3
"""
Battery Selling Smart Timing Module

This module implements intelligent timing decisions for battery selling to maximize revenue
by avoiding selling too early and waiting for peak prices.

Key Features:
- Price forecast analysis
- Peak price detection
- Price trend analysis (rising, falling, stable)
- Smart waiting strategy
- Opportunity cost calculation
- Selling window identification
- Multi-session selling support
- Confidence-based decisions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class PriceTrend(Enum):
    """Price trend types"""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    UNKNOWN = "unknown"


class TimingDecision(Enum):
    """Timing decision types"""
    SELL_NOW = "sell_now"
    WAIT_FOR_PEAK = "wait_for_peak"
    WAIT_FOR_HIGHER = "wait_for_higher"
    NO_OPPORTUNITY = "no_opportunity"


@dataclass
class PriceAnalysis:
    """Analysis of price data"""
    current_price: float
    min_price: float
    max_price: float
    avg_price: float
    median_price: float
    percentile_25th: float
    percentile_75th: float
    percentile_90th: float
    current_percentile: float  # Where current price ranks (0-100)
    is_high_price: bool  # Is current price in top 25%
    is_peak_price: bool  # Is current price in top 10%


@dataclass
class PeakInfo:
    """Information about price peak"""
    peak_time: datetime
    peak_price: float
    time_to_peak_hours: float
    price_increase_percent: float
    confidence: float


@dataclass
class SellingWindow:
    """Represents an optimal selling window"""
    start_time: datetime
    end_time: datetime
    duration_hours: float
    avg_price: float
    peak_price: float
    confidence: float
    priority: int  # 1 = highest priority


@dataclass
class TimingRecommendation:
    """Recommendation for selling timing"""
    decision: TimingDecision
    confidence: float
    reasoning: str
    sell_time: Optional[datetime]
    expected_price: float
    opportunity_cost_pln: float
    peak_info: Optional[PeakInfo]
    selling_windows: List[SellingWindow]
    wait_hours: float
    risk_level: str  # "low", "medium", "high"


class BatterySellingTiming:
    """Intelligent timing engine for battery selling decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the timing engine"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Smart timing configuration
        timing_config = config.get('battery_selling', {}).get('smart_timing', {})
        
        self.enabled = timing_config.get('enabled', True)
        self.forecast_lookahead_hours = timing_config.get('forecast_lookahead_hours', 6)
        self.near_peak_threshold_percent = timing_config.get('near_peak_threshold_percent', 95)
        self.min_peak_difference_percent = timing_config.get('min_peak_difference_percent', 15)
        self.max_wait_time_hours = timing_config.get('max_wait_time_hours', 4)
        self.min_forecast_confidence = timing_config.get('min_forecast_confidence', 0.6)
        
        # Opportunity cost thresholds
        opp_cost_config = timing_config.get('opportunity_cost', {})
        self.significant_savings_percent = opp_cost_config.get('significant_savings_percent', 20)
        self.marginal_savings_percent = opp_cost_config.get('marginal_savings_percent', 5)
        
        # Trend analysis
        trend_config = timing_config.get('trend_analysis', {})
        self.trend_enabled = trend_config.get('enabled', True)
        self.trend_window_hours = trend_config.get('trend_window_hours', 2)
        self.rising_threshold = trend_config.get('rising_threshold', 0.02)
        self.falling_threshold = trend_config.get('falling_threshold', -0.02)
        
        # Multi-session selling
        multi_session_config = timing_config.get('multi_session', {})
        self.multi_session_enabled = multi_session_config.get('enabled', True)
        self.max_sessions_per_day = multi_session_config.get('max_sessions_per_day', 3)
        self.min_session_gap_hours = multi_session_config.get('min_session_gap_hours', 1)
        self.reserve_battery_percent = multi_session_config.get('reserve_battery_percent', 20)
        
        # Battery specifications
        battery_config = config.get('battery_management', {})
        self.battery_capacity_kwh = battery_config.get('capacity_kwh', 20.0)
        
        # Session tracking
        self.planned_sessions: List[Dict[str, Any]] = []
        self.completed_sessions_today: int = 0
        self.last_session_time: Optional[datetime] = None
        
        self.logger.info(f"Battery Selling Timing Engine initialized (enabled: {self.enabled})")
        self.logger.info(f"  - Forecast lookahead: {self.forecast_lookahead_hours}h")
        self.logger.info(f"  - Near peak threshold: {self.near_peak_threshold_percent}%")
        self.logger.info(f"  - Min peak difference: {self.min_peak_difference_percent}%")
        self.logger.info(f"  - Max wait time: {self.max_wait_time_hours}h")
    
    def analyze_selling_timing(self, 
                               current_price: float,
                               price_forecast: List[Dict[str, Any]],
                               current_data: Dict[str, Any],
                               forecast_confidence: float = 1.0) -> TimingRecommendation:
        """
        Main method to analyze selling timing
        
        Args:
            current_price: Current electricity price (PLN/kWh)
            price_forecast: List of forecast price points
            current_data: Current system data (battery SOC, consumption, etc.)
            forecast_confidence: Confidence level of forecast (0.0-1.0)
            
        Returns:
            TimingRecommendation with decision and analysis
        """
        try:
            if not self.enabled:
                return self._create_immediate_sell_recommendation(
                    current_price, "Smart timing disabled"
                )
            
            # Check if forecast is available and reliable
            if not price_forecast or forecast_confidence < self.min_forecast_confidence:
                return self._create_immediate_sell_recommendation(
                    current_price, 
                    f"Forecast unavailable or low confidence ({forecast_confidence:.2f})"
                )
            
            # Step 1: Analyze current price context
            price_analysis = self._analyze_price_context(current_price, price_forecast)
            
            # Step 2: Detect price peak
            peak_info = self._detect_price_peak(current_price, price_forecast)
            
            # Step 3: Analyze price trend
            trend = self._analyze_price_trend(price_forecast)
            
            # Step 4: Calculate opportunity cost
            opportunity_cost = self._calculate_opportunity_cost(
                current_price, peak_info, current_data
            )
            
            # Step 5: Identify selling windows
            selling_windows = self._identify_selling_windows(price_forecast, current_data)
            
            # Step 6: Make timing decision
            recommendation = self._make_timing_decision(
                current_price,
                price_analysis,
                peak_info,
                trend,
                opportunity_cost,
                selling_windows,
                current_data,
                forecast_confidence
            )
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error analyzing selling timing: {e}")
            return self._create_immediate_sell_recommendation(
                current_price, f"Analysis error: {e}"
            )
    
    def _analyze_price_context(self, current_price: float, 
                               price_forecast: List[Dict[str, Any]]) -> PriceAnalysis:
        """Analyze current price in context of forecast data"""
        try:
            # Extract all prices from forecast
            all_prices = [current_price]
            for forecast_point in price_forecast:
                price = forecast_point.get('price', forecast_point.get('forecasted_price_pln', 0))
                if price > 0:
                    all_prices.append(price)
            
            if len(all_prices) < 2:
                # Not enough data, return conservative analysis
                return PriceAnalysis(
                    current_price=current_price,
                    min_price=current_price,
                    max_price=current_price,
                    avg_price=current_price,
                    median_price=current_price,
                    percentile_25th=current_price,
                    percentile_75th=current_price,
                    percentile_90th=current_price,
                    current_percentile=50.0,
                    is_high_price=False,
                    is_peak_price=False
                )
            
            # Calculate statistics
            sorted_prices = sorted(all_prices)
            min_price = min(all_prices)
            max_price = max(all_prices)
            avg_price = statistics.mean(all_prices)
            median_price = statistics.median(all_prices)
            
            # Calculate percentiles
            percentile_25th = sorted_prices[int(len(sorted_prices) * 0.25)]
            percentile_75th = sorted_prices[int(len(sorted_prices) * 0.75)]
            percentile_90th = sorted_prices[int(len(sorted_prices) * 0.90)]
            
            # Determine current price percentile rank
            rank = sum(1 for p in all_prices if p <= current_price)
            current_percentile = (rank / len(all_prices)) * 100
            
            # Determine if high/peak price
            is_high_price = current_price >= percentile_75th
            is_peak_price = current_price >= percentile_90th
            
            return PriceAnalysis(
                current_price=current_price,
                min_price=min_price,
                max_price=max_price,
                avg_price=avg_price,
                median_price=median_price,
                percentile_25th=percentile_25th,
                percentile_75th=percentile_75th,
                percentile_90th=percentile_90th,
                current_percentile=current_percentile,
                is_high_price=is_high_price,
                is_peak_price=is_peak_price
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing price context: {e}")
            # Return safe default
            return PriceAnalysis(
                current_price=current_price,
                min_price=current_price,
                max_price=current_price,
                avg_price=current_price,
                median_price=current_price,
                percentile_25th=current_price,
                percentile_75th=current_price,
                percentile_90th=current_price,
                current_percentile=50.0,
                is_high_price=False,
                is_peak_price=False
            )
    
    def _detect_price_peak(self, current_price: float,
                          price_forecast: List[Dict[str, Any]]) -> Optional[PeakInfo]:
        """Detect upcoming price peak in forecast"""
        try:
            current_time = datetime.now()
            max_wait_time = current_time + timedelta(hours=self.max_wait_time_hours)
            
            # Find peak price within wait window
            peak_price = current_price
            peak_time = current_time
            
            for forecast_point in price_forecast:
                point_time = forecast_point.get('time')
                if isinstance(point_time, str):
                    point_time = datetime.fromisoformat(point_time.replace('Z', '+00:00'))
                
                if not point_time or point_time > max_wait_time:
                    continue
                
                price = forecast_point.get('price', forecast_point.get('forecasted_price_pln', 0))
                if price > peak_price:
                    peak_price = price
                    peak_time = point_time
            
            # If peak is same as current, no peak detected
            if peak_price <= current_price:
                return None
            
            # Calculate peak information
            time_to_peak = (peak_time - current_time).total_seconds() / 3600
            price_increase_percent = ((peak_price - current_price) / current_price) * 100
            
            # Calculate confidence based on peak magnitude and timing
            confidence = min(1.0, price_increase_percent / 30.0)  # 30% increase = 100% confidence
            if time_to_peak > self.max_wait_time_hours * 0.75:
                confidence *= 0.8  # Reduce confidence for distant peaks
            
            return PeakInfo(
                peak_time=peak_time,
                peak_price=peak_price,
                time_to_peak_hours=time_to_peak,
                price_increase_percent=price_increase_percent,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Error detecting price peak: {e}")
            return None
    
    def _analyze_price_trend(self, price_forecast: List[Dict[str, Any]]) -> PriceTrend:
        """Analyze price trend from forecast data"""
        try:
            if not self.trend_enabled or len(price_forecast) < 3:
                return PriceTrend.UNKNOWN
            
            current_time = datetime.now()
            trend_window_end = current_time + timedelta(hours=self.trend_window_hours)
            
            # Extract prices within trend window
            trend_prices = []
            for forecast_point in price_forecast:
                point_time = forecast_point.get('time')
                if isinstance(point_time, str):
                    point_time = datetime.fromisoformat(point_time.replace('Z', '+00:00'))
                
                if not point_time or point_time > trend_window_end:
                    continue
                
                price = forecast_point.get('price', forecast_point.get('forecasted_price_pln', 0))
                if price > 0:
                    trend_prices.append(price)
            
            if len(trend_prices) < 3:
                return PriceTrend.UNKNOWN
            
            # Calculate trend slope using simple linear regression
            n = len(trend_prices)
            x = list(range(n))
            y = trend_prices
            
            x_mean = sum(x) / n
            y_mean = sum(y) / n
            
            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            if denominator == 0:
                return PriceTrend.STABLE
            
            slope = numerator / denominator
            
            # Normalize slope relative to average price
            if y_mean > 0:
                normalized_slope = slope / y_mean
            else:
                normalized_slope = 0
            
            # Determine trend
            if normalized_slope > self.rising_threshold:
                return PriceTrend.RISING
            elif normalized_slope < self.falling_threshold:
                return PriceTrend.FALLING
            else:
                return PriceTrend.STABLE
                
        except Exception as e:
            self.logger.error(f"Error analyzing price trend: {e}")
            return PriceTrend.UNKNOWN
    
    def _calculate_opportunity_cost(self, current_price: float,
                                   peak_info: Optional[PeakInfo],
                                   current_data: Dict[str, Any]) -> float:
        """Calculate opportunity cost of selling now vs. waiting"""
        try:
            if not peak_info:
                return 0.0  # No opportunity cost if no peak detected
            
            # Get battery data
            battery_data = current_data.get('battery', {})
            battery_soc = battery_data.get('soc_percent', 80)
            
            # Calculate available energy for selling
            min_soc = 50  # Safety margin
            available_soc = max(0, battery_soc - min_soc)
            available_energy_kwh = (available_soc / 100) * self.battery_capacity_kwh
            
            # Calculate revenue difference
            current_revenue = available_energy_kwh * current_price
            peak_revenue = available_energy_kwh * peak_info.peak_price
            
            opportunity_cost = peak_revenue - current_revenue
            
            return max(0.0, opportunity_cost)
            
        except Exception as e:
            self.logger.error(f"Error calculating opportunity cost: {e}")
            return 0.0
    
    def _identify_selling_windows(self, price_forecast: List[Dict[str, Any]],
                                 current_data: Dict[str, Any]) -> List[SellingWindow]:
        """Identify optimal selling windows in forecast"""
        try:
            if not self.multi_session_enabled:
                return []
            
            current_time = datetime.now()
            lookahead_time = current_time + timedelta(hours=self.forecast_lookahead_hours)
            
            # Calculate price threshold for selling (75th percentile)
            all_prices = []
            for point in price_forecast:
                price = point.get('price', point.get('forecasted_price_pln', 0))
                if price > 0:
                    all_prices.append(price)
            
            if len(all_prices) < 4:
                return []
            
            sorted_prices = sorted(all_prices)
            threshold_price = sorted_prices[int(len(sorted_prices) * 0.75)]
            
            # Find continuous high-price windows
            windows = []
            window_start = None
            window_prices = []
            
            for i, point in enumerate(price_forecast):
                point_time = point.get('time')
                if isinstance(point_time, str):
                    point_time = datetime.fromisoformat(point_time.replace('Z', '+00:00'))
                
                if not point_time or point_time > lookahead_time:
                    continue
                
                price = point.get('price', point.get('forecasted_price_pln', 0))
                
                if price >= threshold_price:
                    if window_start is None:
                        window_start = point_time
                    window_prices.append(price)
                else:
                    # End of window
                    if window_start and window_prices:
                        window_end = point_time
                        duration = (window_end - window_start).total_seconds() / 3600
                        
                        # Only include windows >= 30 minutes
                        if duration >= 0.5:
                            window = SellingWindow(
                                start_time=window_start,
                                end_time=window_end,
                                duration_hours=duration,
                                avg_price=statistics.mean(window_prices),
                                peak_price=max(window_prices),
                                confidence=0.8,  # Base confidence
                                priority=1 if max(window_prices) >= sorted_prices[-1] * 0.95 else 2
                            )
                            windows.append(window)
                    
                    window_start = None
                    window_prices = []
            
            # Sort by priority (highest first), then by peak price
            windows.sort(key=lambda w: (w.priority, -w.peak_price))
            
            # Limit to max sessions per day
            return windows[:self.max_sessions_per_day]
            
        except Exception as e:
            self.logger.error(f"Error identifying selling windows: {e}")
            return []
    
    def _make_timing_decision(self,
                             current_price: float,
                             price_analysis: PriceAnalysis,
                             peak_info: Optional[PeakInfo],
                             trend: PriceTrend,
                             opportunity_cost: float,
                             selling_windows: List[SellingWindow],
                             current_data: Dict[str, Any],
                             forecast_confidence: float) -> TimingRecommendation:
        """Make final timing decision based on all analysis"""
        try:
            # Decision logic priority:
            # 1. If current price is at/near peak (top 10%) -> SELL NOW
            # 2. If trend is falling and no better peak ahead -> SELL NOW
            # 3. If significant opportunity cost (20%+ more revenue) -> WAIT
            # 4. If current price is high (top 25%) and near peak threshold -> SELL NOW
            # 5. Otherwise -> WAIT or NO_OPPORTUNITY
            
            # Rule 1: Current price at/near peak
            if price_analysis.is_peak_price:
                near_peak_threshold = price_analysis.max_price * (self.near_peak_threshold_percent / 100)
                if current_price >= near_peak_threshold:
                    return TimingRecommendation(
                        decision=TimingDecision.SELL_NOW,
                        confidence=0.95,
                        reasoning=f"Current price {current_price:.3f} PLN/kWh is at peak (top 10%, {price_analysis.current_percentile:.1f}th percentile)",
                        sell_time=datetime.now(),
                        expected_price=current_price,
                        opportunity_cost_pln=0.0,
                        peak_info=None,
                        selling_windows=selling_windows,
                        wait_hours=0.0,
                        risk_level="low"
                    )
            
            # Rule 2: Falling trend and no better peak
            if trend == PriceTrend.FALLING and (not peak_info or peak_info.price_increase_percent < 5):
                return TimingRecommendation(
                    decision=TimingDecision.SELL_NOW,
                    confidence=0.85,
                    reasoning=f"Price is falling and no significant peak ahead - sell now at {current_price:.3f} PLN/kWh",
                    sell_time=datetime.now(),
                    expected_price=current_price,
                    opportunity_cost_pln=0.0,
                    peak_info=peak_info,
                    selling_windows=selling_windows,
                    wait_hours=0.0,
                    risk_level="medium"
                )
            
            # Rule 3: Significant opportunity cost - wait for peak
            if peak_info and peak_info.price_increase_percent >= self.significant_savings_percent:
                return TimingRecommendation(
                    decision=TimingDecision.WAIT_FOR_PEAK,
                    confidence=peak_info.confidence * forecast_confidence,
                    reasoning=f"Peak expected in {peak_info.time_to_peak_hours:.1f}h at {peak_info.peak_price:.3f} PLN/kWh (+{peak_info.price_increase_percent:.1f}%, opportunity cost: {opportunity_cost:.2f} PLN)",
                    sell_time=peak_info.peak_time,
                    expected_price=peak_info.peak_price,
                    opportunity_cost_pln=opportunity_cost,
                    peak_info=peak_info,
                    selling_windows=selling_windows,
                    wait_hours=peak_info.time_to_peak_hours,
                    risk_level="low" if peak_info.time_to_peak_hours < 2 else "medium"
                )
            
            # Rule 4: Current price is high and near peak threshold
            if price_analysis.is_high_price:
                near_peak_threshold = price_analysis.max_price * (self.near_peak_threshold_percent / 100)
                if current_price >= near_peak_threshold:
                    return TimingRecommendation(
                        decision=TimingDecision.SELL_NOW,
                        confidence=0.80,
                        reasoning=f"Current price {current_price:.3f} PLN/kWh is high (top 25%, within {self.near_peak_threshold_percent}% of peak)",
                        sell_time=datetime.now(),
                        expected_price=current_price,
                        opportunity_cost_pln=opportunity_cost if peak_info else 0.0,
                        peak_info=peak_info,
                        selling_windows=selling_windows,
                        wait_hours=0.0,
                        risk_level="low"
                    )
            
            # Rule 5: Moderate opportunity - wait if peak nearby
            if peak_info and peak_info.price_increase_percent >= self.marginal_savings_percent:
                if peak_info.time_to_peak_hours <= self.max_wait_time_hours:
                    return TimingRecommendation(
                        decision=TimingDecision.WAIT_FOR_HIGHER,
                        confidence=peak_info.confidence * forecast_confidence * 0.8,
                        reasoning=f"Moderate price improvement expected in {peak_info.time_to_peak_hours:.1f}h (+{peak_info.price_increase_percent:.1f}%)",
                        sell_time=peak_info.peak_time,
                        expected_price=peak_info.peak_price,
                        opportunity_cost_pln=opportunity_cost,
                        peak_info=peak_info,
                        selling_windows=selling_windows,
                        wait_hours=peak_info.time_to_peak_hours,
                        risk_level="medium"
                    )
            
            # Rule 6: Price is not high enough - no good opportunity
            if not price_analysis.is_high_price:
                return TimingRecommendation(
                    decision=TimingDecision.NO_OPPORTUNITY,
                    confidence=0.90,
                    reasoning=f"Current price {current_price:.3f} PLN/kWh below high threshold (only {price_analysis.current_percentile:.1f}th percentile)",
                    sell_time=None,
                    expected_price=current_price,
                    opportunity_cost_pln=0.0,
                    peak_info=peak_info,
                    selling_windows=selling_windows,
                    wait_hours=0.0,
                    risk_level="high"
                )
            
            # Default: Sell now (conservative approach)
            return TimingRecommendation(
                decision=TimingDecision.SELL_NOW,
                confidence=0.70,
                reasoning=f"No strong signal to wait - sell at current price {current_price:.3f} PLN/kWh",
                sell_time=datetime.now(),
                expected_price=current_price,
                opportunity_cost_pln=opportunity_cost if peak_info else 0.0,
                peak_info=peak_info,
                selling_windows=selling_windows,
                wait_hours=0.0,
                risk_level="medium"
            )
            
        except Exception as e:
            self.logger.error(f"Error making timing decision: {e}")
            return self._create_immediate_sell_recommendation(
                current_price, f"Decision error: {e}"
            )
    
    def _create_immediate_sell_recommendation(self, current_price: float, 
                                             reason: str) -> TimingRecommendation:
        """Create recommendation to sell immediately"""
        return TimingRecommendation(
            decision=TimingDecision.SELL_NOW,
            confidence=0.5,
            reasoning=reason,
            sell_time=datetime.now(),
            expected_price=current_price,
            opportunity_cost_pln=0.0,
            peak_info=None,
            selling_windows=[],
            wait_hours=0.0,
            risk_level="medium"
        )
    
    def should_cancel_waiting(self, current_data: Dict[str, Any],
                             waiting_since: datetime,
                             original_recommendation: TimingRecommendation) -> Tuple[bool, str]:
        """
        Check if we should cancel waiting and sell immediately
        
        Returns:
            Tuple of (should_cancel, reason)
        """
        try:
            # Check 1: Battery SOC dropping too low
            battery_data = current_data.get('battery', {})
            battery_soc = battery_data.get('soc_percent', 80)
            
            if battery_soc < 70:
                return True, f"Battery SOC dropped to {battery_soc}% - sell now to preserve capacity"
            
            # Check 2: Waited too long
            wait_time_hours = (datetime.now() - waiting_since).total_seconds() / 3600
            if wait_time_hours >= self.max_wait_time_hours:
                return True, f"Maximum wait time ({self.max_wait_time_hours}h) reached - sell now"
            
            # Check 3: House consumption spiking
            consumption_data = current_data.get('consumption', {})
            consumption_w = consumption_data.get('power_w', 0)
            
            if consumption_w > 3000:  # High consumption threshold
                return True, f"High house consumption ({consumption_w}W) - battery needed for house"
            
            # Check 4: Price suddenly spiked above original forecast
            if original_recommendation.peak_info:
                current_price = current_data.get('pricing', {}).get('current_price_pln_kwh', 0)
                if current_price > original_recommendation.peak_info.peak_price * 1.05:
                    return True, f"Price unexpectedly high ({current_price:.3f} PLN/kWh) - sell now"
            
            return False, "Continue waiting"
            
        except Exception as e:
            self.logger.error(f"Error checking cancel conditions: {e}")
            return True, f"Error checking conditions: {e}"
    
    def get_timing_status(self) -> Dict[str, Any]:
        """Get current timing engine status"""
        return {
            "enabled": self.enabled,
            "planned_sessions": len(self.planned_sessions),
            "completed_sessions_today": self.completed_sessions_today,
            "last_session_time": self.last_session_time.isoformat() if self.last_session_time else None,
            "configuration": {
                "forecast_lookahead_hours": self.forecast_lookahead_hours,
                "near_peak_threshold_percent": self.near_peak_threshold_percent,
                "min_peak_difference_percent": self.min_peak_difference_percent,
                "max_wait_time_hours": self.max_wait_time_hours,
                "multi_session_enabled": self.multi_session_enabled,
                "max_sessions_per_day": self.max_sessions_per_day
            }
        }

