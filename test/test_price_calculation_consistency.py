#!/usr/bin/env python3
"""
Tests for price calculation consistency

Tests that prices are calculated consistently across components,
especially with timestamp-aware tariff calculations.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from automated_price_charging import AutomatedPriceCharger
from tariff_pricing import TariffPricingCalculator


class TestPriceCalculationConsistency:
    """Test price calculation consistency across components"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'electricity_tariff': {
                'tariff_type': 'g12w',
                'sc_component_pln_kwh': 0.0892,
                'distribution_pricing': {
                    'g12w': {
                        'type': 'time_based',
                        'peak_hours': {'start': 6, 'end': 22},
                        'prices': {'peak': 0.3566, 'off_peak': 0.0749}
                    }
                }
            }
        }
    
    @pytest.fixture
    def charger(self, config):
        """Create AutomatedPriceCharger with config"""
        charger = AutomatedPriceCharger()
        charger.config = config
        charger.tariff_calculator = TariffPricingCalculator(config)
        return charger
    
    def test_calculate_final_price_with_timestamp(self, charger):
        """Test that calculate_final_price uses timestamp correctly"""
        # Market price in PLN/MWh
        market_price_mwh = 400.0
        
        # Peak hour (should use peak distribution price)
        peak_time = datetime(2025, 11, 6, 14, 0, 0)  # 2 PM (peak)
        peak_price = charger.calculate_final_price(market_price_mwh, peak_time)
        peak_price_kwh = peak_price / 1000
        
        # Off-peak hour (should use off-peak distribution price)
        off_peak_time = datetime(2025, 11, 6, 23, 0, 0)  # 11 PM (off-peak)
        off_peak_price = charger.calculate_final_price(market_price_mwh, off_peak_time)
        off_peak_price_kwh = off_peak_price / 1000
        
        # Peak price should be higher than off-peak
        assert peak_price_kwh > off_peak_price_kwh, \
            f"Peak price {peak_price_kwh} should be higher than off-peak {off_peak_price_kwh}"
        
        # Verify SC component is included (both should have it)
        # Market price: 0.4 PLN/kWh, SC: 0.0892 PLN/kWh
        # Peak distribution: 0.3566, Off-peak: 0.0749
        expected_peak = 0.4 + 0.0892 + 0.3566  # ~0.8458 PLN/kWh
        expected_off_peak = 0.4 + 0.0892 + 0.0749  # ~0.5641 PLN/kWh
        
        # Allow small rounding differences
        assert abs(peak_price_kwh - expected_peak) < 0.01, \
            f"Peak price {peak_price_kwh} should be close to {expected_peak}"
        assert abs(off_peak_price_kwh - expected_off_peak) < 0.01, \
            f"Off-peak price {off_peak_price_kwh} should be close to {expected_off_peak}"
    
    def test_price_calculation_without_timestamp_uses_now(self, charger):
        """Test that calculate_final_price uses datetime.now() if timestamp not provided"""
        market_price_mwh = 400.0
        
        # Without timestamp, should use current time
        with patch('automated_price_charging.datetime') as mock_datetime:
            mock_now = datetime(2025, 11, 6, 14, 0, 0)  # Peak hour
            mock_datetime.now.return_value = mock_now
            
            price = charger.calculate_final_price(market_price_mwh)
            price_kwh = price / 1000
            
            # Should calculate with peak distribution price
            assert price_kwh > 0.8  # Should include peak distribution
    
    def test_price_consistency_same_timestamp(self, charger):
        """Test that same timestamp produces same price"""
        market_price_mwh = 500.0
        timestamp = datetime(2025, 11, 6, 15, 30, 0)
        
        price1 = charger.calculate_final_price(market_price_mwh, timestamp)
        price2 = charger.calculate_final_price(market_price_mwh, timestamp)
        
        assert price1 == price2, "Same timestamp should produce same price"
    
    def test_price_difference_peak_vs_offpeak(self, charger):
        """Test that peak and off-peak prices are different"""
        market_price_mwh = 300.0
        
        peak_time = datetime(2025, 11, 6, 12, 0, 0)  # Noon (peak)
        off_peak_time = datetime(2025, 11, 6, 23, 0, 0)  # 11 PM (off-peak)
        
        peak_price = charger.calculate_final_price(market_price_mwh, peak_time)
        off_peak_price = charger.calculate_final_price(market_price_mwh, off_peak_time)
        
        # Peak should be significantly higher
        price_diff = peak_price - off_peak_price
        expected_diff = (0.3566 - 0.0749) * 1000  # Distribution price difference in PLN/MWh
        
        assert abs(price_diff - expected_diff) < 1.0, \
            f"Price difference {price_diff} should be close to {expected_diff}"


class TestPriceCalculationWithTimestamp:
    """Test price calculation with explicit timestamps"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'electricity_tariff': {
                'tariff_type': 'g12w',
                'sc_component_pln_kwh': 0.0892,
                'distribution_pricing': {
                    'g12w': {
                        'type': 'time_based',
                        'peak_hours': {'start': 6, 'end': 22},
                        'prices': {'peak': 0.3566, 'off_peak': 0.0749}
                    }
                }
            }
        }
    
    def test_timestamp_passed_to_tariff_calculator(self, config):
        """Test that timestamp is correctly passed through to tariff calculator"""
        calculator = TariffPricingCalculator(config)
        
        market_price_kwh = 0.4
        
        # Peak hour
        peak_time = datetime(2025, 11, 6, 14, 0, 0)
        peak_components = calculator.calculate_final_price(market_price_kwh, peak_time)
        
        # Off-peak hour
        off_peak_time = datetime(2025, 11, 6, 23, 0, 0)
        off_peak_components = calculator.calculate_final_price(market_price_kwh, off_peak_time)
        
        # Distribution prices should be different
        assert peak_components.distribution_price == 0.3566
        assert off_peak_components.distribution_price == 0.0749
        
        # Final prices should reflect the difference
        assert peak_components.final_price > off_peak_components.final_price


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

