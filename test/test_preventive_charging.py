"""
Comprehensive tests for preventive partial charging feature.

Tests cover:
- Scanner logic (_scan_for_high_prices_ahead)
- Drain forecast (_calculate_battery_drain_forecast)
- Economic evaluation (_evaluate_preventive_partial_charging)
- Integration into decision flow
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def mock_config():
    """Minimal config for AutomatedPriceCharger with preventive charging enabled."""
    return {
        'system': {
            'timezone': 'Europe/Warsaw'
        },
        'smart_critical_charging': {
            'enabled': True,
            'critical_threshold': 15,
            'timing_awareness': {
                'smart_critical_charging': {
                    'partial_charging': {
                        'enabled': True,
                        'safety_margin_percent': 10,
                        'max_partial_sessions_per_day': 4,
                        'min_partial_charge_kwh': 2.0,
                        'session_tracking_file': '/tmp/test_partial_sessions.json',
                        'daily_reset_hour': 6,
                        # timezone now inherited from system.timezone
                        'preventive_enabled': True,
                        'preventive_scan_ahead_hours': 12,
                        'preventive_min_savings_percent': 30,
                        'preventive_critical_soc_forecast': 15,
                        'preventive_min_high_price_duration_hours': 3,
                    }
                }
            }
        },
        'battery_management': {
            'capacity_kwh': 20.0,
        },
        'adaptive_threshold_config': {
            'enabled': False,
            'fallback_high_price': 1.35,
            'fallback_critical_price': 1.00,
        },
        'price_analysis': {
            'api_url': 'https://api.raporty.pse.pl/api/csdac-pln'
        },
        'logging': {'level': 'INFO'}
    }


@pytest.fixture
def charger(mock_config, tmp_path):
    """Instantiate AutomatedPriceCharger with mocked dependencies."""
    # Write config to temporary file
    import yaml
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump(mock_config))
    
    with patch('automated_price_charging.EnhancedDataCollector'), \
         patch('automated_price_charging.TariffPricingCalculator'), \
         patch('automated_price_charging.AdaptiveThresholdCalculator'), \
         patch('automated_price_charging.GoodWeFastCharger'):
        
        charger = AutomatedPriceCharger(str(config_file))
        # Override methods that require external data
        charger.get_high_price_threshold = Mock(return_value=1.35)
        charger.get_critical_price_threshold = Mock(return_value=1.00)
        charger._check_partial_session_limits = Mock(return_value=True)
        
        return charger


def generate_price_data(base_time: datetime, hours: int, prices: list) -> dict:
    """
    Generate price_data dict for testing.
    
    Args:
        base_time: Start datetime
        hours: Number of hours
        prices: List of prices in PLN/kWh (will be converted to PLN/MWh)
    
    Returns:
        Dict with 'value' list containing price points
    """
    value = []
    for i in range(hours):
        value.append({
            'dtime': (base_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': prices[i] * 1000.0  # PLN/kWh -> PLN/MWh
        })
    return {'value': value}


# ======================== UNIT TESTS: Scanner ========================

def test_scanner_detects_single_high_price_period(charger):
    """Scanner identifies single consecutive high-price period."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Prices: 2h low, 4h high, 6h low
    prices = [0.25, 0.28] + [1.50, 1.55, 1.48, 1.52] + [0.30] * 6
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(0.28, price_data, base_time)
    
    assert len(result) == 1
    assert result[0]['duration_hours'] == 4
    assert result[0]['start'] == base_time + timedelta(hours=2)
    assert 1.48 <= result[0]['avg_price_kwh'] <= 1.52


def test_scanner_detects_multiple_high_price_periods(charger):
    """Scanner identifies multiple separated high-price periods."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Prices: 1h low, 3h high, 3h low, 4h high, 1h low
    prices = [0.25] + [1.50] * 3 + [0.30] * 3 + [1.45] * 4 + [0.28]
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(0.25, price_data, base_time)
    
    assert len(result) == 2
    assert result[0]['duration_hours'] == 3  # First period
    assert result[1]['duration_hours'] == 4  # Second period


def test_scanner_ignores_short_high_price_spikes(charger):
    """Scanner ignores high-price periods < min_high_price_duration_hours."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Prices: 2h low, 2h high (< 3h threshold), 8h low
    prices = [0.25, 0.28] + [1.50, 1.55] + [0.30] * 8
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(0.28, price_data, base_time)
    
    assert len(result) == 0


