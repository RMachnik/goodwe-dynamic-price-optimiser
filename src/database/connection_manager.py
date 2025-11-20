"""Lightweight Connection Manager stub for tests.
Provides minimal async pool behavior without external dependencies.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


class FakeConnection:
    """Simple fake connection with async execute/close for tests."""

    def __init__(self):
        self.closed = False

    async def execute(self, *args, **kwargs):
        await asyncio.sleep(0)
        return None

    async def close(self):
        self.closed = True
        await asyncio.sleep(0)


@dataclass
class ConnectionStats:
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    connection_errors: int = 0
    last_connection_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None


class ConnectionPool:
    def __init__(self, db_path: str, max_connections: int = 10, min_connections: int = 2):
        self.db_path = db_path
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.connections: List[FakeConnection] = []
        self.active_connections: List[FakeConnection] = []
        self.stats = ConnectionStats()
        self._lock = asyncio.Lock()
        self._is_running = False

    async def start(self):
        if self._is_running:
            return
        self._is_running = True
        for _ in range(self.min_connections):
            conn = FakeConnection()
            self.connections.append(conn)
            self.stats.total_connections += 1

    async def stop(self):
        if not self._is_running:
            return
        self._is_running = False
        async with self._lock:
            for conn in self.connections + self.active_connections:
                try:
                    await conn.close()
                except Exception:
                    pass
            self.connections.clear()
            self.active_connections.clear()

    async def get_connection(self) -> FakeConnection:
        while self._is_running:
            async with self._lock:
                if self.connections:
                    conn = self.connections.pop()
                    self.active_connections.append(conn)
                    self.stats.active_connections = len(self.active_connections)
                    return conn

                if len(self.active_connections) < self.max_connections:
                    conn = FakeConnection()
                    self.active_connections.append(conn)
                    self.stats.total_connections += 1
                    self.stats.active_connections = len(self.active_connections)
                    return conn

            # wait briefly for a connection outside the lock
            await asyncio.sleep(0.01)
            
        raise Exception("Connection pool stopped or not running")

    async def return_connection(self, conn: FakeConnection):
        async with self._lock:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                self.connections.append(conn)
                self.stats.active_connections = len(self.active_connections)
            else:
                try:
                    await conn.close()
                except Exception:
                    pass

    def get_stats(self) -> Dict[str, Any]:
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
            'min_connections': self.min_connections,
        }


class ConnectionManager:
    def __init__(self, db_path: str, max_connections: int = 10, min_connections: int = 2):
        self.db_path = db_path
        self.pool = ConnectionPool(db_path, max_connections, min_connections)
        self.is_initialized = False
        self.health_check_interval = 60
        self._health_check_task = None
        self._monitoring_task = None

    async def initialize(self):
        if self.is_initialized:
            return
        await self.pool.start()
        self.is_initialized = True

    async def shutdown(self):
        if not self.is_initialized:
            return
        await self.pool.stop()
        self.is_initialized = False

    async def get_connection(self):
        if not self.is_initialized:
            raise Exception("Connection manager not initialized")
        return await self.pool.get_connection()

    async def return_connection(self, conn):
        if not self.is_initialized:
            return
        await self.pool.return_connection(conn)

    def get_stats(self) -> Dict[str, Any]:
        if not self.is_initialized:
            return {}
        return {
            'is_initialized': self.is_initialized,
            'pool_stats': self.pool.get_stats(),
            'health_check_interval': self.health_check_interval
        }

    async def test_connection(self) -> bool:
        try:
            conn = await self.get_connection()
            await conn.execute("SELECT 1")
            await self.return_connection(conn)
            return True
        except Exception:
            return False
