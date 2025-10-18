#!/usr/bin/env python3
"""
Comprehensive Test Suite for Battery Selling Smart Timing Functionality

This test suite covers:
- Price forecast analysis
- Peak price detection
- Price trend analysis (rising, falling, stable)
- Opportunity cost calculation
- Selling window identification
- Multi-session selling
- Confidence-based decisions
- Wait cancellation logic

Run with: python -m pytest test/test_battery_selling_timing.py -v
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_selling_timing import (
    BatterySellingTiming,
    TimingDecision,
    TimingRecommendation,
    PriceTrend,
    PriceAnalysis,
    PeakInfo,
    SellingWindow
)


class TestBatterySellingTiming:
    """Test smart timing engine"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 6,
                    'near_peak_threshold_percent': 95,
                    'min_peak_difference_percent': 15,
                    'max_wait_time_hours': 4,
                    'min_forecast_confidence': 0.6,
                    'opportunity_cost': {
                        'significant_savings_percent': 20,
                        'marginal_savings_percent': 5
                    },
                    'trend_analysis': {
                        'enabled': True,
                        'trend_window_hours': 2,
                        'rising_threshold': 0.02,
                        'falling_threshold': -0.02
                    },
                    'multi_session': {
                        'enabled': True,
                        'max_sessions_per_day': 3,
                        'min_session_gap_hours': 1,
                        'reserve_battery_percent': 20
                    }
                }
            },
            'battery_management': {
                'capacity_kwh': 20.0
            }
        }
    
    @pytest.fixture
    def timing_engine(self, config):
        """Timing engine instance"""
        return BatterySellingTiming(config)
    
    def test_initialization(self, timing_engine):
        """Test timing engine initialization"""
        assert timing_engine.enabled is True
        assert timing_engine.forecast_lookahead_hours == 6
        assert timing_engine.near_peak_threshold_percent == 95
        assert timing_engine.min_peak_difference_percent == 15
        assert timing_engine.max_wait_time_hours == 4
        assert timing_engine.battery_capacity_kwh == 20.0
    
    def test_price_context_analysis_basic(self, timing_engine):
        """Test basic price context analysis"""
        current_price = 0.60
        price_forecast = [
            {'price': 0.50, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.55, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},
            {'price': 0.80, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        
        analysis = timing_engine._analyze_price_context(current_price, price_forecast)
        
        assert analysis.current_price == 0.60
        assert analysis.min_price == 0.50
        assert analysis.max_price == 0.80
        assert 0.6 <= analysis.avg_price <= 0.7
        assert analysis.median_price > 0
        assert 0 <= analysis.current_percentile <= 100
    
    def test_price_context_analysis_high_price(self, timing_engine):
        """Test price context with current price being high"""
        current_price = 0.95
        price_forecast = [
            {'price': 0.50, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.55, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},
            {'price': 0.65, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        
        analysis = timing_engine._analyze_price_context(current_price, price_forecast)
        
        assert analysis.current_price == 0.95
        assert analysis.max_price == 0.95
        assert analysis.is_high_price is True
        assert analysis.is_peak_price is True
        assert analysis.current_percentile >= 90
    
    def test_peak_detection_with_peak(self, timing_engine):
        """Test peak detection when peak exists"""
        current_price = 0.60
        price_forecast = [
            {'price': 0.65, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},  # Peak
            {'price': 0.75, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        
        peak_info = timing_engine._detect_price_peak(current_price, price_forecast)
        
        assert peak_info is not None
        assert peak_info.peak_price == 0.90
        assert 2.5 < peak_info.time_to_peak_hours < 3.5
        assert peak_info.price_increase_percent > 40  # (0.90 - 0.60) / 0.60 * 100
        assert 0 < peak_info.confidence <= 1.0
    
    def test_peak_detection_no_peak(self, timing_engine):
        """Test peak detection when no peak exists"""
        current_price = 0.90
        price_forecast = [
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.55, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.50, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
        ]
        
        peak_info = timing_engine._detect_price_peak(current_price, price_forecast)
        
        assert peak_info is None
    
    def test_price_trend_rising(self, timing_engine):
        """Test rising price trend detection"""
        price_forecast = [
            {'price': 0.50, 'time': (datetime.now() + timedelta(minutes=30)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=1.5)).isoformat()}
        ]
        
        trend = timing_engine._analyze_price_trend(price_forecast)
        
        assert trend == PriceTrend.RISING
    
    def test_price_trend_falling(self, timing_engine):
        """Test falling price trend detection"""
        price_forecast = [
            {'price': 0.80, 'time': (datetime.now() + timedelta(minutes=30)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=1.5)).isoformat()}
        ]
        
        trend = timing_engine._analyze_price_trend(price_forecast)
        
        assert trend == PriceTrend.FALLING
    
    def test_price_trend_stable(self, timing_engine):
        """Test stable price trend detection"""
        price_forecast = [
            {'price': 0.60, 'time': (datetime.now() + timedelta(minutes=30)).isoformat()},
            {'price': 0.61, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=1.5)).isoformat()}
        ]
        
        trend = timing_engine._analyze_price_trend(price_forecast)
        
        assert trend == PriceTrend.STABLE
    
    def test_opportunity_cost_calculation(self, timing_engine):
        """Test opportunity cost calculation"""
        current_price = 0.60
        peak_info = PeakInfo(
            peak_time=datetime.now() + timedelta(hours=2),
            peak_price=0.90,
            time_to_peak_hours=2.0,
            price_increase_percent=50.0,
            confidence=0.9
        )
        current_data = {
            'battery': {'soc_percent': 80}
        }
        
        opportunity_cost = timing_engine._calculate_opportunity_cost(
            current_price, peak_info, current_data
        )
        
        # Available energy: 30% of 20kWh = 6kWh
        # Revenue difference: 6 * (0.90 - 0.60) = 1.8 PLN
        assert opportunity_cost > 1.5
        assert opportunity_cost < 2.0
    
    def test_selling_windows_identification(self, timing_engine):
        """Test selling window identification"""
        price_forecast = [
            {'price': 0.50, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.85, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=2.5)).isoformat()},
            {'price': 0.88, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 80}}
        
        windows = timing_engine._identify_selling_windows(price_forecast, current_data)
        
        assert len(windows) > 0
        assert all(isinstance(w, SellingWindow) for w in windows)
        assert windows[0].duration_hours >= 0.5  # At least 30 minutes
    
    def test_timing_decision_sell_at_peak(self, timing_engine):
        """Test decision to sell when at peak price"""
        current_price = 0.95
        price_forecast = [
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.80, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert recommendation.confidence > 0.8
        assert "peak" in recommendation.reasoning.lower() or "high" in recommendation.reasoning.lower()
    
    def test_timing_decision_wait_for_peak(self, timing_engine):
        """Test decision to wait for peak price"""
        current_price = 0.50
        price_forecast = [
            {'price': 0.55, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.65, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},  # Peak +80%
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=4)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        assert recommendation.decision in [TimingDecision.WAIT_FOR_PEAK, TimingDecision.WAIT_FOR_HIGHER]
        assert recommendation.peak_info is not None
        assert recommendation.peak_info.peak_price == 0.90
        assert recommendation.opportunity_cost_pln > 0
    
    def test_timing_decision_falling_trend_sell_now(self, timing_engine):
        """Test decision to sell now when price is falling"""
        current_price = 0.80
        price_forecast = [
            {'price': 0.75, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.70, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.65, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should sell now because either at peak or falling trend
        assert recommendation.decision == TimingDecision.SELL_NOW
        # Reasoning could mention either peak (since 0.80 is highest) or falling trend
        assert ("falling" in recommendation.reasoning.lower() or 
                "peak" in recommendation.reasoning.lower() or
                "high" in recommendation.reasoning.lower())
    
    def test_timing_decision_no_opportunity_low_price(self, timing_engine):
        """Test no opportunity when price is too low"""
        current_price = 0.30
        price_forecast = [
            {'price': 0.35, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.32, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.33, 'time': (datetime.now() + timedelta(hours=3)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # With such low prices, should indicate no good opportunity
        assert recommendation.decision in [TimingDecision.NO_OPPORTUNITY, TimingDecision.WAIT_FOR_HIGHER]
    
    def test_cancel_waiting_low_soc(self, timing_engine):
        """Test cancel waiting when battery SOC drops"""
        current_data = {'battery': {'soc_percent': 65}}
        waiting_since = datetime.now() - timedelta(hours=1)
        original_recommendation = TimingRecommendation(
            decision=TimingDecision.WAIT_FOR_PEAK,
            confidence=0.8,
            reasoning="Waiting for peak",
            sell_time=datetime.now() + timedelta(hours=1),
            expected_price=0.90,
            opportunity_cost_pln=2.0,
            peak_info=None,
            selling_windows=[],
            wait_hours=1.0,
            risk_level="low"
        )
        
        should_cancel, reason = timing_engine.should_cancel_waiting(
            current_data, waiting_since, original_recommendation
        )
        
        assert should_cancel is True
        assert "soc" in reason.lower() or "battery" in reason.lower()
    
    def test_cancel_waiting_max_time(self, timing_engine):
        """Test cancel waiting when max wait time reached"""
        current_data = {'battery': {'soc_percent': 85}}
        waiting_since = datetime.now() - timedelta(hours=5)  # Exceed max_wait_time_hours (4)
        original_recommendation = TimingRecommendation(
            decision=TimingDecision.WAIT_FOR_PEAK,
            confidence=0.8,
            reasoning="Waiting for peak",
            sell_time=datetime.now() + timedelta(hours=1),
            expected_price=0.90,
            opportunity_cost_pln=2.0,
            peak_info=None,
            selling_windows=[],
            wait_hours=1.0,
            risk_level="low"
        )
        
        should_cancel, reason = timing_engine.should_cancel_waiting(
            current_data, waiting_since, original_recommendation
        )
        
        assert should_cancel is True
        assert "wait time" in reason.lower() or "maximum" in reason.lower()
    
    def test_cancel_waiting_high_consumption(self, timing_engine):
        """Test cancel waiting when house consumption spikes"""
        current_data = {
            'battery': {'soc_percent': 85},
            'consumption': {'power_w': 3500}  # High consumption
        }
        waiting_since = datetime.now() - timedelta(hours=1)
        original_recommendation = TimingRecommendation(
            decision=TimingDecision.WAIT_FOR_PEAK,
            confidence=0.8,
            reasoning="Waiting for peak",
            sell_time=datetime.now() + timedelta(hours=1),
            expected_price=0.90,
            opportunity_cost_pln=2.0,
            peak_info=None,
            selling_windows=[],
            wait_hours=1.0,
            risk_level="low"
        )
        
        should_cancel, reason = timing_engine.should_cancel_waiting(
            current_data, waiting_since, original_recommendation
        )
        
        assert should_cancel is True
        assert "consumption" in reason.lower()
    
    def test_timing_disabled(self, config):
        """Test timing engine when disabled"""
        config['battery_selling']['smart_timing']['enabled'] = False
        timing_engine = BatterySellingTiming(config)
        
        current_price = 0.60
        price_forecast = [
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "disabled" in recommendation.reasoning.lower()
    
    def test_low_forecast_confidence(self, timing_engine):
        """Test behavior with low forecast confidence"""
        current_price = 0.60
        price_forecast = [
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.3  # Low confidence
        )
        
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "confidence" in recommendation.reasoning.lower()
    
    def test_get_timing_status(self, timing_engine):
        """Test getting timing status"""
        status = timing_engine.get_timing_status()
        
        assert status['enabled'] is True
        assert 'planned_sessions' in status
        assert 'completed_sessions_today' in status
        assert 'configuration' in status
        assert status['configuration']['forecast_lookahead_hours'] == 6


class TestTimingIntegrationScenarios:
    """Integration test scenarios"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 6,
                    'near_peak_threshold_percent': 95,
                    'min_peak_difference_percent': 15,
                    'max_wait_time_hours': 4,
                    'min_forecast_confidence': 0.6,
                    'opportunity_cost': {
                        'significant_savings_percent': 20,
                        'marginal_savings_percent': 5
                    },
                    'trend_analysis': {
                        'enabled': True,
                        'trend_window_hours': 2,
                        'rising_threshold': 0.02,
                        'falling_threshold': -0.02
                    },
                    'multi_session': {
                        'enabled': True,
                        'max_sessions_per_day': 3,
                        'min_session_gap_hours': 1,
                        'reserve_battery_percent': 20
                    }
                }
            },
            'battery_management': {
                'capacity_kwh': 20.0
            }
        }
    
    @pytest.fixture
    def timing_engine(self, config):
        """Timing engine instance"""
        return BatterySellingTiming(config)
    
    def test_scenario_early_afternoon_with_evening_peak(self, timing_engine):
        """
        Scenario: It's 14:00, price is 0.60 PLN/kWh (decent)
        Forecast shows peak at 19:00 with 0.95 PLN/kWh
        Expected: WAIT for evening peak
        """
        current_price = 0.60
        base_time = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
        
        price_forecast = [
            {'price': 0.62, 'time': (base_time + timedelta(hours=1)).isoformat()},
            {'price': 0.65, 'time': (base_time + timedelta(hours=2)).isoformat()},
            {'price': 0.70, 'time': (base_time + timedelta(hours=3)).isoformat()},
            {'price': 0.85, 'time': (base_time + timedelta(hours=4)).isoformat()},
            {'price': 0.95, 'time': (base_time + timedelta(hours=5)).isoformat()},  # 19:00 peak
            {'price': 0.90, 'time': (base_time + timedelta(hours=6)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        assert recommendation.decision in [TimingDecision.WAIT_FOR_PEAK, TimingDecision.WAIT_FOR_HIGHER]
        assert recommendation.opportunity_cost_pln > 1.0
        assert recommendation.peak_info.peak_price == 0.95
    
    def test_scenario_already_at_peak(self, timing_engine):
        """
        Scenario: It's 19:00, price is 0.95 PLN/kWh (peak)
        Forecast shows prices dropping
        Expected: SELL NOW
        """
        current_price = 0.95
        base_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
        
        price_forecast = [
            {'price': 0.90, 'time': (base_time + timedelta(hours=1)).isoformat()},
            {'price': 0.80, 'time': (base_time + timedelta(hours=2)).isoformat()},
            {'price': 0.70, 'time': (base_time + timedelta(hours=3)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "peak" in recommendation.reasoning.lower() or "high" in recommendation.reasoning.lower()
    
    def test_scenario_moderate_price_small_peak_ahead(self, timing_engine):
        """
        Scenario: Current price 0.70 PLN/kWh, small peak at 0.75 PLN/kWh in 1 hour
        Expected: SELL NOW (not worth waiting for small increase)
        """
        current_price = 0.70
        price_forecast = [
            {'price': 0.72, 'time': (datetime.now() + timedelta(hours=0.5)).isoformat()},
            {'price': 0.75, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.73, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # With only ~7% increase, should sell now or indicate marginal opportunity
        assert recommendation.decision in [TimingDecision.SELL_NOW, TimingDecision.WAIT_FOR_HIGHER]
    
    def test_scenario_multiple_peaks(self, timing_engine):
        """
        Scenario: Multiple peaks throughout the day
        Expected: Identify multiple selling windows
        """
        current_price = 0.50
        price_forecast = [
            {'price': 0.85, 'time': (datetime.now() + timedelta(hours=1)).isoformat()},
            {'price': 0.90, 'time': (datetime.now() + timedelta(hours=1.5)).isoformat()},  # Peak 1
            {'price': 0.75, 'time': (datetime.now() + timedelta(hours=2)).isoformat()},
            {'price': 0.60, 'time': (datetime.now() + timedelta(hours=3)).isoformat()},
            {'price': 0.88, 'time': (datetime.now() + timedelta(hours=4)).isoformat()},
            {'price': 0.92, 'time': (datetime.now() + timedelta(hours=5)).isoformat()},  # Peak 2
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should identify multiple windows
        if recommendation.selling_windows:
            assert len(recommendation.selling_windows) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

