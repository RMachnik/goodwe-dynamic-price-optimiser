import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.automated_price_charging import AutomatedPriceCharger

@pytest.fixture
def charger():
    """Fixture to create an AutomatedPriceCharger instance with standard config"""
    charger = AutomatedPriceCharger("config/master_coordinator_config.yaml")
    # Mock necessary components
    charger.data_collector = MagicMock()
    charger.goodwe_charger = MagicMock()
    charger.master_coordinator = MagicMock()
    
    # Enable smart critical charging
    charger.smart_critical_enabled = True
    charger.max_critical_price = 1.20
    charger.high_price_threshold = 1.10
    charger.wait_at_10_percent_if_high_price = True
    charger.emergency_battery_threshold = 5.0
    charger.critical_battery_threshold = 30.0
    
    return charger

def test_critical_lookahead_delays_charging(charger):
    """
    Test that critical charging is delayed if a significant price drop is imminent.
    Scenario:
    - Current SOC: 10% (Critical)
    - Current Price: 1.10 PLN (Acceptable for critical)
    - Price in 1 hour: 0.66 PLN (Significant drop > 30%)
    - Result: Should WAIT
    """
    # Prepare price data
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_data = {
        'value': [
            {
                'dtime': now.isoformat() + 'Z',
                'csdac_pln': 1100.0, # 1.10 PLN/kWh (MWh unit)
            },
            {
                'dtime': (now + timedelta(hours=1)).isoformat() + 'Z',
                'csdac_pln': 660.0, # 0.66 PLN/kWh
            }
        ]
    }
    
    # Mock calculate_final_price to return the price as provided (simplification for test)
    charger.calculate_final_price = MagicMock(side_effect=lambda price, dt: price)
    
    battery_soc = 10
    current_price = 1.077
    cheapest_price = 0.66
    cheapest_hour = (now + timedelta(hours=1)).hour
    
    # Update price data to match current_price
    price_data['value'][0]['csdac_pln'] = 1077.0
    
    decision = charger._smart_critical_charging_decision(
        battery_soc, current_price, cheapest_price, cheapest_hour, price_data
    )
    
    assert decision['should_charge'] is False
    assert "significant price drop coming" in decision['reason']
    assert "1.077 -> 0.660" in decision['reason']

def test_critical_lookahead_charges_if_no_ignificant_drop(charger):
    """
    Test that critical charging proceeds if no significant drop is coming.
    Scenario:
    - Current SOC: 10%
    - Current Price: 0.80 PLN
    - Price in 1 hour: 0.75 PLN (Drop < 30%)
    - Result: Should CHARGE
    """
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_data = {
        'value': [
            {
                'dtime': now.isoformat() + 'Z',
                'csdac_pln': 800.0,
            },
            {
                'dtime': (now + timedelta(hours=1)).isoformat() + 'Z',
                'csdac_pln': 750.0,
            }
        ]
    }
    
    charger.calculate_final_price = MagicMock(side_effect=lambda price, dt: price)
    
    battery_soc = 10
    current_price = 0.80
    cheapest_price = 0.75
    cheapest_hour = (now + timedelta(hours=1)).hour
    
    decision = charger._smart_critical_charging_decision(
        battery_soc, current_price, cheapest_price, cheapest_hour, price_data
    )
    
    assert decision['should_charge'] is True
    assert "acceptable price" in decision['reason']

def test_critical_lookahead_charges_at_emergency_soc(charger):
    """
    Test that lookahead is ignored if SOC is below 10% (approaching emergency).
    Scenario:
    - Current SOC: 8%
    - Current Price: 1.10 PLN
    - Price in 1 hour: 0.40 PLN (Huge drop)
    - Result: Should CHARGE (Safety first below 10%)
    """
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    price_data = {
        'value': [
            {
                'dtime': now.isoformat() + 'Z',
                'csdac_pln': 1100.0,
            },
            {
                'dtime': (now + timedelta(hours=1)).isoformat() + 'Z',
                'csdac_pln': 400.0,
            }
        ]
    }
    
    charger.calculate_final_price = MagicMock(side_effect=lambda price, dt: price)
    
    battery_soc = 8
    current_price = 1.10
    cheapest_price = 0.40
    cheapest_hour = (now + timedelta(hours=1)).hour
    
    decision = charger._smart_critical_charging_decision(
        battery_soc, current_price, cheapest_price, cheapest_hour, price_data
    )
    
    assert decision['should_charge'] is True
    assert "acceptable price" in decision['reason']

def test_inclusive_high_price_rule_at_10_percent(charger):
    """
    Test that Rule 1 (wait at 10%) is inclusive of the threshold.
    Scenario:
    - SOC: 10%
    - Price: 1.10 PLN (Equal to high_price_threshold)
    - Result: Should WAIT
    """
    charger.high_price_threshold = 1.10
    battery_soc = 10
    current_price = 1.10
    
    # Rule 1 should trigger
    decision = charger._smart_critical_charging_decision(
        battery_soc, current_price, 0.5, 3
    )
    
    assert decision['should_charge'] is False
    assert "price too high" in decision['reason']
    assert "1.100 > 1.100" or "threshold" in decision['reason']
