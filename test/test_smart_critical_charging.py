#!/usr/bin/env python3
"""
Test script for Smart Critical Charging Logic
Tests the new price-aware critical battery charging behavior
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger
import yaml
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def test_smart_critical_charging():
    """Test the smart critical charging logic"""
    logger.info("Testing Smart Critical Charging Logic")
    
    config = load_config()
    
    # Test scenarios
    test_scenarios = [
        {
            'name': 'Emergency Level (3% SOC) - Should Always Charge',
            'battery_soc': 3,
            'current_price': 1.5,  # High price
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'charge',
            'expected_reason': 'Emergency battery level'
        },
                {
                    'name': 'Critical Level (8% SOC) - Acceptable Price',
                    'battery_soc': 8,
                    'current_price': 0.5,  # Acceptable price
                    'cheapest_price': 0.4,
                    'cheapest_hour': 23,
                    'expected_action': 'charge',
                    'expected_reason': 'acceptable price'
                },
            {
                'name': 'Critical Level (8% SOC) - High Price, Good Savings Soon',
                'battery_soc': 8,
                'current_price': 1.5,  # High price
                'cheapest_price': 0.4,  # Much cheaper
                'cheapest_hour': 23,
                'expected_action_dynamic': True,
                'expected_savings': '73.3%'
            },
            {
                'name': 'Critical Level (8% SOC) - High Price, Long Wait',
                'battery_soc': 8,
                'current_price': 1.5,  # High price
                'cheapest_price': 0.4,  # Much cheaper
                'cheapest_hour': 6,
                'expected_action_dynamic': True,
                'expected_savings': '73.3%'
            },
            {
                'name': 'Critical Level (8% SOC) - High Price, Insufficient Savings',
                'battery_soc': 8,
                'current_price': 1.5,  # High price above threshold
                'cheapest_price': 1.35,  # Small savings
                'cheapest_hour': 23,
                'expected_action_dynamic': True,
                'expected_savings': '10.0%'
            }
    ]
    
    # Initialize the automated price charger
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    charger = AutomatedPriceCharger(str(config_path))
    
    # Test each scenario
    for scenario in test_scenarios:
        logger.info(f"\n--- Testing: {scenario['name']} ---")
        
        # Create mock data
        current_data = {
            'battery': {'soc_percent': scenario['battery_soc']},
            'photovoltaic': {'current_power_w': 0},
            'grid': {'power_w': 0, 'flow_direction': 'Import'},
            'house_consumption': {'current_power_w': 500}
        }
        
        price_data = {
            'current_price': scenario['current_price'],
            'cheapest_price': scenario['cheapest_price'],
            'cheapest_hour': scenario['cheapest_hour']
        }
        
        # Make decision
        decision = charger._make_charging_decision(
            battery_soc=scenario['battery_soc'],
            overproduction=0,
            grid_power=0,
            grid_direction='Import',
            current_price=scenario['current_price'],
            cheapest_price=scenario['cheapest_price'],
            cheapest_hour=scenario['cheapest_hour']
        )
        
        # Check results
        logger.info(f"Decision: {decision}")
        
        # Verify expected action (dynamic where applicable)
        if scenario.get('expected_action_dynamic'):
            now_hour = datetime.now().hour
            hours_to_wait = scenario['cheapest_hour'] - now_hour
            if hours_to_wait < 0:
                hours_to_wait += 24
            savings_percent = float(scenario['expected_savings'].replace('%',''))
            # Calculate dynamic max wait hours based on battery SOC and savings
            # For 8% SOC: battery_multiplier = 0.5 (very critical, <= 8)
            # For 73.3% savings: savings_multiplier = 1.2 (high savings, >= 60)
            # dynamic_max_wait = 6 * 1.2 * 0.5 = 3.6 hours
            battery_soc = scenario['battery_soc']
            if battery_soc <= 8:
                battery_multiplier = 0.5
            elif battery_soc <= 10:
                battery_multiplier = 0.7
            else:
                battery_multiplier = 1.0
            
            if savings_percent >= 80:
                savings_multiplier = 1.5
            elif savings_percent >= 60:
                savings_multiplier = 1.2
            elif savings_percent >= 40:
                savings_multiplier = 1.0
            else:
                savings_multiplier = 0.7
            
            dynamic_max_wait = 6.0 * savings_multiplier * battery_multiplier
            dynamic_max_wait = max(1.0, min(12.0, dynamic_max_wait))
            
            expect_wait = hours_to_wait <= dynamic_max_wait and savings_percent >= 30.0
            if expect_wait:
                assert decision['should_charge'] == False, f"Expected to wait (cheaper price in {hours_to_wait}h within dynamic max {dynamic_max_wait:.1f}h) but got: {decision}"
            else:
                assert decision['should_charge'] == True, f"Expected to charge (wait {hours_to_wait}h exceeds dynamic max {dynamic_max_wait:.1f}h or savings low) but got: {decision}"
        else:
            if scenario['expected_action'] == 'charge':
                assert decision['should_charge'] == True, f"Expected to charge but got: {decision}"
            else:
                assert decision['should_charge'] == False, f"Expected to wait but got: {decision}"
        
        # Verify reason contains expected text
        reason = decision['reason'].lower()
        if scenario.get('expected_reason_dynamic'):
            now_hour = datetime.now().hour
            hours_to_wait = scenario['cheapest_hour'] - now_hour
            if hours_to_wait < 0:
                hours_to_wait += 24
            dynamic_expected = f"waiting {hours_to_wait}h for {scenario['expected_savings']} savings not optimal".lower()
            assert dynamic_expected in reason, f"Expected reason '{dynamic_expected}' not found in '{reason}'"
        elif scenario.get('expected_action_dynamic'):
            now_hour = datetime.now().hour
            hours_to_wait = scenario['cheapest_hour'] - now_hour
            if hours_to_wait < 0:
                hours_to_wait += 24
            savings_text = scenario['expected_savings']
            savings_percent = float(savings_text.replace('%',''))
            # Calculate dynamic max wait hours (same logic as in the main code)
            battery_soc = scenario['battery_soc']
            if battery_soc <= 8:
                battery_multiplier = 0.5
            elif battery_soc <= 10:
                battery_multiplier = 0.7
            else:
                battery_multiplier = 1.0
            
            if savings_percent >= 80:
                savings_multiplier = 1.5
            elif savings_percent >= 60:
                savings_multiplier = 1.2
            elif savings_percent >= 40:
                savings_multiplier = 1.0
            else:
                savings_multiplier = 0.7
            
            dynamic_max_wait = 6.0 * savings_multiplier * battery_multiplier
            dynamic_max_wait = max(1.0, min(12.0, dynamic_max_wait))
            
            expect_wait = hours_to_wait <= dynamic_max_wait and savings_percent >= 30.0
            if expect_wait:
                dynamic_expected = f"much cheaper price in {hours_to_wait}h".lower()
            else:
                dynamic_expected = f"waiting {hours_to_wait}h for {savings_text} savings not optimal".lower()
            assert dynamic_expected in reason, f"Expected reason '{dynamic_expected}' not found in '{reason}'"
        else:
            if scenario.get('expected_reason'):
                assert scenario['expected_reason'].lower() in reason, f"Expected reason '{scenario['expected_reason']}' not found in '{reason}'"
            elif scenario.get('expected_reason_contains'):
                assert scenario['expected_reason_contains'].lower() in reason, f"Expected reason contains '{scenario['expected_reason_contains']}' not found in '{reason}'"
        
        logger.info(f"✓ Test passed: {scenario['name']}")
    
    logger.info("\n🎉 All smart critical charging tests passed!")

def test_configuration_loading():
    """Test that configuration is loaded correctly"""
    logger.info("\n--- Testing Configuration Loading ---")
    
    config = load_config()
    
    # Check battery thresholds
    battery_config = config.get('battery_management', {}).get('soc_thresholds', {})
    assert battery_config.get('critical') == 12, f"Expected critical threshold 12, got {battery_config.get('critical')}"
    assert battery_config.get('emergency') == 5, f"Expected emergency threshold 5, got {battery_config.get('emergency')}"
    
    # Check smart critical charging config
    smart_config = config.get('timing_awareness', {}).get('smart_critical_charging', {})
    assert smart_config.get('enabled') == True, f"Expected smart critical charging enabled, got {smart_config.get('enabled')}"
    # Just verify it exists and is a reasonable value
    max_critical_price = smart_config.get('max_critical_price_pln')
    assert max_critical_price is not None, "Max critical price not configured"
    assert 0.5 <= max_critical_price <= 2.0, f"Max critical price out of range: {max_critical_price}"
    
    logger.info("✓ Configuration loading test passed!")

# Tests are implemented as functions and picked up by pytest; removed direct runner.