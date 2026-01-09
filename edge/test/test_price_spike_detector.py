#!/usr/bin/env python3
"""
Tests for Phase 4: Price Spike Detector

Tests real-time price spike detection for immediate selling decisions.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from price_spike_detector import PriceSpikeDetector, SpikeLevel, PriceSpike


class TestSpikeDetectorInitialization:
    """Test spike detector initialization"""
    
    @pytest.fixture
    def config(self):
        return {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'high_spike_percent': 30,
                        'extreme_spike_percent': 50,
                        'critical_price_threshold': 1.5,
                        'min_price_samples': 3,
                        'lookback_minutes': 60,
                        'min_confidence_threshold': 0.7
                    }
                }
            }
        }
    
    def test_initialization(self, config):
        """Test detector initializes with correct config"""
        detector = PriceSpikeDetector(config)
        
        assert detector.enabled is True
        assert detector.moderate_spike_percent == 15
        assert detector.high_spike_percent == 30
        assert detector.extreme_spike_percent == 50
        assert detector.critical_price_threshold == 1.5
        assert detector.min_price_samples == 3
        assert len(detector.price_history) == 0


class TestPriceSampleCollection:
    """Test price sample collection and history management"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'min_price_samples': 3
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_add_single_sample(self, detector):
        """Test adding single price sample"""
        detector.add_price_sample(0.50)
        
        assert len(detector.price_history) == 1
        assert detector.price_history[0]['price'] == 0.50
    
    def test_add_multiple_samples(self, detector):
        """Test adding multiple price samples"""
        prices = [0.50, 0.55, 0.60, 0.65]
        
        for price in prices:
            detector.add_price_sample(price)
        
        assert len(detector.price_history) == 4
        assert detector.price_history[-1]['price'] == 0.65
    
    def test_history_buffer_limit(self, detector):
        """Test history buffer respects max length (100 samples)"""
        # Add 150 samples
        for i in range(150):
            detector.add_price_sample(0.50 + i * 0.01)
        
        # Should only keep last 100
        assert len(detector.price_history) == 100
        assert detector.price_history[0]['price'] == pytest.approx(1.00, 0.01)  # 50 + (0.01 * 50)


class TestSpikeDetection:
    """Test spike detection logic"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'high_spike_percent': 30,
                        'extreme_spike_percent': 50,
                        'critical_price_threshold': 1.5,
                        'min_price_samples': 3,
                        'lookback_minutes': 60
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_no_spike_stable_prices(self, detector):
        """Test no spike detected with stable prices"""
        # Add stable baseline
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # Current price also 0.50 - no spike
        spike = detector.detect_spike(0.50)
        
        assert spike is None
    
    def test_moderate_spike_15_percent(self, detector):
        """Test moderate spike detection (15% increase)"""
        # Baseline: 0.50 PLN/kWh
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # 17% increase to be safe: 0.585 PLN/kWh
        spike = detector.detect_spike(0.585)
        
        assert spike is not None
        assert spike.spike_level == SpikeLevel.MODERATE
        assert spike.current_price == 0.585
        assert spike.percent_increase >= 15
    
    def test_high_spike_30_percent(self, detector):
        """Test high spike detection (30% increase)"""
        # Baseline: 0.50 PLN/kWh
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # 35% increase: 0.675 PLN/kWh
        spike = detector.detect_spike(0.675)
        
        assert spike is not None
        assert spike.spike_level == SpikeLevel.HIGH
        assert spike.current_price == 0.675
        assert spike.percent_increase >= 30
    
    def test_extreme_spike_50_percent(self, detector):
        """Test extreme spike detection (50% increase)"""
        # Baseline: 0.50 PLN/kWh
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # 60% increase: 0.80 PLN/kWh
        spike = detector.detect_spike(0.80)
        
        assert spike is not None
        assert spike.spike_level == SpikeLevel.EXTREME
        assert spike.current_price == 0.80
        assert spike.percent_increase >= 50
    
    def test_critical_price_threshold(self, detector):
        """Test critical price threshold (>1.5 PLN/kWh = extreme)"""
        # Baseline: 1.40 PLN/kWh
        for _ in range(5):
            detector.add_price_sample(1.40)
        
        # Jump to 1.55 PLN/kWh (only 10.7% increase but above critical threshold)
        spike = detector.detect_spike(1.55)
        
        assert spike is not None
        assert spike.spike_level == SpikeLevel.EXTREME
        assert spike.current_price == 1.55
        assert "critical threshold" in spike.reasoning.lower()
    
    def test_insufficient_samples_no_detection(self, detector):
        """Test no detection with insufficient samples"""
        # Only add 1 sample (need 3, and detect_spike will add current as 2nd)
        detector.add_price_sample(0.50)
        
        # Try to detect spike (this will be sample #2, still need 3)
        spike = detector.detect_spike(0.70)
        
        assert spike is None  # Not enough samples yet (only 2)


class TestConfidenceCalculation:
    """Test confidence scoring for spike detection"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'min_price_samples': 3
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_confidence_increases_with_samples(self, detector):
        """Test confidence increases with more price samples"""
        # Few samples
        for _ in range(5):
            detector.add_price_sample(0.50)
        spike_few = detector.detect_spike(0.60)
        
        # Clear and add many samples
        detector.clear_history()
        for _ in range(20):
            detector.add_price_sample(0.50)
        spike_many = detector.detect_spike(0.60)
        
        assert spike_few.confidence < spike_many.confidence
    
    def test_confidence_increases_with_spike_magnitude(self, detector):
        """Test confidence increases with larger spike"""
        # Setup baseline
        for _ in range(10):
            detector.add_price_sample(0.50)
        
        # Small spike (20%)
        spike_small = detector.detect_spike(0.60)
        
        # Clear and reset
        detector.clear_history()
        for _ in range(10):
            detector.add_price_sample(0.50)
        
        # Large spike (60%)
        spike_large = detector.detect_spike(0.80)
        
        assert spike_small.confidence < spike_large.confidence


