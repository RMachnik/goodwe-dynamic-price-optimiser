#!/usr/bin/env python3
"""
Tests for Tariff Pricing Module

Tests tariff-aware electricity pricing for Polish market tariffs:
- G11 (single-zone, static)
- G12 / G12w (two-zone, time-based)
- G12as (two-zone with volume pricing)
- G14dynamic (dynamic, kompas-based)
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tariff_pricing import TariffPricingCalculator, PriceComponents


def create_test_config(tariff_type="g12w"):
    """Create test configuration"""
    return {
        'electricity_tariff': {
            'tariff_type': tariff_type,
            'sc_component_pln_kwh': 0.0892,
            'distribution_pricing': {
                'g12w': {
                    'type': 'time_based',
                    'peak_hours': {'start': 6, 'end': 22},
                    'prices': {'peak': 0.3566, 'off_peak': 0.0749}
                },
                'g14dynamic': {
                    'type': 'kompas_based',
                    'requires_pse_peak_hours': True,
                    'prices': {
                        'normal_usage': 0.0578,
                        'recommended_usage': 0.0145,
                        'recommended_saving': 0.4339,
                        'required_reduction': 2.8931
                    },
                    'fallback_price': 0.0578
                },
                'g11': {
                    'type': 'static',
                    'price': 0.3125
                }
            }
        }
    }


class TestTariffPricingCalculator:
    """Test TariffPricingCalculator initialization"""
    
    def test_initialization_g12w(self):
        """Test calculator initialization with G12w tariff"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        assert calc.tariff_type == 'g12w'
        assert calc.sc_component == 0.0892
        assert 'g12w' in calc.distribution_config
    
    def test_initialization_g14dynamic(self):
        """Test calculator initialization with G14dynamic tariff"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        assert calc.tariff_type == 'g14dynamic'
        assert calc.sc_component == 0.0892
        assert 'g14dynamic' in calc.distribution_config
    
    def test_initialization_defaults(self):
        """Test calculator with minimal configuration"""
        config = {'electricity_tariff': {}}
        calc = TariffPricingCalculator(config)
        
        # Should default to g12w
        assert calc.tariff_type == 'g12w'
        assert calc.sc_component == 0.0892


class TestG12wTimeBasedPricing:
    """Test G12w time-based pricing"""
    
    def test_peak_hours_pricing(self):
        """Test pricing during peak hours (06:00-22:00)"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5  # 0.5 PLN/kWh
        timestamp = datetime(2025, 10, 18, 14, 0)  # 14:00 - peak time
        
        components = calc.calculate_final_price(market_price, timestamp)
        
        assert components.market_price == 0.5
        assert components.sc_component == 0.0892
        assert components.distribution_price == 0.3566  # Peak
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.3566)
        assert components.tariff_type == 'g12w'
    
    def test_off_peak_hours_pricing(self):
        """Test pricing during off-peak hours (22:00-06:00)"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5  # 0.5 PLN/kWh
        timestamp = datetime(2025, 10, 18, 23, 0)  # 23:00 - off-peak time
        
        components = calc.calculate_final_price(market_price, timestamp)
        
        assert components.market_price == 0.5
        assert components.sc_component == 0.0892
        assert components.distribution_price == 0.0749  # Off-peak
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.0749)
        assert components.tariff_type == 'g12w'
    
    def test_early_morning_off_peak(self):
        """Test pricing in early morning (off-peak)"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.3
        timestamp = datetime(2025, 10, 18, 3, 0)  # 03:00 - off-peak
        
        components = calc.calculate_final_price(market_price, timestamp)
        
        assert components.distribution_price == 0.0749  # Off-peak
    
    def test_boundary_06_00_start_of_peak(self):
        """Test pricing at 06:00 (start of peak)"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        timestamp = datetime(2025, 10, 18, 6, 0)  # 06:00
        components = calc.calculate_final_price(0.5, timestamp)
        
        assert components.distribution_price == 0.3566  # Peak starts at 06:00
    
    def test_boundary_22_00_start_of_off_peak(self):
        """Test pricing at 22:00 (start of off-peak)"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        timestamp = datetime(2025, 10, 18, 22, 0)  # 22:00
        components = calc.calculate_final_price(0.5, timestamp)
        
        assert components.distribution_price == 0.0749  # Off-peak starts at 22:00


