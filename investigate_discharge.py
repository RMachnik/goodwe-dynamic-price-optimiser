#!/usr/bin/env python3
import goodwe
import asyncio

async def investigate():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('='*60)
    print('INVERTER STATUS INVESTIGATION')
    print('='*60)
    
    # Get runtime data
    runtime_data = await inv.read_runtime_data()
    
    print('\n1. BATTERY STATUS:')
    print(f"   Battery SOC: {runtime_data.get('battery_soc', 'N/A')}%")
    print(f"   Battery Voltage: {runtime_data.get('battery_voltage', 'N/A')}V")
    print(f"   Battery Current: {runtime_data.get('ibattery1', 'N/A')}A")
    print(f"   Battery Power: {runtime_data.get('pbattery1', 'N/A')}W")
    print(f"   Battery Temperature: {runtime_data.get('battery_temperature', 'N/A')}°C")
    print(f"   Battery Mode: {runtime_data.get('battery_mode', 'N/A')}")
    print(f"   Battery Status: {runtime_data.get('battery_status', 'N/A')}")
    
    print('\n2. GRID STATUS:')
    print(f"   Grid Power: {runtime_data.get('grid_power', 'N/A')}W")
    print(f"   Grid Voltage: {runtime_data.get('vgrid', 'N/A')}V")
    print(f"   Grid Frequency: {runtime_data.get('fgrid', 'N/A')}Hz")
    print(f"   Grid Mode: {runtime_data.get('grid_mode', 'N/A')}")
    
    print('\n3. PV STATUS:')
    print(f"   PV1 Power: {runtime_data.get('ppv1', 'N/A')}W")
    print(f"   PV2 Power: {runtime_data.get('ppv2', 'N/A')}W")
    print(f"   PV Total Power: {runtime_data.get('ppv', 'N/A')}W")
    
    print('\n4. LOAD/CONSUMPTION:')
    print(f"   Load Power: {runtime_data.get('house_consumption', 'N/A')}W")
    print(f"   Total Load: {runtime_data.get('total_house_consumption', 'N/A')}W")
    
    print('\n5. INVERTER MODE:')
    print(f"   Work Mode: {runtime_data.get('work_mode', 'N/A')}")
    print(f"   Work Mode Code: {runtime_data.get('work_mode_code', 'N/A')}")
    
    # Get grid export settings
    print('\n6. GRID EXPORT SETTINGS:')
    grid_export = await inv.read_setting('grid_export')
    print(f"   Grid Export Enabled: {grid_export}")
    
    grid_export_limit = await inv.read_setting('grid_export_limit')
    print(f"   Grid Export Limit: {grid_export_limit}W")
    
    battery_dod = await inv.read_setting('battery_discharge_depth')
    print(f"   Battery Discharge Depth: {battery_dod}%")
    
    work_mode = await inv.read_setting('work_mode')
    print(f"   Work Mode Setting: {work_mode}")
    
    # Check eco modes
    print('\n7. ECO MODE SETTINGS:')
    for i in range(1, 5):
        eco_mode = await inv.read_setting(f'eco_mode_{i}')
        eco_switch = await inv.read_setting(f'eco_mode_{i}_switch')
        print(f"   Eco Mode {i}: {eco_mode}")
        print(f"   Eco Mode {i} Switch: {eco_switch}")
    
    # Check BMS data
    print('\n8. BMS STATUS:')
    print(f"   BMS Battery SOC: {runtime_data.get('bms_soc', 'N/A')}%")
    print(f"   BMS Battery Voltage: {runtime_data.get('bms_battery_voltage', 'N/A')}V")
    print(f"   BMS Battery Current: {runtime_data.get('bms_battery_current', 'N/A')}A")
    print(f"   BMS Status: {runtime_data.get('bms_status', 'N/A')}")
    print(f"   BMS Warning Code: {runtime_data.get('bms_battery_warning_code', 'N/A')}")
    print(f"   BMS Alarm Code: {runtime_data.get('bms_battery_alarm_code', 'N/A')}")
    
    # Check all sensors for discharge-related info
    print('\n9. ALL AVAILABLE SENSORS:')
    for sensor in inv.sensors():
        if sensor.id_ in runtime_data:
            value = runtime_data[sensor.id_]
            if 'discharge' in sensor.name.lower() or 'export' in sensor.name.lower():
                print(f"   {sensor.name}: {value} {sensor.unit}")
    
    print('\n' + '='*60)
    print('ANALYSIS:')
    print('='*60)
    
    battery_power = runtime_data.get('pbattery1', 0)
    grid_power = runtime_data.get('grid_power', 0)
    pv_power = runtime_data.get('ppv', 0)
    load_power = runtime_data.get('house_consumption', 0)
    
    print(f"\nPower Flow:")
    print(f"  PV Production: {pv_power}W")
    print(f"  House Load: {load_power}W")
    print(f"  Battery Power: {battery_power}W (negative = charging, positive = discharging)")
    print(f"  Grid Power: {grid_power}W (negative = importing, positive = exporting)")
    
    print(f"\nPower Balance:")
    if pv_power > load_power:
        surplus = pv_power - load_power
        print(f"  PV Surplus: {surplus}W (excess solar)")
        print(f"  → Battery should be charging from PV")
        print(f"  → Grid export only happens if battery is full or limited")
    else:
        deficit = load_power - pv_power
        print(f"  PV Deficit: {deficit}W (need more power)")
        print(f"  → Need to draw from battery or grid")
    
    if grid_export == 1:
        print(f"\n✓ Grid export is ENABLED")
        print(f"  But battery won't export to grid unless:")
        print(f"    1. Battery SOC > discharge depth limit ({battery_dod}%)")
        print(f"    2. House load is satisfied")
        print(f"    3. PV is not producing enough to trigger export")
        print(f"    4. Work mode allows grid export")
    else:
        print(f"\n✗ Grid export is DISABLED")

asyncio.run(investigate())


