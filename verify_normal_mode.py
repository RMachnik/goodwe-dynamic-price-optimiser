#!/usr/bin/env python3
import goodwe
import asyncio

async def verify():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('='*60)
    print('INVERTER STATUS - VERIFICATION OF NORMAL MODE')
    print('='*60)
    
    # Get runtime data
    runtime_data = await inv.read_runtime_data()
    
    print('\n1. BATTERY STATUS:')
    print(f"   Battery SOC: {runtime_data.get('battery_soc', 'N/A')}%")
    print(f"   Battery Current: {runtime_data.get('ibattery1', 'N/A')}A")
    print(f"   Battery Power: {runtime_data.get('pbattery1', 'N/A')}W")
    print(f"   Battery Mode: {runtime_data.get('battery_mode', 'N/A')}")
    print(f"   Battery Temperature: {runtime_data.get('battery_temperature', 'N/A')}°C")
    
    print('\n2. GRID STATUS:')
    print(f"   Grid Mode: {runtime_data.get('grid_mode', 'N/A')}")
    print(f"   On-grid Mode: {runtime_data.get('grid_in_out', 'N/A')}")
    
    # Check settings
    print('\n3. GRID EXPORT SETTINGS:')
    grid_export = await inv.read_setting('grid_export')
    print(f"   Grid Export: {grid_export} (0 = disabled, 1 = enabled)")
    
    grid_export_limit = await inv.read_setting('grid_export_limit')
    print(f"   Grid Export Limit: {grid_export_limit}W")
    
    battery_dod = await inv.read_setting('battery_discharge_depth')
    print(f"   Battery Discharge Depth: {battery_dod}%")
    
    work_mode = await inv.read_setting('work_mode')
    print(f"   Work Mode: {work_mode}")
    
    print('\n4. POWER FLOW:')
    pv = runtime_data.get('ppv', 0)
    battery = runtime_data.get('pbattery1', 0)
    house = runtime_data.get('house_consumption', 0)
    
    print(f"   PV Production: {pv}W")
    print(f"   Battery Power: {battery}W (negative = charging, positive = discharging)")
    print(f"   House Load: {house}W")
    
    print('\n' + '='*60)
    print('STATUS VERIFICATION')
    print('='*60)
    
    all_good = True
    
    if grid_export == 0:
        print("✅ Grid export is DISABLED (correct)")
    else:
        print("⚠️ Grid export is still ENABLED")
        all_good = False
    
    if grid_export_limit == 5000:
        print("✅ Grid export limit reset to 5000W (default)")
    else:
        print(f"⚠️ Grid export limit is {grid_export_limit}W")
    
    if battery_dod == 50:
        print("✅ Battery discharge depth at 50% (default)")
    else:
        print(f"⚠️ Battery discharge depth is {battery_dod}%")
    
    battery_power = runtime_data.get('pbattery1', 0)
    if abs(battery_power) < 100:
        print("✅ Battery not actively discharging/charging")
    elif battery_power < 0:
        print(f"ℹ️ Battery charging at {abs(battery_power)}W")
    else:
        print(f"⚠️ Battery still discharging at {battery_power}W")
    
    print('\n' + '='*60)
    if all_good:
        print('✅ INVERTER RESTORED TO NORMAL OPERATION MODE')
    else:
        print('⚠️ Some settings may need attention')
    print('='*60)

asyncio.run(verify())


