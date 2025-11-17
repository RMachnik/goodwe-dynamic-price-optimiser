#!/usr/bin/env python3
import pytest
import goodwe
from goodwe import OperationMode
import inspect

@pytest.mark.asyncio
async def test_operation_modes():
    """Test inverter operation modes and methods"""
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('Inverter model:', inv.model_name)

    # Get available operation modes
    print('\nAvailable operation modes:')
    modes = await inv.get_operation_modes(include_emulated=False)
    for mode in modes:
        print(f"  - {mode}")

    # Get current operation mode
    print('\nCurrent operation mode:')
    current_mode = await inv.get_operation_mode()
    print(f"  {current_mode}")

    # Check method signature
    print('\nChecking set_operation_mode signature:')
    sig = inspect.signature(inv.set_operation_mode)
    print(f"  Signature: {sig}")

    # Check if ECO_DISCHARGE is available
    print('\nOperationMode enum values:')
    eco_discharge_found = False
    for mode in OperationMode:
        print(f"  - {mode.name}: {mode.value}")
        if mode.name == 'ECO_DISCHARGE':
            eco_discharge_found = True

    # Verify we have some operation modes and ECO_DISCHARGE
    assert len(modes) > 0
    assert eco_discharge_found, "ECO_DISCHARGE operation mode should be available"
