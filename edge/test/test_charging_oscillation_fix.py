"""
E2E tests for charging oscillation fix.
Tests that is_charging=True properly delegates to hysteresis logic.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import sys

src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def hysteresis_config():
    """Configuration with hysteresis enabled (stop at 95%)"""
    return {
        'battery_management': {
            'capacity_kwh': 20,
            'soc_thresholds': {'critical': 12, 'emergency': 5},
            'charging_hysteresis': {
                'enabled': True,
                'normal_start_threshold': 85,
                'normal_stop_threshold': 95,
                'normal_target_soc': 95,
                'min_session_duration_minutes': 30,
                'min_discharge_depth_percent': 10,
                'max_sessions_per_day': 4,
            }
        },
        'timing_awareness': {'smart_critical_charging': {'enabled': True, 'adaptive_thresholds': {'enabled': False}}},
        'electricity_tariff': {'sc_component_pln_kwh': 0.0892},
        'data_storage': {
            'database_storage': {
                'enabled': True,
                'sqlite': {'path': ':memory:'}
            }
        }
    }


@pytest.fixture
def sample_price_data():
    return {'value': [{'dtime': '2025-12-06 00:00', 'csdac_pln': 400.0}]}


class TestChargingOscillationFix:
    """Core regression tests for the oscillation fix"""
    
    def test_is_charging_at_93_continues_to_95(self, hysteresis_config, sample_price_data):
        """
        CRITICAL: SOC=93% with is_charging=True should continue to 95%.
        This was the bug: hardcoded 90% check stopped charging at 93%.
        """
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.is_charging = True
        charger.charging_start_time = datetime.now() - timedelta(minutes=35)
        charger.active_charging_session = True
        charger.session_start_time = charger.charging_start_time
        charger.session_start_soc = 85
        
        decision = charger._make_charging_decision(
            battery_soc=93, overproduction=0, grid_power=1000,
            grid_direction='import', current_price=0.35,
            cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
        )
        
        assert decision['should_charge'] is True, "Should continue charging to 95%, not stop at 93%"
    
    def test_is_charging_at_95_stops(self, hysteresis_config, sample_price_data):
        """SOC=95% should stop charging"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.is_charging = True
        charger.charging_start_time = datetime.now() - timedelta(minutes=35)
        charger.active_charging_session = True
        charger.session_start_time = charger.charging_start_time
        charger.session_start_soc = 85
        
        decision = charger._make_charging_decision(
            battery_soc=95, overproduction=0, grid_power=1000,
            grid_direction='import', current_price=0.35,
            cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False, "Should stop at 95%"
    
    def test_syncs_session_state_without_incrementing_counter(self, hysteresis_config, sample_price_data):
        """Sync should NOT increment daily_session_count"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.is_charging = True
        charger.charging_start_time = datetime.now() - timedelta(minutes=10)
        charger.active_charging_session = None  # Out of sync
        charger.daily_session_count = 2
        
        charger._make_charging_decision(
            battery_soc=90, overproduction=0, grid_power=1000,
            grid_direction='import', current_price=0.35,
            cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
        )
        
        assert charger.active_charging_session is True, "Should sync session state"
        assert charger.daily_session_count == 2, "Should NOT increment counter on sync"
    
    def test_price_spike_pauses_charging(self, hysteresis_config, sample_price_data):
        """Price spike should pause even with hysteresis"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.is_charging = True
        charger.active_charging_session = True
        
        decision = charger._make_charging_decision(
            battery_soc=90, overproduction=0, grid_power=1000,
            grid_direction='import', current_price=2.00,  # Price spike!
            cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False, "Price spike should pause charging"
        assert 'spike' in decision['reason'].lower()
    
    def test_full_charge_cycle_no_oscillation(self, hysteresis_config, sample_price_data):
        """Simulate full charge from 85% to 95% - no early stop"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.is_charging = True
        charger.charging_start_time = datetime.now() - timedelta(minutes=35)
        charger.active_charging_session = True
        charger.session_start_soc = 85
        charger.session_start_time = charger.charging_start_time
        
        # Simulate SOC progression - all should continue until 95%
        for soc in [86, 88, 90, 91, 92, 93, 94]:
            decision = charger._make_charging_decision(
                battery_soc=soc, overproduction=0, grid_power=1000,
                grid_direction='import', current_price=0.35,
                cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
            )
            assert decision['should_charge'] is True, f"Should continue at {soc}%"
        
        # At 95% should stop
        decision = charger._make_charging_decision(
            battery_soc=95, overproduction=0, grid_power=1000,
            grid_direction='import', current_price=0.35,
            cheapest_price=0.30, cheapest_hour=2, price_data=sample_price_data
        )
        assert decision['should_charge'] is False, "Should stop at 95%"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
