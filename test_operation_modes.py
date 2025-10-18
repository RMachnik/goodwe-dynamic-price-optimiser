#!/usr/bin/env python3
import goodwe
import asyncio
from goodwe import OperationMode

async def test():
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('Inverter model:', inv.model_name)
    
    # Get available operation modes
    print('\nAvailable operation modes:')
    modes = await inv.get_operation_modes()
    for mode in modes:
        print(f"  - {mode}")
    
    # Get current operation mode
    print('\nCurrent operation mode:')
    current_mode = await inv.get_operation_mode()
    print(f"  {current_mode}")
    
    # Check method signature
    print('\nChecking set_operation_mode signature:')
    import inspect
    sig = inspect.signature(inv.set_operation_mode)
    print(f"  Signature: {sig}")
    
    # Check if ECO_DISCHARGE is available
    print('\nOperationMode enum values:')
    for mode in OperationMode:
        print(f"  - {mode.name}: {mode.value}")

asyncio.run(test())


