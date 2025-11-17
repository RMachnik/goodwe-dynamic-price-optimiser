#!/usr/bin/env python3
"""
Test Database Infrastructure for GoodWe Dynamic Price Optimiser
Comprehensive tests for database schema, storage interface, and connection management
"""

import pytest
import asyncio
import tempfile
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Import database modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.schema import DatabaseSchema, EnergyData, ChargingSession, SystemState
from database.storage_interface import StorageConfig
from database.sqlite_storage import SQLiteStorage
from database.connection_manager import ConnectionManager

class TestDatabaseSchema:
    """Test database schema creation and management"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_schema_creation(self, temp_db):
        """Test database schema creation"""
        schema = DatabaseSchema(temp_db)
        
        # Connect and create tables
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        assert schema.verify_schema()
        
        schema.disconnect()
    
    def test_schema_verification(self, temp_db):
        """Test schema verification"""
        schema = DatabaseSchema(temp_db)
        
        # Create schema
        schema.connect()
        schema.create_tables()
        
        # Verify all tables exist
        assert schema.verify_schema()
        
        schema.disconnect()
    
    def test_schema_without_connection(self, temp_db):
        """Test schema operations without connection"""
        schema = DatabaseSchema(temp_db)
        
        # Should fail without connection
        assert not schema.create_tables()
        assert not schema.create_indexes()
        assert not schema.verify_schema()

class TestStorageInterface:
    """Test storage interface implementation"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration"""
        return StorageConfig(
            db_path=temp_db,
            max_retries=3,
            retry_delay=0.1,
            connection_pool_size=5,
            batch_size=10,
            enable_fallback=True,
            fallback_to_file=True
        )
    
    @pytest.fixture
    def storage(self, storage_config, temp_db):
        """Create storage instance with schema"""
        # Create schema and tables first
        from database.schema import DatabaseSchema
        schema = DatabaseSchema(temp_db)
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        schema.disconnect()

        # Now create storage instance
        return SQLiteStorage(storage_config)
    
    @pytest.mark.asyncio
    async def test_storage_connection(self, storage):
        """Test storage connection"""
        assert await storage.connect()
        assert storage.is_connected
        assert await storage.health_check()
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_energy_data_operations(self, storage):
        """Test energy data save and retrieve"""
        await storage.connect()
        
        # Test data
        test_data = [
            {
                'timestamp': datetime.now(),
                'battery_soc': 75.5,
                'pv_power': 2500.0,
                'grid_power': -1000.0,
                'consumption': 1500.0,
                'price': 0.45,
                'battery_temp': 25.0,
                'battery_voltage': 400.0,
                'grid_voltage': 230.0
            },
            {
                'timestamp': datetime.now() + timedelta(minutes=1),
                'battery_soc': 76.0,
                'pv_power': 2600.0,
                'grid_power': -1100.0,
                'consumption': 1500.0,
                'price': 0.46,
                'battery_temp': 25.5,
                'battery_voltage': 401.0,
                'grid_voltage': 231.0
            }
        ]
        
        # Save data
        assert await storage.save_energy_data(test_data)
        
        # Retrieve data
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved_data = await storage.get_energy_data(start_time, end_time)
        
        assert len(retrieved_data) == 2
        assert retrieved_data[0]['battery_soc'] == 75.5
        assert retrieved_data[1]['battery_soc'] == 76.0
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_charging_session_operations(self, storage):
        """Test charging session save and retrieve"""
        await storage.connect()
        
        # Test session data
        session_data = {
            'session_id': 'test_session_001',
            'start_time': datetime.now(),
            'end_time': datetime.now() + timedelta(hours=2),
            'energy_kwh': 5.5,
            'cost_pln': 2.48,
            'status': 'completed',
            'battery_soc_start': 30.0,
            'battery_soc_end': 85.0,
            'charging_source': 'grid',
            'pv_contribution_kwh': 0.5,
            'grid_contribution_kwh': 5.0
        }
        
        # Save session
        assert await storage.save_charging_session(session_data)
        
        # Retrieve sessions
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() + timedelta(days=1)
        sessions = await storage.get_charging_sessions(start_date, end_date)
        
        assert len(sessions) == 1
        assert sessions[0]['session_id'] == 'test_session_001'
        assert sessions[0]['energy_kwh'] == 5.5
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_system_state_operations(self, storage):
        """Test system state save and retrieve"""
        await storage.connect()
        
        # Test state data
        state_data = {
            'timestamp': datetime.now(),
            'state': 'monitoring',
            'uptime_seconds': 3600.0,
            'current_data': {
                'battery_soc': 75.0,
                'pv_power': 2500.0,
                'grid_power': -1000.0
            },
            'performance_metrics': {
                'cpu_usage': 15.5,
                'memory_usage': 45.2
            },
            'decision_count': 25
        }
        
        # Save state
        assert await storage.save_system_state(state_data)
        
        # Retrieve states
        states = await storage.get_system_state(limit=10)
        
        assert len(states) == 1
        assert states[0]['state'] == 'monitoring'
        assert states[0]['uptime_seconds'] == 3600.0
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_decision_operations(self, storage):
        """Test coordinator decision save and retrieve"""
        await storage.connect()
        
        # Test decision data
        decision_data = {
            'timestamp': datetime.now(),
            'decision_type': 'charging',
            'should_charge': True,
            'reason': 'Low price and good conditions',
            'confidence': 0.85,
            'current_price': 0.45,
            'cheapest_price': 0.40,
            'cheapest_hour': 14,
            'battery_soc': 45.0,
            'pv_power': 2500.0,
            'consumption': 1500.0,
            'decision_score': 75.5
        }
        
        # Save decision
        assert await storage.save_decision(decision_data)
        
        # Retrieve decisions
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        decisions = await storage.get_decisions(start_time, end_time)
        
        assert len(decisions) == 1
        assert decisions[0]['should_charge'] == True
        assert decisions[0]['confidence'] == 0.85
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_weather_data_operations(self, storage):
        """Test weather data save and retrieve"""
        await storage.connect()
        
        # Test weather data
        weather_data = [
            {
                'timestamp': datetime.now(),
                'source': 'imgw',
                'temperature': 22.5,
                'humidity': 65.0,
                'pressure': 1013.25,
                'wind_speed': 5.5,
                'wind_direction': 180.0,
                'precipitation': 0.0,
                'cloud_cover': 30,
                'solar_irradiance': 800.0
            }
        ]
        
        # Save weather data
        assert await storage.save_weather_data(weather_data)
        
        # Retrieve weather data
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved_data = await storage.get_weather_data(start_time, end_time)
        
        assert len(retrieved_data) == 1
        assert retrieved_data[0]['source'] == 'imgw'
        assert retrieved_data[0]['temperature'] == 22.5
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_price_forecast_operations(self, storage):
        """Test price forecast save and retrieve"""
        await storage.connect()
        
        # Test forecast data
        forecast_data = [
            {
                'timestamp': datetime.now(),
                'forecast_date': '2025-01-10',
                'hour': 12,
                'price_pln': 0.45,
                'confidence': 0.85,
                'source': 'pse'
            },
            {
                'timestamp': datetime.now(),
                'forecast_date': '2025-01-10',
                'hour': 13,
                'price_pln': 0.50,
                'confidence': 0.80,
                'source': 'pse'
            }
        ]
        
        # Save forecast
        assert await storage.save_price_forecast(forecast_data)
        
        # Retrieve forecast
        forecasts = await storage.get_price_forecasts('2025-01-10')
        
        assert len(forecasts) == 2
        assert forecasts[0]['hour'] == 12
        assert forecasts[1]['hour'] == 13
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_pv_forecast_operations(self, storage):
        """Test PV forecast save and retrieve"""
        await storage.connect()
        
        # Test forecast data
        forecast_data = [
            {
                'timestamp': datetime.now(),
                'forecast_date': '2025-01-10',
                'hour': 12,
                'predicted_power_w': 2500.0,
                'confidence': 0.90,
                'weather_conditions': 'sunny'
            }
        ]
        
        # Save forecast
        assert await storage.save_pv_forecast(forecast_data)
        
        # Retrieve forecast
        forecasts = await storage.get_pv_forecasts('2025-01-10')
        
        assert len(forecasts) == 1
        assert forecasts[0]['predicted_power_w'] == 2500.0
        assert forecasts[0]['weather_conditions'] == 'sunny'
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_batch_operations(self, storage):
        """Test batch operations for performance"""
        await storage.connect()

        # Create large dataset with sufficient time spread to avoid precision issues
        base_time = datetime.now().replace(microsecond=0)  # Remove microseconds for precision
        large_dataset = []
        for i in range(100):
            large_dataset.append({
                'timestamp': base_time + timedelta(minutes=i),
                'battery_soc': 50.0 + i * 0.1,
                'pv_power': 1000.0 + i * 10,
                'grid_power': -500.0 - i * 5,
                'consumption': 1500.0 + i * 2,
                'price': 0.40 + i * 0.001,
                'battery_temp': 25.0 + i * 0.1,
                'battery_voltage': 400.0 + i * 0.1,
                'grid_voltage': 230.0 + i * 0.01
            })

        # Save in batches
        save_start_time = datetime.now()
        assert await storage.save_energy_data(large_dataset)
        save_end_time = datetime.now()

        # Should complete quickly
        save_duration = (save_end_time - save_start_time).total_seconds()
        assert save_duration < 5.0  # Should complete in under 5 seconds

        # Verify data was saved with wider time range to account for any timing precision issues
        query_start_time = base_time - timedelta(minutes=5)
        query_end_time = base_time + timedelta(hours=2)  # Extend far enough
        retrieved_data = await storage.get_energy_data(query_start_time, query_end_time)

        # Should have all 100 records
        assert len(retrieved_data) == 100

        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_error_handling(self, storage):
        """Test error handling and retry logic"""
        # Test with invalid database path - should raise ConnectionError
        invalid_config = StorageConfig(
            db_path="/invalid/path/database.db",
            max_retries=2,
            retry_delay=0.1
        )
        invalid_storage = SQLiteStorage(invalid_config)

        # Should fail to connect and raise ConnectionError
        try:
            await invalid_storage.connect()
            assert False, "Should have raised ConnectionError"
        except Exception as e:
            # Should raise ConnectionError from the storage interface
            from database.storage_interface import ConnectionError as StorageConnectionError
            assert isinstance(e, StorageConnectionError), f"Unexpected exception type: {type(e)}"

        # Test with valid connection but invalid operations
        await storage.connect()

        # Test with invalid data (should handle gracefully)
        invalid_data = [{'invalid': 'data'}]
        # Should not crash, may use fallback
        result = await storage.save_energy_data(invalid_data)
        # Result may be False due to fallback, but should not crash - doesn't matter for this test

        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_health_check(self, storage):
        """Test health check functionality"""
        await storage.connect()
        
        # Health check should pass
        assert await storage.health_check()
        
        await storage.disconnect()
        
        # Health check should fail after disconnect
        assert not await storage.health_check()

