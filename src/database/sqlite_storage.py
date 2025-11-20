#!/usr/bin/env python3
"""
SQLite Storage Implementation for GoodWe Dynamic Price Optimiser
Concrete implementation of storage interface with SQLite backend
"""

import asyncio
import aiosqlite
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path
import sqlite3

from .storage_interface import (
    StorageInterface, StorageConfig, StorageError, ConnectionError, QueryError,
    RetryMixin, CircuitBreakerMixin, FallbackMixin
)

logger = logging.getLogger(__name__)

class SQLiteStorage(StorageInterface, RetryMixin, CircuitBreakerMixin, FallbackMixin):
    """SQLite storage implementation with error handling and retry logic"""
    
    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.db_path = config.db_path
        self.connection_pool = []
        self.pool_size = config.connection_pool_size
        self.batch_size = config.batch_size
        self.fallback_enabled = config.fallback_to_file
        self.fallback_path = "out/fallback_data"
        
        # Initialize circuit breaker attributes
        self.failure_count = 0
        self.failure_threshold = 5
        self.recovery_timeout = 60
        self.last_failure_time = None
        self.state = "CLOSED"
        
        # Initialize retry attributes
        self.retry_count = 0
        self.max_retries = config.max_retries
    
    async def connect(self) -> bool:
        """Connect to SQLite database"""
        try:
            await self._check_circuit_breaker()
            
            # Ensure database directory exists
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # Test connection
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("SELECT 1")
            
            self.is_connected = True
            self._record_success()
            logger.info(f"Connected to SQLite database: {self.db_path}")
            return True
            
        except Exception as e:
            self._record_failure()
            logger.error(f"Failed to connect to SQLite database: {e}")
            raise ConnectionError(f"SQLite connection failed: {e}")
    
    async def disconnect(self) -> bool:
        """Disconnect from SQLite database"""
        try:
            # Close all connections in pool
            for conn in self.connection_pool:
                await conn.close()
            self.connection_pool.clear()
            
            self.is_connected = False
            logger.info("Disconnected from SQLite database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disconnect from SQLite database: {e}")
            return False
    
    async def _get_connection(self):
        """Get database connection from pool or create new one"""
        if self.connection_pool:
            return self.connection_pool.pop()
        
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            return conn
        except Exception as e:
            raise ConnectionError(f"Failed to create database connection: {e}")
    
    async def _return_connection(self, conn):
        """Return connection to pool"""
        if len(self.connection_pool) < self.pool_size:
            self.connection_pool.append(conn)
        else:
            await conn.close()
    
    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy data with batch processing"""
        if not data:
            return True
        
        try:
            await self._retry_operation(self._save_energy_data_batch, data)
            return True
        except Exception as e:
            logger.error(f"Failed to save energy data: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(data, "energy_data")
            return False
    
    async def _save_energy_data_batch(self, data: List[Dict[str, Any]]):
        """Save energy data in batches"""
        conn = await self._get_connection()
        try:
            # Process in batches
            for i in range(0, len(data), self.batch_size):
                batch = data[i:i + self.batch_size]
                
                values = []
                for record in batch:
                    values.append((
                        record.get('timestamp', datetime.now()),
                        record.get('battery_soc', 0.0),
                        record.get('pv_power', 0.0),
                        record.get('grid_power', 0.0),
                        record.get('consumption', 0.0),
                        record.get('price', 0.0),
                        record.get('battery_temp'),
                        record.get('battery_voltage'),
                        record.get('grid_voltage')
                    ))
                
                await conn.executemany("""
                    INSERT INTO energy_data 
                    (timestamp, battery_soc, pv_power, grid_power, consumption, price, 
                     battery_temp, battery_voltage, grid_voltage)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, values)
            
            await conn.commit()
            logger.debug(f"Saved {len(data)} energy data records")
            
        finally:
            await self._return_connection(conn)
    
    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        """Save charging session"""
        try:
            await self._retry_operation(self._save_charging_session_impl, session)
            return True
        except Exception as e:
            logger.error(f"Failed to save charging session: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(session, "charging_session")
            return False
    
    async def _save_charging_session_impl(self, session: Dict[str, Any]):
        """Save charging session implementation"""
        conn = await self._get_connection()
        try:
            await conn.execute("""
                INSERT OR REPLACE INTO charging_sessions 
                (session_id, start_time, end_time, energy_kwh, cost_pln, status,
                 battery_soc_start, battery_soc_end, charging_source, pv_contribution_kwh, grid_contribution_kwh)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.get('session_id'),
                session.get('start_time'),
                session.get('end_time'),
                session.get('energy_kwh', 0.0),
                session.get('cost_pln', 0.0),
                session.get('status', 'unknown'),
                session.get('battery_soc_start', 0.0),
                session.get('battery_soc_end'),
                session.get('charging_source'),
                session.get('pv_contribution_kwh'),
                session.get('grid_contribution_kwh')
            ))
            
            await conn.commit()
            logger.debug(f"Saved charging session: {session.get('session_id')}")
            
        finally:
            await self._return_connection(conn)
    
    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state"""
        try:
            await self._retry_operation(self._save_system_state_impl, state)
            return True
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(state, "system_state")
            return False
    
    async def _save_system_state_impl(self, state: Dict[str, Any]):
        """Save system state implementation"""
        conn = await self._get_connection()
        try:
            await conn.execute("""
                INSERT INTO system_state 
                (timestamp, state, uptime_seconds, current_data, performance_metrics, decision_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                state.get('timestamp', datetime.now()),
                state.get('state', 'unknown'),
                state.get('uptime_seconds', 0.0),
                json.dumps(state.get('current_data', {})),
                json.dumps(state.get('performance_metrics', {})),
                state.get('decision_count', 0)
            ))
            
            await conn.commit()
            logger.debug("Saved system state")
            
        finally:
            await self._return_connection(conn)
    
    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save coordinator decision"""
        try:
            await self._retry_operation(self._save_decision_impl, decision)
            return True
        except Exception as e:
            logger.error(f"Failed to save decision: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(decision, "coordinator_decision")
            return False
    
    async def _save_decision_impl(self, decision: Dict[str, Any]):
        """Save decision implementation"""
        conn = await self._get_connection()
        try:
            await conn.execute("""
                INSERT INTO coordinator_decisions 
                (timestamp, decision_type, should_charge, reason, confidence, current_price,
                 cheapest_price, cheapest_hour, battery_soc, pv_power, consumption, decision_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.get('timestamp', datetime.now()),
                decision.get('decision_type', 'charging'),
                decision.get('should_charge', False),
                decision.get('reason', ''),
                decision.get('confidence', 0.0),
                decision.get('current_price', 0.0),
                decision.get('cheapest_price', 0.0),
                decision.get('cheapest_hour', 0),
                decision.get('battery_soc', 0.0),
                decision.get('pv_power', 0.0),
                decision.get('consumption', 0.0),
                decision.get('decision_score', 0.0)
            ))
            
            await conn.commit()
            logger.debug("Saved coordinator decision")
            
        finally:
            await self._return_connection(conn)
    
    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save weather data"""
        if not data:
            return True
        
        try:
            await self._retry_operation(self._save_weather_data_batch, data)
            return True
        except Exception as e:
            logger.error(f"Failed to save weather data: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(data, "weather_data")
            return False
    
    async def _save_weather_data_batch(self, data: List[Dict[str, Any]]):
        """Save weather data in batches"""
        conn = await self._get_connection()
        try:
            for record in data:
                await conn.execute("""
                    INSERT INTO weather_data 
                    (timestamp, source, temperature, humidity, pressure, wind_speed,
                     wind_direction, precipitation, cloud_cover, solar_irradiance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.get('timestamp', datetime.now()),
                    record.get('source', 'unknown'),
                    record.get('temperature'),
                    record.get('humidity'),
                    record.get('pressure'),
                    record.get('wind_speed'),
                    record.get('wind_direction'),
                    record.get('precipitation'),
                    record.get('cloud_cover'),
                    record.get('solar_irradiance')
                ))
            
            await conn.commit()
            logger.debug(f"Saved {len(data)} weather data records")
            
        finally:
            await self._return_connection(conn)
    
    async def save_price_forecast(self, forecast: List[Dict[str, Any]]) -> bool:
        """Save price forecast"""
        if not forecast:
            return True
        
        try:
            await self._retry_operation(self._save_price_forecast_batch, forecast)
            return True
        except Exception as e:
            logger.error(f"Failed to save price forecast: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(forecast, "price_forecast")
            return False
    
    async def _save_price_forecast_batch(self, forecast: List[Dict[str, Any]]):
        """Save price forecast in batches"""
        conn = await self._get_connection()
        try:
            for record in forecast:
                await conn.execute("""
                    INSERT INTO price_forecasts 
                    (timestamp, forecast_date, hour, price_pln, confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.get('timestamp', datetime.now()),
                    record.get('forecast_date'),
                    record.get('hour', 0),
                    record.get('price_pln', 0.0),
                    record.get('confidence', 0.0),
                    record.get('source', 'unknown')
                ))
            
            await conn.commit()
            logger.debug(f"Saved {len(forecast)} price forecast records")
            
        finally:
            await self._return_connection(conn)
    
    async def save_pv_forecast(self, forecast: List[Dict[str, Any]]) -> bool:
        """Save PV forecast"""
        if not forecast:
            return True
        
        try:
            await self._retry_operation(self._save_pv_forecast_batch, forecast)
            return True
        except Exception as e:
            logger.error(f"Failed to save PV forecast: {e}")
            if self.fallback_enabled:
                await self._fallback_to_file(forecast, "pv_forecast")
            return False
    
    async def _save_pv_forecast_batch(self, forecast: List[Dict[str, Any]]):
        """Save PV forecast in batches"""
        conn = await self._get_connection()
        try:
            for record in forecast:
                await conn.execute("""
                    INSERT INTO pv_forecasts 
                    (timestamp, forecast_date, hour, predicted_power_w, confidence, weather_conditions)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.get('timestamp', datetime.now()),
                    record.get('forecast_date'),
                    record.get('hour', 0),
                    record.get('predicted_power_w', 0.0),
                    record.get('confidence', 0.0),
                    record.get('weather_conditions')
                ))
            
            await conn.commit()
            logger.debug(f"Saved {len(forecast)} PV forecast records")
            
        finally:
            await self._return_connection(conn)
    
    # Query methods
    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data for time range"""
        try:
            return await self._retry_operation(self._get_energy_data_impl, start_time, end_time)
        except Exception as e:
            logger.error(f"Failed to get energy data: {e}")
            return []
    
    async def _get_energy_data_impl(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM energy_data 
                WHERE timestamp BETWEEN ? AND ? 
                ORDER BY timestamp
            """, (start_time, end_time))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_charging_sessions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get charging sessions for date range"""
        try:
            return await self._retry_operation(self._get_charging_sessions_impl, start_date, end_date)
        except Exception as e:
            logger.error(f"Failed to get charging sessions: {e}")
            return []
    
    async def _get_charging_sessions_impl(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get charging sessions implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM charging_sessions 
                WHERE start_time BETWEEN ? AND ? 
                ORDER BY start_time
            """, (start_date, end_date))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system state"""
        try:
            return await self._retry_operation(self._get_system_state_impl, limit)
        except Exception as e:
            logger.error(f"Failed to get system state: {e}")
            return []
    
    async def _get_system_state_impl(self, limit: int) -> List[Dict[str, Any]]:
        """Get system state implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM system_state 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get coordinator decisions for time range"""
        try:
            return await self._retry_operation(self._get_decisions_impl, start_time, end_time)
        except Exception as e:
            logger.error(f"Failed to get decisions: {e}")
            return []
    
    async def _get_decisions_impl(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get decisions implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM coordinator_decisions 
                WHERE timestamp BETWEEN ? AND ? 
                ORDER BY timestamp
            """, (start_time, end_time))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get weather data for time range"""
        try:
            return await self._retry_operation(self._get_weather_data_impl, start_time, end_time)
        except Exception as e:
            logger.error(f"Failed to get weather data: {e}")
            return []
    
    async def _get_weather_data_impl(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get weather data implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM weather_data 
                WHERE timestamp BETWEEN ? AND ? 
                ORDER BY timestamp
            """, (start_time, end_time))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_price_forecasts(self, date: str) -> List[Dict[str, Any]]:
        """Get price forecasts for date"""
        try:
            return await self._retry_operation(self._get_price_forecasts_impl, date)
        except Exception as e:
            logger.error(f"Failed to get price forecasts: {e}")
            return []
    
    async def _get_price_forecasts_impl(self, date: str) -> List[Dict[str, Any]]:
        """Get price forecasts implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM price_forecasts 
                WHERE forecast_date = ? 
                ORDER BY hour
            """, (date,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def get_pv_forecasts(self, date: str) -> List[Dict[str, Any]]:
        """Get PV forecasts for date"""
        try:
            return await self._retry_operation(self._get_pv_forecasts_impl, date)
        except Exception as e:
            logger.error(f"Failed to get PV forecasts: {e}")
            return []
    
    async def _get_pv_forecasts_impl(self, date: str) -> List[Dict[str, Any]]:
        """Get PV forecasts implementation"""
        conn = await self._get_connection()
        try:
            cursor = await conn.execute("""
                SELECT * FROM pv_forecasts 
                WHERE forecast_date = ? 
                ORDER BY hour
            """, (date,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
            
        finally:
            await self._return_connection(conn)
    
    async def health_check(self) -> bool:
        """Check storage health"""
        # Try health check even if not explicitly connected, since lazy connections might work
        try:
            conn = await self._get_connection()
            await conn.execute("SELECT 1")
            await self._return_connection(conn)
            # If we got here, connection works - update flag if needed
            if not self.is_connected:
                self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def backup_data(self, backup_path: str) -> bool:
        """Backup data"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    async def restore_data(self, backup_path: str) -> bool:
        """Restore data from backup"""
        try:
            import shutil
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Database restored from: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
