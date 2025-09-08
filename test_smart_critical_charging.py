#!/usr/bin/env python3
"""
Test script for Smart Critical Charging Logic
Tests the new price-aware critical battery charging behavior
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from automated_price_charging import AutomatedPriceCharger
from hybrid_charging_logic import HybridChargingLogic
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
            'cheapest_hour': 23,  # 2 hours away
            'expected_action': 'wait',
            'expected_reason': 'much cheaper price'
        },
        {
            'name': 'Critical Level (8% SOC) - High Price, Long Wait',
            'battery_soc': 8,
            'current_price': 1.5,  # High price
            'cheapest_price': 0.4,  # Much cheaper
            'cheapest_hour': 6,  # 8 hours away (next day)
            'expected_action': 'charge',
            'expected_reason': 'waiting too long'
        },
        {
            'name': 'Critical Level (8% SOC) - High Price, Insufficient Savings',
            'battery_soc': 8,
            'current_price': 1.0,  # High price
            'cheapest_price': 0.9,  # Small savings
            'cheapest_hour': 23,  # 2 hours away
            'expected_action': 'charge',
            'expected_reason': 'insufficient savings'
        }
    ]
    
    # Initialize the automated price charger
    charger = AutomatedPriceCharger(config)
    
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
    
    logger.info("\n🎉 All smart critical charging tests passed!")

def test_configuration_loading():
    """Test that configuration is loaded correctly"""
    logger.info("\n--- Testing Configuration Loading ---")
    
    config = load_config()
    
    # Check battery thresholds
    battery_config = config.get('battery_management', {}).get('soc_thresholds', {})
    assert battery_config.get('critical') == 10, f"Expected critical threshold 10, got {battery_config.get('critical')}"
    assert battery_config.get('emergency') == 5, f"Expected emergency threshold 5, got {battery_config.get('emergency')}"
    
    # Check smart critical charging config
    smart_config = config.get('timing_awareness', {}).get('smart_critical_charging', {})
    assert smart_config.get('enabled') == True, f"Expected smart critical charging enabled, got {smart_config.get('enabled')}"
    assert smart_config.get('max_critical_price_pln') == 0.6, f"Expected max critical price 0.6, got {smart_config.get('max_critical_price_pln')}"
    
    logger.info("✓ Configuration loading test passed!")

if __name__ == "__main__":
    try:
        test_configuration_loading()
        test_smart_critical_charging()
        logger.info("\n🎉 All tests completed successfully!")
        logger.info("\nSmart Critical Charging Implementation Summary:")
        logger.info("- Emergency threshold: 5% SOC (always charge)")
        logger.info("- Critical threshold: 10% SOC (price-aware)")
        logger.info("- Max critical price: 0.6 PLN/kWh")
        logger.info("- Max wait time: 6 hours")
        logger.info("- Min savings: 30%")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)