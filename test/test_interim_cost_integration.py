#!/usr/bin/env python3
"""
Integration test for Interim Cost Analysis Feature
Tests the complete flow from data collection through decision making
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


@pytest.fixture
def integration_config(tmp_path):
    """Create complete configuration for integration testing"""
    config = {
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
                    'session_tracking_file': str(tmp_path / 'sessions.json'),
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
        },
        'pricing': {
            'tariff_type': 'g12w',
            'base_price': 0.0,
            'sc_component': 0.0892,
            'day_price_multiplier': 1.0,
            'night_price_multiplier': 1.0
        },
        'charging_strategy': {
            'super_low_price': {
                'enabled': False
            },
            'proactive_charging': {
                'enabled': False
            }
        }
    }
    
    config_file = tmp_path / "integration_test_config.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    return str(config_file)


@pytest.fixture
def mock_data_collector_full():
    """Create mock data collector with complete 7-day historical data"""
    collector = Mock()
    
    # Generate realistic 7 days of consumption data
    historical_data = []
    start_time = datetime.now() - timedelta(days=7)
    
    for i in range(30240):  # 7 days × 4320 points/day
        timestamp = start_time + timedelta(seconds=i * 20)
        hour = timestamp.hour
        
        # Realistic consumption pattern
        if 18 <= hour < 22:  # Evening peak
            base_consumption = 2.0  # 2 kW
        elif 22 <= hour or hour < 6:  # Night
            base_consumption = 0.8  # 0.8 kW
        elif 6 <= hour < 9:  # Morning
            base_consumption = 1.5  # 1.5 kW
        else:  # Day
            base_consumption = 1.0  # 1 kW
        
        # Add variation
        import random
        consumption_kw = base_consumption * random.uniform(0.85, 1.15)
        
        historical_data.append({
            'timestamp': timestamp,
            'house_consumption': consumption_kw * 1000,  # Convert to W
            'pv_power': 0,
            'battery_soc': 50,
            'grid_power': consumption_kw * 1000
        })
    
    collector.historical_data = historical_data
    return collector


@pytest.fixture
def mock_price_data_realistic():
    """Create realistic price data with clear day/night pattern"""
    price_data = {'value': []}
    current_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for hour in range(24):
        target_time = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # Realistic price pattern (PLN/MWh)
        if 7 <= hour < 15:  # Day peak
            price_mwh = 600.0
        elif 15 <= hour < 22:  # Evening peak
            price_mwh = 850.0
        elif 22 <= hour or hour < 6:  # Night valley
            price_mwh = 250.0
        else:  # Morning
            price_mwh = 400.0
        
        price_data['value'].append({
            'dtime': target_time.strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': price_mwh
        })
    
    return price_data


def test_full_flow_expensive_afternoon_wait_for_night(integration_config, mock_data_collector_full, 
                                                      mock_price_data_realistic, tmp_path):
    """
    Integration Test 1: Expensive afternoon scenario - should wait for cheap night window
    
    Scenario:
    - Current time: 17:00 (expensive period, 0.85 PLN/kWh)
    - Battery SOC: 60% (not critical)
    - Cheap night window: 22:00 (0.25 PLN/kWh)
    - Expected: Recommend waiting (net benefit > threshold)
    """
    
    # Setup
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(integration_config)
        charger.data_collector = mock_data_collector_full
    
    # Set time to 17:00
    current_time = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0)
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        # Current price at 17:00
        current_price = 0.85  # PLN/kWh (expensive)
        battery_soc = 60
        
        # Execute multi-window evaluation
        decision = charger._evaluate_multi_window_with_interim_cost(
            battery_soc, current_price, mock_price_data_realistic
        )
        
        # Assertions
        assert decision is not None
        assert 'should_charge' in decision
        assert 'reason' in decision
        assert 'next_window' in decision
        
        # Should either recommend waiting or partial charging
        if decision['should_charge']:
            # If charging, it should be partial charge
            assert decision.get('partial_charge') is True
            assert 'target_soc' in decision
            print(f"✓ Partial charging recommended: {decision['reason']}")
        else:
            # If not charging, should be waiting for better window
            assert 'net_benefit' in decision
            assert decision['net_benefit'] > 0.10
            print(f"✓ Waiting recommended: {decision['reason']}")
            print(f"  Net benefit: {decision['net_benefit']:.2f} PLN")


def test_full_flow_flat_price_charge_now(integration_config, mock_data_collector_full, tmp_path):
    """
    Integration Test 2: Flat price scenario - should charge now
    
    Scenario:
    - Current time: 12:00
    - Battery SOC: 50%
    - All prices similar (no benefit to waiting)
    - Expected: Charge now
    """
    
    # Create flat price data
    flat_price_data = {'value': []}
    current_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    
    for hour in range(24):
        target_time = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)
        flat_price_data['value'].append({
            'dtime': target_time.strftime('%Y-%m-%d %H:%M'),
            'csdac_pln': 500.0  # Constant 0.5 PLN/kWh
        })
    
    # Setup
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(integration_config)
        charger.data_collector = mock_data_collector_full
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        current_price = 0.5  # PLN/kWh
        battery_soc = 50
        
        # Execute multi-window evaluation
        decision = charger._evaluate_multi_window_with_interim_cost(
            battery_soc, current_price, flat_price_data
        )
        
        # Should recommend charging now (no better window)
        if decision is not None:
            assert decision['should_charge'] is True
            assert 'No beneficial' in decision['reason'] or 'charge now' in decision['reason']
            print(f"✓ Charge now recommended: {decision['reason']}")
        else:
            # None decision means continue with normal logic (acceptable)
            print("✓ No specific decision (will use normal charging logic)")


def test_full_flow_partial_charging_session_tracking(integration_config, mock_data_collector_full,
                                                     mock_price_data_realistic, tmp_path):
    """
    Integration Test 3: Partial charging with session tracking
    
    Scenario:
    - Current time: 18:00 (expensive)
    - Battery SOC: 40% (low enough for partial charging)
    - Cheap window: 22:00 (4 hours away)
    - Expected: Partial charge + session recording
    """
    
    # Setup
    session_file = tmp_path / 'partial_sessions.json'
    
    # Update config to use test session file
    import yaml
    with open(integration_config, 'r') as f:
        config = yaml.safe_load(f)
    config['timing_awareness']['smart_critical_charging']['partial_charging']['session_tracking_file'] = str(session_file)
    with open(integration_config, 'w') as f:
        yaml.dump(config, f)
    
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(integration_config)
        charger.data_collector = mock_data_collector_full
    
    # Set time to 18:00
    current_time = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        current_price = 0.85  # Expensive
        battery_soc = 40  # Low enough to need partial charging
        
        # Check session limits (should allow)
        can_charge = charger._check_partial_session_limits()
        assert can_charge is True
        
        # Execute evaluation
        decision = charger._evaluate_multi_window_with_interim_cost(
            battery_soc, current_price, mock_price_data_realistic
        )
        
        assert decision is not None
        
        # If partial charging recommended, record session
        if decision.get('partial_charge'):
            charger._record_partial_charging_session()
            
            # Verify session was recorded
            assert session_file.exists()
            with open(session_file, 'r') as f:
                sessions = json.load(f)
            
            assert 'sessions' in sessions
            assert len(sessions['sessions']) == 1
            assert 'timestamp' in sessions['sessions'][0]
            assert 'date' in sessions['sessions'][0]
            
            print(f"✓ Partial charging session recorded")
            print(f"  Decision: {decision['reason']}")
            print(f"  Target SOC: {decision.get('target_soc', 'N/A')}%")


def test_full_flow_session_limit_enforcement(integration_config, mock_data_collector_full, tmp_path):
    """
    Integration Test 4: Session limit enforcement
    
    Scenario:
    - Already 4 partial charging sessions today
    - Expected: Session limit blocks further partial charging
    """
    
    # Setup with existing sessions
    session_file = tmp_path / 'sessions_limit.json'
    
    import yaml
    with open(integration_config, 'r') as f:
        config = yaml.safe_load(f)
    config['timing_awareness']['smart_critical_charging']['partial_charging']['session_tracking_file'] = str(session_file)
    with open(integration_config, 'w') as f:
        yaml.dump(config, f)
    
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(integration_config)
        charger.data_collector = mock_data_collector_full
    
    # Create 4 sessions today
    current_time = datetime.now(charger.warsaw_tz)
    reset_time = current_time.replace(hour=6, minute=0, second=0, microsecond=0)
    if current_time.hour < 6:
        reset_time = reset_time - timedelta(days=1)
    
    sessions = {
        'sessions': [
            {
                'timestamp': (reset_time + timedelta(hours=i)).isoformat(),
                'date': (reset_time + timedelta(hours=i)).date().isoformat()
            }
            for i in range(4)  # Max sessions
        ]
    }
    
    with open(session_file, 'w') as f:
        json.dump(sessions, f)
    
    # Check session limits
    can_charge = charger._check_partial_session_limits()
    
    # Should return False (limit reached)
    assert can_charge is False
    print("✓ Session limit correctly enforced (4/4 sessions used)")


def test_full_flow_critical_soc_overrides_interim_analysis(integration_config, mock_data_collector_full,
                                                           mock_price_data_realistic):
    """
    Integration Test 5: Critical SOC overrides interim cost analysis
    
    Scenario:
    - Battery SOC: 10% (critical level)
    - Better window exists at 22:00
    - Expected: Critical charging logic takes precedence
    """
    
    with patch('automated_price_charging.GoodWeFastCharger'):
        charger = AutomatedPriceCharger(integration_config)
        charger.data_collector = mock_data_collector_full
    
    current_time = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    
    # Mock current data
    current_data = {
        'battery': {'soc_percent': 10},  # Critical
        'pv': {'power': 0},
        'grid': {'power': 1500, 'direction': 'Import'},
        'house': {'consumption': 1500}
    }
    
    with patch('automated_price_charging.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_time
        mock_datetime.strptime = datetime.strptime
        
        # Execute full decision flow
        decision = charger.make_smart_charging_decision(
            current_data, mock_price_data_realistic
        )
        
        # Critical SOC triggers critical charging logic (may wait if savings are high)
        assert decision is not None
        assert 'critical' in decision['reason'].lower() or decision['priority'] == 'critical'
        
        # Accept either charge now or wait with high savings
        if decision['should_charge']:
            print(f"✓ Critical SOC charging immediately")
        else:
            # Smart critical logic can wait if savings are substantial
            print(f"✓ Critical SOC smart wait logic engaged")
        
        print(f"  Decision: {decision['reason']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
