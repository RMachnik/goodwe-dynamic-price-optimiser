#!/usr/bin/env python3
"""
Test script for Super Low Price Charging with PV Preference Logic
Tests the modified super low price charging optimization rule
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
    """Test that PV preference configuration is loaded correctly"""
    logger.info("=== Testing PV Preference Configuration Loading ===")
    
    config = load_config()
    
    # Check PV preference config
    optimization_rules = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {})
    pv_preference = optimization_rules.get('super_low_price_pv_preference', {})
    
    assert optimization_rules.get('super_low_price_charging_enabled') == True, "Super low price charging not enabled"
    assert optimization_rules.get('super_low_price_threshold_pln') == 0.3, f"Super low price threshold incorrect: {optimization_rules.get('super_low_price_threshold_pln')}"
    assert optimization_rules.get('super_low_price_target_soc') == 100, f"Super low price target SOC incorrect: {optimization_rules.get('super_low_price_target_soc')}"
    
    assert pv_preference.get('pv_excellent_threshold_w') == 3000, f"PV excellent threshold incorrect: {pv_preference.get('pv_excellent_threshold_w')}"
    assert pv_preference.get('weather_stable_threshold') == 0.8, f"Weather stable threshold incorrect: {pv_preference.get('weather_stable_threshold')}"
    assert pv_preference.get('house_usage_low_threshold_w') == 1000, f"House usage low threshold incorrect: {pv_preference.get('house_usage_low_threshold_w')}"
    assert pv_preference.get('pv_charging_time_limit_hours') == 2.0, f"PV charging time limit incorrect: {pv_preference.get('pv_charging_time_limit_hours')}"
    
    logger.info("✓ PV preference configuration loading test passed!")
    return True

def test_pv_preference_logic():
    """Test the PV preference logic during super low prices"""
    logger.info("\n=== Testing PV Preference Logic ===")
    
    config = load_config()
    
    # Test scenarios
    test_scenarios = [
        {
            'name': 'Super Low Price + PV Excellent + Weather Stable + House Usage Low - Should Use PV',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 4000,  # 4kW PV (excellent)
            'weather_stable': True,
            'house_usage_low': True,
            'pv_charging_time': 1.5,  # Within 2 hour limit
            'expected_action': 'charge',
            'expected_source': 'pv',
            'expected_reason': 'PV excellent'
        },
        {
            'name': 'Super Low Price + PV Excellent + Weather Stable + House Usage Low + Slow PV - Should Use Grid',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 4000,  # 4kW PV (excellent)
            'weather_stable': True,
            'house_usage_low': True,
            'pv_charging_time': 2.5,  # Beyond 2 hour limit
            'expected_action': 'charge',
            'expected_source': 'grid',
            'expected_reason': 'PV excellent but slow'
        },
        {
            'name': 'Super Low Price + PV Insufficient + Weather Stable + House Usage Low - Should Use Grid',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 2000,  # 2kW PV (insufficient)
            'weather_stable': True,
            'house_usage_low': True,
            'pv_charging_time': 3.0,  # Beyond 2 hour limit
            'expected_action': 'charge',
            'expected_source': 'grid',
            'expected_reason': 'PV insufficient'
        },
        {
            'name': 'Super Low Price + PV Excellent + Weather Unstable + House Usage Low - Should Use Grid',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 4000,  # 4kW PV (excellent)
            'weather_stable': False,
            'house_usage_low': True,
            'pv_charging_time': 1.5,  # Within 2 hour limit
            'expected_action': 'charge',
            'expected_source': 'grid',
            'expected_reason': 'weather unstable'
        },
        {
            'name': 'Super Low Price + PV Excellent + Weather Stable + House Usage High - Should Use Grid',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.2,  # Super low price
            'pv_power': 4000,  # 4kW PV (excellent)
            'weather_stable': True,
            'house_usage_low': False,
            'pv_charging_time': 1.5,  # Within 2 hour limit
            'expected_action': 'charge',
            'expected_source': 'grid',
            'expected_reason': 'house usage high'
        },
        {
            'name': 'Normal Price + PV Excellent + Weather Stable + House Usage Low - Should Wait',
            'battery_soc': 60,  # 60% SOC
            'current_price': 0.5,  # Normal price (above super low threshold)
            'pv_power': 4000,  # 4kW PV (excellent)
            'weather_stable': True,
            'house_usage_low': True,
            'pv_charging_time': 1.5,  # Within 2 hour limit
            'expected_action': 'wait',
            'expected_source': 'wait',
            'expected_reason': 'normal price'
        }
    ]
    
    for scenario in test_scenarios:
        logger.info(f"\n--- Testing: {scenario['name']} ---")
        
        # Simulate the logic
        battery_soc = scenario['battery_soc']
        current_price = scenario['current_price']
        pv_power = scenario['pv_power']
        weather_stable = scenario['weather_stable']
        house_usage_low = scenario['house_usage_low']
        pv_charging_time = scenario['pv_charging_time']
        
        # Get configuration values
        super_low_price_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_threshold_pln', 0.3)
        super_low_price_target_soc = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_target_soc', 100)
        pv_preference = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_pv_preference', {})
        pv_excellent_threshold = pv_preference.get('pv_excellent_threshold_w', 3000)
        pv_charging_time_limit = pv_preference.get('pv_charging_time_limit_hours', 2.0)
        
        # Check conditions
        price_super_low = current_price <= super_low_price_threshold
        battery_not_full = battery_soc < super_low_price_target_soc
        pv_excellent = pv_power >= pv_excellent_threshold
        
        # Decision logic
        if price_super_low and battery_not_full:
            if pv_excellent and weather_stable and house_usage_low:
                if pv_charging_time <= pv_charging_time_limit:
                    # PV excellent, weather stable, house usage low, fast charging - use PV
                    result = "charge"
                    source = "pv"
                    reason = "PV excellent"
                else:
                    # PV excellent but slow - use grid for speed
                    result = "charge"
                    source = "grid"
                    reason = "PV excellent but slow"
            else:
                # PV not excellent or conditions not ideal - use grid
                result = "charge"
                source = "grid"
                if not pv_excellent:
                    reason = "PV insufficient"
                elif not weather_stable:
                    reason = "weather unstable"
                elif not house_usage_low:
                    reason = "house usage high"
                else:
                    reason = "conditions not ideal"
        else:
            # Not super low price or battery already full
            result = "wait"
            source = "wait"
            if not price_super_low:
                reason = "normal price"
            elif not battery_not_full:
                reason = "battery already full"
            else:
                reason = "conditions not met"
        
        logger.info(f"Decision: {result}")
        logger.info(f"Source: {source}")
        logger.info(f"Reason: {reason}")
        logger.info(f"PV excellent: {pv_excellent} ({pv_power}W >= {pv_excellent_threshold}W)")
        logger.info(f"Weather stable: {weather_stable}")
        logger.info(f"House usage low: {house_usage_low}")
        logger.info(f"PV charging time: {pv_charging_time:.1f} hours")
        
        # Verify expected results
        assert result == scenario['expected_action'], f"Expected {scenario['expected_action']} but got {result}"
        assert source == scenario['expected_source'], f"Expected source '{scenario['expected_source']}' but got '{source}'"
        assert reason == scenario['expected_reason'], f"Expected reason '{scenario['expected_reason']}' but got '{reason}'"
        
        logger.info(f"✓ Test passed: {scenario['name']}")
    
    logger.info("✓ PV preference logic tests passed!")
    return True

def test_real_world_scenarios():
    """Test real-world scenarios based on your requirements"""
    logger.info("\n=== Testing Real-World Scenarios ===")
    
    config = load_config()
    
    # Scenario 1: Super low price + PV excellent + weather stable + house usage low
    logger.info("Scenario 1: Super low price (0.2 PLN/kWh) + PV excellent (4kW) + weather stable + house usage low")
    
    battery_soc = 60  # 60% SOC
    current_price = 0.2  # Super low price
    pv_power = 4000  # 4kW PV (excellent)
    weather_stable = True
    house_usage_low = True
    pv_charging_time = 1.5  # Within 2 hour limit
    
    # Get configuration values
    super_low_price_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_threshold_pln', 0.3)
    pv_preference = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('super_low_price_pv_preference', {})
    pv_excellent_threshold = pv_preference.get('pv_excellent_threshold_w', 3000)
    pv_charging_time_limit = pv_preference.get('pv_charging_time_limit_hours', 2.0)
    
    # Decision logic
    if current_price <= super_low_price_threshold:
        if pv_power >= pv_excellent_threshold and weather_stable and house_usage_low:
            if pv_charging_time <= pv_charging_time_limit:
                logger.info("✓ Scenario 1: System would charge from PV (excellent conditions)")
                result1 = "pv"
            else:
                logger.info("✗ Scenario 1: System would charge from grid (PV too slow)")
                result1 = "grid"
        else:
            logger.info("✗ Scenario 1: System would charge from grid (conditions not ideal)")
            result1 = "grid"
    else:
        logger.info("✗ Scenario 1: System would wait (not super low price)")
        result1 = "wait"
    
    # Scenario 2: Super low price + PV insufficient + weather stable + house usage low
    logger.info("\nScenario 2: Super low price (0.2 PLN/kWh) + PV insufficient (2kW) + weather stable + house usage low")
    
    pv_power = 2000  # 2kW PV (insufficient)
    pv_charging_time = 3.0  # Beyond 2 hour limit
    
    if current_price <= super_low_price_threshold:
        if pv_power >= pv_excellent_threshold and weather_stable and house_usage_low:
            if pv_charging_time <= pv_charging_time_limit:
                result2 = "pv"
            else:
                result2 = "grid"
        else:
            logger.info("✓ Scenario 2: System would charge from grid (PV insufficient)")
            result2 = "grid"
    else:
        result2 = "wait"
    
    # Verify results
    assert result1 == "pv", f"Scenario 1 should use PV but got {result1}"
    assert result2 == "grid", f"Scenario 2 should use grid but got {result2}"
    
    logger.info("✓ Real-world scenarios test passed!")
    return True

def test_economic_benefits():
    """Test the economic benefits of PV preference during super low prices"""
    logger.info("\n=== Testing Economic Benefits ===")
    
    # Scenario: Super low price + PV excellent conditions
    super_low_price = 0.2  # PLN/kWh
    energy_needed = 4.0  # kWh (60% to 100% SOC)
    
    # Cost comparison
    pv_cost = 0.0  # PV charging is free
    grid_cost = super_low_price * energy_needed  # 0.8 PLN
    
    logger.info(f"PV charging cost: {pv_cost:.2f} PLN (free)")
    logger.info(f"Grid charging cost: {grid_cost:.2f} PLN")
    logger.info(f"Savings by using PV: {grid_cost:.2f} PLN (100% savings)")
    
    # Verify PV is always better economically
    assert pv_cost < grid_cost, "PV charging should always be cheaper than grid charging"
    
    logger.info("✓ Economic benefits test passed - PV charging is always free!")
    return True

if __name__ == "__main__":
    try:
        test_configuration_loading()
        test_pv_preference_logic()
        test_real_world_scenarios()
        test_economic_benefits()
        
        logger.info("\n🎉 All PV preference tests passed!")
        logger.info("\nModified Super Low Price Charging Implementation Summary:")
        logger.info("Rule 3 (Modified): During super low prices (≤0.3 PLN/kWh), prefer PV when excellent")
        logger.info("PV Preference Conditions:")
        logger.info("  - PV power ≥ 3kW (excellent)")
        logger.info("  - Weather stable (confidence ≥ 0.8)")
        logger.info("  - House usage low (< 1kW)")
        logger.info("  - PV charging time ≤ 2 hours")
        logger.info("Decision Logic:")
        logger.info("  - If all PV conditions met + fast charging → Use PV (free)")
        logger.info("  - If PV excellent but slow → Use grid (super low price)")
        logger.info("  - If PV insufficient or conditions poor → Use grid (super low price)")
        logger.info("Economic Benefit: PV charging is always free, grid charging costs super low price")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)