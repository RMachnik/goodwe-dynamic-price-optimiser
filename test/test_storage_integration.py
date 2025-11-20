import pytest
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.storage_factory import StorageFactory
from database.storage_interface import StorageConfig

# Test data
SAMPLE_ENERGY_DATA = [
    {
        "timestamp": datetime.now().isoformat(),
        "battery_soc": 85.5,
        "pv_power": 1500,
        "grid_power": -500,
        "house_consumption": 1000,
        "battery_power": -500,
        "grid_voltage": 230.5,
        "grid_frequency": 50.0,
        "battery_voltage": 52.1,
        "battery_current": 10.5,
        "battery_temperature": 25.0,
        "price_pln": 0.50
    }
]

SAMPLE_STATE = {
    "timestamp": datetime.now().isoformat(),
    "state": "running",
    "uptime": 3600,
    "active_modules": ["collector", "optimizer"],
    "last_error": None,
    "metrics": {"cpu": 10, "memory": 20}
}

@pytest.fixture
def temp_storage_config(tmp_path):
    """Create a temporary storage configuration."""
    db_path = tmp_path / "test_db.sqlite"
    energy_dir = tmp_path / "energy_data"
    
    # Create directories
    energy_dir.mkdir(parents=True, exist_ok=True)
    
    config_dict = {
        "file_storage": {
            "enabled": True,
            "energy_data_dir": str(energy_dir)
        },
        "database_storage": {
            "enabled": True,
            "sqlite": {
                "path": str(db_path)
            }
        }
    }
    
    return config_dict, db_path, energy_dir

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_composite_storage_flow(temp_storage_config):
    """Test the full flow of CompositeStorage: Connect -> Write -> Read -> Disconnect."""
    config_dict, db_path, energy_dir = temp_storage_config
    
    # 1. Create Storage
    storage = StorageFactory.create_storage(config_dict)
    
    # Hack to set the base_dir for file storage correctly for the test
    # In the real app, FileStorage uses hardcoded paths relative to 'out', 
    # but for testing we want to use tmp_path.
    # We need to inspect the composite structure to patch the FileStorage instance.
    file_storage = storage.secondaries[0]
    file_storage.energy_data_dir = str(energy_dir)
    file_storage.base_dir = str(energy_dir.parent)
    
    # 2. Connect
    assert await storage.connect() is True
    assert await storage.health_check() is True
    
    # 3. Write Data
    assert await storage.save_energy_data(SAMPLE_ENERGY_DATA) is True
    assert await storage.save_system_state(SAMPLE_STATE) is True
    
    # 4. Verify DB Write (Primary)
    # We can read back using the storage interface
    start = datetime.now().replace(hour=0, minute=0, second=0)
    end = datetime.now().replace(hour=23, minute=59, second=59)
    
    read_data = await storage.get_energy_data(start, end)
    assert len(read_data) == 1
    assert read_data[0]['battery_soc'] == 85.5
    
    # 5. Verify File Write (Secondary)
    # Check if file exists
    files = list(energy_dir.glob("energy_data_*.json"))
    assert len(files) > 0
    
    with open(files[0], 'r') as f:
        file_content = json.load(f)
        assert len(file_content) == 1
        assert file_content[0]['battery_soc'] == 85.5
        
    # 6. Test Fallback (Simulate DB Failure)
    # We'll manually close the DB connection to simulate failure
    await storage.primary.disconnect()
    
    # Try to read - should fall back to file
    # Note: The composite storage health check might fail, but read should try fallback
    fallback_data = await storage.get_energy_data(start, end)
    assert len(fallback_data) == 1
    assert fallback_data[0]['battery_soc'] == 85.5
    
    # 7. Disconnect
    await storage.disconnect()

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_storage_factory_modes(tmp_path):
    """Test that factory creates correct instances based on config."""
    
    # Case 1: DB Only
    config_db_only = {
        "file_storage": {"enabled": False},
        "database_storage": {"enabled": True, "sqlite": {"path": str(tmp_path / "db.sqlite")}}
    }
    storage = StorageFactory.create_storage(config_db_only)
    assert storage.__class__.__name__ == "SQLiteStorage"
    
    # Case 2: File Only
    config_file_only = {
        "file_storage": {"enabled": True},
        "database_storage": {"enabled": False}
    }
    storage = StorageFactory.create_storage(config_file_only)
    assert storage.__class__.__name__ == "FileStorage"
    
    # Case 3: Composite
    config_composite = {
        "file_storage": {"enabled": True},
        "database_storage": {"enabled": True, "sqlite": {"path": str(tmp_path / "db.sqlite")}}
    }
    storage = StorageFactory.create_storage(config_composite)
    assert storage.__class__.__name__ == "CompositeStorage"

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_system_state_operations(storage):
    """Test saving and retrieving system state."""
    # Save state
    assert await storage.save_system_state(SAMPLE_STATE) is True
    
    # Retrieve recent state
    states = await storage.get_system_state(limit=10)
    assert len(states) > 0
    assert states[0]['state'] == SAMPLE_STATE['state']
    
    # Retrieve state range
    start = datetime.now() - timedelta(hours=1)
    end = datetime.now() + timedelta(hours=1)
    states_range = await storage.get_system_state_range(start, end)
    assert len(states_range) > 0
    assert states_range[0]['state'] == SAMPLE_STATE['state']

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_decision_operations(storage):
    """Test decision-making operations."""
    # This is a placeholder for actual decision-making logic
    pass
