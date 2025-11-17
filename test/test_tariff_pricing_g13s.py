#!/usr/bin/env python3
"""
Tests for G13s tariff pricing implementation.

Tests seasonal, day-type-aware, and time-based distribution pricing
for the Polish G13s electricity tariff.
"""

import sys
from pathlib import Path
from datetime import datetime, date

import pytest

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from tariff_pricing import TariffPricingCalculator
from utils.polish_holidays import is_free_day, is_polish_holiday, is_weekend


def create_g13s_config():
    """Create a test configuration for G13s tariff."""
    return {
        'electricity_tariff': {
            'tariff_type': 'g13s',
            'sc_component_pln_kwh': 0.0892,
            'distribution_pricing': {
                'g13s': {
                    'type': 'seasonal_time_based',
                    'requires_pse_forecast': True,
                    'seasons': {
                        'summer': {
                            'start_month': 4,
                            'start_day': 1,
                            'end_month': 9,
                            'end_day': 30,
                            'time_zones': {
                                'day_peak_morning': {'start': 7, 'end': 9},
                                'day_off_peak': {'start': 9, 'end': 17},
                                'day_peak_evening': {'start': 17, 'end': 21},
                                'night': {'start': 21, 'end': 7}
                            }
                        },
                        'winter': {
                            'start_month': 10,
                            'start_day': 1,
                            'end_month': 3,
                            'end_day': 31,
                            'time_zones': {
                                'day_peak_morning': {'start': 7, 'end': 10},
                                'day_off_peak': {'start': 10, 'end': 15},
                                'day_peak_evening': {'start': 15, 'end': 21},
                                'night': {'start': 21, 'end': 7}
                            }
                        }
                    },
                    'prices': {
                        'working_days': {
                            'summer': {
                                'day_peak': 0.290,
                                'day_off_peak': 0.100,
                                'night': 0.110
                            },
                            'winter': {
                                'day_peak': 0.340,
                                'day_off_peak': 0.200,
                                'night': 0.110
                            }
                        },
                        'free_days': {
                            'all_hours': 0.110
                        }
                    }
                }
            }
        }
    }


class TestPolishHolidayDetection:
    """Test Polish holiday detection functionality."""
    
    def test_fixed_holidays_2024(self):
        """Test detection of fixed Polish holidays in 2024."""
        fixed_holidays = [
            date(2024, 1, 1),   # New Year
            date(2024, 1, 6),   # Epiphany
            date(2024, 5, 1),   # Labour Day
            date(2024, 5, 3),   # Constitution Day
            date(2024, 8, 15),  # Assumption of Mary
            date(2024, 11, 1),  # All Saints
            date(2024, 11, 11), # Independence Day
            date(2024, 12, 25), # Christmas
            date(2024, 12, 26), # Second Day of Christmas
        ]
        
        for holiday in fixed_holidays:
            assert is_polish_holiday(holiday), f"Failed to detect {holiday} as holiday"
    
    def test_movable_holidays_2024(self):
        """Test detection of movable Polish holidays in 2024."""
        # Easter 2024: March 31
        easter_2024 = date(2024, 3, 31)
        easter_monday_2024 = date(2024, 4, 1)
        pentecost_2024 = date(2024, 5, 19)  # 49 days after Easter
        corpus_christi_2024 = date(2024, 5, 30)  # 60 days after Easter
        
        assert is_polish_holiday(easter_2024), "Failed to detect Easter 2024"
        assert is_polish_holiday(easter_monday_2024), "Failed to detect Easter Monday 2024"
        assert is_polish_holiday(pentecost_2024), "Failed to detect Pentecost 2024"
        assert is_polish_holiday(corpus_christi_2024), "Failed to detect Corpus Christi 2024"
    
    def test_movable_holidays_2025(self):
        """Test detection of movable Polish holidays in 2025."""
        # Easter 2025: April 20
        easter_2025 = date(2025, 4, 20)
        easter_monday_2025 = date(2025, 4, 21)
        pentecost_2025 = date(2025, 6, 8)  # 49 days after Easter
        corpus_christi_2025 = date(2025, 6, 19)  # 60 days after Easter
        
        assert is_polish_holiday(easter_2025), "Failed to detect Easter 2025"
        assert is_polish_holiday(easter_monday_2025), "Failed to detect Easter Monday 2025"
        assert is_polish_holiday(pentecost_2025), "Failed to detect Pentecost 2025"
        assert is_polish_holiday(corpus_christi_2025), "Failed to detect Corpus Christi 2025"
    
    def test_weekend_detection(self):
        """Test weekend detection."""
        # Saturday and Sunday
        saturday = date(2024, 6, 15)
        sunday = date(2024, 6, 16)
        monday = date(2024, 6, 17)
        
        assert is_weekend(saturday), "Failed to detect Saturday"
        assert is_weekend(sunday), "Failed to detect Sunday"
        assert not is_weekend(monday), "Incorrectly detected Monday as weekend"
    
    def test_free_day_detection(self):
        """Test free day detection (weekends + holidays)."""
        # Weekend
        saturday = date(2024, 6, 15)
        assert is_free_day(saturday), "Failed to detect Saturday as free day"
        
        # Holiday on weekday
        independence_day = date(2024, 11, 11)  # Monday in 2024
        assert is_free_day(independence_day), "Failed to detect holiday as free day"
        
        # Regular working day
        regular_day = date(2024, 6, 17)  # Monday
        assert not is_free_day(regular_day), "Incorrectly detected working day as free day"


