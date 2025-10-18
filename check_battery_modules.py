#!/usr/bin/env python3
"""
Battery Modules Diagnostic Script
Checks voltage and status for each battery module separately
"""
import goodwe
import asyncio
from datetime import datetime

async def check_battery_modules():
    """Check individual battery module voltages and data"""
    try:
        print('='*80)
        print('BATTERY MODULES DIAGNOSTIC REPORT')
        print('='*80)
        print(f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print()
        
        # Connect to inverter
        print('Connecting to inverter at 192.168.33.6...')
        inv = await goodwe.connect('192.168.33.6', family='ET')
        print(f'✓ Connected to: {inv.model_name}')
        print(f'✓ Serial: {inv.serial_number}')
        print()
        
        # Get runtime data
        runtime_data = await inv.read_runtime_data()
        
        # Check number of modules
        battery_modules = runtime_data.get('battery_modules', 'N/A')
        print('='*80)
        print('BATTERY MODULES CONFIGURATION')
        print('='*80)
        print(f'  Detected Modules: {battery_modules}')
        print()
        
        # SEARCH FOR MODULE-SPECIFIC DATA
        print('='*80)
        print('SEARCHING FOR INDIVIDUAL MODULE DATA')
        print('='*80)
        
        # Search for battery1, battery2, etc. related sensors
        battery_related = {}
        for key, value in runtime_data.items():
            if 'battery' in key.lower() or 'bms' in key.lower():
                battery_related[key] = value
        
        # Group by potential module number
        print('\n1. ALL BATTERY-RELATED SENSORS:')
        print('-'*80)
        for key in sorted(battery_related.keys()):
            value = battery_related[key]
            print(f'  {key:40s} = {value}')
        
        print()
        print('='*80)
        print('2. MODULE-SPECIFIC DATA ANALYSIS')
        print('='*80)
        
        # Try to find module-specific voltage data
        module_voltages = {}
        module_currents = {}
        module_powers = {}
        
        # Check for vbattery1, vbattery2, vbattery3, etc.
        for i in range(1, 10):
            voltage_key = f'vbattery{i}'
            current_key = f'ibattery{i}'
            power_key = f'pbattery{i}'
            
            if voltage_key in runtime_data:
                module_voltages[i] = runtime_data[voltage_key]
            if current_key in runtime_data:
                module_currents[i] = runtime_data[current_key]
            if power_key in runtime_data:
                module_powers[i] = runtime_data[power_key]
        
        if module_voltages:
            print('\n  Found Module Voltages:')
            for module_num, voltage in module_voltages.items():
                current = module_currents.get(module_num, 'N/A')
                power = module_powers.get(module_num, 'N/A')
                print(f'    Module {module_num}:')
                print(f'      Voltage: {voltage} V')
                print(f'      Current: {current} A')
                print(f'      Power:   {power} W')
        else:
            print('\n  ❌ No individual module voltage sensors found (vbattery2, vbattery3, etc.)')
        
        print()
        print('='*80)
        print('3. TOTAL BATTERY PACK DATA')
        print('='*80)
        total_voltage = runtime_data.get('vbattery1', 'N/A')
        total_current = runtime_data.get('ibattery1', 'N/A')
        total_power = runtime_data.get('pbattery1', 'N/A')
        battery_soc = runtime_data.get('battery_soc', 'N/A')
        
        print(f'  Total Pack Voltage:  {total_voltage} V')
        print(f'  Total Pack Current:  {total_current} A')
        print(f'  Total Pack Power:    {total_power} W')
        print(f'  State of Charge:     {battery_soc} %')
        
        # If you have 2 modules, estimate voltage per module
        if battery_modules == 2 and total_voltage != 'N/A':
            try:
                estimated_per_module = float(total_voltage) / 2
                print(f'\n  Estimated voltage per module: {estimated_per_module:.1f} V')
                print(f'  (Total {total_voltage}V / 2 modules)')
            except (ValueError, TypeError):
                pass
        
        print()
        print('='*80)
        print('4. CELL-LEVEL DATA (ACROSS ALL MODULES)')
        print('='*80)
        max_cell_v = runtime_data.get('battery_max_cell_voltage', 'N/A')
        min_cell_v = runtime_data.get('battery_min_cell_voltage', 'N/A')
        max_cell_v_id = runtime_data.get('battery_max_cell_voltage_id', 'N/A')
        min_cell_v_id = runtime_data.get('battery_min_cell_voltage_id', 'N/A')
        
        print(f'  Max Cell Voltage: {max_cell_v} V  (Cell ID: {max_cell_v_id})')
        print(f'  Min Cell Voltage: {min_cell_v} V  (Cell ID: {min_cell_v_id})')
        
        max_cell_t = runtime_data.get('battery_max_cell_temp', 'N/A')
        min_cell_t = runtime_data.get('battery_min_cell_temp', 'N/A')
        max_cell_t_id = runtime_data.get('battery_max_cell_temp_id', 'N/A')
        min_cell_t_id = runtime_data.get('battery_min_cell_temp_id', 'N/A')
        
        print(f'  Max Cell Temp:    {max_cell_t} °C  (Cell ID: {max_cell_t_id})')
        print(f'  Min Cell Temp:    {min_cell_t} °C  (Cell ID: {min_cell_t_id})')
        
        print()
        print('='*80)
        print('5. CHECKING ALL AVAILABLE SENSORS')
        print('='*80)
        print('\nSearching for any sensors that might contain module-specific data...')
        
        # Get all sensors from inverter
        all_sensors = inv.sensors()
        module_related = [s for s in all_sensors if 'battery' in s.id_.lower() or 'bms' in s.id_.lower() or 'module' in s.id_.lower()]
        
        print(f'\nFound {len(module_related)} battery/module-related sensors:')
        for sensor in module_related:
            value = runtime_data.get(sensor.id_, 'N/A')
            print(f'  {sensor.id_:40s} ({sensor.name:30s}) = {value} {sensor.unit}')
        
        print()
        print('='*80)
        print('SUMMARY')
        print('='*80)
        print(f'Number of battery modules: {battery_modules}')
        print()
        
        if len(module_voltages) > 1:
            print('✓ Individual module voltages ARE available:')
            for module_num, voltage in module_voltages.items():
                print(f'  Module {module_num}: {voltage} V')
        else:
            print('✗ Individual module voltages NOT available via API')
            print('  API reports only total pack voltage for all modules combined')
            print(f'  Total voltage: {total_voltage} V')
            if battery_modules == 2:
                print(f'  Estimated per module: ~{float(total_voltage)/2:.1f} V')
        
        print()
        print('Cell-level data is aggregated across all modules.')
        print('='*80)
        
    except Exception as e:
        print(f'\n❌ ERROR: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(check_battery_modules())


