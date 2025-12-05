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
    
    config_dict = {
        "database_storage": {
            "enabled": True,
            "sqlite": {
                "path": str(db_path)
            }
        }
    }
    
    return config_dict, db_path

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_sqlite_storage_flow(temp_storage_config):
    """Test the full flow of SQLiteStorage: Connect -> Write -> Read -> Disconnect."""
    config_dict, db_path = temp_storage_config
    
    # 1. Create Storage
    storage = StorageFactory.create_storage(config_dict)
    assert storage.__class__.__name__ == "SQLiteStorage"
    
    # 2. Connect
    assert await storage.connect() is True
    assert await storage.health_check() is True
    
    # 3. Write Data
    assert await storage.save_energy_data(SAMPLE_ENERGY_DATA) is True
    assert await storage.save_system_state(SAMPLE_STATE) is True
    
    # 4. Verify DB Write
    start = datetime.now().replace(hour=0, minute=0, second=0)
    end = datetime.now().replace(hour=23, minute=59, second=59)
    
    read_data = await storage.get_energy_data(start, end)
    assert len(read_data) == 1
    assert read_data[0]['battery_soc'] == 85.5
    
    # 5. Disconnect
    await storage.disconnect()

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_storage_factory_modes(tmp_path):
    """Test that factory creates SQLiteStorage when database is enabled."""
    
    # Case 1: DB Enabled
    config_db_only = {
        "database_storage": {"enabled": True, "sqlite": {"path": str(tmp_path / "db.sqlite")}}
    }
    storage = StorageFactory.create_storage(config_db_only)
    assert storage.__class__.__name__ == "SQLiteStorage"
    
    # Case 2: DB Disabled (should raise error)
    config_db_disabled = {
        "database_storage": {"enabled": False}
    }
    with pytest.raises(ValueError, match="Database storage must be enabled"):
        StorageFactory.create_storage(config_db_disabled)

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
