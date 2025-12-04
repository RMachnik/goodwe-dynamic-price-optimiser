#!/usr/bin/env python3
"""
Unit tests for Automated Price Charging - Interim Cost Analysis Feature
Tests the interim cost calculation, multi-window evaluation, and partial charging logic
"""

import sys
import os
from pathlib import Path
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import json
import tempfile

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger


# Test fixtures
@pytest.fixture
def mock_config():
    """Create mock configuration for testing"""
    return {
        'system': {
            'timezone': 'Europe/Warsaw'
        },
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
                    'time_of_day_adjustment': True,
                    'evening_peak_multiplier': 1.5,
                    'night_discount_multiplier': 0.8,
                    'fallback_consumption_kw': 1.25,
                    'min_historical_hours': 48,
                    'lookback_days': 7
                },
                'partial_charging': {
                    'enabled': True,
                    'safety_margin_percent': 10,
                    'max_partial_sessions_per_day': 4,
                    'min_partial_charge_kwh': 2.0,
                    'session_tracking_file': 'out/partial_charging_sessions.json',
                    'daily_reset_hour': 6
                    # timezone now inherited from system.timezone
                }
            }
        },
        'battery': {
            'capacity_kwh': 20.0
        },
        'inverter_adapter': {
            'type': 'goodwe'
        },
        'data_collection': {
            'buffer_size': 30240
        },
        'price_analysis': {
            'api_url': 'https://api.raporty.pse.pl/api/csdac-pln'
        }
    }


@pytest.fixture
def mock_data_collector():
    """Create mock data collector with 7-day historical data"""
    collector = Mock()
    
    # Generate 7 days of historical data (20-second intervals)
    # Simulate varying consumption: 1.0 kW at night, 1.5 kW during evening peak
    historical_data = []
    start_time = datetime.now() - timedelta(days=7)
    
    for i in range(30240):  # 7 days worth
        timestamp = start_time + timedelta(seconds=i * 20)
        hour = timestamp.hour
        
        # Simulate time-of-day consumption pattern
        if 18 <= hour < 22:  # Evening peak
            consumption_kw = 1.8
        elif 22 <= hour or hour < 6:  # Night
            consumption_kw = 0.9
        else:  # Day
            consumption_kw = 1.2
        
        # Add some randomness
        import random
        consumption_kw *= random.uniform(0.9, 1.1)
        
        historical_data.append({
            'timestamp': timestamp,
            'house_consumption': consumption_kw * 1000,  # Convert to W
            'pv_power': 0,  # Not relevant for interim cost
            'battery_soc': 50,
            'grid_power': consumption_kw * 1000
        })
    
    collector.historical_data = historical_data
    return collector


@pytest.fixture
def mock_price_data():
    """Create mock price data with various price levels"""
    current_time = datetime.now()
    price_data = {'value': []}
    
    # Generate 24 hours of price data
    for hour in range(24):
        target_time = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # Create price pattern: high afternoon, low night
        if 16 <= hour < 20:  # Expensive afternoon/evening
            price_mwh = 800.0
        elif 22 <= hour or hour < 6:  # Cheap night
            price_mwh = 300.0
        else:  # Moderate day
            price_mwh = 500.0
        
        price_data['value'].append({
            'dtime': target_time.strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': price_mwh
        })
    
    return price_data


@pytest.fixture
def charger_instance(mock_config, mock_data_collector, tmp_path):
    """Create AutomatedPriceCharger instance for testing"""
    # Create temporary config file
    config_file = tmp_path / "test_config.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(mock_config, f)
    
    # Patch the GoodWeFastCharger to avoid hardware dependencies
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(str(config_file))
        charger.data_collector = mock_data_collector
        return charger


# Test 1: Calculate interim cost with full historical data
def test_calculate_interim_cost_with_full_data(charger_instance, mock_price_data):
    """Test interim cost calculation with 7 days of historical data"""
    
    # Set up time window: current to 3 hours later
    current_time = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
    end_time = current_time + timedelta(hours=3)
    
    # Calculate interim cost
    interim_cost = charger_instance._calculate_interim_cost(
        current_time, end_time, mock_price_data
    )
    
    # Assertions
    assert interim_cost is not None
    assert isinstance(interim_cost, float)
    assert interim_cost > 0  # Should have positive cost
    
    # Cost should be higher during evening peak hours (19:00-22:00)
    # With evening multiplier of 1.5x
    # Expected: ~1.8 kW consumption × 1.5 multiplier × 3 hours × ~0.5-0.8 PLN/kWh
    assert interim_cost > 1.5  # Should be at least 1.5 PLN for 3 hours
    assert interim_cost < 20.0  # Should be reasonable (< 20 PLN)


