#!/usr/bin/env python3
"""
Test script for Advanced Optimization Rules
Tests the new optimization rules for smart critical charging
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger
import yaml
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def test_optimization_rule_1():
    """Test Rule 1: At 10% SOC with high price, always wait for price drop"""
    logger.info("\n=== Testing Rule 1: 10% SOC + High Price = Wait ===")
    
    config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
    charger = AutomatedPriceCharger(str(config_path))
    
    test_scenarios = [
        {
            'name': '10% SOC + High Price (1.0 PLN/kWh) - Should Wait',
            'battery_soc': 10,
            'current_price': 1.0,  # Above 0.8 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'wait',
            'expected_reason': 'high price'
        },
        {
            'name': '10% SOC + Acceptable Price (0.5 PLN/kWh) - Should Charge',
            'battery_soc': 10,
            'current_price': 0.5,  # Below 0.8 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'charge',
                'expected_reason': 'waiting 9h for 20.0% savings not optimal'
        },
        {
            'name': '9% SOC + High Price (1.0 PLN/kWh) - Should Use Normal Logic',
            'battery_soc': 9,  # Below 10%, not exactly 10%
            'current_price': 1.0,
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'charge',
                'expected_reason': 'waiting 9h for 60.0% savings not optimal'
        }
    ]
    
    for scenario in test_scenarios:
        logger.info(f"\n--- Testing: {scenario['name']} ---")
        
        decision = charger._make_charging_decision(
            battery_soc=scenario['battery_soc'],
            overproduction=0,
            grid_power=0,
            grid_direction='Import',
            current_price=scenario['current_price'],
            cheapest_price=scenario['cheapest_price'],
            cheapest_hour=scenario['cheapest_hour']
        )
        
        logger.info(f"Decision: {decision}")
        
        # Verify expected action
        if scenario['expected_action'] == 'charge':
            assert decision['should_charge'] == True, f"Expected to charge but got: {decision}"
        else:
            assert decision['should_charge'] == False, f"Expected to wait but got: {decision}"
        
        # Verify reason contains expected text
        reason = decision['reason'].lower()
        expected_reason = scenario['expected_reason'].lower()
        assert expected_reason in reason, f"Expected reason '{expected_reason}' not found in '{reason}'"
        
        logger.info(f"✓ Test passed: {scenario['name']}")

def test_optimization_rule_2():
    """Test Rule 2: Proactive charging when PV is poor, weather won't improve, battery <80%, and price is not high"""
    logger.info("\n=== Testing Rule 2: Proactive Charging ===")
    
    config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
    charger = AutomatedPriceCharger(str(config_path))
    
    test_scenarios = [
        {
            'name': 'Proactive Charging - All Conditions Met',
            'battery_soc': 50,  # Below 80%
            'overproduction': -100,  # PV poor (100W, below 200W threshold)
            'current_price': 0.5,  # Below 0.7 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'charge',
            'expected_reason': 'proactive charging'
        },
        {
            'name': 'PV Good - No Proactive Charging',
            'battery_soc': 50,  # Below 80%
            'overproduction': -500,  # PV good (500W, above 200W threshold)
            'current_price': 0.5,  # Below 0.7 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'wait',
            'expected_reason': 'pv overproduction'
        },
        {
            'name': 'Battery High - No Proactive Charging',
            'battery_soc': 85,  # Above 80%
            'overproduction': -100,  # PV poor (100W)
            'current_price': 0.5,  # Below 0.7 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'wait',
            'expected_reason': 'better conditions'
        },
        {
            'name': 'Price High - No Proactive Charging',
            'battery_soc': 50,  # Below 80%
            'overproduction': -100,  # PV poor (100W)
            'current_price': 0.8,  # Above 0.7 threshold
            'cheapest_price': 0.4,
            'cheapest_hour': 23,
            'expected_action': 'wait',
            'expected_reason': 'much cheaper price'
        }
    ]
    
    for scenario in test_scenarios:
        logger.info(f"\n--- Testing: {scenario['name']} ---")
        
        decision = charger._make_charging_decision(
            battery_soc=scenario['battery_soc'],
            overproduction=scenario['overproduction'],
            grid_power=0,
            grid_direction='Import',
            current_price=scenario['current_price'],
            cheapest_price=scenario['cheapest_price'],
            cheapest_hour=scenario['cheapest_hour']
        )
        
        logger.info(f"Decision: {decision}")
        
        # Verify expected action
        if scenario['expected_action'] == 'charge':
            assert decision['should_charge'] == True, f"Expected to charge but got: {decision}"
        else:
            assert decision['should_charge'] == False, f"Expected to wait but got: {decision}"
        
        # Verify reason contains expected text
        reason = decision['reason'].lower()
        expected_reason = scenario['expected_reason'].lower()
        assert expected_reason in reason, f"Expected reason '{expected_reason}' not found in '{reason}'"
        
        logger.info(f"✓ Test passed: {scenario['name']}")

