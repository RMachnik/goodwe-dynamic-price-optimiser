#!/usr/bin/env python3
"""
Tests for Phase 2: Multi-Session Daily Scheduler

Tests the battery selling scheduler that plans multiple selling sessions
throughout the day based on price peaks.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from battery_selling_scheduler import (
    BatterySellingScheduler,
    PeakQuality,
    SellingSession,
    DailySellingPlan
)


class TestSchedulerInitialization:
    """Test scheduler initialization and configuration"""
    
    @pytest.fixture
    def config(self):
        return {
            'battery_management': {'capacity_kwh': 20.0},
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'max_daily_cycles': 2,
                'grid_export_limit_w': 5000,
                'smart_timing': {
                    'multi_session_scheduler': {
                        'enabled': True,
                        'min_peak_price': 0.70,
                        'min_peak_separation_hours': 3.0,
                        'max_sessions_per_day': 3,
                        'reserve_for_evening_peak': True,
                        'evening_peak_start_hour': 17,
                        'evening_peak_end_hour': 22
                    },
                    'percentile_thresholds': {
                        'aggressive_sell': 5,
                        'standard_sell': 15,
                        'conditional_sell': 25
                    }
                }
            }
        }
    
    def test_initialization(self, config):
        """Test scheduler initializes correctly"""
        scheduler = BatterySellingScheduler(config)
        
        assert scheduler.enabled is True
        assert scheduler.battery_capacity_kwh == 20.0
        assert scheduler.min_peak_price == 0.70
        assert scheduler.min_peak_separation_hours == 3.0
        assert scheduler.max_sessions_per_day == 3
        assert scheduler.reserve_for_evening_peak is True


class TestPeakIdentification:
    """Test price peak identification logic"""
    
    @pytest.fixture
    def scheduler(self):
        config = {
            'battery_management': {'capacity_kwh': 20.0},
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'smart_timing': {
                    'multi_session_scheduler': {
                        'enabled': True,
                        'min_peak_price': 0.70,
                        'min_peak_separation_hours': 3.0
                    }
                }
            }
        }
        return BatterySellingScheduler(config)
    
    def test_identify_single_peak(self, scheduler):
        """Test identification of single clear peak"""
        now = datetime.now()
        forecast = [
            {'price': 0.50, 'time': (now + timedelta(hours=1)).isoformat()},
            {'price': 0.80, 'time': (now + timedelta(hours=2)).isoformat()},  # Peak
            {'price': 0.60, 'time': (now + timedelta(hours=3)).isoformat()},
        ]
        
        peaks = scheduler._identify_peaks(forecast, 0.55)
        
        assert len(peaks) == 1
        assert peaks[0]['price'] == 0.80
    
    def test_identify_multiple_peaks(self, scheduler):
        """Test identification of multiple separated peaks"""
        now = datetime.now()
        forecast = [
            {'price': 0.50, 'time': (now + timedelta(hours=1)).isoformat()},
            {'price': 0.80, 'time': (now + timedelta(hours=2)).isoformat()},  # Peak 1
            {'price': 0.60, 'time': (now + timedelta(hours=3)).isoformat()},
            {'price': 0.55, 'time': (now + timedelta(hours=6)).isoformat()},
            {'price': 0.90, 'time': (now + timedelta(hours=7)).isoformat()},  # Peak 2
            {'price': 0.65, 'time': (now + timedelta(hours=8)).isoformat()},
        ]
        
        peaks = scheduler._identify_peaks(forecast, 0.55)
        
        assert len(peaks) == 2
        assert peaks[0]['price'] == 0.80
        assert peaks[1]['price'] == 0.90
    
    def test_filter_below_threshold(self, scheduler):
        """Test that peaks below min_peak_price are filtered out"""
        now = datetime.now()
        forecast = [
            {'price': 0.40, 'time': (now + timedelta(hours=1)).isoformat()},
            {'price': 0.65, 'time': (now + timedelta(hours=2)).isoformat()},  # Below 0.70 threshold
            {'price': 0.50, 'time': (now + timedelta(hours=3)).isoformat()},
        ]
        
        peaks = scheduler._identify_peaks(forecast, 0.55)
        
        assert len(peaks) == 0  # All peaks below threshold
    
    def test_peak_separation(self, scheduler):
        """Test that only highest peak is kept when peaks are too close"""
        now = datetime.now()
        forecast = [
            {'price': 0.75, 'time': (now + timedelta(hours=1)).isoformat()},  # Peak
            {'price': 0.70, 'time': (now + timedelta(hours=2)).isoformat()},  # Too close, lower
            {'price': 0.80, 'time': (now + timedelta(hours=2.5)).isoformat()},  # Too close, higher
        ]
        
        peaks = scheduler._identify_peaks(forecast, 0.55)
        
        # Should keep only the highest peak (0.80)
        assert len(peaks) == 1
        assert peaks[0]['price'] == 0.80


class TestPeakClassification:
    """Test peak quality classification"""
    
    @pytest.fixture
    def scheduler(self):
        config = {
            'battery_management': {'capacity_kwh': 20.0},
            'battery_selling': {
                'smart_timing': {
                    'multi_session_scheduler': {'enabled': True},
                    'percentile_thresholds': {
                        'aggressive_sell': 5,   # Top 5%
                        'standard_sell': 15,    # Top 15%
                        'conditional_sell': 25  # Top 25%
                    }
                }
            }
        }
        return BatterySellingScheduler(config)
    
    def test_classify_excellent_peak(self, scheduler):
        """Test classification of top 5% peak as EXCELLENT"""
        # Create forecast with clear distribution
        # Need at least 20 samples for top 5% to work well
        forecast = []
        for i in range(100):
            price = 0.30 + (i * 0.007)  # Gradual increase from 0.30 to ~1.00
            forecast.append({'price': price, 'time': datetime.now().isoformat()})
        
        # Peak at the very top
        peaks = [{'price': 1.00, 'time': datetime.now()}]
        classified = scheduler._classify_peaks(peaks, forecast)
        
        assert classified[0]['quality'] == PeakQuality.EXCELLENT
        assert classified[0]['priority'] == 1
    
    def test_classify_good_peak(self, scheduler):
        """Test classification of top 15% peak as GOOD"""
        # Create forecast with 100 samples
        forecast = []
        for i in range(100):
            price = 0.30 + (i * 0.007)  # 0.30 to ~1.00
            forecast.append({'price': price, 'time': datetime.now().isoformat()})
        
        # Price at ~90th percentile (top 10-15%, should be GOOD or EXCELLENT)
        peaks = [{'price': 0.90, 'time': datetime.now()}]
        classified = scheduler._classify_peaks(peaks, forecast)
        
        assert classified[0]['quality'] in [PeakQuality.GOOD, PeakQuality.EXCELLENT]


class TestDailyPlanning:
    """Test complete daily plan creation"""
    
    @pytest.fixture
    def scheduler(self):
        config = {
            'battery_management': {'capacity_kwh': 20.0},
            'battery_selling': {
                'min_battery_soc': 80,
                'safety_margin_soc': 50,
                'grid_export_limit_w': 5000,
                'discharge_efficiency': 0.92,
                'smart_timing': {
                    'multi_session_scheduler': {
                        'enabled': True,
                        'min_peak_price': 0.70,
                        'min_peak_separation_hours': 3.0,
                        'max_sessions_per_day': 3,
                        'reserve_for_evening_peak': True,
                        'evening_peak_start_hour': 17,
                        'evening_peak_end_hour': 22
                    },
                    'percentile_thresholds': {
                        'aggressive_sell': 5,
                        'standard_sell': 15,
                        'conditional_sell': 25
                    }
                }
            }
        }
        return BatterySellingScheduler(config)
    
    def test_create_plan_with_good_peaks(self, scheduler):
        """Test creating a plan with good selling opportunities"""
        now = datetime.now()
        
        # Create forecast with varied prices (not all the same)
        forecast = []
        for i in range(24):
            # Create varied baseline prices
            base_price = 0.45 + (i % 6) * 0.02  # Varies between 0.45-0.55
            forecast.append({'price': base_price, 'time': (now + timedelta(hours=i)).isoformat()})
        
        # Add 3 clear peaks that stand out
        forecast[8] = {'price': 0.95, 'time': (now + timedelta(hours=8)).isoformat()}   # Morning peak
        forecast[14] = {'price': 0.90, 'time': (now + timedelta(hours=14)).isoformat()} # Afternoon peak
        forecast[19] = {'price': 1.05, 'time': (now + timedelta(hours=19)).isoformat()} # Evening peak (highest)
        
        plan = scheduler.create_daily_plan(
            current_soc=90,
            price_forecast=forecast,
            current_price=0.50,
            forecast_confidence=0.85
        )
        
        assert plan is not None
        assert len(plan.sessions) > 0
        assert len(plan.sessions) <= 3  # Max 3 sessions
        assert plan.total_expected_revenue > 0
        assert plan.battery_end_soc >= scheduler.safety_margin_soc
    
    def test_create_plan_respects_safety_margin(self, scheduler):
        """Test that plan never violates safety margin"""
        now = datetime.now()
        
        # Create extremely high peaks
        forecast = [
            {'price': 2.0, 'time': (now + timedelta(hours=i)).isoformat()}
            for i in range(12)
        ]
        
        plan = scheduler.create_daily_plan(
            current_soc=55,  # Very low SOC
            price_forecast=forecast,
            current_price=0.55
        )
        
        # Either no plan (too low SOC) or plan respects safety
        if plan:
            assert plan.battery_end_soc >= scheduler.safety_margin_soc
    
    def test_no_plan_without_good_peaks(self, scheduler):
        """Test that no plan is created when prices are too low"""
        now = datetime.now()
        
        # All prices below threshold
        forecast = [
            {'price': 0.40, 'time': (now + timedelta(hours=i)).isoformat()}
            for i in range(24)
        ]
        
        plan = scheduler.create_daily_plan(
            current_soc=90,
            price_forecast=forecast,
            current_price=0.40
        )
        
        assert plan is None  # No good opportunities
    
    def test_evening_peak_reservation(self, scheduler):
        """Test that evening peaks are prioritized when configured"""
        now = datetime.now()
        
        # Create forecast with morning and evening peaks
        forecast = [
            {'price': 0.50, 'time': (now + timedelta(hours=i)).isoformat()}
            for i in range(24)
        ]
        
        forecast[10] = {'price': 0.95, 'time': (now + timedelta(hours=10)).isoformat()}  # Morning peak (higher)
        forecast[19] = {'price': 0.90, 'time': (now + timedelta(hours=19)).isoformat()}  # Evening peak
        
        plan = scheduler.create_daily_plan(
            current_soc=90,
            price_forecast=forecast,
            current_price=0.55
        )
        
        if plan and len(plan.sessions) > 0:
            # Check if evening peak (hour 19) is included
            evening_sessions = [s for s in plan.sessions if 17 <= s.start_time.hour <= 22]
            assert len(evening_sessions) > 0  # At least one evening session


class TestSessionManagement:
    """Test session management utilities"""
    
    @pytest.fixture
    def sample_plan(self):
        """Create a sample daily plan"""
        now = datetime.now()
        
        sessions = [
            SellingSession(
                session_id="session_1",
                start_time=now + timedelta(hours=2),
                duration_hours=1.5,
                target_price=0.90,
                peak_quality=PeakQuality.GOOD,
                allocated_energy_kwh=3.0,
                target_soc_end=75,
                expected_revenue=2.70,
                priority=2,
                confidence=0.8
            ),
            SellingSession(
                session_id="session_2",
                start_time=now + timedelta(hours=8),
                duration_hours=2.0,
                target_price=1.00,
                peak_quality=PeakQuality.EXCELLENT,
                allocated_energy_kwh=4.0,
                target_soc_end=65,
                expected_revenue=4.00,
                priority=1,
                confidence=0.9
            )
        ]
        
        return DailySellingPlan(
            plan_date=now.date(),
            sessions=sessions,
            total_planned_energy_kwh=7.0,
            total_expected_revenue=6.70,
            battery_start_soc=90,
            battery_end_soc=65,
            confidence=0.85,
            reasoning="2 sessions planned"
        )
    
    def test_get_next_session(self, sample_plan):
        """Test getting next upcoming session"""
        config = {
            'battery_management': {'capacity_kwh': 20.0},
            'battery_selling': {
                'smart_timing': {'multi_session_scheduler': {'enabled': True}}
            }
        }
        scheduler = BatterySellingScheduler(config)
        
        next_session = scheduler.get_next_session(sample_plan)
        
        # Should get the first upcoming session
        assert next_session is not None
        assert next_session.session_id == "session_1"