class TestConnectionManager:
    """Test connection manager functionality"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_connection_manager_lifecycle(self, temp_db):
        """Test connection manager initialization and shutdown"""
        manager = ConnectionManager(temp_db, max_connections=5, min_connections=2)
        
        # Initialize
        await manager.initialize()
        assert manager.is_initialized
        
        # Test connection
        assert await manager.test_connection()
        
        # Get stats
        stats = manager.get_stats()
        assert stats['is_initialized']
        assert 'pool_stats' in stats
        
        # Shutdown
        await manager.shutdown()
        assert not manager.is_initialized
    
    @pytest.mark.asyncio
    async def test_connection_pooling(self, temp_db):
        """Test connection pooling functionality"""
        manager = ConnectionManager(temp_db, max_connections=3, min_connections=1)
        await manager.initialize()
        
        # Get multiple connections
        connections = []
        for _ in range(3):
            conn = await manager.get_connection()
            connections.append(conn)
        
        # Should have 3 active connections
        stats = manager.get_stats()
        assert stats['pool_stats']['active_connections'] == 3
        
        # Return connections
        for conn in connections:
            await manager.return_connection(conn)
        
        # Should have connections back in pool
        stats = manager.get_stats()
        assert stats['pool_stats']['active_connections'] == 0
        
        await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_connection_manager_without_initialization(self, temp_db):
        """Test connection manager operations without initialization"""
        manager = ConnectionManager(temp_db)
        
        # Should fail without initialization
        with pytest.raises(Exception):
            await manager.get_connection()
        
        # Stats should be empty
        stats = manager.get_stats()
        assert not stats

class TestIntegration:
    """Integration tests for complete database functionality"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, temp_db):
        """Test complete database workflow"""
        # Create schema
        schema = DatabaseSchema(temp_db)
        assert schema.connect()
        assert schema.create_tables()
        assert schema.create_indexes()
        schema.disconnect()
        
        # Create storage
        config = StorageConfig(db_path=temp_db)
        storage = SQLiteStorage(config)
        assert await storage.connect()
        
        # Create connection manager
        manager = ConnectionManager(temp_db)
        await manager.initialize()
        
        # Test complete data flow
        test_data = [
            {
                'timestamp': datetime.now(),
                'battery_soc': 75.0,
                'pv_power': 2500.0,
                'grid_power': -1000.0,
                'consumption': 1500.0,
                'price': 0.45
            }
        ]
        
        # Save data
        assert await storage.save_energy_data(test_data)
        
        # Retrieve data
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        retrieved_data = await storage.get_energy_data(start_time, end_time)
        
        assert len(retrieved_data) == 1
        assert retrieved_data[0]['battery_soc'] == 75.0
        
        # Test health check
        assert await storage.health_check()
        
        # Test backup
        backup_path = temp_db + '.backup'
        assert await storage.backup_data(backup_path)
        assert os.path.exists(backup_path)
        
        # Cleanup
        await storage.disconnect()
        await manager.shutdown()
        os.unlink(backup_path)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
