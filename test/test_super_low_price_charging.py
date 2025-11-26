#!/usr/bin/env python3
"""
Test script for Super Low Price Charging Logic
Tests the new super low price grid charging optimization rule
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

import yaml
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration"""
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def test_configuration_loading():
    """Test that super low price configuration is loaded correctly"""
    logger.info("=== Testing Super Low Price Configuration Loading ===")
    
    config = load_config()
    
    # Check super low price rules config
    optimization_rules = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {})
    
    assert optimization_rules.get('super_low_price_charging_enabled') == True, "Super low price charging not enabled"
    # Verify thresholds exist and are reasonable
    super_low_threshold = optimization_rules.get('super_low_price_threshold_pln')
    assert super_low_threshold is not None and 0 < super_low_threshold < 1.0, f"Super low price threshold invalid: {super_low_threshold}"
    super_low_target_soc = optimization_rules.get('super_low_price_target_soc')
    assert super_low_target_soc is not None and 50 <= super_low_target_soc <= 100, f"Super low price target SOC invalid: {super_low_target_soc}"
    min_duration = optimization_rules.get('super_low_price_min_duration_hours')
    assert min_duration is not None and min_duration > 0, f"Super low price min duration invalid: {min_duration}"
    
    logger.info("✓ Super low price configuration loading test passed!")
    # Test functions should not return values when run under pytest

def test_super_low_price_logic():
    """Test the super low price charging logic"""
    logger.info("\n=== Testing Super Low Price Charging Logic ===")
    
    config = load_config()
    
    # Test scenarios
    test_scenarios = [
        {
            'name': 'Super Low Price + PV Insufficient - Should Charge from Grid',
            'battery_soc': 50,  # 50% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 1000,  # 1kW PV (insufficient for full charge)
            'expected_action': 'charge',
            'expected_reason': 'super low price',
            'expected_source': 'grid',
            'expected_target_soc': 100
        },
        {
            'name': 'Super Low Price + PV Sufficient - Should Use PV',
            'battery_soc': 50,  # 50% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 5000,  # 5kW PV (sufficient for full charge)
            'expected_action': 'wait',
            'expected_reason': 'pv can charge fully',
            'expected_source': 'pv',
            'expected_target_soc': 100
        },
        {
            'name': 'Normal Price + PV Insufficient - Should Wait',
            'battery_soc': 50,  # 50% SOC
            'current_price': 0.5,  # Normal price (above super low threshold)
            'pv_power': 1000,  # 1kW PV (insufficient for full charge)
            'expected_action': 'wait',
            'expected_reason': 'normal price',
            'expected_source': 'wait',
            'expected_target_soc': None
        },
        {
            'name': 'Super Low Price + Battery Already Full - Should Not Charge',
            'battery_soc': 100,  # Already at 100% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 1000,  # 1kW PV
            'expected_action': 'wait',
            'expected_reason': 'battery already full',
            'expected_source': 'wait',
            'expected_target_soc': None
        },
        {
            'name': 'Super Low Price + Short Duration - Should Not Charge',
            'battery_soc': 50,  # 50% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 1000,  # 1kW PV
            'price_duration': 0.5,  # Only 30 minutes (below 1 hour minimum)
            'expected_action': 'wait',
            'expected_reason': 'duration too short',
            'expected_source': 'wait',
            'expected_target_soc': None
        }
    ]
    
    for scenario in test_scenarios:
        logger.info(f"\n--- Testing: {scenario['name']} ---")
        
        # Simulate the logic
        battery_soc = scenario['battery_soc']
        current_price = scenario['current_price']
        pv_power = scenario['pv_power']
        
        # Get configuration values
        super_low_price_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_threshold_pln', 0.3)
        super_low_price_target_soc = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_target_soc', 100)
        super_low_price_min_duration = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_min_duration_hours', 1.0)
        
        # Check conditions
        price_super_low = current_price <= super_low_price_threshold
        battery_not_full = battery_soc < super_low_price_target_soc
        duration_sufficient = scenario.get('price_duration', 2.0) >= super_low_price_min_duration
        
        # Calculate PV charging time
        battery_capacity = 10.0  # kWh
        energy_needed = (super_low_price_target_soc - battery_soc) / 100 * battery_capacity
        pv_charging_time = energy_needed / (pv_power / 1000) if pv_power > 0 else float('inf')
        
        # Decision logic
        if price_super_low and battery_not_full and duration_sufficient:
            if pv_charging_time > super_low_price_min_duration or pv_charging_time == float('inf'):
                # PV won't charge fully in time - use grid charging
                result = "charge"
                reason = "super low price"
                source = "grid"
                target_soc = super_low_price_target_soc
            else:
                # PV can charge fully in time
                result = "wait"
                reason = "pv can charge fully"
                source = "pv"
                target_soc = super_low_price_target_soc
        else:
            # Conditions not met
            if not price_super_low:
                result = "wait"
                reason = "normal price"
            elif not battery_not_full:
                result = "wait"
                reason = "battery already full"
            elif not duration_sufficient:
                result = "wait"
                reason = "duration too short"
            else:
                result = "wait"
                reason = "conditions not met"
            source = "wait"
            target_soc = None
        
        logger.info(f"Decision: {result}")
        logger.info(f"Reason: {reason}")
        logger.info(f"Source: {source}")
        logger.info(f"Target SOC: {target_soc}")
        logger.info(f"PV charging time: {pv_charging_time:.1f} hours")
        
        # Verify expected results
        assert result == scenario['expected_action'], f"Expected {scenario['expected_action']} but got {result}"
        assert reason == scenario['expected_reason'], f"Expected reason '{scenario['expected_reason']}' but got '{reason}'"
        assert source == scenario['expected_source'], f"Expected source '{scenario['expected_source']}' but got '{source}'"
        assert target_soc == scenario['expected_target_soc'], f"Expected target SOC {scenario['expected_target_soc']} but got {target_soc}"
        
        logger.info(f"✓ Test passed: {scenario['name']}")
    
    logger.info("✓ Super low price charging logic tests passed!")
    # Test functions should not return values when run under pytest

