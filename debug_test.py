#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, 'src')

from hybrid_charging_logic import HybridChargingLogic
from datetime import datetime

# Test data from the failing test
current_data = {
    'battery': {
        'soc_percent': 25.0,
        'temperature': 25.0,
        'voltage': 400.0,
        'current': 10.0,
        'power': 4000.0,
        'capacity_kwh': 10.0
    },
    'photovoltaic': {
        'current_power_w': 800.0,  # 800W PV (insufficient for fast charging)
        'voltage': 350.0,
        'current': 4.3,
        'daily_energy': 8.5
    },
    'grid': {
        'power': -200.0,  # 200W export
        'voltage': 230.0,
        'frequency': 50.0
    },
    'house_consumption': {
        'current_power_w': 1300.0,  # 1.3 kW consumption
        'daily_energy': 6.2
    },
    'timestamp': datetime.now()
}

price_data = {
    'prices': [0.03, 0.04, 0.05, 0.06],  # 1-hour window (more urgent)
    'date': '2025-09-07',
    'currency': 'PLN',
    'unit': 'kWh',
    'current_price': 0.03,  # Very low price
    'low_price_threshold': 0.20,
    'price_window_remaining_hours': 1.0  # Very short window
}

pv_forecast = [
    {'hour': 0, 'power_kw': 0.8, 'confidence': 0.8},
    {'hour': 1, 'power_kw': 1.2, 'confidence': 0.7},
    {'hour': 2, 'power_kw': 1.8, 'confidence': 0.6},
    {'hour': 3, 'power_kw': 2.5, 'confidence': 0.5}
]

# Test configuration
config = {
    'hybrid_charging': {
        'enabled': True,
        'max_charging_power': 3000,  # 3 kW
        'pv_charging_efficiency': 0.95,
        'grid_charging_efficiency': 0.90,
        'min_pv_power_threshold': 500,  # 500W minimum PV for charging
        'max_pv_charging_power': 2500,  # 2.5 kW max PV charging
        'grid_charging_power': 3000,    # 3 kW grid charging
        'battery_capacity_kwh': 10.0,
        'target_soc_percent': 80.0
    },
    'timing_analysis': {
        'max_wait_time_hours': 2.0,
        'min_price_savings_percent': 30.0,
        'critical_battery_soc': 12.0,
        'urgent_charging_soc': 15.0
    },
    'price_analysis': {
        'very_low_price_threshold': 0.15,  # 0.15 PLN/kWh
        'low_price_threshold': 0.35,       # 0.35 PLN/kWh
        'medium_price_threshold': 0.60,    # 0.60 PLN/kWh
        'high_price_threshold': 1.40,      # 1.40 PLN/kWh (to match test expectations)
        'very_high_price_threshold': 1.50, # 1.50 PLN/kWh
        'min_savings_threshold_pln': 0.1,  # Very low threshold for testing
        'reference_price_pln': 500.0  # Low reference price for testing (PLN/MWh)
    },
    'cost_optimization': {
        'min_savings_threshold_pln': 2.0,
        'max_cost_per_kwh': 1.0,
        'prefer_pv_charging': True,
        'grid_charging_price_threshold': 0.25
    },
    'data_directory': 'out/energy_data'
}

print('Test data:')
print(f'Battery SOC: {current_data["battery"]["soc_percent"]}%')
print(f'PV power: {current_data["photovoltaic"]["current_power_w"]}W')
print(f'Current price: {price_data["current_price"]} PLN/kWh')
print(f'Price window: {price_data["price_window_remaining_hours"]}h')

# Run the decision logic
logic = HybridChargingLogic(config)

print('\nRunning decision logic...')
decision = logic.make_charging_decision(current_data, price_data, pv_forecast)

print(f'\nDecision: {decision.charging_source}')
print(f'Action: {decision.action}')
print(f'Reason: {decision.reason}')
print(f'Confidence: {decision.confidence}')

# Let's also check what the timing analysis returns
print('\nRunning timing analysis...')
timing_analysis = logic.price_analyzer.analyze_timing_vs_price(
    price_data, pv_forecast, 
    logic._calculate_energy_needed(current_data['battery']['soc_percent']),
    current_data['photovoltaic']['current_power_w']
)

print(f'Timing analysis recommendation: {timing_analysis.get("recommendation")}')
print(f'Timing analysis reason: {timing_analysis.get("reason")}')
if timing_analysis.get('optimal_window'):
    print(f'Optimal window: {timing_analysis["optimal_window"]}')
else:
    print('No optimal window found')
