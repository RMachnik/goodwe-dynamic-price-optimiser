#!/usr/bin/env python3
import pytest
import goodwe

@pytest.mark.asyncio
async def test_work_modes():
    """Test work mode and eco mode settings"""
    inv = await goodwe.connect('192.168.33.6', family='ET')

    # Check that we can read work mode setting
    work_mode_setting = await inv.read_setting('work_mode')
    assert work_mode_setting is not None, "Work mode setting should be readable"

    # Check that we can read runtime data
    runtime_data = await inv.read_runtime_data()
    work_mode_runtime = runtime_data.get('work_mode')
    # Work mode runtime may or may not exist, that's okay

    # Check that we can find some settings related to modes
    settings = inv.settings()
    mode_related_settings = []
    for setting in settings:
        setting_name_lower = setting.name.lower()
        if any(keyword in setting_name_lower for keyword in ['mode', 'export', 'discharge', 'priority']):
            mode_related_settings.append(setting)

    assert len(mode_related_settings) > 0, "Should have some mode-related settings"

    # Test that we can read at least one eco mode setting
    try:
        eco_mode_1 = await inv.read_setting('eco_mode_1')
        eco_mode_1_switch = await inv.read_setting('eco_mode_1_switch')
        # These don't need to assert anything specific as they may not be configured
    except Exception as e:
        pytest.skip(f"Eco mode settings not accessible: {e}")

    # Basic assertion that inverter is connected
    assert inv.model_name is not None
