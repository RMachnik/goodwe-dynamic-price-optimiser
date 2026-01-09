#!/usr/bin/env python3
"""
Sensor Investigator for GoodWe Inverter
Investigates what sensors are actually available and their data formats
"""

import asyncio
import json
from fast_charge import GoodWeFastCharger

async def investigate_sensors():
    """Investigate all available sensors from the GoodWe inverter"""
    
    # Initialize charger
    charger = GoodWeFastCharger("fast_charge_config.yaml")
    
    if not await charger.connect_inverter():
        print("Failed to connect to inverter")
        return
    
    print("🔍 INVESTIGATING GOODWE INVERTER SENSORS")
    print("=" * 60)
    
    # Get inverter info
    inverter = charger.inverter
    print(f"Inverter Model: {inverter.model_name}")
    print(f"Serial Number: {inverter.serial_number}")
    print(f"Firmware: {inverter.firmware}")
    print(f"Rated Power: {inverter.rated_power}W")
    print()
    
    # Get all available sensors
    print("📊 AVAILABLE SENSORS:")
    print("-" * 60)
    
    sensors = inverter.sensors()
    for i, sensor in enumerate(sensors):
        print(f"{i+1:2d}. {sensor.id_:<20} | {sensor.name:<30} | {sensor.unit}")
    
    print()
    
    # Get runtime data to see actual values
    print("📈 CURRENT SENSOR VALUES:")
    print("-" * 60)
    
    try:
        runtime_data = await inverter.read_runtime_data()
        
        # Group sensors by category
        battery_sensors = []
        pv_sensors = []
        grid_sensors = []
        other_sensors = []
        
        for sensor in sensors:
            if sensor.id_ in runtime_data:
                value = runtime_data[sensor.id_]
                sensor_info = {
                    'id': sensor.id_,
                    'name': sensor.name,
                    'value': value,
                    'unit': sensor.unit
                }
                
                # Categorize sensors
                if 'battery' in sensor.id_.lower() or 'soc' in sensor.id_.lower():
                    battery_sensors.append(sensor_info)
                elif 'pv' in sensor.id_.lower() or 'solar' in sensor.id_.lower():
                    pv_sensors.append(sensor_info)
                elif 'grid' in sensor.id_.lower() or 'meter' in sensor.id_.lower():
                    grid_sensors.append(sensor_info)
                else:
                    other_sensors.append(sensor_info)
        
        # Print categorized sensors
        if battery_sensors:
            print("🔋 BATTERY SENSORS:")
            for sensor in battery_sensors:
                print(f"  {sensor['id']:<20} | {sensor['name']:<30} | {sensor['value']} {sensor['unit']}")
            print()
        
        if pv_sensors:
            print("☀️ PHOTOVOLTAIC SENSORS:")
            for sensor in pv_sensors:
                print(f"  {sensor['id']:<20} | {sensor['name']:<30} | {sensor['value']} {sensor['unit']}")
            print()
        
        if grid_sensors:
            print("⚡ GRID SENSORS:")
            for sensor in grid_sensors:
                print(f"  {sensor['id']:<20} | {sensor['name']:<30} | {sensor['value']} {sensor['unit']}")
            print()
        
        if other_sensors:
            print("🔧 OTHER SENSORS:")
            for sensor in other_sensors:
                print(f"  {sensor['id']:<20} | {sensor['name']:<30} | {sensor['value']} {sensor['unit']}")
            print()
        
        # Show total sensors with values
        total_with_values = len([s for s in sensors if s.id_ in runtime_data])
        print(f"📊 SUMMARY: {total_with_values}/{len(sensors)} sensors have values")
        
    except Exception as e:
        print(f"Error reading runtime data: {e}")
    
    # Try to read specific settings
    print("\n⚙️ INVERTER SETTINGS:")
    print("-" * 60)
    
    settings_to_check = [
        'pv_power', 'grid_power', 'battery_voltage', 'battery_current',
        'pv_voltage', 'pv_current', 'grid_voltage', 'grid_current',
        'battery_power', 'house_power', 'load_power'
    ]
    
    for setting in settings_to_check:
        try:
            value = await inverter.read_setting(setting)
            print(f"  {setting:<20} | {value}")
        except Exception as e:
            print(f"  {setting:<20} | Error: {str(e)[:50]}...")
    
    # Save sensor information to file
    sensor_data = {
        'inverter_info': {
            'model': inverter.model_name,
            'serial': inverter.serial_number,
            'firmware': inverter.firmware,
            'rated_power': inverter.rated_power
        },
        'available_sensors': [
            {
                'id': sensor.id_,
                'name': sensor.name,
                'unit': sensor.unit
            }
            for sensor in sensors
        ],
        'runtime_data': runtime_data if 'runtime_data' in locals() else {},
        'investigation_time': asyncio.get_event_loop().time()
    }
    
    with open('sensor_investigation.json', 'w', encoding='utf-8') as f:
        json.dump(sensor_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Sensor investigation saved to 'sensor_investigation.json'")

async def main():
    """Main function"""
    await investigate_sensors()

if __name__ == "__main__":
    asyncio.run(main())
