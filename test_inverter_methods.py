#!/usr/bin/env python3
import pytest
import goodwe

@pytest.mark.asyncio
async def test_inverter_methods():
    """Test inverter methods exploration"""
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('Inverter model:', inv.model_name)
    print('\nAvailable methods:')
    methods = [m for m in dir(inv) if not m.startswith('_') and callable(getattr(inv, m))]
    for method in sorted(methods):
        print(f"  - {method}")

    # Just test that we got some methods
    assert len(methods) > 0