# Test 2: Calculate interim cost with partial historical data
def test_calculate_interim_cost_with_partial_data(charger_instance, mock_price_data):
    """Test interim cost calculation with limited historical data (< 48h)"""
    
    # Reduce historical data to < 48 hours (only 1 day)
    one_day_data = charger_instance.data_collector.historical_data[:4320]
    charger_instance.data_collector.historical_data = one_day_data
    
    current_time = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
    end_time = current_time + timedelta(hours=2)
    
    interim_cost = charger_instance._calculate_interim_cost(
        current_time, end_time, mock_price_data
    )
    
    # With < 48h data, should use fallback consumption (1.25 kW)
    assert interim_cost is not None
    assert isinstance(interim_cost, float)
    assert interim_cost > 0
    
    # Should use fallback: 1.25 kW × 2 hours × price
    # For hour 15-17, price is ~0.5 PLN/kWh (moderate)
    assert 1.0 < interim_cost < 3.0  # Reasonable range for fallback


# Test 3: Calculate interim cost fallback when no historical data
def test_calculate_interim_cost_fallback(charger_instance, mock_price_data):
    """Test interim cost calculation fallback when no historical data"""
    
    # Empty historical data
    charger_instance.data_collector.historical_data = []
    
    current_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = current_time + timedelta(hours=1)
    
    interim_cost = charger_instance._calculate_interim_cost(
        current_time, end_time, mock_price_data
    )
    
    # Should use fallback consumption
    assert interim_cost is not None
    assert isinstance(interim_cost, float)
    assert interim_cost > 0
    
    # 1 hour × 1.25 kW × ~0.5 PLN/kWh = ~0.6 PLN
    assert 0.3 < interim_cost < 1.5


# Test 4: Multi-window evaluation finds optimal window
def test_multi_window_evaluation_finds_optimal(charger_instance, mock_price_data):
    """Test that multi-window evaluation identifies the best future window"""
    
    # Set current time to expensive afternoon (17:00)
    current_time = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0)
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        # Current price is high (0.8 PLN/kWh at 17:00)
        # Best window is at 22:00 (0.3 PLN/kWh)
        current_price = 0.8
        battery_soc = 60
        
        decision = charger_instance._evaluate_multi_window_with_interim_cost(
            battery_soc, current_price, mock_price_data
        )
        
        # Should recommend waiting for better window
        assert decision is not None
        assert decision['should_charge'] is False or decision.get('partial_charge') is True
        assert 'net_benefit' in decision or 'partial_charge' in decision
        assert 'next_window' in decision


# Test 5: Multi-window evaluation with no beneficial window
def test_multi_window_evaluation_no_benefit(charger_instance, mock_price_data):
    """Test multi-window evaluation when no future window offers benefit"""
    
    # Create flat price data (no savings opportunity)
    flat_price_data = {'value': []}
    current_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    for hour in range(24):
        target_time = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        flat_price_data['value'].append({
            'dtime': target_time.strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': 500.0  # Constant price
        })
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        current_price = 0.5
        battery_soc = 60
        
        decision = charger_instance._evaluate_multi_window_with_interim_cost(
            battery_soc, current_price, flat_price_data
        )
        
        # Should recommend charging now (no better window)
        if decision is not None:
            assert decision['should_charge'] is True
            assert 'No beneficial' in decision['reason'] or 'charge now' in decision['reason']


# Test 6: Multi-window blocks windows above critical threshold
def test_multi_window_blocks_critical_prices(charger_instance, mock_price_data):
    """Test that multi-window evaluation blocks windows with prices above critical threshold"""
    
    # Create price data with all windows above critical threshold
    high_price_data = {'value': []}
    current_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    
    for hour in range(24):
        target_time = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        high_price_data['value'].append({
            'dtime': target_time.strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': 2000.0  # Very high price > critical threshold
        })
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        # Mock get_critical_price_threshold to return a value
        with patch.object(charger_instance, 'get_critical_price_threshold', return_value=1.0):
            current_price = 2.0  # High but current
            battery_soc = 60
            
            decision = charger_instance._evaluate_multi_window_with_interim_cost(
                battery_soc, current_price, high_price_data
            )
            
            # Should either recommend charging now or return None (no valid windows)
            # Because all future windows are blocked by critical threshold
            if decision is not None:
                assert decision['should_charge'] is True


