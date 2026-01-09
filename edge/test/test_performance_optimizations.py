#!/usr/bin/env python3
"""
Test Performance Optimizations for SQLite Storage
Tests for batch operations, data retention, and query optimization
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

# Import database modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.storage_interface import StorageConfig
from database.sqlite_storage import SQLiteStorage


class TestBatchOperations:
    """Test batch operation performance enhancements"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except (FileNotFoundError, OSError, PermissionError):
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration with custom batch size"""
        return StorageConfig(
            db_path=temp_db,
            max_retries=3,
            retry_delay=0.1,
            connection_pool_size=5,
            batch_size=50,  # Test batch processing
            enable_fallback=True,
            fallback_to_file=False
        )
    
    @pytest.mark.asyncio
    async def test_small_batch_operations(self, storage_config):
        """Test batch operations with small dataset (< batch_size)"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Create 25 records (less than batch_size of 50)
        base_time = datetime.now().replace(microsecond=0)
        test_data = []
        for i in range(25):
            test_data.append({
                'timestamp': base_time + timedelta(minutes=i),
                'battery_soc': 50.0 + i * 0.5,
                'pv_power': 1000.0 + i * 10,
                'grid_power': -500.0 - i * 5,
                'house_consumption': 1500.0 + i * 2,
                'price_pln': 0.40 + i * 0.001
            })
        
        # Save should complete in single batch
        assert await storage.save_energy_data(test_data)
        
        # Verify all records saved
        query_start = base_time - timedelta(minutes=5)
        query_end = base_time + timedelta(hours=1)
        retrieved = await storage.get_energy_data(query_start, query_end)
        
        assert len(retrieved) == 25
        assert retrieved[0]['battery_soc'] == 50.0
        assert retrieved[-1]['battery_soc'] == 50.0 + 24 * 0.5
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_large_batch_operations(self, storage_config):
        """Test batch operations with large dataset (> batch_size)"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Create 150 records (3x batch_size of 50)
        base_time = datetime.now().replace(microsecond=0)
        test_data = []
        for i in range(150):
            test_data.append({
                'timestamp': base_time + timedelta(minutes=i),
                'battery_soc': 30.0 + i * 0.3,
                'pv_power': 500.0 + i * 5,
                'grid_power': -200.0 - i * 2,
                'house_consumption': 1200.0 + i,
                'price_pln': 0.35 + i * 0.0005
            })
        
        # Save should process in 3 batches
        start_time = datetime.now()
        assert await storage.save_energy_data(test_data)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Should complete reasonably fast even with batching
        assert duration < 10.0
        
        # Verify all records saved
        query_start = base_time - timedelta(minutes=5)
        query_end = base_time + timedelta(hours=3)
        retrieved = await storage.get_energy_data(query_start, query_end)
        
        assert len(retrieved) == 150
        
        await storage.disconnect()


class TestDataRetention:
    """Test data retention and cleanup functionality"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except (FileNotFoundError, OSError, PermissionError):
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration"""
        return StorageConfig(
            db_path=temp_db,
            retention_days=7,
            enable_auto_cleanup=True
        )
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, storage_config):
        """Test automatic cleanup of old data"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Insert data from different time periods
        now = datetime.now()
        
        # Old data (10 days ago) - should be cleaned
        old_data = []
        for i in range(5):
            old_data.append({
                'timestamp': (now - timedelta(days=10, minutes=i)),
                'battery_soc': 40.0,
                'pv_power': 1000.0
            })
        
        # Recent data (2 days ago) - should be kept
        recent_data = []
        for i in range(5):
            recent_data.append({
                'timestamp': (now - timedelta(days=2, minutes=i)),
                'battery_soc': 60.0,
                'pv_power': 2000.0
            })
        
        # Save both datasets
        assert await storage.save_energy_data(old_data)
        assert await storage.save_energy_data(recent_data)
        
        # Verify initial count
        all_data = await storage.get_energy_data(
            now - timedelta(days=15),
            now + timedelta(days=1)
        )
        assert len(all_data) == 10
        
        # Run cleanup with 7-day retention
        cleanup_results = await storage.cleanup_old_data(7)
        
        # Should have cleaned old data from energy_data table
        assert 'energy_data' in cleanup_results
        assert cleanup_results['energy_data'] == 5
        
        # Verify only recent data remains
        remaining_data = await storage.get_energy_data(
            now - timedelta(days=15),
            now + timedelta(days=1)
        )
        assert len(remaining_data) == 5
        assert all(d['battery_soc'] == 60.0 for d in remaining_data)
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_cleanup_multiple_tables(self, storage_config):
        """Test cleanup across multiple tables"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        now = datetime.now()
        
        # Add old data to multiple tables
        # Energy data
        await storage.save_energy_data([{
            'timestamp': now - timedelta(days=10),
            'battery_soc': 50.0,
            'pv_power': 1000.0
        }])
        
        # System state
        await storage.save_system_state({
            'timestamp': now - timedelta(days=10),
            'state': 'old_state',
            'uptime': 3600
        })
        
        # Decision
        await storage.save_decision({
            'timestamp': now - timedelta(days=10),
            'decision_type': 'old_decision',
            'action': 'charge'
        })
        
        # Run cleanup
        results = await storage.cleanup_old_data(7)
        
        # Should have cleaned from multiple tables
        assert results.get('energy_data', 0) >= 1
        assert results.get('system_state', 0) >= 1
        assert results.get('coordinator_decisions', 0) >= 1
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_cleanup_zero_retention(self, storage_config):
        """Test that zero retention doesn't delete anything"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Add some data
        await storage.save_energy_data([{
            'timestamp': datetime.now() - timedelta(days=100),
            'battery_soc': 50.0,
            'pv_power': 1000.0
        }])
        
        # Run cleanup with 0 retention (should not delete)
        results = await storage.cleanup_old_data(0)
        
        # Should return empty results (no cleanup)
        assert results == {}
        
        await storage.disconnect()


