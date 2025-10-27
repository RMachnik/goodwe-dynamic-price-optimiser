#!/usr/bin/env python3
"""
Battery Selling Multi-Session Scheduler

Identifies daily price peaks and plans optimal battery selling sessions
to maximize revenue while respecting battery capacity and cycle limits.

Phase 2 Feature: Intelligent Daily Peak Planning
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum


class PeakQuality(Enum):
    """Quality classification of price peaks"""
    EXCELLENT = "excellent"  # Top 5% price, very high revenue potential
    GOOD = "good"            # Top 15% price, good revenue potential
    MODERATE = "moderate"    # Top 25% price, moderate revenue
    POOR = "poor"            # Below top 25%, low priority


@dataclass
class SellingSession:
    """Planned selling session"""
    session_id: str
    start_time: datetime
    duration_hours: float
    target_price: float
    peak_quality: PeakQuality
    allocated_energy_kwh: float
    target_soc_end: float
    expected_revenue: float
    priority: int  # 1=highest, 2=medium, 3=lowest
    confidence: float


@dataclass
class DailySellingPlan:
    """Complete daily selling plan"""
    plan_date: datetime
    sessions: List[SellingSession]
    total_planned_energy_kwh: float
    total_expected_revenue: float
    battery_start_soc: float
    battery_end_soc: float
    confidence: float
    reasoning: str


class BatterySellingScheduler:
    """
    Plans daily battery selling sessions based on price forecasts
    
    Responsibilities:
    - Identify price peaks in 24h forecast
    - Classify peak quality
    - Allocate battery energy across peaks
    - Create optimized daily selling plan
    """
    
    def __init__(self, config: Dict):
        """Initialize scheduler with configuration"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Battery configuration
        battery_config = config.get('battery_management', {})
        self.battery_capacity_kwh = battery_config.get('capacity_kwh', 20.0)
        
        # Selling configuration
        selling_config = config.get('battery_selling', {})
        self.min_selling_soc = selling_config.get('min_battery_soc', 80)
        self.safety_margin_soc = selling_config.get('safety_margin_soc', 50)
        self.max_daily_cycles = selling_config.get('max_daily_cycles', 2)
        self.grid_export_limit_w = selling_config.get('grid_export_limit_w', 5000)
        self.discharge_efficiency = selling_config.get('discharge_efficiency', 0.92)
        
        # Multi-session configuration
        scheduler_config = selling_config.get('smart_timing', {}).get('multi_session_scheduler', {})
        self.enabled = scheduler_config.get('enabled', True)
        self.min_peak_price = scheduler_config.get('min_peak_price', 0.70)
        self.min_peak_separation_hours = scheduler_config.get('min_peak_separation_hours', 3.0)
        self.max_sessions_per_day = scheduler_config.get('max_sessions_per_day', 3)
        self.reserve_for_evening_peak = scheduler_config.get('reserve_for_evening_peak', True)
        self.evening_peak_start_hour = scheduler_config.get('evening_peak_start_hour', 17)
        self.evening_peak_end_hour = scheduler_config.get('evening_peak_end_hour', 22)
        
        # Percentile thresholds for peak quality
        percentile_config = selling_config.get('smart_timing', {}).get('percentile_thresholds', {})
        self.excellent_threshold = percentile_config.get('aggressive_sell', 5)  # Top 5%
        self.good_threshold = percentile_config.get('standard_sell', 15)  # Top 15%
        self.moderate_threshold = percentile_config.get('conditional_sell', 25)  # Top 25%
        
        self.logger.info(f"Battery Selling Scheduler initialized: "
                        f"max_sessions={self.max_sessions_per_day}, "
                        f"reserve_evening={self.reserve_for_evening_peak}")
    
    def create_daily_plan(
        self,
        current_soc: float,
        price_forecast: List[Dict],
        current_price: float,
        forecast_confidence: float = 0.8
    ) -> Optional[DailySellingPlan]:
        """
        Create optimized daily selling plan
        
        Args:
            current_soc: Current battery SOC (%)
            price_forecast: 24h price forecast
            current_price: Current price (PLN/kWh)
            forecast_confidence: Confidence in forecast (0-1)
            
        Returns:
            DailySellingPlan or None if no good opportunities
        """
        try:
            if not self.enabled:
                return None
            
            if not price_forecast or len(price_forecast) < 6:
                self.logger.warning("Insufficient forecast data for daily planning")
                return None
            
            # Step 1: Identify price peaks
            peaks = self._identify_peaks(price_forecast, current_price)
            if not peaks:
                self.logger.info("No suitable price peaks found for selling")
                return None
            
            # Step 2: Classify peak quality
            classified_peaks = self._classify_peaks(peaks, price_forecast)
            
            # Step 3: Select best peaks (limit to max_sessions_per_day)
            selected_peaks = self._select_peaks(classified_peaks, current_soc)
            if not selected_peaks:
                self.logger.info("No peaks selected after quality filtering")
                return None
            
            # Step 4: Allocate battery energy across sessions
            sessions = self._allocate_energy(selected_peaks, current_soc)
            if not sessions:
                self.logger.info("Could not allocate energy to sessions")
                return None
            
            # Step 5: Create complete daily plan
            plan = self._create_plan(sessions, current_soc, forecast_confidence)
            
            self.logger.info(f"Created daily plan with {len(sessions)} sessions, "
                           f"expected revenue: {plan.total_expected_revenue:.2f} PLN")
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Error creating daily plan: {e}")
            return None
    
    def _identify_peaks(
        self,
        price_forecast: List[Dict],
        current_price: float
    ) -> List[Dict]:
        """
        Identify local price peaks in forecast
        
        A peak is:
        - Higher than min_peak_price threshold
        - Higher than surrounding prices (local maximum)
        - Separated by at least min_peak_separation_hours from other peaks
        """
        peaks = []
        
        # Sort forecast by time
        sorted_forecast = sorted(
            price_forecast,
            key=lambda x: datetime.fromisoformat(x['time'].replace('Z', '+00:00'))
            if isinstance(x['time'], str) else x['time']
        )
        
        for i, point in enumerate(sorted_forecast):
            price = point.get('price', point.get('forecasted_price_pln', 0))
            time = point.get('time')
            
            if price < self.min_peak_price:
                continue
            
            # Check if local maximum (higher than neighbors)
            is_peak = True
            
            # Check previous point
            if i > 0:
                prev_price = sorted_forecast[i-1].get('price', sorted_forecast[i-1].get('forecasted_price_pln', 0))
                if price <= prev_price:
                    is_peak = False
            
            # Check next point
            if i < len(sorted_forecast) - 1:
                next_price = sorted_forecast[i+1].get('price', sorted_forecast[i+1].get('forecasted_price_pln', 0))
                if price <= next_price:
                    is_peak = False
            
            if is_peak:
                # Parse time
                if isinstance(time, str):
                    time = datetime.fromisoformat(time.replace('Z', '+00:00'))
                
                # Check separation from existing peaks
                too_close = False
                for existing_peak in peaks:
                    time_diff = abs((time - existing_peak['time']).total_seconds() / 3600)
                    if time_diff < self.min_peak_separation_hours:
                        # Keep the higher peak
                        if price > existing_peak['price']:
                            peaks.remove(existing_peak)
                        else:
                            too_close = True
                        break
                
                if not too_close:
                    peaks.append({
                        'time': time,
                        'price': price,
                        'index': i
                    })
        
        self.logger.info(f"Identified {len(peaks)} price peaks")
        return peaks
    
    def _classify_peaks(
        self,
        peaks: List[Dict],
        price_forecast: List[Dict]
    ) -> List[Dict]:
        """
        Classify peak quality based on percentile ranking
        
        Uses Phase 1 percentile thresholds:
        - Top 5%: EXCELLENT
        - Top 15%: GOOD
        - Top 25%: MODERATE
        - Below 25%: POOR
        """
        # Calculate price percentiles from forecast
        all_prices = [
            p.get('price', p.get('forecasted_price_pln', 0))
            for p in price_forecast
            if p.get('price', p.get('forecasted_price_pln', 0)) > 0
        ]
        
        if not all_prices:
            return []
        
        sorted_prices = sorted(all_prices)
        
        for peak in peaks:
            # Calculate percentile rank (0-100)
            # Count how many prices are less than or equal to this peak price
            lower_or_equal_count = sum(1 for p in sorted_prices if p <= peak['price'])
            # Percentile: what percent of values are at or below this value
            percentile = (lower_or_equal_count / len(sorted_prices)) * 100
            
            # Classify quality based on percentile
            # Top 5% means >= 95th percentile
            if percentile >= (100 - self.excellent_threshold):  # >= 95th percentile
                quality = PeakQuality.EXCELLENT
                priority = 1
            elif percentile >= (100 - self.good_threshold):  # >= 85th percentile
                quality = PeakQuality.GOOD
                priority = 2
            elif percentile >= (100 - self.moderate_threshold):  # >= 75th percentile
                quality = PeakQuality.MODERATE
                priority = 3
            else:
                quality = PeakQuality.POOR
                priority = 4
            
            peak['quality'] = quality
            peak['priority'] = priority
            peak['percentile'] = percentile
        
        return peaks
    
    def _select_peaks(
        self,
        classified_peaks: List[Dict],
        current_soc: float
    ) -> List[Dict]:
        """
        Select best peaks for selling sessions
        
        Selection criteria:
        - Maximum max_sessions_per_day sessions
        - Prioritize higher quality peaks
        - Reserve energy for evening peak if configured
        - Ensure sufficient battery energy available
        """
        # Filter out POOR quality peaks
        viable_peaks = [p for p in classified_peaks if p['quality'] != PeakQuality.POOR]
        
        if not viable_peaks:
            return []
        
        # Sort by priority (lower number = higher priority) then by price
        sorted_peaks = sorted(
            viable_peaks,
            key=lambda x: (x['priority'], -x['price'])
        )
        
        # Reserve energy for evening peak if configured
        if self.reserve_for_evening_peak:
            evening_peaks = [
                p for p in sorted_peaks
                if self.evening_peak_start_hour <= p['time'].hour <= self.evening_peak_end_hour
            ]
            
            if evening_peaks:
                # Ensure best evening peak is included
                best_evening_peak = evening_peaks[0]
                selected = [best_evening_peak]
                
                # Add other peaks up to limit
                for peak in sorted_peaks:
                    if peak != best_evening_peak and len(selected) < self.max_sessions_per_day:
                        selected.append(peak)
                
                return selected
        
        # No evening peak reservation - just take top N peaks
        return sorted_peaks[:self.max_sessions_per_day]
    
    def _allocate_energy(
        self,
        selected_peaks: List[Dict],
        current_soc: float
    ) -> List[SellingSession]:
        """
        Allocate battery energy across selected peaks
        
        Allocation strategy:
        - Higher priority peaks get more energy
        - Ensure battery doesn't go below safety margin
        - Balance energy across sessions
        """
        sessions = []
        
        # Calculate available energy
        available_energy_kwh = (current_soc - self.safety_margin_soc) * self.battery_capacity_kwh / 100
        
        if available_energy_kwh <= 0:
            self.logger.warning(f"No available energy: current_soc={current_soc}%, safety_margin={self.safety_margin_soc}%")
            return []
        
        # Calculate total priority weight (lower priority number = higher weight)
        # Priority 1 = weight 3, Priority 2 = weight 2, Priority 3 = weight 1
        total_weight = sum(4 - p['priority'] for p in selected_peaks)
        
        current_soc_tracker = current_soc
        
        for idx, peak in enumerate(selected_peaks):
            # Allocate energy based on priority weight
            weight = 4 - peak['priority']
            allocated_energy = (weight / total_weight) * available_energy_kwh
            
            # Ensure we don't allocate more than physically possible
            max_energy_from_current = (current_soc_tracker - self.safety_margin_soc) * self.battery_capacity_kwh / 100
            allocated_energy = min(allocated_energy, max_energy_from_current)
            
            if allocated_energy <= 0:
                continue
            
            # Calculate target end SOC
            soc_decrease = (allocated_energy / self.battery_capacity_kwh) * 100
            target_soc_end = current_soc_tracker - soc_decrease
            
            # Estimate duration based on export limit
            export_power_kw = self.grid_export_limit_w / 1000
            duration_hours = allocated_energy / (export_power_kw * self.discharge_efficiency)
            
            # Calculate expected revenue
            expected_revenue = allocated_energy * peak['price']
            
            session = SellingSession(
                session_id=f"session_{idx+1}_{peak['time'].strftime('%H%M')}",
                start_time=peak['time'],
                duration_hours=duration_hours,
                target_price=peak['price'],
                peak_quality=peak['quality'],
                allocated_energy_kwh=allocated_energy,
                target_soc_end=target_soc_end,
                expected_revenue=expected_revenue,
                priority=peak['priority'],
                confidence=0.8 if peak['quality'] in [PeakQuality.EXCELLENT, PeakQuality.GOOD] else 0.6
            )
            
            sessions.append(session)
            current_soc_tracker = target_soc_end
            
            self.logger.info(f"Session {idx+1}: {peak['time'].strftime('%H:%M')}, "
                           f"{peak['price']:.3f} PLN/kWh, "
                           f"{allocated_energy:.2f} kWh, "
                           f"{expected_revenue:.2f} PLN")
        
        return sessions
    
    def _create_plan(
        self,
        sessions: List[SellingSession],
        current_soc: float,
        forecast_confidence: float
    ) -> DailySellingPlan:
        """Create complete daily plan from sessions"""
        total_energy = sum(s.allocated_energy_kwh for s in sessions)
        total_revenue = sum(s.expected_revenue for s in sessions)
        
        final_soc = current_soc
        if sessions:
            final_soc = sessions[-1].target_soc_end
        
        # Sort sessions by start time
        sorted_sessions = sorted(sessions, key=lambda x: x.start_time)
        
        # Calculate overall confidence (average of session confidences * forecast confidence)
        avg_session_confidence = sum(s.confidence for s in sessions) / len(sessions) if sessions else 0
        overall_confidence = avg_session_confidence * forecast_confidence
        
        # Generate reasoning
        session_descriptions = []
        for s in sorted_sessions:
            session_descriptions.append(
                f"{s.start_time.strftime('%H:%M')} ({s.peak_quality.value}, {s.target_price:.3f} PLN/kWh, {s.expected_revenue:.2f} PLN)"
            )
        
        reasoning = f"{len(sessions)} sessions planned: " + ", ".join(session_descriptions)
        
        return DailySellingPlan(
            plan_date=datetime.now().date(),
            sessions=sorted_sessions,
            total_planned_energy_kwh=total_energy,
            total_expected_revenue=total_revenue,
            battery_start_soc=current_soc,
            battery_end_soc=final_soc,
            confidence=overall_confidence,
            reasoning=reasoning
        )
    
    def get_current_session(self, plan: DailySellingPlan) -> Optional[SellingSession]:
        """Get the session that should be active now"""
        now = datetime.now()
        
        for session in plan.sessions:
            session_end = session.start_time + timedelta(hours=session.duration_hours)
            if session.start_time <= now <= session_end:
                return session
        
        return None
    
    def get_next_session(self, plan: DailySellingPlan) -> Optional[SellingSession]:
        """Get the next upcoming session"""
        now = datetime.now()
        
        upcoming_sessions = [
            s for s in plan.sessions
            if s.start_time > now
        ]
        
        if upcoming_sessions:
            return min(upcoming_sessions, key=lambda x: x.start_time)
        
        return None