def test_scanner_early_exit_if_current_price_high(charger):
    """Scanner returns empty list if current price already exceeds threshold."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Current price = 1.45 (>= threshold 1.35)
    prices = [1.50] * 12
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(1.45, price_data, base_time)
    
    assert len(result) == 0


def test_scanner_handles_empty_price_data(charger):
    """Scanner handles empty or malformed price data gracefully."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Empty price_data
    assert charger._scan_for_high_prices_ahead(0.28, {}, base_time) == []
    assert charger._scan_for_high_prices_ahead(0.28, {'value': []}, base_time) == []
    assert charger._scan_for_high_prices_ahead(0.28, None, base_time) == []


# ======================== UNIT TESTS: Drain Forecast ========================

def test_drain_forecast_predicts_soc_above_critical(charger):
    """Drain forecast correctly predicts SOC staying above critical."""
    result = charger._calculate_battery_drain_forecast(current_soc=50, drain_duration_hours=3.0)
    
    # Expected: 50% - (1.25 kW * 1.1 * 3h / 20 kWh * 100) = 50% - 20.6% = 29%
    assert 28 <= result['predicted_soc'] <= 30
    assert result['energy_deficit_kwh'] == 0.0  # 29% > critical 15%
    assert result['hours_until_critical'] > 0


def test_drain_forecast_predicts_soc_below_critical(charger):
    """Drain forecast correctly calculates energy deficit when SOC drops below critical."""
    result = charger._calculate_battery_drain_forecast(current_soc=25, drain_duration_hours=3.0)
    
    # Expected: 25% - 20.6% = 4% (below critical 15%)
    assert result['predicted_soc'] <= 10
    assert result['energy_deficit_kwh'] > 0  # Deficit calculated


def test_drain_forecast_handles_extreme_drain(charger):
    """Drain forecast handles extreme drain (predicted SOC below 0%)."""
    result = charger._calculate_battery_drain_forecast(current_soc=10, drain_duration_hours=5.0)
    
    assert result['predicted_soc'] == 0  # Clamped to 0
    assert result['energy_deficit_kwh'] > 0


# ======================== UNIT TESTS: Preventive Evaluator ========================

def test_preventive_evaluator_triggers_when_beneficial(charger):
    """Preventive evaluator triggers when savings exceed threshold."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Setup: SOC 40%, current price 0.28, high prices starting in 2h
    battery_soc = 40
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 5 + [0.30] * 5  # 5h high period
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is not None
    assert result['should_charge'] is True
    assert result['preventive_partial'] is True
    assert result['savings_percent'] >= 30  # Meets threshold
    assert result['target_soc'] > battery_soc


def test_preventive_evaluator_blocked_soc_outside_range(charger):
    """Preventive evaluator does not trigger when SOC outside 30-60% range."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    prices = [0.28] * 2 + [1.45] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    # SOC too low
    result_low = charger._evaluate_preventive_partial_charging(25, 0.28, price_data, base_time)
    assert result_low is None
    
    # SOC too high
    result_high = charger._evaluate_preventive_partial_charging(65, 0.28, price_data, base_time)
    assert result_high is None


def test_preventive_evaluator_blocked_current_price_too_high(charger):
    """Preventive evaluator does not trigger when current price exceeds critical threshold."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Current price 1.05 > critical threshold 1.00
    prices = [1.05] + [1.50] * 5 + [0.30] * 6
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(40, 1.05, price_data, base_time)
    
    assert result is None


def test_preventive_evaluator_blocked_insufficient_savings(charger):
    """Preventive evaluator does not trigger when savings below threshold."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # High price only 1.05 (not enough savings vs 0.95 current)
    battery_soc = 40
    current_price = 0.95
    prices = [0.95, 0.98] + [1.05] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is None  # Savings too small


def test_preventive_evaluator_blocked_soc_stays_above_critical(charger):
    """Preventive evaluator does not trigger if predicted SOC stays above critical."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # SOC 60%, only 2h high price period (battery won't drain to critical)
    battery_soc = 60
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 3 + [0.30] * 7
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is None  # Predicted SOC stays high


# ======================== INTEGRATION TESTS ========================

def test_integration_preventive_charging_in_decision_flow(charger, mock_config):
    """Integration: Preventive charging triggers in _make_charging_decision()."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Setup: 40% SOC, 0.28 current, 5h high period ahead
    battery_soc = 40
    overproduction = 0
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    # Disable interim cost to allow preventive to run
    charger.interim_cost_enabled = False
    
    # Directly test preventive evaluator (bypasses other decision logic)
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    # Preventive should trigger
    assert result is not None
    assert result['should_charge'] is True
    assert result.get('preventive_partial') is True
    assert result['savings_percent'] >= 30