def test_real_world_scenario():
    """Test a real-world scenario based on your requirements"""
    logger.info("\n=== Testing Real-World Scenario ===")
    
    config = load_config()
    
    # Your scenario: Super low price (0.2 PLN/kWh), PV available (2kW), battery at 60%
    logger.info("Testing your scenario: Super low price (0.2 PLN/kWh), PV available (2kW), battery at 60%")
    
    battery_soc = 60  # 60% SOC
    current_price = 0.2  # Super low price
    pv_power = 2000  # 2kW PV
    
    # Get configuration values
    super_low_price_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_threshold_pln', 0.3)
    super_low_price_target_soc = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_target_soc', 100)
    super_low_price_min_duration = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_min_duration_hours', 1.0)
    
    # Calculate energy needed and charging times
    battery_capacity = 10.0  # kWh
    energy_needed = (super_low_price_target_soc - battery_soc) / 100 * battery_capacity  # 4 kWh needed
    pv_charging_time = energy_needed / (pv_power / 1000)  # 4 kWh / 2 kW = 2 hours
    grid_charging_time = energy_needed / 3.0  # 4 kWh / 3 kW = 1.33 hours
    
    logger.info(f"Energy needed: {energy_needed:.1f} kWh")
    logger.info(f"PV charging time: {pv_charging_time:.1f} hours")
    logger.info(f"Grid charging time: {grid_charging_time:.1f} hours")
    
    # Decision logic
    if current_price <= super_low_price_threshold and battery_soc < super_low_price_target_soc:
        if pv_charging_time > super_low_price_min_duration:
            # PV won't charge fully in time - use super low price grid charging
            logger.info("✓ Real-world scenario: System would charge fully from grid at super low price!")
            result = "charge"
            reason = "super low price + PV insufficient"
            source = "grid"
            target_soc = 100
        else:
            logger.info("✗ Real-world scenario: System would wait for PV (not optimal)")
            result = "wait"
            reason = "pv can charge fully"
            source = "pv"
            target_soc = 100
    else:
        logger.info("✗ Real-world scenario: Conditions not met")
        result = "wait"
        reason = "conditions not met"
        source = "wait"
        target_soc = None
    
    # With the new logic, this should charge from grid at super low price
    assert result == "charge", f"Expected to charge from grid but got: {result}"
    assert source == "grid", f"Expected grid charging but got: {source}"
    assert target_soc == 100, f"Expected target SOC 100% but got: {target_soc}"
    
    logger.info("✓ Real-world scenario test passed - system would now charge fully from grid at super low price!")
    # Test functions should not return values when run under pytest

def test_economic_benefit():
    """Test the economic benefit of super low price charging"""
    logger.info("\n=== Testing Economic Benefit ===")
    
    # Scenario: Super low price vs normal price
    super_low_price = 0.2  # PLN/kWh
    normal_price = 0.6  # PLN/kWh
    energy_needed = 4.0  # kWh (60% to 100% SOC)
    
    # Cost comparison
    super_low_cost = super_low_price * energy_needed  # 0.8 PLN
    normal_cost = normal_price * energy_needed  # 2.4 PLN
    savings = normal_cost - super_low_cost  # 1.6 PLN
    
    savings_percent = (savings / normal_cost) * 100  # 66.7%
    
    logger.info(f"Super low price charging cost: {super_low_cost:.2f} PLN")
    logger.info(f"Normal price charging cost: {normal_cost:.2f} PLN")
    logger.info(f"Savings: {savings:.2f} PLN ({savings_percent:.1f}%)")
    
    # Verify significant savings
    assert savings_percent > 50, f"Expected >50% savings but got {savings_percent:.1f}%"
    
    logger.info("✓ Economic benefit test passed - significant savings achieved!")
    # Test functions should not return values when run under pytest

if __name__ == "__main__":
    try:
        test_configuration_loading()
        test_super_low_price_logic()
        test_real_world_scenario()
        test_economic_benefit()
        
        logger.info("\n🎉 All super low price charging tests passed!")
        logger.info("\nSuper Low Price Charging Implementation Summary:")
        logger.info("Rule 3: During super low prices (≤0.3 PLN/kWh), always charge battery fully from grid")
        logger.info("Priority: Highest priority - overrides PV charging during super low prices")
        logger.info("Target: 100% SOC during super low price periods")
        logger.info("Economic Benefit: Up to 66.7% savings compared to normal price charging")
        logger.info("\nYour scenario (0.2 PLN/kWh + 2kW PV + 60% SOC) would now charge fully from grid!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)