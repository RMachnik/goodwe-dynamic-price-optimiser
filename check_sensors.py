#!/usr/bin/env python3
"""
Quick sensor check script to investigate grid voltage issue
"""

import asyncio
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import goodwe
except ImportError as e:
    print(f"Error importing goodwe: {e}")
    sys.exit(1)

async def check_sensors():
    """Check current sensor values"""
    try:
        # Connect to inverter
        inverter = await goodwe.connect(
            host="192.168.33.15",
            family="ET",
            timeout=1
        )
        
        print("✓ Connected to inverter")
        print(f"Model: {inverter.model_name}")
        print(f"Serial: {inverter.serial_number}")
        print()
        
        # Get runtime data
        runtime_data = await inverter.read_runtime_data()
        
        # Check grid voltage sensors
        print("🔍 GRID VOLTAGE SENSORS:")
        print("-" * 50)
        
        grid_voltage_sensors = ['vgrid', 'vgrid2', 'vgrid3']
        for sensor_id in grid_voltage_sensors:
            if sensor_id in runtime_data:
                value = runtime_data[sensor_id]
                print(f"{sensor_id:<10}: {value}V")
            else:
                print(f"{sensor_id:<10}: Not available")
        
        print()
        
        # Check grid current sensors
        print("🔍 GRID CURRENT SENSORS:")
        print("-" * 50)
        
        grid_current_sensors = ['igrid', 'igrid2', 'igrid3']
        for sensor_id in grid_current_sensors:
            if sensor_id in runtime_data:
                value = runtime_data[sensor_id]
                print(f"{sensor_id:<10}: {value}A")
            else:
                print(f"{sensor_id:<10}: Not available")
        
        print()
        
        # Check grid power sensors
        print("🔍 GRID POWER SENSORS:")
        print("-" * 50)
        
        grid_power_sensors = ['pgrid', 'pgrid2', 'pgrid3', 'meter_active_power_total']
        for sensor_id in grid_power_sensors:
            if sensor_id in runtime_data:
                value = runtime_data[sensor_id]
                print(f"{sensor_id:<25}: {value}W")
            else:
                print(f"{sensor_id:<25}: Not available")
        
        print()
        
        # Check grid mode
        print("🔍 GRID STATUS:")
        print("-" * 50)
        
        if 'grid_mode_label' in runtime_data:
            print(f"Grid Mode: {runtime_data['grid_mode_label']}")
        if 'grid_in_out_label' in runtime_data:
            print(f"Grid In/Out: {runtime_data['grid_in_out_label']}")
        
        print()
        
        # Check battery status
        print("🔍 BATTERY STATUS:")
        print("-" * 50)
        
        battery_sensors = ['battery_soc', 'battery_voltage', 'battery_temperature']
        for sensor_id in battery_sensors:
            if sensor_id in runtime_data:
                value = runtime_data[sensor_id]
                unit = "V" if "voltage" in sensor_id else ("°C" if "temperature" in sensor_id else "%")
                print(f"{sensor_id:<20}: {value}{unit}")
            else:
                print(f"{sensor_id:<20}: Not available")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_sensors())