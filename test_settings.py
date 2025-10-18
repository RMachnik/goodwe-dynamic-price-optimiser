#!/usr/bin/env python3
import goodwe
import asyncio

async def test():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('Inverter model:', inv.model_name)
    
    # Get all available settings
    print('\nAvailable settings:')
    settings = inv.settings()
    for setting in settings:
        print(f"  - {setting.id_}: {setting.name} ({setting.unit})")
        try:
            value = await inv.read_setting(setting.id_)
            print(f"      Current value: {value}")
        except Exception as e:
            print(f"      Error reading: {e}")

asyncio.run(test())


