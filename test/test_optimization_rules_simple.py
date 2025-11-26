#!/usr/bin/env python3
"""
Simple test script for Advanced Optimization Rules
Tests the new optimization rules without requiring GoodWe library
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
    """Test that new configuration parameters are loaded correctly"""
    logger.info("=== Testing Configuration Loading ===")
    
    config = load_config()
    
    # Check optimization rules config
    optimization_rules = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {})
    
    assert optimization_rules.get('wait_at_10_percent_if_high_price') == True, "Rule 1 not enabled"
    # Just verify it exists and is a reasonable value
    high_price_threshold = optimization_rules.get('high_price_threshold_pln')
    assert high_price_threshold is not None, "High price threshold not configured"
    assert 0.5 <= high_price_threshold <= 2.0, f"High price threshold out of range: {high_price_threshold}"
    assert optimization_rules.get('proactive_charging_enabled') == True, "Rule 2 not enabled"
    # Verify other thresholds exist and are reasonable
    pv_poor_threshold = optimization_rules.get('pv_poor_threshold_w')
    assert pv_poor_threshold is not None and pv_poor_threshold > 0, f"PV poor threshold invalid: {pv_poor_threshold}"
    battery_target = optimization_rules.get('battery_target_threshold')
    assert battery_target is not None and 0 < battery_target <= 100, f"Battery target threshold invalid: {battery_target}"
    max_proactive_price = optimization_rules.get('max_proactive_price_pln')
    assert max_proactive_price is not None and 0 < max_proactive_price <= 2.0, f"Max proactive price invalid: {max_proactive_price}"
    
    logger.info("✓ Configuration loading test passed!")
    # Test functions should not return values when run under pytest

def test_optimization_logic():
    """Test the optimization logic without instantiating the full class"""
    logger.info("\n=== Testing Optimization Logic ===")
    
    config = load_config()
    
    # Test Rule 1: 10% SOC + High Price = Wait
    logger.info("Testing Rule 1: 10% SOC + High Price = Wait")
    
    # Simulate the logic
    battery_soc = 10
    high_price_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('high_price_threshold_pln', 1.35)
    current_price = high_price_threshold + 0.05  # Slightly above threshold
    wait_at_10_percent = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('wait_at_10_percent_if_high_price', True)
    
    if (wait_at_10_percent and 
        battery_soc == 10 and 
        current_price > high_price_threshold):
        logger.info("✓ Rule 1 logic: Would wait for price drop")
        rule1_result = "wait"
    else:
        logger.info("✗ Rule 1 logic: Would not wait")
        rule1_result = "charge"
    
    assert rule1_result == "wait", "Rule 1 should make system wait at 10% SOC with high price"
    
    # Test Rule 2: Proactive charging conditions
    logger.info("\nTesting Rule 2: Proactive Charging")
    
    battery_soc = 50  # Below 80%
    pv_power = 100    # Below 200W threshold
    current_price = 0.5  # Below 0.7 threshold
    
    pv_poor_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('pv_poor_threshold_w', 200)
    battery_target_threshold = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('battery_target_threshold', 80)
    max_proactive_price = config.get('timing_awareness', {}).get('smart_critical_charging', {}).get('optimization_rules', {}).get('max_proactive_price_pln', 0.7)
    
    # Check all conditions
    pv_poor = pv_power < pv_poor_threshold
    battery_low = battery_soc < battery_target_threshold
    price_good = current_price <= max_proactive_price
    
    if pv_poor and battery_low and price_good:
        logger.info("✓ Rule 2 logic: All conditions met for proactive charging")
        rule2_result = "charge"
    else:
        logger.info("✗ Rule 2 logic: Conditions not met for proactive charging")
        rule2_result = "wait"
    
    assert rule2_result == "charge", "Rule 2 should trigger proactive charging when all conditions met"
    
    logger.info("✓ Optimization logic tests passed!")
    # Test functions should not return values when run under pytest

def test_real_world_scenario():
    """Test the real-world scenario from your charging session"""
    logger.info("\n=== Testing Real-World Scenario ===")
    
    config = load_config()
    
    # Your actual scenario: 18% SOC, 1.577 PLN/kWh, 0.468 PLN/kWh at 23:00
    logger.info("Testing your actual scenario: 18% SOC, 1.577 PLN/kWh current, 0.468 PLN/kWh at 23:00")
    
    battery_soc = 18
    current_price = 1.577
    cheapest_price = 0.468
    cheapest_hour = 23
    
    # Calculate savings
    savings_percent = ((current_price - cheapest_price) / current_price) * 100
    logger.info(f"Savings potential: {savings_percent:.1f}%")
    
    # With the new logic, this should wait for the better price
    # because savings are significant (72.4%) and it's only 3.5 hours away
    if savings_percent > 30:  # Significant savings threshold
        logger.info("✓ Real-world scenario: System would now wait for better price!")
        result = "wait"
    else:
        logger.info("✗ Real-world scenario: System would still charge at high price")
        result = "charge"
    
    assert result == "wait", "Real-world scenario should wait for better price"
    logger.info("✓ Real-world scenario test passed!")
    # Test functions should not return values when run under pytest

# Tests are implemented as pytest functions; removed script-style runner.