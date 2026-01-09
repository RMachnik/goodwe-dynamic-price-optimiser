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
                'optimization_rules': {
                    'wait_at_10_percent_if_high_price': True,
                    'high_price_threshold_pln': 1.10
                }
            }
        },
        'data_storage': {
            'database_storage': {'enabled': False}
        },
        'charging_hysteresis': {
            'max_sessions_per_day': 6,
            'min_discharge_depth_percent': 10
        }
    }
    
    with patch('automated_price_charging.GoodWeFastCharger'):
        with patch('automated_price_charging.EnhancedDataCollector'):
            with patch('automated_price_charging.TariffPricingCalculator'):
                with patch('automated_price_charging.AdaptiveThresholdCalculator'):
                    charger = AutomatedPriceCharger(config)
                    # Force default tolerance and disable interfering logic
                    charger.opportunistic_tolerance_percent = 0.15
                    charger.opportunistic_pre_peak_enabled = False
                    charger.hysteresis_enabled = True # Ensure hysteresis active for session limits
                    charger.proactive_charging_enabled = False # Disable proactive logic
                    charger.is_charging = False
                    charger.active_charging_session = False
                    return charger

def test_t2_price_tolerance(charger):
    """Verify that price tolerance is increased to 25% in T2."""
    # Scenario: Current price is 20% above the cheapest next 12h
    # In T1 (15% tolerance) -> should WAIT
    # In T2 (25% tolerance) -> should CHARGE
    
    cheapest = 0.50
    current = 0.60 # exactly 20% above
    
    with patch.object(charger, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = cheapest
        
        # 1. T1 case
        decision_t1 = charger._make_charging_decision(
            battery_soc=30,
            overproduction=0,
            grid_power=0,
            grid_direction='import',
            current_price=current,
            cheapest_price=cheapest,
            cheapest_hour=5,
            price_data={'value': []},
            tariff_zone='T1'
        )
        assert decision_t1['should_charge'] == False, f"T1 should WAIT for 0.60 vs 0.50 (reason: {decision_t1['reason']})"

        # 2. T2 case
        decision_t2 = charger._make_charging_decision(
            battery_soc=30,
            overproduction=0,
            grid_power=0,
            grid_direction='import',
            current_price=current,
            cheapest_price=cheapest,
            cheapest_hour=5,
            price_data={'value': []},
            tariff_zone='T2'
        )
        assert decision_t2['should_charge'] == True, f"T2 should CHARGE for 0.60 vs 0.50 (reason: {decision_t2['reason']})"

def test_t2_deadline_fallback(charger):
    """Verify that charging starts when the T2 window is about to end."""
    # Mock datetime to 5:30 AM (T2 ends at 6:00 AM)
    # Remaining time = 0.5 hours
    # SOC = 30%. Capacity = 20kWh. Target = 85%.
    # Energy needed = 20 * (85-30)/100 = 11 kWh
    # At 3kW charge rate, we need ~3.6 hours.
    # 0.5 hours remaining <= 3.6 hours needed -> should TRIGGER fallback.
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        # Mock 5:30 AM
        mock_now = datetime(2026, 1, 7, 5, 30)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.combine = datetime.combine
        mock_datetime.min = datetime.min
        mock_datetime.max = datetime.max
        
        with patch.object(charger, '_find_cheapest_price_next_hours') as mock_find:
            mock_find.return_value = 0.50 # cheapest
            
            decision = charger._make_charging_decision(
                battery_soc=30,
                overproduction=0,
                grid_power=0,
                grid_direction='import',
                current_price=1.50, # very expensive
                cheapest_price=0.50,
                cheapest_hour=2,
                price_data={'value': []},
                tariff_zone='T2'
            )
            
            assert decision['should_charge'] == True, f"Deadline fallback should trigger (reason: {decision['reason']})"
            assert "T2 window ending soon" in decision['reason']

def test_session_limit_increase(charger):
    """Verify that the daily session limit is now 6."""
    assert charger.max_sessions_per_day == 6
    
    # Mock being at session 5 and starting session 6
    charger.daily_session_count = 5
    charger.active_charging_session = False
    charger.session_start_time = None
    
    with patch.object(charger, '_find_cheapest_price_next_hours') as mock_find:
        mock_find.return_value = 0.40
        with patch.object(charger, '_is_price_cheap_for_normal_tier') as mock_cheap:
            mock_cheap.return_value = True
            
            # Should still be able to start session 6
            decision = charger._make_charging_decision(
                battery_soc=60, # Use NORMAL tier SOC
                overproduction=0,
                grid_power=0,
                grid_direction='import',
                current_price=0.50,
                cheapest_price=0.40,
                cheapest_hour=5,
                price_data={'value': []},
                tariff_zone='T2'
            )
            assert decision['should_charge'] == True, f"Should allow session 6 (reason: {decision['reason']})"
            assert "session #6" in decision['reason'].lower()
            
            # Now at 6 sessions
            charger.daily_session_count = 6
            charger.active_charging_session = False # RESET for test
            charger.session_start_time = None       # RESET for test
            
            decision_max = charger._make_charging_decision(
                battery_soc=60,
                overproduction=0,
                grid_power=0,
                grid_direction='import',
                current_price=0.50,
                cheapest_price=0.40,
                cheapest_hour=5,
                price_data={'value': []},
                tariff_zone='T2'
            )
            assert decision_max['should_charge'] == False, f"Should BLOCK session 7 (reason: {decision_max['reason']})"
            assert "Max sessions" in decision_max['reason']