class TestG14dynamicKompasBased:
    """Test G14dynamic kompas-based pricing"""
    
    def test_normal_usage_pricing(self):
        """Test pricing for NORMAL USAGE kompas status"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, 'NORMAL USAGE')
        
        assert components.distribution_price == 0.0578
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.0578)
    
    def test_recommended_usage_pricing(self):
        """Test pricing for RECOMMENDED USAGE (cheapest)"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, 'RECOMMENDED USAGE')
        
        assert components.distribution_price == 0.0145
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.0145)
    
    def test_recommended_saving_pricing(self):
        """Test pricing for RECOMMENDED SAVING"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, 'RECOMMENDED SAVING')
        
        assert components.distribution_price == 0.4339
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.4339)
    
    def test_required_reduction_pricing(self):
        """Test pricing for REQUIRED REDUCTION (most expensive)"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, 'REQUIRED REDUCTION')
        
        assert components.distribution_price == 2.8931
        assert components.final_price == pytest.approx(0.5 + 0.0892 + 2.8931)
    
    def test_no_kompas_status_fallback(self):
        """Test fallback when no kompas status provided"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, None)
        
        # Should use fallback price (normal_usage)
        assert components.distribution_price == 0.0578
    
    def test_unknown_kompas_status_fallback(self):
        """Test fallback for unknown kompas status"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        timestamp = datetime(2025, 10, 18, 14, 0)
        
        components = calc.calculate_final_price(market_price, timestamp, 'UNKNOWN STATUS')
        
        # Should use fallback price
        assert components.distribution_price == 0.0578


class TestG11StaticPricing:
    """Test G11 static pricing"""
    
    def test_static_pricing_any_time(self):
        """Test that G11 has same price at any time"""
        config = create_test_config('g11')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.5
        
        # Test different times - should all have same distribution price
        times = [
            datetime(2025, 10, 18, 0, 0),   # Midnight
            datetime(2025, 10, 18, 6, 0),   # Morning
            datetime(2025, 10, 18, 12, 0),  # Noon
            datetime(2025, 10, 18, 18, 0),  # Evening
            datetime(2025, 10, 18, 23, 0),  # Night
        ]
        
        for timestamp in times:
            components = calc.calculate_final_price(market_price, timestamp)
            assert components.distribution_price == 0.3125
            assert components.final_price == pytest.approx(0.5 + 0.0892 + 0.3125)


class TestPriceComponents:
    """Test PriceComponents dataclass"""
    
    def test_price_breakdown(self):
        """Test that price components add up correctly"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        market_price = 0.4
        timestamp = datetime(2025, 10, 18, 10, 0)  # Peak time
        
        components = calc.calculate_final_price(market_price, timestamp)
        
        # Verify breakdown
        expected_final = components.market_price + components.sc_component + components.distribution_price
        assert components.final_price == pytest.approx(expected_final)
        assert components.timestamp == timestamp
        assert components.tariff_type == 'g12w'


class TestRealWorldScenarios:
    """Test real-world pricing scenarios"""
    
    def test_g12w_night_charging(self):
        """Test typical night charging scenario with G12w"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        # Market price at night (typically lower)
        market_price = 0.25  # 250 PLN/MWh -> 0.25 PLN/kWh
        timestamp = datetime(2025, 10, 18, 23, 30)  # 23:30 - off-peak
        
        components = calc.calculate_final_price(market_price, timestamp)
        
        # Expected: 0.25 (market) + 0.0892 (SC) + 0.0749 (off-peak) = 0.4141
        assert components.final_price == pytest.approx(0.4141)
    
    def test_g14dynamic_grid_overload(self):
        """Test G14dynamic during grid overload (REQUIRED REDUCTION)"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        # Market price during peak
        market_price = 0.70  # 700 PLN/MWh
        timestamp = datetime(2025, 10, 18, 18, 0)  # Evening peak
        
        components = calc.calculate_final_price(market_price, timestamp, 'REQUIRED REDUCTION')
        
        # Expected: 0.70 + 0.0892 + 2.8931 = 3.6823 PLN/kWh (very expensive!)
        assert components.final_price == pytest.approx(3.6823)
        assert components.final_price > 3.5  # Should discourage charging
    
    def test_g14dynamic_low_grid_load(self):
        """Test G14dynamic during low grid load (RECOMMENDED USAGE)"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        # Market price during low demand
        market_price = 0.30  # 300 PLN/MWh
        timestamp = datetime(2025, 10, 18, 3, 0)  # Night
        
        components = calc.calculate_final_price(market_price, timestamp, 'RECOMMENDED USAGE')
        
        # Expected: 0.30 + 0.0892 + 0.0145 = 0.4037 PLN/kWh (cheap!)
        assert components.final_price == pytest.approx(0.4037)
        assert components.final_price < 0.45  # Should encourage charging


class TestGetTariffInfo:
    """Test get_tariff_info method"""
    
    def test_get_tariff_info_g12w(self):
        """Test getting tariff info for G12w"""
        config = create_test_config('g12w')
        calc = TariffPricingCalculator(config)
        
        info = calc.get_tariff_info()
        
        assert info['tariff_type'] == 'g12w'
        assert info['sc_component'] == 0.0892
        assert info['distribution_type'] == 'time_based'
        assert 'config' in info
    
    def test_get_tariff_info_g14dynamic(self):
        """Test getting tariff info for G14dynamic"""
        config = create_test_config('g14dynamic')
        calc = TariffPricingCalculator(config)
        
        info = calc.get_tariff_info()
        
        assert info['tariff_type'] == 'g14dynamic'
        assert info['distribution_type'] == 'kompas_based'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

