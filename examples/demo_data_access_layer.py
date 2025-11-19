#!/usr/bin/env python3
"""
Demo script showing the Data Access Layer abstraction in action
(Moved from test/test_data_access_layer_demo.py)
"""

# NOTE: This file is a demo and is not collected by pytest. Run manually:
# python examples/demo_data_access_layer.py

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_access_layer import (
    DataAccessLayer,
    DataStorageConfig,
    create_data_access_layer
)

# (Demo functions copied unchanged from test/test_data_access_layer_demo.py)

async def demo_file_storage():
    """Demo file-based storage"""

    print("🔹 Demoing File-Based Storage Backend 🔹")

    # Create file-only configuration
    config = DataStorageConfig(
        mode="file",
        file_config={
            'base_path': 'out/demo_file_storage'
        }
    )

    dal = DataAccessLayer(config)
    print(f"Backend: {dal.get_backend_info()}")

    await dal.connect()

    # Save some energy data
    energy_data = [{
        'timestamp': datetime.now().isoformat(),
        'battery_soc': 85.2,
        'pv_power': 3200.0
    }]

    await dal.save_energy_data(energy_data)
    print(f"✅ Saved {len(energy_data)} energy data records to files")

    # Retrieve data
    start_time = datetime.now() - timedelta(hours=1)
    end_time = datetime.now() + timedelta(hours=1)
    retrieved = await dal.get_energy_data(start_time, end_time)
    print(f"📊 Retrieved {len(retrieved)} energy data records from files")

    # Save system state
    state_data = {
        'timestamp': datetime.now().isoformat(),
        'state': 'charging',
        'uptime_seconds': 7200
    }
    await dal.save_system_state(state_data)
    print("✅ Saved system state to file")

    # Get states
    states = await dal.get_system_state(5)
    print(f"📊 Retrieved {len(states)} system state records from files")

    # Save decision
    decision_data = {
        'timestamp': datetime.now().isoformat(),
        'action': 'start_pv_charging',
        'reason': 'Optimal PV conditions detected'
    }
    await dal.save_decision(decision_data)
    print("✅ Saved coordinator decision to file")

    await dal.disconnect()
    print("🚪 Disconnected from file storage\n")

# For brevity, the remaining demo functions are omitted in this example copy.

async def main():
    print("Run the full demo from the original test file if needed.")

if __name__ == "__main__":
    asyncio.run(main())
