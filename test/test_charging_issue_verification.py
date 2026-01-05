import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger

@pytest.fixture
def charger():
    """Create AutomatedPriceCharger with mocked dependencies."""
    config = {
        'battery_management': {
            'soc_thresholds': {
                'emergency': 5,
                'critical': 12
            },
            'capacity_kwh': 20.0
        },
        'timing_awareness': {
            'smart_critical_charging': {
                'enabled': True,
                'max_wait_hours': 8,
                'min_price_savings_percent': 30,
                'adaptive_thresholds': {
                    'enabled': False
                },
                'optimization_rules': {
                    'wait_at_10_percent_if_high_price': True,
                    'high_price_threshold_pln': 1.10
                }
            }
        },
        'data_storage': {
            'database_storage': {'enabled': False}
        }
    }
    
    with patch('automated_price_charging.GoodWeFastCharger'):
        with patch('automated_price_charging.EnhancedDataCollector'):
            with patch('automated_price_charging.TariffPricingCalculator'):
                with patch('automated_price_charging.AdaptiveThresholdCalculator'):
                    charger = AutomatedPriceCharger(config)
                    # Force thresholds since we mocked the calculator
                    charger.high_price_threshold = 1.10
                    charger.max_critical_price = 0.35
                    return charger

def test_reported_issue_scenario(charger):
    """
    Verify the reported issue scenario: 
    10% SOC, 1.29 PLN price, 0.51 PLN available 7 hours later.
    Should now WAIT instead of CHARGE.
    """
    # 1. Test mandatory wait rule (Rule 1: 10% SOC + price > 1.10)
    decision = charger._make_charging_decision(
        battery_soc=10,
        overproduction=0,
        grid_power=0,
        grid_direction='import',
        current_price=1.29,
        cheapest_price=0.51,
        cheapest_hour=(datetime.now().hour + 7) % 24
    )
    
    assert decision['should_charge'] == False
    assert "waiting for drop" in decision['reason']
    assert "10%" in decision['reason']

    # 2. Test dynamic wait time calculation (for 10% SOC, 60% savings)
    # Savings = (1.29 - 0.51) / 1.29 = 60.4%
    # With new logic: 
    # savings_multiplier = 1.6 (for >= 60%)
    # battery_multiplier = 1.0 (for 10% SOC and >= 50% savings)
    # base_wait = 8
    # dynamic_max_wait = 8 * 1.6 * 1.0 = 12.8 -> capped at 12
    # 7 hours < 12 hours -> should WAIT even without Rule 1
    
    # Let's test with SOC 11% (Rule 1 doesn't apply to 11%)
    decision_11 = charger._make_charging_decision(
        battery_soc=11,
        overproduction=0,
        grid_power=0,
        grid_direction='import',
        current_price=1.29,
        cheapest_price=0.51,
        cheapest_hour=(datetime.now().hour + 7) % 24
    )
    
    assert decision_11['should_charge'] == False
    assert "cheaper price" in decision_11['reason'].lower()

def test_price_spike_during_active_charging(charger):
    """
    Verify that if charging is already in progress, it stops if price spikes.
    """
    charger.is_charging = True
    charger.charging_start_time = datetime.now() - timedelta(minutes=20) # skip flip-flop
    
    decision = charger._make_charging_decision(
        battery_soc=10,
        overproduction=0,
        grid_power=0,
        grid_direction='import',
        current_price=1.38, # Price spiked
        cheapest_price=0.51,
        cheapest_hour=(datetime.now().hour + 5) % 24
    )
    
    assert decision['should_charge'] == False
    assert "spiked" in decision['reason'].lower()
    assert "pausing" in decision['reason'].lower()
