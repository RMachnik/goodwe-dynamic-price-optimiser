#!/usr/bin/env python3
"""
Demo script showing the Data Access Layer abstraction in action
"""

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

async def demo_database_storage():
    """Demo database-backed storage"""
    print("🔹 Demoing Database-Backed Storage Backend 🔹")

    # Setup database schema first
    from database.schema import DatabaseSchema
    schema = DatabaseSchema('goodwe_demo.db')
    schema.connect()
    schema.create_tables()
    schema.create_indexes()
    schema.disconnect()
    print("✅ Database schema created")

    # Create database-only configuration
    config = DataStorageConfig(
        mode="database",
        database_config={
            'db_path': 'goodwe_demo.db',
            'batch_size': 50
        }
    )

    dal = DataAccessLayer(config)
    print(f"Backend: {dal.get_backend_info()}")

    await dal.connect()

    # Generate larger dataset for demo
    energy_dataset = []
    base_time = datetime.now() - timedelta(hours=12)

    for i in range(100):
        energy_dataset.append({
            'timestamp': (base_time + timedelta(minutes=i*10)).isoformat(),
            'battery_soc': 60.0 + i * 0.2,  # Gradual increase
            'pv_power': 1000 + i * 50  # Gradual increase
        })

    print(f"📊 Saving {len(energy_dataset)} energy records to database...")
    await dal.save_energy_data(energy_dataset)
    print("✅ Saved energy dataset to database")

    # Retrieve subset
    start_time = datetime.now() - timedelta(hours=2)
    end_time = datetime.now() + timedelta(hours=2)
    retrieved = await dal.get_energy_data(start_time, end_time)
    print(f"📊 Retrieved {len(retrieved)} recent energy records from database")

    # Save system states
    for i in range(20):
        state_data = {
            'timestamp': (datetime.now() + timedelta(minutes=i)).isoformat(),
            'state': ['monitoring', 'charging', 'waiting'][i % 3],
            'uptime_seconds': i * 300
        }
        await dal.save_system_state(state_data)

    print("✅ Saved 20 system state records to database")

    states = await dal.get_system_state(50)
    print(f"📊 Retrieved {len(states)} system state records from database")

    # Clean up demo database
    try:
        Path('goodwe_demo.db').unlink()
        print("🧹 Cleaned up demo database")
    except:
        pass

    await dal.disconnect()
    print("🚪 Disconnected from database storage\n")

async def demo_backend_switching():
    """Demo runtime backend switching"""
    print("🔹 Demoing Runtime Backend Switching 🔹")

    # Setup database first
    from database.schema import DatabaseSchema
    schema = DatabaseSchema('goodwe_demo.db')
    schema.connect()
    schema.create_tables()
    schema.create_indexes()
    schema.disconnect()

    # Mixed configuration
    config = DataStorageConfig(
        mode="file",  # Start with file
        database_config={'db_path': 'goodwe_demo.db'},
        file_config={'base_path': 'out/demo_switching'}
    )

    dal = DataAccessLayer(config)

    # Start with file backend
    await dal.connect()
    print(f"📁 Started with file backend: {dal.get_backend_info()}")

    # Save data to file
    file_data = [{
        'timestamp': datetime.now().isoformat(),
        'battery_soc': 70.0,
        'source': 'file_backend'
    }]

    await dal.save_energy_data(file_data)
    print("✅ Saved data to file backend")

    # Switch to database at runtime
    dal.switch_backend("database")
    print(f"🗄️ Switched to database backend: {dal.get_backend_info()}")

    # Continue working with database
    db_data = [{
        'timestamp': datetime.now().isoformat(),
        'battery_soc': 80.0,
        'source': 'database_backend'
    }]

    await dal.save_energy_data(db_data)
    print("✅ Saved data to database backend")

    # Retrieve from database
    start_time = datetime.now() - timedelta(hours=1)
    end_time = datetime.now() + timedelta(hours=1)
    all_data = await dal.get_energy_data(start_time, end_time)
    print(f"📊 Retrieved {len(all_data)} total records from current backend")

    # Switch back to file
    dal.switch_backend("file")
    print(f"📁 Switched back to file backend: {dal.get_backend_info()}")

    # Add more data to file
    more_file_data = [{
        'timestamp': datetime.now().isoformat(),
        'battery_soc': 90.0,
        'source': 'file_backend_again'
    }]

    await dal.save_energy_data(more_file_data)
    print("✅ Saved more data to file backend")

    # Clean up
    await dal.disconnect()

    # Cleanup demo files
    try:
        import shutil
        shutil.rmtree('out/demo_switching')
        Path('goodwe_demo.db').unlink()
        print("🧹 Cleaned up demo files")
    except:
        pass

    print("🚪 Backend switching demo complete\n")

async def demo_configuration_from_dict():
    """Demo creating DAL from configuration dictionary"""
    print("🔹 Demoing Configuration-Driven Setup 🔹")

    # Simulate app configuration
    app_config = {
        'data_storage': {
            'mode': 'file',
            'file': {
                'base_path': 'out/config_demo'
            }
        }
    }

    # Use factory function
    dal = create_data_access_layer(app_config)
    print(f"⚙️ Created DAL from config: {dal.get_backend_info()}")

    await dal.connect()

    # Test operations
    test_data = [{
        'timestamp': datetime.now().isoformat(),
        'battery_soc': 75.0
    }]

    await dal.save_energy_data(test_data)
    await dal.save_system_state({'timestamp': datetime.now().isoformat(), 'state': 'active'})

    await dal.disconnect()

    # Cleanup
    try:
        import shutil
        shutil.rmtree('out/config_demo')
    except:
        pass

    print("⚙️ Configuration demo complete\n")

async def main():
    """Main demo function"""
    print("🗄️ **DATA ACCESS LAYER ABSTRACTION DEMO** 🗂️\n")
    print("This demo shows switching between file-based and database-backed storage")
    print("="*70 + "\n")

    try:
        await demo_file_storage()
        await demo_database_storage()
        await demo_backend_switching()
        await demo_configuration_from_dict()

        print("🎉 **ALL DEMOS COMPLETED SUCCESSFULLY!** 🎉\n")
        print("📋 **SUMMARY:**")
        print("✅ File-based backend working")
        print("✅ Database-backed backend working")
        print("✅ Runtime backend switching")
        print("✅ Configuration-driven setup")
        print("✅ Gradual migration support")
        print("\n💡 **USE CASES:**")
        print("• Component-by-component migration (e.g., master_coordinator → database, others → file)")
        print("• Runtime environment switching (dev file → prod database)")
        print("• Fallback mechanisms (database fails → file backup)")
        print("• Dual mode for testing and validation")

    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("This demo has been moved to `examples/demo_data_access_layer.py`. Run that file for the full demo.")
    # Keep a no-op main to avoid pytest collection issues when imported.
    # The working demo lives in `examples/`.
