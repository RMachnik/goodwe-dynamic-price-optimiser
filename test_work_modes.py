#!/usr/bin/env python3
import goodwe
import asyncio

async def test():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('='*60)
    print('WORK MODE INVESTIGATION')
    print('='*60)
    
    # Check current work mode
    print('\nCurrent Settings:')
    work_mode_setting = await inv.read_setting('work_mode')
    print(f"  Work Mode Setting: {work_mode_setting}")
    
    runtime_data = await inv.read_runtime_data()
    work_mode_runtime = runtime_data.get('work_mode', 'N/A')
    print(f"  Work Mode Runtime: {work_mode_runtime}")
    
    # Check all settings related to modes
    print('\nSearching for discharge/export related settings:')
    for setting in inv.settings():
        setting_name_lower = setting.name.lower()
        if any(keyword in setting_name_lower for keyword in ['mode', 'export', 'discharge', 'priority']):
            try:
                value = await inv.read_setting(setting.id_)
                print(f"  {setting.name} ({setting.id_}): {value}")
            except:
                print(f"  {setting.name} ({setting.id_}): <error reading>")
    
    print('\n' + '='*60)
    print('ECO MODE DETAILS')
    print('='*60)
    print('\nEco modes can be used to schedule battery discharge:')
    print('Format: start_time-end_time days power% (SoC limit%) mode')
    print('\nMode options typically include:')
    print('  - Off: Disabled')
    print('  - On: Enabled to discharge/charge based on power%')
    print('  - Unset: Not configured')
    
    for i in range(1, 5):
        eco_mode = await inv.read_setting(f'eco_mode_{i}')
        eco_switch = await inv.read_setting(f'eco_mode_{i}_switch')
        print(f'\nEco Mode {i}:')
        print(f'  Schedule: {eco_mode}')
        print(f'  Switch: {eco_switch}')
        print(f'  Status: {"Enabled" if eco_switch != 0 else "Disabled"}')
    
    print('\n' + '='*60)
    print('POSSIBLE SOLUTIONS')
    print('='*60)
    print('\n1. ECO MODE APPROACH (Recommended):')
    print('   - Configure an eco mode to discharge battery at 100% power')
    print('   - This forces battery discharge to grid during specified times')
    print('   - Requires setting: eco_mode_X with discharge power > 0')
    
    print('\n2. WORK MODE APPROACH:')
    print('   - work_mode=0: General (default, prioritizes house load)')
    print('   - work_mode may have other values for different priorities')
    print('   - Need to test different work_mode values')
    
    print('\n3. REDUCE HOUSE LOAD:')
    print('   - Turn off appliances to create power surplus')
    print('   - When PV + Battery > House, excess exports to grid')
    
    print('\n4. WAIT FOR LOW CONSUMPTION PERIOD:')
    print('   - Evening/night when appliances are off')
    print('   - Or when PV production drops and battery becomes primary source')

asyncio.run(test())