# Test 7: Partial charging within battery capacity
def test_partial_charging_within_capacity(charger_instance, tmp_path):
    """Test partial charging calculation stays within battery capacity"""
    
    # Create session tracking file
    session_file = tmp_path / "sessions.json"
    charger_instance.partial_session_tracking_file = str(session_file)
    
    # Best window is 4 hours away
    best_window = {
        'time': datetime.now() + timedelta(hours=4),
        'price_kwh': 0.3,
        'net_benefit': 5.0,
        'hours_to_wait': 4.0
    }
    
    battery_soc = 85  # High SOC
    current_time = datetime.now()
    current_price = 0.5  # Below critical threshold
    
    with patch.object(charger_instance, 'get_critical_price_threshold', return_value=0.8):
        decision = charger_instance._evaluate_partial_charging(
            battery_soc, best_window, current_time, current_price
        )
        
        # At 85% SOC (17 kWh), adding 5 kWh would exceed 20 kWh capacity
        # Should return None (insufficient capacity)
        assert decision is None or decision.get('target_soc', 0) <= 100


# Test 8: Partial charging session limits enforcement
def test_partial_charging_session_limits(charger_instance, tmp_path):
    """Test that partial charging respects max sessions per day"""
    
    # Create session tracking file with 4 sessions today
    session_file = tmp_path / "sessions.json"
    charger_instance.partial_session_tracking_file = str(session_file)
    
    current_time = datetime.now(charger_instance.warsaw_tz)
    
    # Create 4 sessions after reset hour (6 AM)
    reset_time = current_time.replace(hour=6, minute=0, second=0, microsecond=0)
    if current_time.hour < 6:
        reset_time = reset_time - timedelta(days=1)
    
    sessions = {
        'sessions': [
            {
                'timestamp': (reset_time + timedelta(hours=i)).isoformat(),
                'date': (reset_time + timedelta(hours=i)).date().isoformat()
            }
            for i in range(4)  # Already at max (4 sessions)
        ]
    }
    
    with open(session_file, 'w') as f:
        json.dump(sessions, f)
    
    # Try to check session limits
    can_charge = charger_instance._check_partial_session_limits()
    
    # Should return False (limit reached)
    assert can_charge is False


# Test 9: Partial charging timezone-aware session tracking
def test_partial_charging_timezone_aware(charger_instance, tmp_path):
    """Test that partial charging session tracking handles timezone and DST correctly"""
    
    # Create session tracking file
    session_file = tmp_path / "sessions.json"
    charger_instance.partial_session_tracking_file = str(session_file)
    
    # Create sessions from yesterday (before reset)
    current_time = datetime.now(charger_instance.warsaw_tz)
    yesterday_time = current_time - timedelta(days=1, hours=12)
    
    sessions = {
        'sessions': [
            {
                'timestamp': yesterday_time.isoformat(),
                'date': yesterday_time.date().isoformat()
            }
            for _ in range(3)  # 3 sessions yesterday
        ]
    }
    
    with open(session_file, 'w') as f:
        json.dump(sessions, f)
    
    # Check session limits (should allow because yesterday's sessions don't count)
    can_charge = charger_instance._check_partial_session_limits()
    
    # Should return True (yesterday's sessions are before reset)
    assert can_charge is True
    
    # Record a new session
    charger_instance._record_partial_charging_session()
    
    # Verify session was recorded with timezone
    with open(session_file, 'r') as f:
        updated_sessions = json.load(f)
    
    assert len(updated_sessions['sessions']) == 4
    latest_session = updated_sessions['sessions'][-1]
    assert 'timestamp' in latest_session
    assert 'date' in latest_session
    
    # Parse timestamp and check it has timezone info
    from datetime import datetime as dt
    timestamp = dt.fromisoformat(latest_session['timestamp'])
    assert timestamp.tzinfo is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
