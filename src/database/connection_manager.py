#!/usr/bin/env python3
"""
Connection Manager for GoodWe Dynamic Price Optimiser
Manages database connections with pooling and monitoring
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    """Connection statistics"""
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    connection_errors: int = 0
    last_connection_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None

class ConnectionPool:
    """Database connection pool"""
    
    def __init__(self, db_path: str, max_connections: int = 10, min_connections: int = 2):
        self.db_path = db_path
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.connections: List[aiosqlite.Connection] = []
        self.active_connections: List[aiosqlite.Connection] = []
        self.stats = ConnectionStats()
        self._lock = asyncio.Lock()
        self._cleanup_task = None
        self._is_running = False
    
    async def start(self):
        """Start connection pool"""
        if self._is_running:
            return
        
        self._is_running = True
        # Create minimum connections
        for _ in range(self.min_connections):
            await self._create_connection()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_connections())
        logger.info(f"Connection pool started with {len(self.connections)} connections")
    
    async def stop(self):
        """Stop connection pool"""
        if not self._is_running:
            return
        
        self._is_running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        async with self._lock:
            for conn in self.connections + self.active_connections:
                try:
                    await conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            self.connections.clear()
            self.active_connections.clear()
        
        logger.info("Connection pool stopped")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get connection from pool"""
        async with self._lock:
            # Try to get existing connection
            if self.connections:
                conn = self.connections.pop()
                self.active_connections.append(conn)
                self.stats.active_connections = len(self.active_connections)
                return conn
            
            # Create new connection if under limit
            if len(self.active_connections) < self.max_connections:
                conn = await self._create_connection()
                self.active_connections.append(conn)
                self.stats.active_connections = len(self.active_connections)
                return conn
            
            # Wait for connection to become available
            while not self.connections and len(self.active_connections) >= self.max_connections:
                await asyncio.sleep(0.1)
            
            if self.connections:
                conn = self.connections.pop()
                self.active_connections.append(conn)
                self.stats.active_connections = len(self.active_connections)
                return conn
            
            raise Exception("Failed to get database connection")
    
    async def return_connection(self, conn: aiosqlite.Connection):
        """Return connection to pool"""
        async with self._lock:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                self.connections.append(conn)
                self.stats.active_connections = len(self.active_connections)
            else:
                # Connection not in active list, close it
                try:
                    await conn.close()
                except Exception as e:
                    logger.warning(f"Error closing unknown connection: {e}")
    
    async def _create_connection(self) -> aiosqlite.Connection:
        """Create new database connection"""
        try:
            # Ensure database directory exists
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            
            # Test connection
            await conn.execute("SELECT 1")
            
            self.stats.total_connections += 1
            self.stats.last_connection_time = datetime.now()
            
            logger.debug(f"Created new database connection (total: {self.stats.total_connections})")
            return conn
            
        except Exception as e:
            self.stats.failed_connections += 1
            self.stats.connection_errors += 1
            self.stats.last_error_time = datetime.now()
            logger.error(f"Failed to create database connection: {e}")
            raise
    
    async def _cleanup_connections(self):
        """Cleanup unused connections"""
        while self._is_running:
            try:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
                async with self._lock:
                    # Remove connections that have been idle for too long
                    current_time = datetime.now()
                    connections_to_remove = []
                    
                    for conn in self.connections:
                        # Check if connection is still valid
                        try:
                            await conn.execute("SELECT 1")
                        except Exception:
                            connections_to_remove.append(conn)
                    
                    # Remove invalid connections
                    for conn in connections_to_remove:
                        self.connections.remove(conn)
                        try:
                            await conn.close()
                        except Exception:
                            pass
                    
                    # Keep minimum number of connections
                    while len(self.connections) > self.min_connections:
                        conn = self.connections.pop()
                        try:
                            await conn.close()
                        except Exception:
                            pass
                
                logger.debug(f"Connection cleanup completed. Pool: {len(self.connections)}, Active: {len(self.active_connections)}")
                
            except Exception as e:
                logger.error(f"Error in connection cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        return {
            'total_connections': self.stats.total_connections,
            'active_connections': self.stats.active_connections,
            'available_connections': len(self.connections),
            'failed_connections': self.stats.failed_connections,
            'connection_errors': self.stats.connection_errors,
            'last_connection_time': self.stats.last_connection_time,
            'last_error_time': self.stats.last_error_time,
            'pool_size': len(self.connections),
            'max_connections': self.max_connections,
            'min_connections': self.min_connections
        }

class ConnectionManager:
    """Database connection manager with monitoring"""
    
    def __init__(self, db_path: str, max_connections: int = 10, min_connections: int = 2):
        self.db_path = db_path
        self.pool = ConnectionPool(db_path, max_connections, min_connections)
        self.is_initialized = False
        self.health_check_interval = 60  # seconds
        self._health_check_task = None
        self._monitoring_task = None
    
    async def initialize(self):
        """Initialize connection manager"""
        if self.is_initialized:
            return
        
        try:
            await self.pool.start()
            self.is_initialized = True
            
            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            
            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            logger.info("Connection manager initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize connection manager: {e}")
            raise
    
    async def shutdown(self):
        """Shutdown connection manager"""
        if not self.is_initialized:
            return
        
        try:
            # Cancel tasks
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Stop connection pool
            await self.pool.stop()
            
            self.is_initialized = False
            logger.info("Connection manager shutdown")
            
        except Exception as e:
            logger.error(f"Error during connection manager shutdown: {e}")
    
    async def get_connection(self) -> aiosqlite.Connection:
        """Get database connection"""
        if not self.is_initialized:
            raise Exception("Connection manager not initialized")
        
        return await self.pool.get_connection()
    
    async def return_connection(self, conn: aiosqlite.Connection):
        """Return database connection"""
        if not self.is_initialized:
            return
        
        await self.pool.return_connection(conn)
    
    async def _health_check_loop(self):
        """Health check loop"""
        while self.is_initialized:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Test connection
                conn = await self.get_connection()
                try:
                    await conn.execute("SELECT 1")
                    await self.return_connection(conn)
                    logger.debug("Health check passed")
                except Exception as e:
                    logger.warning(f"Health check failed: {e}")
                    # Don't return connection if it's broken
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    async def _monitoring_loop(self):
        """Monitoring loop"""
        while self.is_initialized:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                stats = self.pool.get_stats()
                
                # Log statistics
                logger.info(f"Connection pool stats: {stats}")
                
                # Check for issues
                if stats['connection_errors'] > 10:
                    logger.warning(f"High connection error rate: {stats['connection_errors']}")
                
                if stats['active_connections'] >= stats['max_connections']:
                    logger.warning("Connection pool at maximum capacity")
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics"""
        if not self.is_initialized:
            return {}
        
        return {
            'is_initialized': self.is_initialized,
            'pool_stats': self.pool.get_stats(),
            'health_check_interval': self.health_check_interval
        }
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = await self.get_connection()
            await conn.execute("SELECT 1")
            await self.return_connection(conn)
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

