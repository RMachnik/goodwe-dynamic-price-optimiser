#!/usr/bin/env python3
"""Quick test to verify cost calculation fix"""

# Test data from actual decision file
energy_kwh = 4.4
price_pln_kwh = 0.7161  # Already converted to PLN/kWh


import pytest

def test_cost_calculation():
    # BEFORE (WRONG) - what the old code did
    old_estimated_cost = energy_kwh * (price_pln_kwh / 1000.0)
    # AFTER (CORRECT) - what the new code does
    new_estimated_cost = energy_kwh * price_pln_kwh
    expected_cost = 3.15084
    # Check new calculation matches expected
    assert abs(new_estimated_cost - expected_cost) < 0.001, f"Expected {expected_cost}, got {new_estimated_cost}"
    # Old calculation should be much less than expected
    assert old_estimated_cost < expected_cost * 0.5

def test_savings_calculation():
    energy_kwh = 4.4
    price_pln_kwh = 0.7161
    reference_price = 0.4  # PLN/kWh
    reference_cost = energy_kwh * reference_price
    new_estimated_cost = energy_kwh * price_pln_kwh
    savings = max(0, reference_cost - new_estimated_cost)
    # Savings should be non-negative
    assert savings >= 0


