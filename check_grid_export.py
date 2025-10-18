#!/usr/bin/env python3
import goodwe
import asyncio

async def check():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    data = await inv.read_runtime_data()
    
    print("=" * 60)
    print("GRID EXPORT VERIFICATION")
    print("=" * 60)
    
    # Check all grid-related sensors
    print("\nGRID POWER SENSORS:")
    for sensor in inv.sensors():
        if 'grid' in sensor.name.lower() or 'meter' in sensor.name.lower():
            if sensor.id_ in data:
                print(f"  {sensor.name}: {data[sensor.id_]} {sensor.unit}")
    
    print("\nPOWER FLOW:")
    pv = data.get('ppv', 0)
    battery = data.get('pbattery1', 0)
    house = data.get('house_consumption', 0)
    
    print(f"  PV Production: {pv}W")
    print(f"  Battery Power: {battery}W (+ = discharging, - = charging)")
    print(f"  House Load: {house}W")
    
    total_production = pv + (battery if battery > 0 else 0)
    print(f"\n  Total Production: {total_production}W")
    print(f"  House Consumption: {house}W")
    print(f"  Expected Export: {total_production - house}W")
    
    print("\n" + "=" * 60)

asyncio.run(check())


