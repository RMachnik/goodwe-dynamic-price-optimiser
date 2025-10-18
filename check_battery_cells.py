#!/usr/bin/env python3
"""
Battery Cell Voltage and Temperature Check Script
Retrieves detailed information about individual battery cells from GoodWe inverter
"""
import goodwe
import asyncio
from datetime import datetime

async def check_battery_cells():
    """Check battery cell voltages and temperatures"""
    try:
        print('='*80)
        print('BATTERY CELLS DIAGNOSTIC REPORT')
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
        
        # BATTERY GENERAL INFO
        print('='*80)
        print('1. BATTERY GENERAL INFORMATION')
        print('='*80)
        battery_voltage = runtime_data.get('vbattery1', 'N/A')
        battery_current = runtime_data.get('ibattery1', 'N/A')
        battery_power = runtime_data.get('pbattery1', 'N/A')
        battery_soc = runtime_data.get('battery_soc', 'N/A')
        battery_soh = runtime_data.get('battery_soh', 'N/A')
        battery_temp = runtime_data.get('battery_temperature', 'N/A')
        battery_modules = runtime_data.get('battery_modules', 'N/A')
        
        print(f'  Battery Voltage:        {battery_voltage} V')
        print(f'  Battery Current:        {battery_current} A')
        print(f'  Battery Power:          {battery_power} W')
        print(f'  State of Charge (SOC):  {battery_soc} %')
        print(f'  State of Health (SOH):  {battery_soh} %')
        print(f'  Battery Temperature:    {battery_temp} °C')
        print(f'  Number of Modules:      {battery_modules}')
        print()
        
        # CELL VOLTAGE INFORMATION
        print('='*80)
        print('2. CELL VOLTAGE INFORMATION')
        print('='*80)
        max_cell_voltage = runtime_data.get('battery_max_cell_voltage', 'N/A')
        min_cell_voltage = runtime_data.get('battery_min_cell_voltage', 'N/A')
        max_cell_voltage_id = runtime_data.get('battery_max_cell_voltage_id', 'N/A')
        min_cell_voltage_id = runtime_data.get('battery_min_cell_voltage_id', 'N/A')
        
        print(f'  Max Cell Voltage:       {max_cell_voltage} V  (Cell ID: {max_cell_voltage_id})')
        print(f'  Min Cell Voltage:       {min_cell_voltage} V  (Cell ID: {min_cell_voltage_id})')
        
        # Calculate voltage difference if both values available
        if max_cell_voltage != 'N/A' and min_cell_voltage != 'N/A':
            try:
                voltage_diff = float(max_cell_voltage) - float(min_cell_voltage)
                print(f'  Voltage Difference:     {voltage_diff:.3f} V')
                
                # Check if cells are balanced (typical threshold ~0.05V)
                if voltage_diff < 0.05:
                    print(f'  Balance Status:         ✓ GOOD (cells well balanced)')
                elif voltage_diff < 0.1:
                    print(f'  Balance Status:         ⚠ ACCEPTABLE (slight imbalance)')
                else:
                    print(f'  Balance Status:         ✗ WARNING (significant imbalance)')
            except (ValueError, TypeError):
                pass
        print()
        
        # CELL TEMPERATURE INFORMATION
        print('='*80)
        print('3. CELL TEMPERATURE INFORMATION')
        print('='*80)
        max_cell_temp = runtime_data.get('battery_max_cell_temp', 'N/A')
        min_cell_temp = runtime_data.get('battery_min_cell_temp', 'N/A')
        max_cell_temp_id = runtime_data.get('battery_max_cell_temp_id', 'N/A')
        min_cell_temp_id = runtime_data.get('battery_min_cell_temp_id', 'N/A')
        
        print(f'  Max Cell Temperature:   {max_cell_temp} °C  (Cell ID: {max_cell_temp_id})')
        print(f'  Min Cell Temperature:   {min_cell_temp} °C  (Cell ID: {min_cell_temp_id})')
        
        # Calculate temperature difference if both values available
        if max_cell_temp != 'N/A' and min_cell_temp != 'N/A':
            try:
                temp_diff = float(max_cell_temp) - float(min_cell_temp)
                print(f'  Temperature Difference: {temp_diff:.1f} °C')
                
                # Check temperature spread (typical threshold ~5°C)
                if temp_diff < 5:
                    print(f'  Thermal Balance:        ✓ GOOD (uniform temperature)')
                elif temp_diff < 10:
                    print(f'  Thermal Balance:        ⚠ ACCEPTABLE (slight variation)')
                else:
                    print(f'  Thermal Balance:        ✗ WARNING (high variation)')
            except (ValueError, TypeError):
                pass
        print()
        
        # BMS INFORMATION
        print('='*80)
        print('4. BATTERY MANAGEMENT SYSTEM (BMS) STATUS')
        print('='*80)
        battery_bms = runtime_data.get('battery_bms', 'N/A')
        battery_status = runtime_data.get('battery_status', 'N/A')
        battery_protocol = runtime_data.get('battery_protocol', 'N/A')
        battery_charge_limit = runtime_data.get('battery_charge_limit', 'N/A')
        battery_discharge_limit = runtime_data.get('battery_discharge_limit', 'N/A')
        battery_sw_version = runtime_data.get('battery_sw_version', 'N/A')
        battery_hw_version = runtime_data.get('battery_hw_version', 'N/A')
        
        print(f'  BMS Type:               {battery_bms}')
        print(f'  Battery Status:         {battery_status}')
        print(f'  Battery Protocol:       {battery_protocol}')
        print(f'  Charge Limit:           {battery_charge_limit} A')
        print(f'  Discharge Limit:        {battery_discharge_limit} A')
        print(f'  Software Version:       {battery_sw_version}')
        print(f'  Hardware Version:       {battery_hw_version}')
        print()
        
        # BMS WARNINGS AND ERRORS
        print('='*80)
        print('5. BMS WARNINGS AND ERRORS')
        print('='*80)
        battery_warning = runtime_data.get('battery_warning', 'N/A')
        battery_warning_l = runtime_data.get('battery_warning_l', 'N/A')
        battery_warning_h = runtime_data.get('battery_warning_h', 'N/A')
        battery_error = runtime_data.get('battery_error', 'N/A')
        battery_error_l = runtime_data.get('battery_error_l', 'N/A')
        battery_error_h = runtime_data.get('battery_error_h', 'N/A')
        
        print(f'  Battery Warning:        {battery_warning}')
        print(f'  Battery Warning L:      {battery_warning_l}')
        print(f'  Battery Warning H:      {battery_warning_h}')
        print(f'  Battery Error:          {battery_error}')
        print(f'  Battery Error L:        {battery_error_l}')
        print(f'  Battery Error H:        {battery_error_h}')
        print()
        
        # ADDITIONAL CELL DATA (if available)
        print('='*80)
        print('6. LOOKING FOR ADDITIONAL CELL DATA')
        print('='*80)
        
        # Check if there are any additional cell-related sensors
        cell_related_keys = [key for key in runtime_data.keys() if 'cell' in key.lower()]
        if cell_related_keys:
            print('  Found additional cell-related data:')
            for key in sorted(cell_related_keys):
                print(f'    {key}: {runtime_data[key]}')
        else:
            print('  No additional per-cell data available from inverter API.')
            print('  Only min/max cell voltages and temperatures are exposed.')
        print()
        
        # SUMMARY
        print('='*80)
        print('SUMMARY')
        print('='*80)
        print('Available cell information:')
        print('  ✓ Maximum cell voltage and its ID')
        print('  ✓ Minimum cell voltage and its ID')
        print('  ✓ Maximum cell temperature and its ID')
        print('  ✓ Minimum cell temperature and its ID')
        print('  ✓ Number of battery modules')
        print()
        print('Limitations:')
        print('  ✗ Individual voltage for each cell NOT available via API')
        print('  ✗ Individual temperature for each cell NOT available via API')
        print()
        print('The GoodWe API provides only aggregated cell data (min/max values)')
        print('for monitoring battery health and balance status.')
        print('='*80)
        
    except Exception as e:
        print(f'\n❌ ERROR: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(check_battery_cells())


