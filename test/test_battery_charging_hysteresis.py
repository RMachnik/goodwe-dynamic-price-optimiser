"""
Tests for battery charging hysteresis logic.

Tests the hysteresis-based charging control system that reduces
charging sessions from 8-10 to 1-2 per night for battery longevity.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def hysteresis_config():
    """Configuration with hysteresis enabled"""
    return {
        'battery_management': {
            'capacity_kwh': 20,
            'soc_thresholds': {
                'critical': 12,
                'emergency': 5
            },
            'charging_hysteresis': {
                'enabled': True,
                'normal_start_threshold': 85,
                'normal_stop_threshold': 95,
                'normal_target_soc': 95,
                'opportunistic_start_threshold': 70,
                'opportunistic_stop_threshold': 85,
                'min_session_duration_minutes': 30,
                'min_discharge_depth_percent': 10,
                'max_sessions_per_day': 4,
                'override_on_emergency': True,
                'override_on_critical': True
            }
        },
        'timing_awareness': {
            'smart_critical_charging': {
                'enabled': True,
                'adaptive_thresholds': {
                    'enabled': False
                }
            }
        },
        'electricity_tariff': {
            'sc_component_pln_kwh': 0.0892
        },
        'data_storage': {
            'database_storage': {
                'enabled': True,
                'sqlite': {
                    'path': ':memory:'  # Use in-memory database for tests
                }
            }
        }
    }


@pytest.fixture
def hysteresis_disabled_config(hysteresis_config):
    """Configuration with hysteresis disabled (legacy behavior)"""
    import copy
    config = copy.deepcopy(hysteresis_config)
    config['battery_management']['charging_hysteresis']['enabled'] = False
    return config


@pytest.fixture
def sample_price_data():
    """Sample price data for testing"""
    return {
        'value': [
            {'dtime': '2025-12-06 00:00', 'csdac_pln': 400.0},
            {'dtime': '2025-12-06 01:00', 'csdac_pln': 350.0},
            {'dtime': '2025-12-06 02:00', 'csdac_pln': 300.0},  # Cheapest
            {'dtime': '2025-12-06 03:00', 'csdac_pln': 320.0},
            {'dtime': '2025-12-06 04:00', 'csdac_pln': 380.0},
        ]
    }


class TestHysteresisConfiguration:
    """Test hysteresis configuration loading"""
    
    def test_hysteresis_enabled_loads_config(self, hysteresis_config):
        """Test that hysteresis configuration is loaded correctly"""
        charger = AutomatedPriceCharger(hysteresis_config)
        
        assert charger.hysteresis_enabled is True
        assert charger.normal_start_threshold == 85
        assert charger.normal_stop_threshold == 95
        assert charger.normal_target_soc == 95
        assert charger.min_session_duration_minutes == 30
        assert charger.min_discharge_depth_percent == 10
        assert charger.max_sessions_per_day == 4
    
    def test_hysteresis_disabled_uses_defaults(self, hysteresis_disabled_config):
        """Test that hysteresis can be disabled"""
        charger = AutomatedPriceCharger(hysteresis_disabled_config)
        
        assert charger.hysteresis_enabled is False
    
    def test_session_tracking_variables_initialized(self, hysteresis_config):
        """Test that session tracking variables are initialized"""
        charger = AutomatedPriceCharger(hysteresis_config)
        
        assert charger.active_charging_session is None
        assert charger.session_start_time is None
        assert charger.session_start_soc is None
        assert charger.last_full_charge_soc is None
        assert charger.daily_session_count == 0
        assert charger.last_session_reset is not None


class TestHysteresisStartThreshold:
    """Test hysteresis start threshold logic"""
    
    def test_above_start_threshold_no_charge(self, hysteresis_config, sample_price_data):
        """Test that charging doesn't start when SOC is above start threshold"""
        charger = AutomatedPriceCharger(hysteresis_config)
        
        # SOC 87% is above start threshold (85%)
        decision = charger._make_charging_decision(
            battery_soc=87,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False
        assert 'above start threshold' in decision['reason']
    
    def test_below_start_threshold_good_price_starts_charge(self, hysteresis_config, sample_price_data):
        """Test that charging starts when SOC below threshold and price is good"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False  # Disable adaptive for predictable test
        
        # Mock the price check to return True
        with patch.object(charger, '_is_price_cheap_for_normal_tier', return_value=True):
            # SOC 84% is below start threshold (85%)
            decision = charger._make_charging_decision(
                battery_soc=84,
                overproduction=0,
                grid_power=1000,
                grid_direction='import',
                current_price=0.35,
                cheapest_price=0.30,
                cheapest_hour=2,
                price_data=sample_price_data
            )
            
            assert decision['should_charge'] is True
            assert 'starting session' in decision['reason'].lower()
            assert decision['target_soc'] == 95


class TestHysteresisStopThreshold:
    """Test hysteresis stop threshold logic"""
    
    def test_active_session_reaches_target_stops(self, hysteresis_config, sample_price_data):
        """Test that active session stops when target SOC reached"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Start a session
        charger.active_charging_session = True
        charger.session_start_time = datetime.now() - timedelta(minutes=35)
        charger.session_start_soc = 84
        
        # SOC 95% reaches stop threshold
        decision = charger._make_charging_decision(
            battery_soc=95,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False
        assert 'target soc reached' in decision['reason'].lower()
        assert charger.active_charging_session is None
        assert charger.last_full_charge_soc == 95


class TestSessionConsolidation:
    """Test session consolidation logic"""
    
    def test_minimum_session_duration_prevents_early_stop(self, hysteresis_config, sample_price_data):
        """Test that minimum session duration prevents early stopping"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Start a session 10 minutes ago (less than 30 min minimum)
        charger.active_charging_session = True
        charger.session_start_time = datetime.now() - timedelta(minutes=10)
        charger.session_start_soc = 84
        
        # SOC 90% (not at target yet)
        decision = charger._make_charging_decision(
            battery_soc=90,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is True
        assert 'continuing session' in decision['reason'].lower() or 'min duration' in decision['reason'].lower()
    
    def test_minimum_discharge_depth_prevents_recharge(self, hysteresis_config, sample_price_data):
        """Test that minimum discharge depth prevents premature recharging"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Set last full charge to 95%
        charger.last_full_charge_soc = 95
        
        # Current SOC 90% (only 5% discharge, less than 10% minimum)
        decision = charger._make_charging_decision(
            battery_soc=90,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False
        assert 'insufficient discharge' in decision['reason'].lower()
    
    def test_sufficient_discharge_allows_recharge(self, hysteresis_config, sample_price_data):
        """Test that sufficient discharge allows recharging"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Set last full charge to 95%
        charger.last_full_charge_soc = 95
        
        # Mock price check
        with patch.object(charger, '_is_price_cheap_for_normal_tier', return_value=True):
            # Current SOC 84% (11% discharge, more than 10% minimum)
            decision = charger._make_charging_decision(
                battery_soc=84,
                overproduction=0,
                grid_power=1000,
                grid_direction='import',
                current_price=0.35,
                cheapest_price=0.30,
                cheapest_hour=2,
                price_data=sample_price_data
            )
            
            assert decision['should_charge'] is True


class TestDailySessionLimit:
    """Test daily session limit logic"""
    
    def test_max_sessions_per_day_prevents_charging(self, hysteresis_config, sample_price_data):
        """Test that max sessions per day limit is enforced"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Set daily session count to max (4)
        charger.daily_session_count = 4
        charger.last_session_reset = datetime.now().date()
        
        # Try to charge at SOC 84%
        decision = charger._make_charging_decision(
            battery_soc=84,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is False
        assert 'max sessions' in decision['reason'].lower()
    
    def test_daily_session_count_resets_new_day(self, hysteresis_config, sample_price_data):
        """Test that daily session count resets on new day"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Set session count to max but for yesterday
        charger.daily_session_count = 4
        charger.last_session_reset = datetime.now().date() - timedelta(days=1)
        
        # Mock price check
        with patch.object(charger, '_is_price_cheap_for_normal_tier', return_value=True):
            # Try to charge at SOC 84%
            decision = charger._make_charging_decision(
                battery_soc=84,
                overproduction=0,
                grid_power=1000,
                grid_direction='import',
                current_price=0.35,
                cheapest_price=0.30,
                cheapest_hour=2,
                price_data=sample_price_data
            )
            
            # Should reset count and allow charging
            assert charger.daily_session_count == 1  # Reset to 0, then incremented to 1
            assert decision['should_charge'] is True


class TestEmergencyOverride:
    """Test emergency override logic"""
    
    def test_emergency_soc_bypasses_hysteresis(self, hysteresis_config, sample_price_data):
        """Test that emergency SOC bypasses hysteresis"""
        charger = AutomatedPriceCharger(hysteresis_config)
        
        # SOC 4% is below emergency threshold (5%)
        decision = charger._make_charging_decision(
            battery_soc=4,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=1.50,  # Even at high price
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['should_charge'] is True
        assert decision['priority'] == 'emergency'
        assert 'emergency' in decision['reason'].lower()
    
    def test_critical_soc_bypasses_hysteresis(self, hysteresis_config, sample_price_data):
        """Test that critical SOC bypasses hysteresis"""
        charger = AutomatedPriceCharger(hysteresis_config)
        
        # SOC 10% is below critical threshold (12%)
        decision = charger._make_charging_decision(
            battery_soc=10,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.80,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        assert decision['priority'] == 'critical'
        assert 'critical' in decision['reason'].lower()


class TestHysteresisVsLegacy:
    """Test hysteresis vs legacy behavior"""
    
    def test_legacy_mode_uses_old_logic(self, hysteresis_disabled_config, sample_price_data):
        """Test that legacy mode (hysteresis disabled) uses old logic"""
        charger = AutomatedPriceCharger(hysteresis_disabled_config)
        charger.adaptive_enabled = False
        
        # With hysteresis disabled, should use legacy percentile logic
        decision = charger._make_charging_decision(
            battery_soc=87,  # Above hysteresis start threshold
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        # Legacy logic should evaluate based on percentile, not hysteresis
        assert charger.hysteresis_enabled is False
    
    def test_hysteresis_mode_reduces_sessions(self, hysteresis_config, sample_price_data):
        """Test that hysteresis mode reduces charging sessions"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Simulate multiple SOC levels that would trigger charging in legacy mode
        soc_levels = [94, 93, 92, 91, 90, 89, 88, 87, 86, 85, 84]
        charge_decisions = []
        
        # Mock price check to return True
        with patch.object(charger, '_is_price_cheap_for_normal_tier', return_value=True):
            for soc in soc_levels:
                decision = charger._make_charging_decision(
                    battery_soc=soc,
                    overproduction=0,
                    grid_power=1000,
                    grid_direction='import',
                    current_price=0.35,
                    cheapest_price=0.30,
                    cheapest_hour=2,
                    price_data=sample_price_data
                )
                charge_decisions.append(decision['should_charge'])
        
        # With hysteresis, should only charge when SOC < 85%
        # SOC 94-85 should NOT charge (above threshold)
        # SOC 84 should charge (below threshold)
        assert charge_decisions[0:7] == [False] * 7  # 94-88: above threshold
        assert charge_decisions[7] == False  # 87: above threshold
        assert charge_decisions[8] == False  # 86: above threshold
        assert charge_decisions[9] == False  # 85: at threshold
        assert charge_decisions[10] == True  # 84: below threshold


class TestSessionTracking:
    """Test session tracking and state management"""
    
    def test_session_number_increments(self, hysteresis_config, sample_price_data):
        """Test that session number increments correctly"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Mock price check
        with patch.object(charger, '_is_price_cheap_for_normal_tier', return_value=True):
            # Start first session
            decision1 = charger._make_charging_decision(
                battery_soc=84,
                overproduction=0,
                grid_power=1000,
                grid_direction='import',
                current_price=0.35,
                cheapest_price=0.30,
                cheapest_hour=2,
                price_data=sample_price_data
            )
            
            assert decision1['should_charge'] is True
            assert charger.daily_session_count == 1
            
            # Complete session
            charger.active_charging_session = None
            charger.last_full_charge_soc = 95
            
            # Start second session (after sufficient discharge)
            decision2 = charger._make_charging_decision(
                battery_soc=84,
                overproduction=0,
                grid_power=1000,
                grid_direction='import',
                current_price=0.35,
                cheapest_price=0.30,
                cheapest_hour=2,
                price_data=sample_price_data
            )
            
            assert decision2['should_charge'] is True
            assert charger.daily_session_count == 2
    
    def test_session_state_preserved_during_charging(self, hysteresis_config, sample_price_data):
        """Test that session state is preserved during active charging"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # Start session
        charger.active_charging_session = True
        charger.session_start_time = datetime.now() - timedelta(minutes=35)
        charger.session_start_soc = 84
        
        # Make decision while charging
        decision = charger._make_charging_decision(
            battery_soc=90,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=0.35,
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        # Should continue charging
        assert decision['should_charge'] is True
        assert charger.active_charging_session is True
        assert charger.session_start_soc == 84


class TestPriceIntegration:
    """Test integration with price-based logic"""
    
    def test_hysteresis_respects_price_thresholds(self, hysteresis_config, sample_price_data):
        """Test that hysteresis still respects price thresholds"""
        charger = AutomatedPriceCharger(hysteresis_config)
        charger.adaptive_enabled = False
        
        # SOC below threshold but price too high
        decision = charger._make_charging_decision(
            battery_soc=84,
            overproduction=0,
            grid_power=1000,
            grid_direction='import',
            current_price=1.50,  # Very high price
            cheapest_price=0.30,
            cheapest_hour=2,
            price_data=sample_price_data
        )
        
        # Should not charge due to high price
        assert decision['should_charge'] is False
        assert 'price' in decision['reason'].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
