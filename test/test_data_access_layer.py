#!/usr/bin/env python3
"""
Test Data Access Layer abstraction
Tests the ability to switch between file and database backends
"""

import pytest
import asyncio
import tempfile
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import os
import shutil

# Import data access layer
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from data_access_layer import (
    DataAccessLayer, DataStorageConfig, FileStorageBackend, DatabaseStorageBackend,
    create_data_access_layer
)

class TestDataAccessLayer:
    """Test the data access layer abstraction"""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        temp_base = Path(tempfile.mkdtemp())
        db_path = temp_base / "test.db"
        file_path = temp_base / "files"

        yield {
            'base': temp_base,
            'db_path': str(db_path),
            'file_path': str(file_path)
        }

        # Cleanup
        try:
            shutil.rmtree(temp_base)
        except:
            pass

    @pytest.mark.asyncio
    async def test_file_backend_operations(self, temp_dirs):
        """Test file backend operations"""
        # Create file backend directly
        config = {
            'base_path': temp_dirs['file_path']
        }
        backend = FileStorageBackend(config)

        assert await backend.connect()
        assert backend.is_connected
        assert await backend.health_check()

        # Test energy data operations
        test_data = [
            {
                'timestamp': datetime.now().isoformat(),
                'battery_soc': 75.5,
                'pv_power': 2500.0
            }
        ]

        assert await backend.save_energy_data(test_data)

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved = await backend.get_energy_data(start_time, end_time)

        assert len(retrieved) == 1
        assert retrieved[0]['battery_soc'] == 75.5

        # Test system state operations
        state_data = {
            'timestamp': datetime.now().isoformat(),
            'state': 'monitoring',
            'uptime_seconds': 3600
        }

        assert await backend.save_system_state(state_data)
        states = await backend.get_system_state(10)
        assert len(states) >= 1

        # Test decision operations
        decision_data = {
            'timestamp': datetime.now().isoformat(),
            'action': 'wait',
            'reason': 'Low price window'
        }

        assert await backend.save_decision(decision_data)
        decisions = await backend.get_decisions(start_time, end_time)
        assert len(decisions) >= 1

        assert await backend.disconnect()

    @pytest.mark.asyncio
    async def test_database_backend_operations(self, temp_dirs):
        """Test database backend operations"""
        # Create database backend directly
        config = {
            'db_path': temp_dirs['db_path'],
            'batch_size': 10
        }
        backend = DatabaseStorageBackend(config)

        # Database backend needs schema to be created first
        from database.schema import DatabaseSchema
        schema = DatabaseSchema(temp_dirs['db_path'])
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        schema.disconnect()

        assert await backend.connect()
        assert backend.is_connected
        assert await backend.health_check()

        # Test energy data operations
        test_data = [
            {
                'timestamp': datetime.now(),
                'battery_soc': 80.0,
                'pv_power': 2200.0
            },
            {
                'timestamp': datetime.now() + timedelta(minutes=1),
                'battery_soc': 81.0,
                'pv_power': 2300.0
            }
        ]

        assert await backend.save_energy_data(test_data)

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved = await backend.get_energy_data(start_time, end_time)

        assert len(retrieved) == 2
        assert retrieved[0]['battery_soc'] == 80.0
        assert retrieved[1]['battery_soc'] == 81.0

        # Test batch operations (100 records)
        large_dataset = []
        for i in range(100):
            large_dataset.append({
                'timestamp': datetime.now() + timedelta(minutes=i),
                'battery_soc': 50.0 + i * 0.1,
                'pv_power': 1000.0 + i * 10
            })

        assert await backend.save_energy_data(large_dataset)
        retrieved_large = await backend.get_energy_data(
            datetime.now() - timedelta(minutes=5),
            datetime.now() + timedelta(hours=2)
        )

        # Should have all 102 records (2 original + 100 new)
        assert len(retrieved_large) == 102

        # Test system state and decision operations
        state_data = {
            'timestamp': datetime.now(),
            'state': 'monitoring',
            'uptime_seconds': 3600
        }

        assert await backend.save_system_state(state_data)
        states = await backend.get_system_state(10)
        assert len(states) >= 1

        decision_data = {
            'timestamp': datetime.now(),
            'action': 'wait',
            'reason': 'Database backend test'
        }

        assert await backend.save_decision(decision_data)
        decisions = await backend.get_decisions(start_time, end_time)
        assert len(decisions) >= 1

        assert await backend.disconnect()

    @pytest.mark.asyncio
    async def test_data_access_layer_file_mode(self, temp_dirs):
        """Test data access layer in file mode"""
        config = DataStorageConfig(
            mode="file",
            file_config={
                'base_path': temp_dirs['file_path']
            }
        )

        dal = DataAccessLayer(config)

        assert await dal.connect()
        assert dal.get_backend_mode() == "file"

        backend_info = dal.get_backend_info()
        assert backend_info['mode'] == 'file'
        assert 'FileStorageBackend' in backend_info['backend_type']

        # Test operations
        test_data = [{
            'timestamp': datetime.now().isoformat(),
            'battery_soc': 70.0
        }]

        assert await dal.save_energy_data(test_data)

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved = await dal.get_energy_data(start_time, end_time)

        assert len(retrieved) == 1
        assert await dal.health_check()
        assert await dal.disconnect()

    @pytest.mark.asyncio
    async def test_data_access_layer_database_mode(self, temp_dirs):
        """Test data access layer in database mode"""
        # Setup database schema first
        from database.schema import DatabaseSchema
        schema = DatabaseSchema(temp_dirs['db_path'])
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        schema.disconnect()

        config = DataStorageConfig(
            mode="database",
            database_config={
                'db_path': temp_dirs['db_path']
            }
        )

        dal = DataAccessLayer(config)

        assert await dal.connect()
        assert dal.get_backend_mode() == "database"

        backend_info = dal.get_backend_info()
        assert backend_info['mode'] == 'database'
        assert 'DatabaseStorageBackend' in backend_info['backend_type']

        # Test operations
        test_data = [{
            'timestamp': datetime.now(),
            'battery_soc': 85.0
        }]

        assert await dal.save_energy_data(test_data)

        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved = await dal.get_energy_data(start_time, end_time)

        assert len(retrieved) == 1
        assert retrieved[0]['battery_soc'] == 85.0

        # Test backend switching
        dal.switch_backend("file")
        assert dal.get_backend_mode() == "file"

        new_data = [{
            'timestamp': datetime.now().isoformat(),
            'battery_soc': 90.0
        }]

        assert await dal.save_energy_data(new_data)
        retrieved_after_switch = await dal.get_energy_data(start_time, end_time)
        assert len(retrieved_after_switch) == 2  # File backend loads all available data

        assert await dal.health_check()
        assert await dal.disconnect()

    @pytest.mark.asyncio
    async def test_real_world_usage_scenario(self, temp_dirs):
        """Test real-world usage scenario with backend switching"""
        # Setup database
        from database.schema import DatabaseSchema
        schema = DatabaseSchema(temp_dirs['db_path'])
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        schema.disconnect()

        # Start with database mode
        config = DataStorageConfig(
            mode="database",
            database_config={'db_path': temp_dirs['db_path']},
            file_config={'base_path': temp_dirs['file_path']}
        )

        dal = DataAccessLayer(config)

        # Connect and operate with database
        assert await dal.connect()
        assert dal.get_backend_mode() == "database"

        # Save some initial data
        initial_data = [{
            'timestamp': datetime.now(),
            'battery_soc': 75.0,
            'pv_power': 2500.0
        }]

        assert await dal.save_energy_data(initial_data)

        # Simulate system using database backend
        for i in range(10):
            monitoring_data = [{
                'timestamp': datetime.now() + timedelta(minutes=i),
                'battery_soc': 75.0 + i,
                'pv_power': 2500 + i * 100
            }]

            assert await dal.save_energy_data(monitoring_data)

            # Save periodic state
            state_data = {
                'timestamp': datetime.now() + timedelta(minutes=i),
                'state': 'monitoring',
                'uptime_seconds': i * 60
            }

            assert await dal.save_system_state(state_data)

        # Verify database data
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        energy_data = await dal.get_energy_data(start_time, end_time)
        system_states = await dal.get_system_state(50)

        assert len(energy_data) == 11  # Initial + 10 monitoring
        assert len(system_states) == 10

        # Now simulate transitioning to file-based storage
        # (could be due to database maintenance, switching environments, etc.)
        dal.switch_backend("file")
        assert dal.get_backend_mode() == "file"

        # Continue operations with file backend
        for i in range(5):
            file_data = [{
                'timestamp': datetime.now().isoformat(),
                'battery_soc': 85.0 + i,
                'pv_power': 3000 + i * 50
            }]

            assert await dal.save_energy_data(file_data)

        # Verify both backends work independently
        # File backend should return recent data
        recent_data = await dal.get_energy_data(
            datetime.now() - timedelta(minutes=10),
            datetime.now() + timedelta(minutes=1)
        )
        assert len(recent_data) >= 5  # At least the 5 file-based records

        # Switch back to database and verify original data is still there
        dal.switch_backend("database")
        db_data = await dal.get_energy_data(start_time, end_time)
        assert len(db_data) == 11

        # Test that health checks work for both backends
        assert await dal.health_check()

        # Cleanup
        assert await dal.disconnect()

# Tests are implemented as pytest test functions; remove script-style runner.
