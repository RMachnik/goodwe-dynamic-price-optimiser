import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from price_window_analyzer import PriceWindowAnalyzer
from pse_price_forecast_collector import PriceForecastPoint


def _analyzer():
    return PriceWindowAnalyzer({
        'pse_price_forecast': {
            'decision_rules': {
                'wait_for_better_price_enabled': True,
                'min_savings_to_wait_percent': 15,
                'max_wait_time_hours': 4,
            }
        }
    })


def test_should_wait_for_better_price_zero_guard():
    analyzer = _analyzer()
    now = datetime.now()
    forecast = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]

    res = analyzer._should_wait_for_better_price(current_price=0.0, forecast_data=forecast)
    assert isinstance(res, dict)
    assert res['should_wait'] is False
    assert res['expected_savings_percent'] == 0.0


def test_should_wait_for_better_price_bool_guard():
    analyzer = _analyzer()
    now = datetime.now()
    forecast = [
        PriceForecastPoint(time=now + timedelta(hours=1), forecasted_price_pln=100.0)
    ]

    # Boolean-returning wrapper should not raise and should be False
    should_wait = analyzer.should_wait_for_better_price(current_price=0.0, forecast_data=forecast)
    assert should_wait is False