class TestG13sSeasonDetection:
    """Test season detection for G13s tariff."""
    
    def test_summer_season(self):
        """Test summer season detection (April 1 - September 30)."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Start of summer
        assert calc._get_season(datetime(2024, 4, 1, 12, 0)) == 'summer'
        
        # Mid-summer
        assert calc._get_season(datetime(2024, 6, 15, 12, 0)) == 'summer'
        assert calc._get_season(datetime(2024, 7, 20, 12, 0)) == 'summer'
        
        # End of summer
        assert calc._get_season(datetime(2024, 9, 30, 12, 0)) == 'summer'
    
    def test_winter_season(self):
        """Test winter season detection (October 1 - March 31)."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Start of winter
        assert calc._get_season(datetime(2024, 10, 1, 12, 0)) == 'winter'
        
        # Mid-winter
        assert calc._get_season(datetime(2024, 12, 15, 12, 0)) == 'winter'
        assert calc._get_season(datetime(2025, 1, 20, 12, 0)) == 'winter'
        
        # End of winter
        assert calc._get_season(datetime(2025, 3, 31, 12, 0)) == 'winter'
    
    def test_season_boundaries(self):
        """Test exact season boundary dates."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Last day of winter / first day of summer
        assert calc._get_season(datetime(2024, 3, 31, 23, 59)) == 'winter'
        assert calc._get_season(datetime(2024, 4, 1, 0, 0)) == 'summer'
        
        # Last day of summer / first day of winter
        assert calc._get_season(datetime(2024, 9, 30, 23, 59)) == 'summer'
        assert calc._get_season(datetime(2024, 10, 1, 0, 0)) == 'winter'


class TestG13sTimeZoneDetection:
    """Test time zone detection for G13s tariff."""
    
    def test_summer_time_zones(self):
        """Test summer time zone detection."""
        calc = TariffPricingCalculator(create_g13s_config())
        time_zones = {}
        
        # Morning peak: 7-9h
        assert calc._get_g13s_time_zone(7, time_zones, 'summer') == 'day_peak'
        assert calc._get_g13s_time_zone(8, time_zones, 'summer') == 'day_peak'
        
        # Day off-peak: 9-17h
        assert calc._get_g13s_time_zone(9, time_zones, 'summer') == 'day_off_peak'
        assert calc._get_g13s_time_zone(12, time_zones, 'summer') == 'day_off_peak'
        assert calc._get_g13s_time_zone(16, time_zones, 'summer') == 'day_off_peak'
        
        # Evening peak: 17-21h
        assert calc._get_g13s_time_zone(17, time_zones, 'summer') == 'day_peak'
        assert calc._get_g13s_time_zone(18, time_zones, 'summer') == 'day_peak'
        assert calc._get_g13s_time_zone(20, time_zones, 'summer') == 'day_peak'
        
        # Night: 21-7h
        assert calc._get_g13s_time_zone(21, time_zones, 'summer') == 'night'
        assert calc._get_g13s_time_zone(0, time_zones, 'summer') == 'night'
        assert calc._get_g13s_time_zone(3, time_zones, 'summer') == 'night'
        assert calc._get_g13s_time_zone(6, time_zones, 'summer') == 'night'
    
    def test_winter_time_zones(self):
        """Test winter time zone detection."""
        calc = TariffPricingCalculator(create_g13s_config())
        time_zones = {}
        
        # Morning peak: 7-10h
        assert calc._get_g13s_time_zone(7, time_zones, 'winter') == 'day_peak'
        assert calc._get_g13s_time_zone(8, time_zones, 'winter') == 'day_peak'
        assert calc._get_g13s_time_zone(9, time_zones, 'winter') == 'day_peak'
        
        # Day off-peak: 10-15h
        assert calc._get_g13s_time_zone(10, time_zones, 'winter') == 'day_off_peak'
        assert calc._get_g13s_time_zone(12, time_zones, 'winter') == 'day_off_peak'
        assert calc._get_g13s_time_zone(14, time_zones, 'winter') == 'day_off_peak'
        
        # Evening peak: 15-21h
        assert calc._get_g13s_time_zone(15, time_zones, 'winter') == 'day_peak'
        assert calc._get_g13s_time_zone(18, time_zones, 'winter') == 'day_peak'
        assert calc._get_g13s_time_zone(20, time_zones, 'winter') == 'day_peak'
        
        # Night: 21-7h
        assert calc._get_g13s_time_zone(21, time_zones, 'winter') == 'night'
        assert calc._get_g13s_time_zone(0, time_zones, 'winter') == 'night'
        assert calc._get_g13s_time_zone(3, time_zones, 'winter') == 'night'
        assert calc._get_g13s_time_zone(6, time_zones, 'winter') == 'night'


class TestG13sDistributionPricing:
    """Test G13s distribution price calculation."""
    
    def test_summer_working_day_prices(self):
        """Test distribution prices for summer working days."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Summer Monday (working day)
        monday_summer = datetime(2024, 6, 17, 0, 0)  # Monday, June 17
        
        # Morning peak (7-9h): 0.290 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 17, 8, 0))
        assert components.distribution_price == 0.290
        
        # Day off-peak (9-17h): 0.100 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 17, 12, 0))
        assert components.distribution_price == 0.100
        
        # Evening peak (17-21h): 0.290 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 17, 19, 0))
        assert components.distribution_price == 0.290
        
        # Night (21-7h): 0.110 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 17, 23, 0))
        assert components.distribution_price == 0.110
    
    def test_winter_working_day_prices(self):
        """Test distribution prices for winter working days."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Winter Monday (working day)
        monday_winter = datetime(2024, 12, 16, 0, 0)  # Monday, December 16
        
        # Morning peak (7-10h): 0.340 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 12, 16, 9, 0))
        assert components.distribution_price == 0.340
        
        # Day off-peak (10-15h): 0.200 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 12, 16, 12, 0))
        assert components.distribution_price == 0.200
        
        # Evening peak (15-21h): 0.340 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 12, 16, 18, 0))
        assert components.distribution_price == 0.340
        
        # Night (21-7h): 0.110 PLN/kWh
        components = calc.calculate_final_price(0.30, datetime(2024, 12, 16, 23, 0))
        assert components.distribution_price == 0.110
    
    def test_weekend_flat_pricing(self):
        """Test that weekends use flat 0.110 PLN/kWh."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Saturday in summer
        saturday_summer = datetime(2024, 6, 15, 0, 0)
        
        # All hours should be 0.110
        for hour in range(24):
            components = calc.calculate_final_price(0.30, datetime(2024, 6, 15, hour, 0))
            assert components.distribution_price == 0.110, f"Hour {hour} should be 0.110 on weekend"
        
        # Sunday in winter
        sunday_winter = datetime(2024, 12, 15, 0, 0)
        
        # All hours should be 0.110
        for hour in range(24):
            components = calc.calculate_final_price(0.30, datetime(2024, 12, 15, hour, 0))
            assert components.distribution_price == 0.110, f"Hour {hour} should be 0.110 on weekend"
    
    def test_holiday_flat_pricing(self):
        """Test that holidays use flat 0.110 PLN/kWh."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # New Year 2024 (Wednesday - working day normally)
        new_year = datetime(2024, 1, 1, 0, 0)
        
        # All hours should be 0.110
        for hour in range(24):
            components = calc.calculate_final_price(0.30, datetime(2024, 1, 1, hour, 0))
            assert components.distribution_price == 0.110, f"Hour {hour} should be 0.110 on holiday"
        
        # Independence Day 2024 (Monday - working day normally)
        independence_day = datetime(2024, 11, 11, 0, 0)
        
        # All hours should be 0.110
        for hour in range(24):
            components = calc.calculate_final_price(0.30, datetime(2024, 11, 11, hour, 0))
            assert components.distribution_price == 0.110, f"Hour {hour} should be 0.110 on holiday"


class TestG13sFinalPriceCalculation:
    """Test complete final price calculation for G13s."""
    
    def test_final_price_components(self):
        """Test that final price correctly sums all components."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Market price: 0.30, SC: 0.0892, Distribution: varies
        market_price = 0.30
        sc_component = 0.0892
        
        # Summer working day morning peak: distribution = 0.290
        components = calc.calculate_final_price(market_price, datetime(2024, 6, 17, 8, 0))
        expected_final = market_price + sc_component + 0.290
        assert abs(components.final_price - expected_final) < 0.001
        assert components.market_price == market_price
        assert components.sc_component == sc_component
        assert components.distribution_price == 0.290
        assert components.tariff_type == 'g13s'
    
    def test_realistic_pricing_scenarios(self):
        """Test realistic pricing scenarios."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Scenario 1: Cheap night charging in summer
        # Market: 0.20, SC: 0.0892, Distribution (night): 0.110
        # Expected: 0.3992 PLN/kWh
        components = calc.calculate_final_price(0.20, datetime(2024, 7, 15, 2, 0))
        assert abs(components.final_price - 0.3992) < 0.001
        
        # Scenario 2: Expensive winter peak
        # Market: 0.60, SC: 0.0892, Distribution (winter peak): 0.340
        # Expected: 1.0292 PLN/kWh
        components = calc.calculate_final_price(0.60, datetime(2024, 12, 10, 18, 0))
        assert abs(components.final_price - 1.0292) < 0.001
        
        # Scenario 3: Weekend pricing (should be cheapest distribution)
        # Market: 0.40, SC: 0.0892, Distribution (free day): 0.110
        # Expected: 0.5992 PLN/kWh
        components = calc.calculate_final_price(0.40, datetime(2024, 6, 16, 12, 0))
        assert abs(components.final_price - 0.5992) < 0.001


class TestG13sEdgeCases:
    """Test edge cases for G13s tariff."""
    
    def test_midnight_crossing(self):
        """Test pricing around midnight."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Just before midnight (night zone)
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 17, 23, 59))
        assert components.distribution_price == 0.110
        
        # Just after midnight (still night zone)
        components = calc.calculate_final_price(0.30, datetime(2024, 6, 18, 0, 0))
        assert components.distribution_price == 0.110
    
    def test_season_boundary_transition(self):
        """Test pricing at season boundaries."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Use March 29, 2024 (Friday) for winter and April 2, 2024 (Tuesday) for summer
        # to avoid holidays (March 31 is Easter Sunday, April 1 is Easter Monday)
        
        # Last working day of winter (March 29, 23:00) - Night
        components_winter_night = calc.calculate_final_price(0.30, datetime(2024, 3, 29, 23, 0))
        assert components_winter_night.distribution_price == 0.110  # Night
        
        # First working day of summer (April 2, 0:00) - Night
        components_summer_night = calc.calculate_final_price(0.30, datetime(2024, 4, 2, 0, 0))
        assert components_summer_night.distribution_price == 0.110  # Night
        
        # But during day, prices should differ between seasons
        # Winter day peak (March 29, 18:00): 0.340
        components_winter_day = calc.calculate_final_price(0.30, datetime(2024, 3, 29, 18, 0))
        assert components_winter_day.distribution_price == 0.340
        
        # Summer day peak (April 2, 18:00): 0.290
        components_summer_day = calc.calculate_final_price(0.30, datetime(2024, 4, 2, 18, 0))
        assert components_summer_day.distribution_price == 0.290
    
    def test_holiday_on_weekend(self):
        """Test holiday that falls on weekend (should still be 0.110)."""
        calc = TariffPricingCalculator(create_g13s_config())
        
        # Christmas 2024 is Wednesday, but let's test Saturday Dec 21 (regular weekend)
        # and Dec 25 (holiday on Wednesday)
        
        # Regular weekend
        components_weekend = calc.calculate_final_price(0.30, datetime(2024, 12, 21, 12, 0))
        assert components_weekend.distribution_price == 0.110
        
        # Holiday on weekday
        components_holiday = calc.calculate_final_price(0.30, datetime(2024, 12, 25, 12, 0))
        assert components_holiday.distribution_price == 0.110


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

