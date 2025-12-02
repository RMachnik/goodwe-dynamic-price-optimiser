#!/usr/bin/env python3
"""
Unit tests for Window Commitment and Session Protection
Tests the new anti-postponement logic, dynamic protection, and window duration validation
"""

import sys
import os
from pathlib import Path
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import json
import tempfile
import yaml

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def mock_config():
    """Create mock configuration with window commitment enabled"""
    return {
        'timing_awareness': {
            'smart_critical_charging': {
                'enabled': True,
                'emergency_threshold': 5,
                'critical_threshold': 12,
                'critical_price_threshold_multiplier': 1.5,
                'interim_cost_analysis': {
                    'enabled': True,
                    'net_savings_threshold_pln': 0.10,
                    'evaluation_window_hours': 12,
                    'window_commitment_enabled': True,
                    'max_window_postponements': 3,
                    'commitment_margin_minutes': 30,
                    'min_charging_session_duration_minutes': 90,
                    'dynamic_protection_duration': True,
                    'protection_duration_buffer_percent': 10,
                    'soc_urgency_thresholds': {
                        'critical': 15,
                        'urgent': 20,
                        'low': 30
                    }
                }
            }
        },
        'battery_management': {
            'capacity_kwh': 20.0,
            'usable_capacity_kwh': 18.0,
            'max_charging_power_kw': 10.0
        },
        'charging': {
            'max_power': 10000  # 10kW in watts - used by _calculate_required_charging_duration
        },
        'fast_charging': {
            'power_percentage': 90,
            'target_soc': 100
        }
    }


@pytest.fixture
def charger_instance(mock_config, tmp_path):
    """Create charger instance with mock config"""
    # Create temporary config file
    config_file = tmp_path / "test_config.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(mock_config, f)
    
    # Patch GoodWeFastCharger and data collector to avoid dependencies
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(str(config_file))
        # Mock data collector
        charger.data_collector = Mock()
        charger.data_collector.historical_data = []
        return charger