class TestDatabaseStats:
    """Test database statistics and monitoring"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except (FileNotFoundError, OSError, PermissionError):
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration"""
        return StorageConfig(db_path=temp_db)
    
    @pytest.mark.asyncio
    async def test_get_database_stats(self, storage_config):
        """Test database statistics retrieval"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Add some data
        test_data = [{
            'timestamp': datetime.now(),
            'battery_soc': 75.0,
            'pv_power': 2500.0
        }]
        await storage.save_energy_data(test_data)
        
        # Get stats
        stats = await storage.get_database_stats()
        
        # Verify stats structure
        assert 'energy_data_count' in stats
        assert stats['energy_data_count'] >= 1
        assert 'database_size_bytes' in stats
        assert 'database_size_mb' in stats
        assert 'page_count' in stats
        assert 'page_size' in stats
        assert 'schema_version' in stats
        
        # Schema version should be current
        assert stats['schema_version'] >= 3
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_stats_all_tables(self, storage_config):
        """Test stats include all tables"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        stats = await storage.get_database_stats()
        
        # Verify all table counts are present
        expected_tables = [
            'energy_data', 'system_state', 'coordinator_decisions',
            'charging_sessions', 'battery_selling_sessions',
            'weather_data', 'price_forecasts', 'pv_forecasts'
        ]
        
        for table in expected_tables:
            assert f'{table}_count' in stats
            assert isinstance(stats[f'{table}_count'], int)
        
        await storage.disconnect()


class TestQueryOptimization:
    """Test query performance analysis"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except (FileNotFoundError, OSError, PermissionError):
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration"""
        return StorageConfig(db_path=temp_db)
    
    @pytest.mark.asyncio
    async def test_analyze_query_performance(self, storage_config):
        """Test query performance analysis"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Analyze a simple query
        query = "SELECT * FROM energy_data WHERE timestamp > ?"
        params = ('2025-01-01T00:00:00',)
        
        analysis = await storage.analyze_query_performance(query, params)
        
        # Verify analysis structure
        assert 'query' in analysis
        assert analysis['query'] == query
        assert 'query_plan' in analysis
        assert isinstance(analysis['query_plan'], list)
        assert 'indexes_used' in analysis
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_optimize_database(self, storage_config):
        """Test database optimization"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Add some data first
        await storage.save_energy_data([{
            'timestamp': datetime.now(),
            'battery_soc': 75.0,
            'pv_power': 2500.0
        }])
        
        # Run optimization
        results = await storage.optimize_database()
        
        # Verify optimization completed
        assert results['success'] is True
        assert 'results' in results
        assert results['results']['analyze'] == 'completed'
        assert results['results']['vacuum'] == 'completed'
        assert 'database_stats' in results['results']
        
        await storage.disconnect()


class TestSchemaVersion:
    """Test schema version 3 migration with new indexes"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        try:
            os.unlink(db_path)
        except (FileNotFoundError, OSError, PermissionError):
            pass
    
    @pytest.fixture
    def storage_config(self, temp_db):
        """Create storage configuration"""
        return StorageConfig(db_path=temp_db)
    
    @pytest.mark.asyncio
    async def test_version_4_indexes_created(self, storage_config):
        """Test that version 4 migration creates performance indexes"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Check schema version
        version = await storage._get_current_schema_version()
        assert version == 4
        
        # Verify new indexes exist
        async with storage._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ) as cursor:
            rows = await cursor.fetchall()
            index_names = [row[0] for row in rows]
        
        # Check for some of the new composite indexes
        expected_indexes = [
            'idx_decisions_type_time',
            'idx_sessions_status_start',
            'idx_price_forecast_date',
            'idx_pv_forecast_date'
        ]
        
        for idx in expected_indexes:
            assert idx in index_names, f"Index {idx} not found"
        
        await storage.disconnect()
    
    @pytest.mark.asyncio
    async def test_indexes_improve_queries(self, storage_config):
        """Test that indexes are used in queries"""
        storage = SQLiteStorage(storage_config)
        assert await storage.connect()
        
        # Insert some test data
        now = datetime.now()
        for i in range(10):
            await storage.save_decision({
                'timestamp': now + timedelta(minutes=i),
                'decision_type': 'charging',
                'action': 'start',
                'reason': 'test'
            })
        
        # Analyze query that should use index
        query = "SELECT * FROM coordinator_decisions WHERE decision_type = ? AND timestamp > ?"
        params = ('charging', now.isoformat())
        
        analysis = await storage.analyze_query_performance(query, params)
        
        # Should use the composite index
        assert len(analysis.get('indexes_used', [])) > 0
        
        await storage.disconnect()
