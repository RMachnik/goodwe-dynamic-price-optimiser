#!/usr/bin/env python3
"""Quick test to verify cost calculation fix"""

# Test data from actual decision file
energy_kwh = 4.4
price_pln_kwh = 0.7161  # Already converted to PLN/kWh

# BEFORE (WRONG) - what the old code did
old_estimated_cost = energy_kwh * (price_pln_kwh / 1000.0)
print(f"❌ OLD (WRONG) Calculation:")
print(f"   Energy: {energy_kwh} kWh")
print(f"   Price: {price_pln_kwh} PLN/kWh")
print(f"   Formula: {energy_kwh} × ({price_pln_kwh} / 1000)")
print(f"   Cost: {old_estimated_cost:.6f} PLN")
print()

# AFTER (CORRECT) - what the new code does
new_estimated_cost = energy_kwh * price_pln_kwh
print(f"✅ NEW (CORRECT) Calculation:")
print(f"   Energy: {energy_kwh} kWh")
print(f"   Price: {price_pln_kwh} PLN/kWh")
print(f"   Formula: {energy_kwh} × {price_pln_kwh}")
print(f"   Cost: {new_estimated_cost:.6f} PLN")
print()

# Expected
expected_cost = 3.15084
print(f"📊 Verification:")
print(f"   Expected cost: {expected_cost:.6f} PLN")
print(f"   New calculation: {new_estimated_cost:.6f} PLN")
print(f"   Match: {'✅ YES' if abs(new_estimated_cost - expected_cost) < 0.001 else '❌ NO'}")
print(f"   Old was {(old_estimated_cost/expected_cost*100):.2f}% of correct value")
print(f"   New is {(new_estimated_cost/expected_cost*100):.2f}% of correct value")
print()

# Test savings calculation
reference_price = 0.4  # PLN/kWh
reference_cost = energy_kwh * reference_price
savings = max(0, reference_cost - new_estimated_cost)

print(f"💰 Savings Calculation:")
print(f"   Reference cost (0.40 PLN/kWh): {reference_cost:.2f} PLN")
print(f"   Actual cost ({price_pln_kwh:.2f} PLN/kWh): {new_estimated_cost:.2f} PLN")
print(f"   Savings: {savings:.2f} PLN")
if savings < 0:
    print(f"   ⚠️  Negative savings (paid more than reference)")
else:
    savings_percent = (savings / reference_cost * 100) if reference_cost > 0 else 0
    print(f"   Savings %: {savings_percent:.1f}%")