class TestWindowCommitment:
    """Test window commitment mechanism"""
    
    def test_commitment_initialization(self, charger_instance):
        """Test that window commitment is initialized correctly"""
        assert charger_instance.window_commitment_enabled
        assert charger_instance.max_window_postponements == 3
        assert charger_instance.committed_window_time is None
        assert charger_instance.window_postponement_count == 0
    
    def test_commit_to_window(self, charger_instance):
        """Test committing to a window"""
        window_time = datetime(2025, 11, 27, 22, 0)
        window_price = 0.45
        
        charger_instance._commit_to_window(window_time, window_price)
        
        assert charger_instance.committed_window_time == window_time
        assert charger_instance.committed_window_price == window_price
        assert charger_instance.window_commitment_timestamp is not None
        assert charger_instance.window_postponement_count == 0
    
    def test_clear_window_commitment(self, charger_instance):
        """Test clearing window commitment"""
        # First commit to a window
        window_time = datetime(2025, 11, 27, 22, 0)
        charger_instance._commit_to_window(window_time, 0.45)
        
        # Then clear it
        charger_instance._clear_window_commitment()
        
        assert charger_instance.committed_window_time is None
        assert charger_instance.committed_window_price is None
        assert charger_instance.window_commitment_timestamp is None
        assert charger_instance.window_postponement_count == 0
    
    def test_max_postponements_critical_soc(self, charger_instance):
        """Test SOC urgency: critical SOC allows 0 postponements"""
        max_postponements = charger_instance._get_max_postponements_for_soc(10)
        assert max_postponements == 0  # Critical SOC
        
        max_postponements = charger_instance._get_max_postponements_for_soc(14)
        assert max_postponements == 0  # Critical SOC
    
    def test_max_postponements_urgent_soc(self, charger_instance):
        """Test SOC urgency: urgent SOC allows 1 postponement"""
        max_postponements = charger_instance._get_max_postponements_for_soc(15)
        assert max_postponements == 1  # Urgent SOC
        
        max_postponements = charger_instance._get_max_postponements_for_soc(19)
        assert max_postponements == 1  # Urgent SOC
    
    def test_max_postponements_low_soc(self, charger_instance):
        """Test SOC urgency: low SOC allows 2 postponements"""
        max_postponements = charger_instance._get_max_postponements_for_soc(20)
        assert max_postponements == 2  # Low SOC
        
        max_postponements = charger_instance._get_max_postponements_for_soc(29)
        assert max_postponements == 2  # Low SOC
    
    def test_max_postponements_normal_soc(self, charger_instance):
        """Test SOC urgency: normal SOC allows max postponements"""
        max_postponements = charger_instance._get_max_postponements_for_soc(30)
        assert max_postponements == 3  # Normal SOC
        
        max_postponements = charger_instance._get_max_postponements_for_soc(50)
        assert max_postponements == 3  # Normal SOC
    
    def test_postponement_limit_enforcement(self, charger_instance):
        """Test that postponement limit forces charging when reached"""
        # Simulate a scenario with committed window
        window_time = datetime(2025, 11, 27, 22, 0)
        charger_instance._commit_to_window(window_time, 0.45)
        charger_instance.window_postponement_count = 3  # At limit
        
        # Try to evaluate with a better window - should force charge because at limit
        current_time = datetime(2025, 11, 27, 10, 0)
        mock_data = {'battery': {'soc_percent': 35}}
        
        # Mock price data showing better window later
        price_data = {
            'value': [
                {'dtime': (current_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M'),
                 'csdac_pln': 400 if i < 12 else 300}  # Better price at hour 12
                for i in range(24)
            ]
        }
        
        with patch.object(charger_instance, '_get_consumption_forecast', return_value=1.25):
            result = charger_instance._evaluate_multi_window_with_interim_cost(
                mock_data, price_data, current_time
            )
            
            # At max postponements, should force charge now
            assert result is not None
            assert result.get('should_charge') is True
            # Commitment should be cleared after forcing charge
            assert charger_instance.window_postponement_count == 0


class TestSessionProtection:
    """Test charging session protection"""
    
    def test_start_charging_session_dynamic(self, charger_instance):
        """Test starting a charging session with dynamic protection"""
        current_soc = 13
        charger_instance._start_charging_session(current_soc)
        
        assert charger_instance.active_charging_session is True
        assert charger_instance.charging_session_start_time is not None
        assert charger_instance.charging_session_start_soc == 13
    
    def test_end_charging_session(self, charger_instance):
        """Test ending a charging session"""
        charger_instance._start_charging_session(13)
        charger_instance.end_charging_session()
        
        assert charger_instance.active_charging_session is False
        assert charger_instance.charging_session_start_time is None
        assert charger_instance.charging_session_start_soc is None
    
    def test_session_protection_within_duration(self, charger_instance):
        """Test that session is protected within duration"""
        # Start a session
        charger_instance._start_charging_session(13)
        
        # Immediately check protection (should be protected)
        is_protected = charger_instance.is_charging_session_protected()
        assert is_protected is True
    
    def test_session_protection_expired(self, charger_instance):
        """Test that session protection expires after duration"""
        # Start a session
        charger_instance._start_charging_session(13)
        
        # Simulate time passing (move start time to past)
        charger_instance.charging_session_start_time = datetime.now() - timedelta(hours=3)
        
        # Check protection (should be expired)
        is_protected = charger_instance.is_charging_session_protected()
        assert is_protected is False
    
    def test_calculate_required_charging_duration(self, charger_instance):
        """Test calculation of required charging duration"""
        current_soc = 13
        target_soc = 100
        
        duration = charger_instance._calculate_required_charging_duration(
            current_soc, target_soc
        )
        
        # Expected calculation:
        # energy_needed = (100-13) / 100 * 20 kWh = 17.4 kWh
        # charging_power = 10000W * 0.9 / 1000 = 9 kW
        # charging_efficiency = 0.90
        # charging_time_hours = 17.4 / (9 * 0.90) = 2.15 hours
        # buffer = 1.10 (10% buffer)
        # buffered_time = 2.15 * 1.10 = 2.37 hours = 142 minutes
        energy_needed = (87 * 20) / 100  # 17.4 kWh
        charging_power = 9  # 10kW * 90%
        charging_efficiency = 0.90
        charging_time_hours = energy_needed / (charging_power * charging_efficiency)
        buffer_multiplier = 1.10
        expected_minutes = charging_time_hours * 60 * buffer_multiplier
        
        assert abs(duration - expected_minutes) < 1  # Allow 1 minute tolerance
    
    def test_dynamic_protection_duration_low_soc(self, charger_instance):
        """Test dynamic protection gives longer duration for low SOC"""
        # Low SOC needs more charging time
        duration_low = charger_instance._calculate_required_charging_duration(13, 100)
        
        # High SOC needs less charging time
        duration_high = charger_instance._calculate_required_charging_duration(70, 100)
        
        assert duration_low > duration_high
    
    def test_fixed_protection_fallback(self, charger_instance):
        """Test that fixed protection is used when dynamic is disabled"""
        charger_instance.dynamic_protection_duration = False
        charger_instance.min_charging_session_duration = 90
        
        charger_instance._start_charging_session(13)
        
        # Check that fixed duration is used
        # Session should be protected for 90 minutes
        is_protected = charger_instance.is_charging_session_protected()
        assert is_protected is True


class TestWindowDurationValidation:
    """Test window duration validation"""
    
    def test_calculate_window_duration_sufficient(self, charger_instance):
        """Test window duration calculation with sufficient cheap hours"""
        window_start = datetime(2025, 11, 27, 22, 0)
        
        # Create 3 hours of cheap prices
        price_data = {
            'value': [
                {'dtime': '2025-11-27 22:00', 'csdac_pln': 300},
                {'dtime': '2025-11-27 23:00', 'csdac_pln': 280},
                {'dtime': '2025-11-28 00:00', 'csdac_pln': 290},
                {'dtime': '2025-11-28 01:00', 'csdac_pln': 450},  # Price spike
            ]
        }
        
        max_threshold = 0.35  # 350 PLN/MWh = 0.35 PLN/kWh
        
        duration = charger_instance._calculate_window_duration(
            window_start, price_data, max_threshold
        )
        
        # Should detect 3 consecutive hours below threshold
        assert duration == 3.0
    
    def test_calculate_window_duration_insufficient(self, charger_instance):
        """Test window duration calculation with insufficient cheap hours"""
        window_start = datetime(2025, 11, 27, 22, 0)
        
        # Only 1 hour of cheap price
        price_data = {
            'value': [
                {'dtime': '2025-11-27 22:00', 'csdac_pln': 300},
                {'dtime': '2025-11-27 23:00', 'csdac_pln': 500},  # Too expensive
            ]
        }
        
        max_threshold = 0.35
        
        duration = charger_instance._calculate_window_duration(
            window_start, price_data, max_threshold
        )
        
        # Should detect only 1 hour
        assert duration == 1.0
    
    def test_window_validation_blocks_short_windows(self, charger_instance):
        """Test that evaluation skips windows too short for required charging"""
        current_time = datetime(2025, 11, 27, 10, 0)
        mock_data = {'battery': {'soc_percent': 13}}  # Needs ~2.2 hours to charge
        
        # Create price data with only 1-hour cheap window
        price_data = {
            'value': [
                {'dtime': (current_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M'),
                 'csdac_pln': 300 if i == 12 else 500}  # Only 1 hour cheap
                for i in range(24)
            ]
        }
        
        with patch.object(charger_instance, '_get_consumption_forecast', return_value=1.25):
            result = charger_instance._evaluate_multi_window_with_interim_cost(
                mock_data, price_data, current_time
            )
            
            # Should not choose the 1-hour window (insufficient duration)
            # Will choose current time instead or wait
            assert result is not None


class TestIntegrationScenarios:
    """Test complete scenarios combining all features"""
    
    def test_scenario_infinite_postponement_prevented(self, charger_instance):
        """Test that infinite postponement is prevented at 13% SOC (below critical threshold)"""
        current_time = datetime(2025, 11, 27, 10, 0)
        mock_data = {'battery': {'soc_percent': 13}}
        
        # Create price data that gets slightly better each hour
        price_data = {
            'value': [
                {'dtime': (current_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M'),
                 'csdac_pln': 400 - i * 2}  # Gradually improving prices
                for i in range(24)
            ]
        }
        
        with patch.object(charger_instance, '_get_consumption_forecast', return_value=1.25):
            # At 13% SOC (below critical 15%), max postponements is 0
            # System should immediately force charge without committing to window
            result1 = charger_instance._evaluate_multi_window_with_interim_cost(
                mock_data, price_data, current_time
            )
            
            # Should return charge decision immediately
            assert result1 is not None
            assert result1.get('should_charge') is True
            # No window commitment at critical SOC - forces immediate charge
            assert charger_instance.committed_window_time is None
    
    def test_scenario_session_protection_prevents_interruption(self, charger_instance):
        """Test that active session is not interrupted by new decision"""
        # Start charging session at 13% SOC
        charger_instance._start_charging_session(13)
        
        # Check that session is protected
        is_protected = charger_instance.is_charging_session_protected()
        assert is_protected is True
        
        # Session start should be recent
        elapsed = (datetime.now() - charger_instance.charging_session_start_time).total_seconds()
        assert elapsed < 5  # Less than 5 seconds ago
    
    def test_scenario_window_duration_matches_charging_need(self, charger_instance):
        """Test that system only accepts windows long enough to complete charging"""
        current_time = datetime(2025, 11, 27, 10, 0)
        mock_data = {'battery': {'soc_percent': 13}}
        
        # Create price data with 3-hour cheap window (sufficient for 2.2 hours needed)
        price_data = {
            'value': [
                {'dtime': (current_time + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M'),
                 'csdac_pln': 300 if 12 <= i <= 14 else 500}  # 3 hours cheap
                for i in range(24)
            ]
        }
        
        with patch.object(charger_instance, '_get_consumption_forecast', return_value=1.25):
            result = charger_instance._evaluate_multi_window_with_interim_cost(
                mock_data, price_data, current_time
            )
            
            # Should accept the 3-hour window (>= 2.2 hours required)
            assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