def test_real_world_scenario():
    """Test the real-world scenario from your charging session"""
    logger.info("\n=== Testing Real-World Scenario ===")
    
    config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
    charger = AutomatedPriceCharger(str(config_path))
    
    # Your actual scenario: 18% SOC, 1.577 PLN/kWh, 0.468 PLN/kWh at 23:00
    logger.info("Testing your actual scenario: 18% SOC, 1.577 PLN/kWh current, 0.468 PLN/kWh at 23:00")
    
    decision = charger._make_charging_decision(
        battery_soc=18,  # Your actual battery level
        overproduction=0,  # No PV at night
        grid_power=0,
        grid_direction='Import',
        current_price=1.577,  # Your actual high price
        cheapest_price=0.468,  # Your actual cheap price
        cheapest_hour=23  # Your actual cheap hour
    )
    
    logger.info(f"Decision: {decision}")
    
    # With the new logic, this should wait for the better price
    assert decision['should_charge'] == False, f"Expected to wait for better price but got: {decision}"
    assert 'much cheaper price' in decision['reason'].lower(), f"Expected 'much cheaper price' in reason: {decision['reason']}"
    
    logger.info("✓ Real-world scenario test passed - system would now wait for better price!")

def test_configuration_loading():
    """Test that new configuration parameters are loaded correctly"""
    logger.info("\n=== Testing Configuration Loading ===")
    
    config = load_config()
    
    # Check optimization rules config
    optimization_rules = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {})
    
    assert optimization_rules.get('wait_at_10_percent_if_high_price') == True, "Rule 1 not enabled"
    assert optimization_rules.get('high_price_threshold_pln') == 0.8, f"High price threshold incorrect: {optimization_rules.get('high_price_threshold_pln')}"
    assert optimization_rules.get('proactive_charging_enabled') == True, "Rule 2 not enabled"
    assert optimization_rules.get('pv_poor_threshold_w') == 200, f"PV poor threshold incorrect: {optimization_rules.get('pv_poor_threshold_w')}"
    assert optimization_rules.get('battery_target_threshold') == 80, f"Battery target threshold incorrect: {optimization_rules.get('battery_target_threshold')}"
    assert optimization_rules.get('max_proactive_price_pln') == 0.7, f"Max proactive price incorrect: {optimization_rules.get('max_proactive_price_pln')}"
    
    logger.info("✓ Configuration loading test passed!")

if __name__ == "__main__":
    try:
        test_configuration_loading()
        test_optimization_rule_1()
        test_optimization_rule_2()
        test_real_world_scenario()
        
        logger.info("\n🎉 All advanced optimization rule tests passed!")
        logger.info("\nAdvanced Optimization Rules Summary:")
        logger.info("Rule 1: At 10% SOC with high price (>0.8 PLN/kWh) → Always wait")
        logger.info("Rule 2: PV poor (<200W) + battery <80% + price ≤0.7 PLN/kWh + weather poor → Proactive charge")
        logger.info("\nYour scenario (18% SOC, 1.577 PLN/kWh) would now wait for 0.468 PLN/kWh at 23:00!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)