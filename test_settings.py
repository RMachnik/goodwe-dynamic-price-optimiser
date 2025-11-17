#!/usr/bin/env python3
import pytest
import goodwe

@pytest.mark.asyncio
async def test_settings():
    """Test inverter settings exploration"""
    inv = await goodwe.connect('192.168.33.6', family='ET')
    print('Inverter model:', inv.model_name)

    # Get all available settings
    print('\nAvailable settings:')
    settings = inv.settings()
    assert len(settings) > 0, "Should have some settings"

    readable_settings = 0
    for setting in settings:
        print(f"  - {setting.id_}: {setting.name} ({setting.unit})")
        try:
            value = await inv.read_setting(setting.id_)
            print(f"      Current value: {value}")
            readable_settings += 1
        except Exception as e:
            print(f"      Error reading: {e}")

    # Verify we can read at least some settings
    assert readable_settings > 0, "Should be able to read at least some settings"
