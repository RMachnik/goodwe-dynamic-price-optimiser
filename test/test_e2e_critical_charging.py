import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from src.automated_price_charging import AutomatedPriceCharger

@pytest.fixture
def base_config():
    return {
        'automated_price_charging': {
            'enabled': True,
            'emergency_battery_threshold': 5,
            'critical_battery_threshold': 30, # Match user config
        },
        'timing_awareness': {
            'smart_critical_charging': {
                'enabled': True,
                'max_critical_price_pln': 1.20,
                'max_wait_hours': 8,
                'min_price_savings_percent': 30,
                'optimization_rules': {
                    'wait_at_10_percent_if_high_price': True,
                    'high_price_threshold_pln': 1.10
                }
            }
        }
    }

@pytest.fixture
def charger(base_config):
    with patch('src.automated_price_charging.GoodWeFastCharger'):
        with patch('src.automated_price_charging.EnhancedDataCollector'):
            with patch('src.automated_price_charging.TariffPricingCalculator'):
                charger = AutomatedPriceCharger(base_config)
                charger.is_charging = False
                charger.calculate_final_price = MagicMock(side_effect=lambda price, dt: price)
                return charger

def test_e2e_critical_price_drop_transition(charger):
    """
    E2E scenario:
    - 21:00: SOC 10%, Price 1.077 PLN. Next hour 22:00 price is 0.66 PLN.
      Result: Should WAIT despite critical battery.
    - 22:00: SOC 10%, Price 0.66 PLN.
      Result: Should CHARGE.
    """
    
    # Base time: 21:00 UTC
    t21 = datetime(2026, 1, 7, 21, 0, 0, tzinfo=timezone.utc)
    # 22:00 UTC
    t22 = datetime(2026, 1, 7, 22, 0, 0, tzinfo=timezone.utc)
    
    # Prepare price data for both steps
    price_data = {
        'value': [
            {'dtime': t21.strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 1077.0},
            {'dtime': t22.strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 660.0},
            {'dtime': (t22 + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 660.0}
        ]
    }
    
    common_data = {
        'battery': {'soc_percent': 10},
        'photovoltaic': {'current_power_kw': 0},
        'house_consumption': {'calculated_power_kw': 0.5},
        'grid_import_total_kwh': 1000,
        'tariff_zone': 'T1'
    }

    # STEP 1: 21:00
    with patch('src.automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = t21
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        
        decision = charger.make_smart_charging_decision(common_data, price_data)
        
        assert decision['should_charge'] is False
        assert "significant price drop coming" in decision['reason']
        assert "1.077 -> 0.660" in decision['reason']

    # STEP 2: 22:00
    with patch('src.automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = t22
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        
        decision = charger.make_smart_charging_decision(common_data, price_data)
        
        assert decision['should_charge'] is True
        # Accept either critical tier or proactive charging (both are valid at 22:00 with 0.66 PLN)
        assert any(word in decision['reason'] for word in ["charging", "Critical", "acceptable price"])
        assert "0.660" in decision['reason'] or "good price" in decision['reason']

def test_e2e_rule1_inclusive_wait(charger):
    """
    E2E scenario:
    - 21:00: SOC 10%, Price 1.100 PLN (exactly high_price_threshold).
      Result: Should WAIT due to Rule 1.
    """
    t21 = datetime(2026, 1, 7, 21, 0, 0, tzinfo=timezone.utc)
    
    price_data = {
        'value': [
            {'dtime': t21.strftime('%Y-%m-%d %H:%M'), 'csdac_pln': 1100.0}
        ]
    }
    
    common_data = {
        'battery': {'soc_percent': 10},
        'photovoltaic': {'current_power_kw': 0},
        'house_consumption': {'calculated_power_kw': 0.5},
        'grid_import_total_kwh': 1000,
        'tariff_zone': 'T1'
    }

    with patch('src.automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = t21
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        
        decision = charger.make_smart_charging_decision(common_data, price_data)
        
        assert decision['should_charge'] is False
        assert "price too high" in decision['reason']
