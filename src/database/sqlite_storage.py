import json
import logging
import asyncio
import shutil
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiosqlite

from .storage_interface import DataStorageInterface, StorageConfig, ConnectionError
from .schema import (
    CREATE_ENERGY_DATA_TABLE,
    CREATE_SYSTEM_STATE_TABLE,
    CREATE_DECISIONS_TABLE,
    CREATE_CHARGING_SESSIONS_TABLE,
    CREATE_SELLING_SESSIONS_TABLE,
    CREATE_WEATHER_DATA_TABLE,
    ALL_TABLES,
    CREATE_INDEXES
)


class SQLiteStorage(DataStorageInterface):
    """
    Production-ready SQLite storage implementation using aiosqlite.
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.db_path = config.db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = logging.getLogger(__name__)

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connection is not None

    async def connect(self) -> bool:
        """Establish connection to the SQLite database."""
        try:
            if not self.db_path:
                raise ConnectionError("Database path not configured")
                
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            
            # Initialize schema
            await self._init_schema()
            
            self.logger.info(f"Connected to SQLite database at {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to SQLite: {e}")
            return False

    async def _init_schema(self):
        """Initialize database schema."""
        if not self._connection:
            return
            
        async with self._connection.cursor() as cursor:
            # Create tables
            for table_sql in ALL_TABLES:
                await cursor.execute(table_sql)
            
            # Create indexes
            for index_sql in CREATE_INDEXES:
                await cursor.execute(index_sql)
                
        await self._connection.commit()

    async def disconnect(self) -> None:
        """Close connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self.logger.info("Disconnected from SQLite database")

    async def health_check(self) -> bool:
        """Check if connection is alive."""
        if not self._connection:
            return False
        try:
            async with self._connection.execute("SELECT 1") as cursor:
                result = await cursor.fetchone()
                return result[0] == 1
        except Exception:
            return False

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save a batch of energy readings."""
        if not self._connection or not data:
            return False
            
        try:
            query = """
            INSERT OR REPLACE INTO energy_data (
                timestamp, battery_soc, pv_power, grid_power, house_consumption,
                battery_power, grid_voltage, grid_frequency, battery_voltage,
                battery_current, battery_temperature, price_pln
            ) VALUES (
                :timestamp, :battery_soc, :pv_power, :grid_power, :house_consumption,
                :battery_power, :grid_voltage, :grid_frequency, :battery_voltage,
                :battery_current, :battery_temperature, :price_pln
            )
            """
            
            # Ensure timestamps are strings
            processed_data = []
            for item in data:
                item_copy = item.copy()
                if isinstance(item_copy.get('timestamp'), datetime):
                    item_copy['timestamp'] = item_copy['timestamp'].isoformat()
                processed_data.append(item_copy)
                
            await self._connection.executemany(query, processed_data)
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving energy data: {e}")
            return False

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical energy data."""
        if not self._connection:
            return []
            
        try:
            query = """
            SELECT * FROM energy_data 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """
            
            async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving energy data: {e}")
            return []

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save MasterCoordinator state."""
        if not self._connection:
            return False
            
        try:
            query = """
            INSERT INTO system_state (
                timestamp, state, uptime, active_modules, last_error, metrics
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            ts = state.get('timestamp')
            if isinstance(ts, datetime):
                ts = ts.isoformat()
                
            metrics_json = json.dumps(state.get('metrics', {}))
            active_modules = ",".join(state.get('active_modules', []))
            
            await self._connection.execute(query, (
                ts,
                state.get('state'),
                state.get('uptime'),
                active_modules,
                state.get('last_error'),
                metrics_json
            ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving system state: {e}")
            return False

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent system states."""
        if not self._connection:
            return []
            
        try:
            query = """
            SELECT * FROM system_state 
            ORDER BY timestamp DESC 
            LIMIT ?
            """
            
            async with self._connection.execute(query, (limit,)) as cursor:
                rows = await cursor.fetchall()
                
            results = []
            for row in rows:
                d = dict(row)
                if d.get('metrics'):
                    try:
                        d['metrics'] = json.loads(d['metrics'])
                    except:
                        pass
                results.append(d)
                
            return results
        except Exception as e:
            self.logger.error(f"Error retrieving system state: {e}")
            return []

    async def get_system_state_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve system states within a time range."""
        if not self._connection:
            return []
            
        try:
            query = """
            SELECT * FROM system_state 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """
            
            async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                rows = await cursor.fetchall()
                
            results = []
            for row in rows:
                d = dict(row)
                if d.get('metrics'):
                    try:
                        d['metrics'] = json.loads(d['metrics'])
                    except:
                        pass
                results.append(d)
                
            return results
        except Exception as e:
            self.logger.error(f"Error retrieving system state range: {e}")
            return []

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save charging/discharging decisions."""
        if not self._connection:
            return False
            
        try:
            query = """
            INSERT INTO coordinator_decisions (
                timestamp, decision_type, action, reason, parameters, source_module
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
            
            ts = decision.get('timestamp')
            if isinstance(ts, datetime):
                ts = ts.isoformat()
                
            params_json = json.dumps(decision.get('parameters', {}))
            
            await self._connection.execute(query, (
                ts,
                decision.get('decision_type'),
                decision.get('action'),
                decision.get('reason'),
                params_json,
                decision.get('source_module')
            ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving decision: {e}")
            return False

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical decisions."""
        if not self._connection:
            return []
            
        try:
            query = """
            SELECT * FROM coordinator_decisions 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """
            
            async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    d = dict(row)
                    if d.get('parameters'):
                        try:
                            d['parameters'] = json.loads(d['parameters'])
                        except:
                            pass
                    results.append(d)
                return results
        except Exception as e:
            self.logger.error(f"Error retrieving decisions: {e}")
            return []

    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        """Save or update a charging session."""
        if not self._connection:
            return False
            
        try:
            query = """
            INSERT OR REPLACE INTO charging_sessions (
                session_id, start_time, end_time, target_soc, 
                energy_kwh, cost_pln, status, avg_price
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            start_ts = session.get('start_time')
            if isinstance(start_ts, datetime):
                start_ts = start_ts.isoformat()
                
            end_ts = session.get('end_time')
            if isinstance(end_ts, datetime):
                end_ts = end_ts.isoformat()
            
            await self._connection.execute(query, (
                session.get('session_id'),
                start_ts,
                end_ts,
                session.get('target_soc'),
                session.get('energy_kwh'),
                session.get('cost_pln'),
                session.get('status'),
                session.get('avg_price')
            ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving charging session: {e}")
            return False

    async def get_charging_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve charging sessions."""
        if not self._connection:
            return []
            
        try:
            query = """
            SELECT * FROM charging_sessions 
            WHERE start_time BETWEEN ? AND ?
            ORDER BY start_time ASC
            """
            
            async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving charging sessions: {e}")
            return []


    async def get_charging_sessions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [s for s in self._charging_sessions if start_date <= s['start_time'] <= end_date]

    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        for rec in data:
            r = dict(rec)
            r['timestamp'] = self._normalize_ts(r.get('timestamp'))
            self._weather_data.append(r)
        return True

    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [r for r in self._weather_data if start_time <= r['timestamp'] <= end_time]

    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        for rec in forecast_list:
            r = dict(rec)
            r['timestamp'] = self._normalize_ts(r.get('timestamp'))
            self._price_forecasts.append(r)
        return True

    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [f for f in self._price_forecasts if f.get('forecast_date') == date_str]

    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        for rec in forecast_list:
            r = dict(rec)
            r['timestamp'] = self._normalize_ts(r.get('timestamp'))
            self._pv_forecasts.append(r)
        return True

    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [f for f in self._pv_forecasts if f.get('forecast_date') == date_str]

    async def backup_data(self, backup_path: str) -> bool:
        await asyncio.sleep(0)
        try:
            db_path = getattr(self.config, 'db_path', None)
            if db_path and os.path.exists(db_path):
                shutil.copy2(db_path, backup_path)
            else:
                snapshot = {
                    'energy': self._energy,
                    'system_states': self._system_states,
                    'decisions': self._decisions,
                    'charging_sessions': self._charging_sessions,
                    'weather_data': self._weather_data,
                    'price_forecasts': self._price_forecasts,
                    'pv_forecasts': self._pv_forecasts,
                }
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(snapshot, f, default=str)
            return True
        except Exception:
            return False
