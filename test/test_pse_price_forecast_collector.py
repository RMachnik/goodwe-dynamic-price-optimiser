import sys
from pathlib import Path
import pytest
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pse_price_forecast_collector import PSEPriceForecastCollector, PriceForecastPoint


def _collector():
    return PSEPriceForecastCollector({
        'pse_price_forecast': {
            'enabled': True,
            'decision_rules': {
                'wait_for_better_price_enabled': True,
                'min_savings_to_wait_percent': 15,
                'max_wait_time_hours': 4,
            }
        }
    })


def test_should_wait_guard_zero_price():
    c = _collector()
    now = datetime.now()
    c.forecast_cache = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]
    c.last_update_time = now

    res = c.should_wait_for_better_price(current_price=0.0, current_time=now)
    assert res['should_wait'] is False
    assert res['expected_savings_percent'] == 0.0


def test_should_wait_guard_negative_price():
    c = _collector()
    now = datetime.now()
    c.forecast_cache = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]
    c.last_update_time = now

    res = c.should_wait_for_better_price(current_price=-50.0, current_time=now)
    assert res['should_wait'] is False
    assert res['expected_savings_percent'] == 0.0