class TestRecommendedActions:
    """Test action recommendations based on spikes"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'high_spike_percent': 30,
                        'extreme_spike_percent': 50,
                        'critical_price_threshold': 1.5,
                        'min_price_samples': 3
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_extreme_spike_sell_immediately(self, detector):
        """Test extreme spike recommends immediate selling"""
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        spike = detector.detect_spike(0.80)
        
        assert "SELL IMMEDIATELY" in spike.recommended_action or "SELL NOW" in spike.recommended_action
    
    def test_high_spike_sell_now(self, detector):
        """Test high spike recommends selling now"""
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        spike = detector.detect_spike(0.67)
        
        assert "SELL" in spike.recommended_action.upper()
    
    def test_moderate_spike_evaluate(self, detector):
        """Test moderate spike recommends evaluation"""
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        spike = detector.detect_spike(0.58)
        
        # Should recommend evaluation or monitoring
        assert "EVALUATE" in spike.recommended_action.upper() or "MONITOR" in spike.recommended_action.upper()


class TestSpikeTracking:
    """Test spike tracking and statistics"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'min_price_samples': 3
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_spike_count_tracking(self, detector):
        """Test daily spike counting"""
        # Add baseline
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # Detect first spike
        detector.detect_spike(0.60)
        assert detector.spike_count_today == 1
        
        # Reset baseline
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        # Detect second spike
        detector.detect_spike(0.62)
        assert detector.spike_count_today == 2
    
    def test_is_spike_active_within_window(self, detector):
        """Test active spike detection within time window"""
        # Setup and detect spike
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        detector.detect_spike(0.60)
        
        # Should be active within 5 minutes
        assert detector.is_spike_active(max_age_minutes=5) is True
    
    def test_get_spike_statistics(self, detector):
        """Test spike statistics retrieval"""
        # Add baseline and detect spike
        for _ in range(5):
            detector.add_price_sample(0.50)
        
        detector.detect_spike(0.60)
        
        stats = detector.get_spike_statistics()
        
        assert stats['enabled'] is True
        assert stats['samples_collected'] >= 5
        assert stats['spikes_today'] == 1
        assert stats['last_spike'] is not None
        assert stats['last_spike']['level'] is not None


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.fixture
    def detector(self):
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': True,
                        'moderate_spike_percent': 15,
                        'min_price_samples': 3
                    }
                }
            }
        }
        return PriceSpikeDetector(config)
    
    def test_disabled_detector_returns_none(self):
        """Test disabled detector returns None"""
        config = {
            'battery_selling': {
                'smart_timing': {
                    'spike_detection': {
                        'enabled': False
                    }
                }
            }
        }
        detector = PriceSpikeDetector(config)
        
        spike = detector.detect_spike(1.50)
        assert spike is None
    
    def test_negative_price_handling(self, detector):
        """Test handling of negative prices"""
        # Negative prices (rare but possible in energy markets)
        detector.add_price_sample(-0.10)
        detector.add_price_sample(-0.05)
        detector.add_price_sample(-0.02)
        
        # Jump to positive
        spike = detector.detect_spike(0.50)
        
        # Should handle gracefully (huge percentage increase but from negative base)
        assert spike is None or spike.spike_level in [SpikeLevel.EXTREME, SpikeLevel.HIGH]
    
    def test_zero_reference_price_handling(self, detector):
        """Test handling when reference price is zero"""
        detector.add_price_sample(0.0)
        detector.add_price_sample(0.0)
        detector.add_price_sample(0.0)
        
        spike = detector.detect_spike(0.50)
        
        # Should not crash with division by zero
        assert spike is None  # Reference is 0, can't calculate percentage
    
    def test_clear_history(self, detector):
        """Test clearing price history"""
        # Add samples
        for i in range(10):
            detector.add_price_sample(0.50 + i * 0.01)
        
        assert len(detector.price_history) == 10
        
        # Clear
        detector.clear_history()
        
        assert len(detector.price_history) == 0
        assert detector.last_spike is None

