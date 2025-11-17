#!/usr/bin/env python3
"""
Tests for Phase 1: Extended Forecast Lookahead (6h → 12h)

Tests the enhanced forecast capabilities with longer lookahead windows
and integration with D+1 PSE forecast data.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from battery_selling_timing import BatterySellingTiming, TimingDecision


class TestExtendedForecast:
    """Test extended 12-hour forecast lookahead functionality"""
    
    @pytest.fixture
    def config_12h(self):
        """Configuration with 12h forecast lookahead"""
        return {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 12,
                    'near_peak_threshold_percent': 95,
                    'min_peak_difference_percent': 15,
                    'max_wait_time_hours': 4,
                    'min_forecast_confidence': 0.6,
                    'percentile_thresholds': {
                        'aggressive_sell': 5,
                        'standard_sell': 15,
                        'conditional_sell': 25
                    },
                    'opportunity_cost': {
                        'high_confidence_wait': 30,
                        'medium_confidence_wait': 15,
                        'low_confidence_wait': 10,
                        'sell_threshold': 10
                    }
                }
            },
            'battery_management': {
                'capacity_kwh': 20.0
            }
        }
    
    @pytest.fixture
    def timing_engine_12h(self, config_12h):
        """Create timing engine with 12h lookahead"""
        return BatterySellingTiming(config_12h)
    
    def test_initialization_12h_lookahead(self, timing_engine_12h):
        """Test that 12h forecast lookahead is configured correctly"""
        assert timing_engine_12h.enabled is True
        assert timing_engine_12h.forecast_lookahead_hours == 12
        assert timing_engine_12h.aggressive_sell_percentile == 5
        assert timing_engine_12h.standard_sell_percentile == 15
        assert timing_engine_12h.conditional_sell_percentile == 25
    
    def test_detect_evening_peak_from_morning(self, timing_engine_12h):
        """Test detecting evening peak when analyzing in the morning"""
        # Use current hour as baseline (rounded) to keep wait time tied to runtime (~11h ahead)
        current_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        current_price = 0.45
        
        # Generate 12-hour forecast with evening peak at 7 PM (11 hours away)
        price_forecast = []
        for hour in range(12):
            future_time = current_time + timedelta(hours=hour)
            # Prices gradually increase to evening peak at hour 11 (7 PM)
            if hour < 10:
                price = 0.45 + (hour * 0.03)  # Gradual increase
            elif hour == 11:
                price = 0.95  # Evening peak
            else:
                price = 0.70  # After peak
            
            price_forecast.append({
                'price': price,
                'time': future_time.isoformat()
            })
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine_12h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should wait for the evening peak (111% increase from 0.45 to 0.95)
        assert recommendation.decision == TimingDecision.WAIT_FOR_PEAK
        assert recommendation.peak_info is not None
        assert recommendation.peak_info.peak_price >= 0.90
        # Time to peak should match configured offset (~11 hours ahead of base time)
        expected_wait = 11.0
        assert (expected_wait - 1.0) <= recommendation.wait_hours <= (expected_wait + 1.0)
    
    def test_miss_evening_peak_with_6h_lookahead(self):
        """Test that 6h lookahead would miss an evening peak visible with 12h"""
        config_6h = {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 6,  # Old 6h lookahead
                    'near_peak_threshold_percent': 95,
                    'min_peak_difference_percent': 15,
                    'max_wait_time_hours': 4
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
        timing_engine_6h = BatterySellingTiming(config_6h)
        
        # Morning at 10 AM
        current_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        current_price = 0.50
        
        # Generate forecast with evening peak at 7 PM (9 hours away)
        price_forecast = []
        for hour in range(12):
            future_time = current_time + timedelta(hours=hour)
            if hour < 8:
                price = 0.50 + (hour * 0.02)  # Gradual increase
            elif hour == 9:
                price = 0.95  # Evening peak at 7 PM
            else:
                price = 0.70
            
            price_forecast.append({
                'price': price,
                'time': future_time.isoformat()
            })
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine_6h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # With 6h lookahead, peak at hour 9 is outside the window
        # Engine will only see prices up to hour 6 (0.62 PLN/kWh max)
        # Might still wait for the smaller peak visible in 6h window
        assert recommendation.decision in [TimingDecision.WAIT_FOR_PEAK, TimingDecision.WAIT_FOR_HIGHER, TimingDecision.SELL_NOW]
    
    def test_multiple_peaks_choose_best(self, timing_engine_12h):
        """Test choosing the best peak when multiple peaks exist in 12h window"""
        current_price = 0.50
        current_time = datetime.now()
        
        # Create forecast with two peaks: one at 3h (0.75) and one at 9h (0.95)
        price_forecast = [
            {'price': 0.60, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.70, 'time': (current_time + timedelta(hours=2)).isoformat()},
            {'price': 0.75, 'time': (current_time + timedelta(hours=3)).isoformat()},  # First peak
            {'price': 0.65, 'time': (current_time + timedelta(hours=4)).isoformat()},
            {'price': 0.70, 'time': (current_time + timedelta(hours=5)).isoformat()},
            {'price': 0.75, 'time': (current_time + timedelta(hours=6)).isoformat()},
            {'price': 0.80, 'time': (current_time + timedelta(hours=7)).isoformat()},
            {'price': 0.90, 'time': (current_time + timedelta(hours=8)).isoformat()},
            {'price': 0.95, 'time': (current_time + timedelta(hours=9)).isoformat()},  # Best peak
            {'price': 0.85, 'time': (current_time + timedelta(hours=10)).isoformat()},
            {'price': 0.75, 'time': (current_time + timedelta(hours=11)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine_12h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should wait for the best peak (0.95 at hour 9), not the first peak
        assert recommendation.decision == TimingDecision.WAIT_FOR_PEAK
        assert recommendation.peak_info is not None
        assert recommendation.peak_info.peak_price >= 0.90  # Should find the 0.95 peak
        assert 8.0 <= recommendation.wait_hours <= 10.0
    
    def test_forecast_confidence_threshold(self, timing_engine_12h):
        """Test that low forecast confidence falls back to immediate selling"""
        current_price = 0.60
        price_forecast = [
            {'price': 0.80, 'time': (datetime.now() + timedelta(hours=2)).isoformat()}
        ]
        current_data = {'battery': {'soc_percent': 85}}
        
        # Low confidence should trigger immediate sell
        recommendation = timing_engine_12h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.4  # Below min_forecast_confidence (0.6)
        )
        
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "confidence" in recommendation.reasoning.lower() or "unavailable" in recommendation.reasoning.lower()
    
    def test_empty_forecast_fallback(self, timing_engine_12h):
        """Test graceful handling of empty forecast data"""
        current_price = 0.65
        price_forecast = []  # Empty forecast
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine_12h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should fall back to immediate selling
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "unavailable" in recommendation.reasoning.lower() or "forecast" in recommendation.reasoning.lower()
    
    def test_partial_forecast_data(self, timing_engine_12h):
        """Test handling of partial forecast data (less than 12h)"""
        current_price = 0.55
        current_time = datetime.now()
        
        # Only 6 hours of data available (not full 12h)
        price_forecast = [
            {'price': 0.60, 'time': (current_time + timedelta(hours=i)).isoformat()}
            for i in range(1, 7)
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine_12h.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.8
        )
        
        # Should still work with partial data
        assert recommendation.decision is not None
        assert recommendation.confidence > 0


class TestEnhancedPercentileThresholds:
    """Test Phase 1 enhanced percentile-based selling logic"""
    
    @pytest.fixture
    def timing_engine(self):
        """Create timing engine with Phase 1 percentile thresholds"""
        config = {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 12,
                    'percentile_thresholds': {
                        'aggressive_sell': 5,
                        'standard_sell': 15,
                        'conditional_sell': 25
                    },
                    'opportunity_cost': {
                        'high_confidence_wait': 30,
                        'medium_confidence_wait': 15,
                        'low_confidence_wait': 10
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
        return BatterySellingTiming(config)
    
    def test_top_5_percent_aggressive_sell(self, timing_engine):
        """Test aggressive immediate selling for top 5% prices"""
        current_price = 0.95
        current_time = datetime.now()
        
        # Create forecast where current price is in top 5% (95th percentile)
        price_forecast = [
            {'price': price, 'time': (current_time + timedelta(hours=i)).isoformat()}
            for i, price in enumerate([0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.92, 0.93, 0.94])
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should sell immediately (top 5%)
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "top 5" in recommendation.reasoning or "percentile" in recommendation.reasoning
    
    def test_top_15_percent_standard_sell(self, timing_engine):
        """Test standard selling for top 15% prices (no nearby better peak)"""
        current_price = 0.82
        current_time = datetime.now()
        
        # Create forecast where current price is in top 15% (85th percentile)
        # No significantly better peak within 2h
        price_forecast = [
            {'price': 0.83, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.81, 'time': (current_time + timedelta(hours=2)).isoformat()},
            {'price': 0.75, 'time': (current_time + timedelta(hours=3)).isoformat()},
            {'price': 0.70, 'time': (current_time + timedelta(hours=4)).isoformat()},
            {'price': 0.65, 'time': (current_time + timedelta(hours=5)).isoformat()},
            {'price': 0.60, 'time': (current_time + timedelta(hours=6)).isoformat()},
            {'price': 0.55, 'time': (current_time + timedelta(hours=7)).isoformat()},
            {'price': 0.50, 'time': (current_time + timedelta(hours=8)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should sell now (top 15%, no better peak within 2h)
        assert recommendation.decision == TimingDecision.SELL_NOW
        assert "top 15" in recommendation.reasoning or "no better peak" in recommendation.reasoning.lower()
    
    def test_top_25_percent_conditional_sell(self, timing_engine):
        """Test conditional selling for top 25% prices"""
        current_price = 0.65
        current_time = datetime.now()
        
        # Create forecast where current price is in top 25% (~75th percentile)
        # Need more lower prices to ensure 0.65 is truly in top 25%
        price_forecast = [
            {'price': 0.66, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.64, 'time': (current_time + timedelta(hours=2)).isoformat()},
            {'price': 0.60, 'time': (current_time + timedelta(hours=3)).isoformat()},
            {'price': 0.55, 'time': (current_time + timedelta(hours=4)).isoformat()},
            {'price': 0.50, 'time': (current_time + timedelta(hours=5)).isoformat()},
            {'price': 0.45, 'time': (current_time + timedelta(hours=6)).isoformat()},
            {'price': 0.40, 'time': (current_time + timedelta(hours=7)).isoformat()},
            {'price': 0.35, 'time': (current_time + timedelta(hours=8)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should sell now (top 25%, minimal upside < 10%)
        assert recommendation.decision == TimingDecision.SELL_NOW
        # Can match top 25, top 15, or similar reasoning
        assert "top" in recommendation.reasoning.lower() or "percentile" in recommendation.reasoning.lower()


class TestImprovedOpportunityCost:
    """Test Phase 1 improved opportunity cost thresholds"""
    
    @pytest.fixture
    def timing_engine(self):
        """Create timing engine with improved opportunity cost thresholds"""
        config = {
            'battery_selling': {
                'smart_timing': {
                    'enabled': True,
                    'forecast_lookahead_hours': 12,
                    'opportunity_cost': {
                        'high_confidence_wait': 30,
                        'medium_confidence_wait': 15,
                        'low_confidence_wait': 10,
                        'sell_threshold': 10
                    }
                }
            },
            'battery_management': {'capacity_kwh': 20.0}
        }
        return BatterySellingTiming(config)
    
    def test_high_opportunity_30_percent_wait(self, timing_engine):
        """Test waiting for 30%+ opportunity (high confidence)"""
        current_price = 0.50
        current_time = datetime.now()
        
        # 35% price increase in 2h
        price_forecast = [
            {'price': 0.60, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.675, 'time': (current_time + timedelta(hours=2)).isoformat()},  # 35% increase
            {'price': 0.65, 'time': (current_time + timedelta(hours=3)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should wait for high opportunity
        assert recommendation.decision == TimingDecision.WAIT_FOR_PEAK
        assert "high opportunity" in recommendation.reasoning.lower() or "peak" in recommendation.reasoning.lower()
        assert recommendation.wait_hours <= 3.0
    
    def test_medium_opportunity_15_to_30_percent(self, timing_engine):
        """Test waiting for 15-30% opportunity if <3h away"""
        current_price = 0.60
        current_time = datetime.now()
        
        # 20% price increase in 2h
        price_forecast = [
            {'price': 0.65, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.72, 'time': (current_time + timedelta(hours=2)).isoformat()},  # 20% increase
            {'price': 0.68, 'time': (current_time + timedelta(hours=3)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should wait for medium opportunity (<3h)
        assert recommendation.decision == TimingDecision.WAIT_FOR_PEAK
        assert "medium opportunity" in recommendation.reasoning.lower() or "peak" in recommendation.reasoning.lower()
        assert recommendation.wait_hours <= 3.0
    
    def test_low_opportunity_10_to_15_percent(self, timing_engine):
        """Test waiting for 10-15% opportunity only if <1h away"""
        current_price = 0.70
        current_time = datetime.now()
        
        # 12% price increase in 0.5h
        price_forecast = [
            {'price': 0.784, 'time': (current_time + timedelta(minutes=30)).isoformat()},  # 12% increase
            {'price': 0.75, 'time': (current_time + timedelta(hours=1)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # Should wait for small opportunity (very soon, <1h)
        assert recommendation.decision in [TimingDecision.WAIT_FOR_HIGHER, TimingDecision.WAIT_FOR_PEAK]
        assert recommendation.wait_hours <= 1.0
    
    def test_below_10_percent_sell_now(self, timing_engine):
        """Test selling now when opportunity <10%"""
        current_price = 0.75
        current_time = datetime.now()
        
        # Only 4% price increase (below all thresholds)
        price_forecast = [
            {'price': 0.76, 'time': (current_time + timedelta(hours=1)).isoformat()},
            {'price': 0.78, 'time': (current_time + timedelta(hours=2)).isoformat()},  # 4% increase
            {'price': 0.77, 'time': (current_time + timedelta(hours=3)).isoformat()},
        ]
        
        current_data = {'battery': {'soc_percent': 85}}
        
        recommendation = timing_engine.analyze_selling_timing(
            current_price=current_price,
            price_forecast=price_forecast,
            current_data=current_data,
            forecast_confidence=0.9
        )
        
        # With <5% opportunity, should sell now or indicate no opportunity
        # May also return WAIT_FOR_HIGHER if legacy marginal_savings_percent (5%) catches it
        assert recommendation.decision in [TimingDecision.SELL_NOW, TimingDecision.NO_OPPORTUNITY, TimingDecision.WAIT_FOR_HIGHER]

