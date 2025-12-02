#!/usr/bin/env python3
"""
Test that enhanced aggressive charging decisions are respected and not overridden by legacy fallback.

This test verifies the fix for the issue where:
- At 11:05:22, price was 1.122 PLN/kWh (matched cheapest in old data)
- At 11:20:59, better window at 11:30 was identified with 0.661 PLN/kWh
- The legacy fallback was incorrectly triggering charging at the higher price

The fix ensures that when enhanced aggressive charging returns a "don't charge" decision
(because it found a better window), the legacy fallback doesn't override that smart decision.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from automated_price_charging import AutomatedPriceCharger


@pytest.fixture
def config_with_enhanced_aggressive():
    """Configuration with enhanced aggressive charging enabled"""
    return {
        'coordinator': {
            'cheapest_price_aggressive_charging': {
                'enabled': True,
                'price_threshold_percent': 10,
                'super_cheap_threshold': 0.20,
                'very_cheap_threshold': 0.30,
                'cheap_threshold': 0.40,
                'moderate_threshold': 0.60,
                'expensive_threshold': 0.80,
                'min_battery_soc_for_aggressive': 30,
                'max_battery_soc_for_aggressive': 85,
                'use_percentile_analysis': True,
                'percentile_threshold': 25,
                'use_d1_forecast': True,
                'min_tomorrow_price_diff_percent': 30
            },
            'interim_cost_analysis': {
                'enabled': True
            },
            'optimization_rules': {}
        },
        'battery_selling': {'enabled': False},
        'tariff': {}
    }


@pytest.fixture
def config_without_enhanced_aggressive():
    """Configuration with enhanced aggressive charging disabled (legacy only)"""
    config = {
        'coordinator': {
            'cheapest_price_aggressive_charging': {
                'enabled': False  # Enhanced disabled
            },
            'timing_awareness': {
                'smart_critical_charging': {
                    'optimization_rules': {
                        'proactive_charging_enabled': False  # Disable proactive to test legacy only
                    }
                }
            }
        },
        'battery_selling': {'enabled': False},
        'battery_management': {
            'soc_thresholds': {
                'critical': 12,
                'emergency': 5
            }
        },
        'tariff': {}
    }
    return config


def test_enhanced_aggressive_blocks_legacy_fallback(config_with_enhanced_aggressive):
    """Test that enhanced aggressive charging decision blocks legacy fallback"""
    
    charger = AutomatedPriceCharger(config_with_enhanced_aggressive)
    
    # Simulate the scenario:
    # - Current price: 1.122 PLN/kWh (matches cheapest in limited data)
    # - Better window exists later at 0.661 PLN/kWh
    # - Enhanced aggressive should return "don't charge" to wait for better window
    # - Legacy fallback should NOT override this decision
    
    battery_soc = 65
    overproduction = 0
    grid_power = 500
    grid_direction = "import"
    current_price = 1.122
    cheapest_price = 1.122  # Same as current (would trigger legacy logic)
    cheapest_hour = 11
    
    price_data = {
        'value': [
            {'datetime': '2025-12-01T11:00:00', 'value': 1.122},
            {'datetime': '2025-12-01T11:30:00', 'value': 0.661},  # Better window!
            {'datetime': '2025-12-01T12:00:00', 'value': 0.665},
        ]
    }
    
    # Mock the enhanced aggressive charging to return "don't charge"
    with patch.object(charger.enhanced_aggressive, 'should_charge_aggressively') as mock_enhanced:
        from enhanced_aggressive_charging import ChargingDecision, PriceCategory
        
        # Enhanced logic says "don't charge, wait for better window"
        mock_enhanced.return_value = ChargingDecision(
            should_charge=False,
            reason="Better window at 11:30 (0.661 PLN/kWh): net benefit 4.61 PLN",
            priority='low',
            confidence=0.8,
            target_soc=battery_soc,
            estimated_duration_hours=0.0,
            price_category=PriceCategory.VERY_EXPENSIVE,
            opportunity_cost=4.61
        )
        
        decision = charger._make_charging_decision(
            battery_soc=battery_soc,
            overproduction=overproduction,
            grid_power=grid_power,
            grid_direction=grid_direction,
            current_price=current_price,
            cheapest_price=cheapest_price,
            cheapest_hour=cheapest_hour,
            price_data=price_data
        )
        
        # The decision should NOT be to charge
        # Even though current_price == cheapest_price (which would trigger legacy fallback),
        # the enhanced aggressive decision should be respected
        assert decision['should_charge'] == False, \
            f"Enhanced aggressive 'don't charge' decision should be respected, not overridden by legacy fallback. Got: {decision}"


def test_legacy_fallback_works_when_enhanced_disabled(config_without_enhanced_aggressive):
    """Test that legacy fallback still works when enhanced aggressive is disabled"""
    
    charger = AutomatedPriceCharger(config_without_enhanced_aggressive)
    
    battery_soc = 65
    overproduction = 0
    grid_power = 500
    grid_direction = "import"
    current_price = 0.40
    cheapest_price = 0.40
    cheapest_hour = 11
    
    price_data = {
        'value': [
            {'datetime': '2025-12-01T11:00:00', 'value': 0.40},
            {'datetime': '2025-12-01T12:00:00', 'value': 0.50},
        ]
    }
    
    decision = charger._make_charging_decision(
        battery_soc=battery_soc,
        overproduction=overproduction,
        grid_power=grid_power,
        grid_direction=grid_direction,
        current_price=current_price,
        cheapest_price=cheapest_price,
        cheapest_hour=cheapest_hour,
        price_data=price_data
    )
    
    # When enhanced aggressive is disabled, some charging decision should be made
    # (could be legacy aggressive or proactive charging depending on conditions)
    assert decision['should_charge'] == True, \
        "Charging should occur when enhanced aggressive is disabled and conditions are met"
    # Just verify we got a reasonable decision, not necessarily legacy aggressive
    # (proactive charging may be prioritized based on conditions)
    assert decision['reason'] is not None and len(decision['reason']) > 0


def test_enhanced_aggressive_charge_decision_is_returned(config_with_enhanced_aggressive):
    """Test that when enhanced aggressive says 'charge', that decision is returned"""
    
    charger = AutomatedPriceCharger(config_with_enhanced_aggressive)
    
    battery_soc = 65
    current_price = 0.15  # Super cheap
    
    price_data = {
        'value': [
            {'datetime': '2025-12-01T11:00:00', 'value': 0.15},
            {'datetime': '2025-12-01T12:00:00', 'value': 0.50},
        ]
    }
    
    with patch.object(charger.enhanced_aggressive, 'should_charge_aggressively') as mock_enhanced:
        from enhanced_aggressive_charging import ChargingDecision, PriceCategory
        
        # Enhanced logic says "charge now - super cheap"
        mock_enhanced.return_value = ChargingDecision(
            should_charge=True,
            reason="SUPER CHEAP price 0.15 PLN/kWh - charge to 100%",
            priority='high',
            confidence=0.95,
            target_soc=100,
            estimated_duration_hours=2.0,
            price_category=PriceCategory.SUPER_CHEAP,
            opportunity_cost=0.0
        )
        
        decision = charger._make_charging_decision(
            battery_soc=battery_soc,
            overproduction=0,
            grid_power=500,
            grid_direction="import",
            current_price=current_price,
            cheapest_price=0.15,
            cheapest_hour=11,
            price_data=price_data
        )
        
        # The charge decision should be returned
        assert decision['should_charge'] == True
        assert decision['target_soc'] == 100
        assert 'SUPER CHEAP' in decision['reason']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