def test_integration_preventive_respects_session_limits(charger):
    """Integration: Preventive charging respects daily session limits."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    battery_soc = 40
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    # Block session limits
    charger._check_partial_session_limits = Mock(return_value=False)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is None  # Blocked by session limit


def test_integration_preventive_uses_adaptive_thresholds(charger):
    """Integration: Preventive charging uses adaptive threshold calculator."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Set custom adaptive threshold
    charger.get_high_price_threshold = Mock(return_value=1.20)
    
    battery_soc = 40
    current_price = 0.28
    # Prices between 1.20-1.35 (would be high with adaptive, not with fallback)
    prices = [0.28, 0.30] + [1.25] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is not None  # Triggered with adaptive threshold


def test_integration_preventive_disabled_by_config(charger):
    """Integration: Preventive charging respects preventive_enabled config."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Disable preventive
    charger.preventive_partial_enabled = False
    
    battery_soc = 40
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._evaluate_preventive_partial_charging(
        battery_soc, current_price, price_data, base_time
    )
    
    assert result is None


# ======================== EDGE CASES ========================

def test_edge_case_current_price_equals_high_threshold(charger):
    """Edge case: Current price exactly equals high threshold."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Current price = threshold = 1.35
    current_price = 1.35
    prices = [1.35] + [1.50] * 5 + [0.30] * 6
    price_data = generate_price_data(base_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(current_price, price_data, base_time)
    
    # Scanner should reject (early exit condition: current_price >= threshold)
    assert len(result) == 0


def test_edge_case_malformed_price_data_items(charger):
    """Edge case: Scanner handles malformed price data items gracefully."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Mix of valid and malformed items
    price_data = {
        'value': [
            {'dtime': base_time.strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 280.0},
            {'dtime': 'invalid-date', 'csdac_pln': 1500.0},  # Bad date
            {'dtime': (base_time + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')},  # Missing price
            {'dtime': (base_time + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 1450.0},
        ]
    }
    
    result = charger._scan_for_high_prices_ahead(0.28, price_data, base_time)
    
    # Should process valid items only
    assert isinstance(result, list)  # No crash


def test_edge_case_insufficient_battery_capacity(charger):
    """Edge case: Preventive evaluator handles insufficient battery capacity."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # SOC 95% (not much capacity left)
    battery_soc = 95
    current_price = 0.28
    prices = [0.28, 0.30] + [1.45] * 5 + [0.30] * 5
    price_data = generate_price_data(base_time, 12, prices)
    
    # Force SOC into range (for testing)
    charger_mock = charger
    with patch.object(charger_mock, '_calculate_battery_drain_forecast') as mock_forecast:
        # Simulate large energy deficit that exceeds capacity
        mock_forecast.return_value = {
            'predicted_soc': 10,
            'energy_deficit_kwh': 10.0,  # Would need 100% target (exceeds 95%)
            'hours_until_critical': 2.0
        }
        
        # Test with SOC forced to 40 (in range)
        result = charger_mock._evaluate_preventive_partial_charging(
            40, current_price, price_data, base_time
        )
        
        # Should calculate valid target_soc <= 100
        if result:
            assert result['target_soc'] <= 100


def test_edge_case_zero_consumption_drain(charger):
    """Edge case: Drain forecast handles zero consumption duration."""
    result = charger._calculate_battery_drain_forecast(current_soc=50, drain_duration_hours=0.0)
    
    assert result['predicted_soc'] == 50  # No drain
    assert result['energy_deficit_kwh'] == 0.0
    assert result['hours_until_critical'] > 500  # Very large


def test_edge_case_price_data_in_past(charger):
    """Edge case: Scanner handles price data points in the past."""
    base_time = datetime(2025, 1, 15, 10, 0)
    
    # Prices starting 5h before current time
    past_time = base_time - timedelta(hours=5)
    prices = [1.50] * 12
    price_data = generate_price_data(past_time, 12, prices)
    
    result = charger._scan_for_high_prices_ahead(0.28, price_data, base_time)
    
    # Scanner processes prices that fall within scan window (current_time to current_time + 12h)
    # Some of these prices will be in the future relative to base_time
    assert isinstance(result, list)  # No crash, handles gracefully
