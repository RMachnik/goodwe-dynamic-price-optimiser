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
    
    Features:
    - Connection pooling with semaphore-based concurrency control
    - Retry logic for transient failures
    - WAL mode for better concurrent read/write performance
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.db_path = config.db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = logging.getLogger(__name__)
        
        # Connection pooling settings
        self._pool_size = getattr(config, 'connection_pool_size', 5)
        self._connection_semaphore = asyncio.Semaphore(self._pool_size)
        
        # Retry settings
        self._max_retries = getattr(config, 'max_retries', 3)
        self._retry_delay = getattr(config, 'retry_delay', 0.1)

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connection is not None

    async def _execute_with_retry(self, operation, *args, **kwargs):
        """Execute an operation with retry logic for transient failures."""
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return await operation(*args, **kwargs)
            except aiosqlite.OperationalError as e:
                last_error = e
                error_str = str(e).lower()
                # Retry on database locked or busy errors
                if 'locked' in error_str or 'busy' in error_str:
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2 ** attempt)  # Exponential backoff
                        self.logger.warning(f"Database locked, retrying in {delay:.2f}s (attempt {attempt + 1}/{self._max_retries})")
                        await asyncio.sleep(delay)
                        continue
                raise
            except Exception as e:
                last_error = e
                raise
        if last_error:
            raise last_error

    async def connect(self) -> bool:
        """Establish connection to the SQLite database with retry logic."""
        last_error = None
        
        for attempt in range(self._max_retries):
            try:
                if not self.db_path:
                    raise ConnectionError("Database path not configured")
                    
                # Ensure directory exists
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                
                self._connection = await aiosqlite.connect(self.db_path)
                self._connection.row_factory = aiosqlite.Row
                
                # Enable WAL mode for better concurrent access
                await self._connection.execute("PRAGMA journal_mode=WAL")
                await self._connection.execute("PRAGMA synchronous=NORMAL")
                await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
                await self._connection.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
                
                # Initialize schema
                await self._init_schema()
                
                self.logger.info(f"Connected to SQLite database at {self.db_path} (pool_size={self._pool_size})")
                return True
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Retry on transient errors (locked, busy, I/O errors)
                if any(err in error_str for err in ['locked', 'busy', 'i/o', 'disk']):
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2 ** attempt)
                        self.logger.warning(f"Database connection failed, retrying in {delay:.2f}s (attempt {attempt + 1}/{self._max_retries}): {e}")
                        await asyncio.sleep(delay)
                        continue
                break
        
        self.logger.error(f"Failed to connect to SQLite after {self._max_retries} attempts: {last_error}")
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
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_save():
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
                    
                    # Define expected fields with defaults
                    expected_fields = {
                        'battery_soc': None,
                        'pv_power': None,
                        'grid_power': None,
                        'house_consumption': None,
                        'battery_power': None,
                        'grid_voltage': None,
                        'grid_frequency': None,
                        'battery_voltage': None,
                        'battery_current': None,
                        'battery_temperature': None,
                        'price_pln': None
                    }
                    
                    # Process data and ensure all required fields exist
                    processed_data = []
                    for item in data:
                        item_copy = expected_fields.copy()
                        item_copy.update(item)
                        
                        # Ensure timestamp is a string
                        if isinstance(item_copy.get('timestamp'), datetime):
                            item_copy['timestamp'] = item_copy['timestamp'].isoformat()
                        elif 'timestamp' not in item_copy:
                            item_copy['timestamp'] = datetime.now().isoformat()
                            
                        processed_data.append(item_copy)
                        
                    await self._connection.executemany(query, processed_data)
                    await self._connection.commit()
                    return True
                
                return await self._execute_with_retry(_do_save)
            except Exception as e:
                self.logger.error(f"Error saving energy data: {e}")
                return False

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical energy data."""
        if not self._connection:
            return []
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_query():
                    query = """
                    SELECT * FROM energy_data 
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                    """
                    
                    async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
                
                return await self._execute_with_retry(_do_query)
            except Exception as e:
                self.logger.error(f"Error retrieving energy data: {e}")
                return []

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save MasterCoordinator state."""
        if not self._connection:
            return False
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_save():
                    query = """
                    INSERT INTO system_state (
                        timestamp, state, uptime, active_modules, last_error, metrics
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """
                    
                    ts = state.get('timestamp')
                    if isinstance(ts, datetime):
                        ts = ts.isoformat()
                    
                    # Handle uptime - could be 'uptime' or 'uptime_seconds'
                    uptime = state.get('uptime') or state.get('uptime_seconds')
                    
                    # Build metrics JSON including extra fields
                    metrics = state.get('metrics', state.get('performance_metrics', {}))
                    if state.get('current_data'):
                        metrics['current_data'] = state.get('current_data')
                    if state.get('decision_count'):
                        metrics['decision_count'] = state.get('decision_count')
                    if uptime:
                        metrics['uptime_seconds'] = uptime
                    metrics_json = json.dumps(metrics, default=str)
                    
                    active_modules = ",".join(state.get('active_modules', []))
                    
                    await self._connection.execute(query, (
                        ts,
                        state.get('state'),
                        uptime,
                        active_modules,
                        state.get('last_error'),
                        metrics_json
                    ))
                    await self._connection.commit()
                    return True
                
                return await self._execute_with_retry(_do_save)
            except Exception as e:
                self.logger.error(f"Error saving system state: {e}")
                return False

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent system states."""
        if not self._connection:
            return []
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_query():
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
                                metrics = json.loads(d['metrics'])
                                d['metrics'] = metrics
                                # Flatten metrics fields to top level for compatibility
                                if 'uptime_seconds' in metrics:
                                    d['uptime_seconds'] = metrics['uptime_seconds']
                                if 'current_data' in metrics:
                                    d['current_data'] = metrics['current_data']
                                if 'decision_count' in metrics:
                                    d['decision_count'] = metrics['decision_count']
                            except:
                                pass
                        results.append(d)
                        
                    return results
                
                return await self._execute_with_retry(_do_query)
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
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_save():
                    query = """
                    INSERT INTO coordinator_decisions (
                        timestamp, decision_type, action, reason, parameters, source_module
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """
                    
                    ts = decision.get('timestamp')
                    if isinstance(ts, datetime):
                        ts = ts.isoformat()
                    
                    # Store all extra fields in parameters JSON
                    params = decision.get('parameters', {})
                    extra_fields = ['should_charge', 'confidence', 'current_price', 'cheapest_price', 
                                   'cheapest_hour', 'battery_soc', 'pv_power', 'consumption', 'decision_score']
                    for field in extra_fields:
                        if field in decision:
                            params[field] = decision[field]
                    params_json = json.dumps(params, default=str)
                    
                    self.logger.info(f"📝 Executing INSERT: ts={ts}, type={decision.get('decision_type')}, action={decision.get('action')}")
                    await self._connection.execute(query, (
                        ts,
                        decision.get('decision_type'),
                        decision.get('action'),
                        decision.get('reason'),
                        params_json,
                        decision.get('source_module')
                    ))
                    self.logger.info(f"💾 Committing transaction...")
                    await self._connection.commit()
                    self.logger.info(f"✅ Commit successful!")
                    return True
                
                return await self._execute_with_retry(_do_save)
            except Exception as e:
                self.logger.error(f"Error saving decision: {e}")
                return False

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical decisions."""
        if not self._connection:
            return []
            
        async with self._connection_semaphore:  # Connection pooling
            try:
                async def _do_query():
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
                                    params = json.loads(d['parameters'])
                                    d['parameters'] = params
                                    # Flatten parameter fields to top level for compatibility
                                    for key in ['should_charge', 'confidence', 'current_price', 'cheapest_price',
                                                'cheapest_hour', 'battery_soc', 'pv_power', 'consumption', 'decision_score']:
                                        if key in params:
                                            d[key] = params[key]
                                except:
                                    pass
                            results.append(d)
                        return results
                
                return await self._execute_with_retry(_do_query)
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

    async def save_selling_session(self, session: Dict[str, Any]) -> bool:
        """Save or update a battery selling session."""
        if not self._connection:
            return False
            
        async with self._connection_semaphore:
            try:
                async def _do_save():
                    query = """
                    INSERT OR REPLACE INTO battery_selling_sessions (
                        session_id, start_time, end_time, energy_sold_kwh,
                        revenue_pln, avg_price, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
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
                        session.get('energy_sold_kwh'),
                        session.get('revenue_pln'),
                        session.get('avg_price'),
                        session.get('status')
                    ))
                    await self._connection.commit()
                    return True
                
                return await self._execute_with_retry(_do_save)
            except Exception as e:
                self.logger.error(f"Error saving selling session: {e}")
                return False

    async def get_selling_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve battery selling sessions."""
        if not self._connection:
            return []
            
        async with self._connection_semaphore:
            try:
                async def _do_query():
                    query = """
                    SELECT * FROM battery_selling_sessions 
                    WHERE start_time BETWEEN ? AND ?
                    ORDER BY start_time ASC
                    """
                    
                    async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                        rows = await cursor.fetchall()
                        return [dict(row) for row in rows]
                
                return await self._execute_with_retry(_do_query)
            except Exception as e:
                self.logger.error(f"Error retrieving selling sessions: {e}")
                return []

    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save weather data."""
        if not self._connection or not data:
            return False
        try:
            query = """
            INSERT OR REPLACE INTO weather_data (
                timestamp, source, temperature, humidity, pressure, 
                wind_speed, wind_direction, cloud_cover, solar_irradiance, precipitation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            for rec in data:
                ts = rec.get('timestamp')
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                await self._connection.execute(query, (
                    ts,
                    rec.get('source'),
                    rec.get('temperature'),
                    rec.get('humidity'),
                    rec.get('pressure'),
                    rec.get('wind_speed'),
                    rec.get('wind_direction'),
                    rec.get('cloud_cover'),
                    rec.get('solar_irradiance'),
                    rec.get('precipitation')
                ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving weather data: {e}")
            return False

    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve weather data."""
        if not self._connection:
            return []
        try:
            query = """
            SELECT * FROM weather_data 
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """
            async with self._connection.execute(query, (start_time.isoformat(), end_time.isoformat())) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving weather data: {e}")
            return []

    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save price forecast data."""
        if not self._connection or not forecast_list:
            return False
        try:
            query = """
            INSERT OR REPLACE INTO price_forecasts (
                timestamp, forecast_date, hour, price_pln, source, confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
            """
            for rec in forecast_list:
                ts = rec.get('timestamp')
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                # Handle price field which might be price_pln or price
                price = rec.get('price_pln') or rec.get('price')
                await self._connection.execute(query, (
                    ts,
                    rec.get('forecast_date'),
                    rec.get('hour'),
                    price,
                    rec.get('source'),
                    rec.get('confidence')
                ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving price forecast: {e}")
            return False

    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Retrieve price forecasts for a date."""
        if not self._connection:
            return []
        try:
            query = """
            SELECT * FROM price_forecasts 
            WHERE forecast_date = ?
            ORDER BY hour ASC
            """
            async with self._connection.execute(query, (date_str,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving price forecasts: {e}")
            return []

    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save PV forecast data."""
        if not self._connection or not forecast_list:
            return False
        try:
            query = """
            INSERT OR REPLACE INTO pv_forecasts (
                timestamp, forecast_date, hour, predicted_power_w, source, confidence, weather_conditions
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            for rec in forecast_list:
                ts = rec.get('timestamp')
                if isinstance(ts, datetime):
                    ts = ts.isoformat()
                # Handle power field which might be power_w or predicted_power_w
                power = rec.get('predicted_power_w') or rec.get('power_w')
                await self._connection.execute(query, (
                    ts,
                    rec.get('forecast_date'),
                    rec.get('hour'),
                    power,
                    rec.get('source'),
                    rec.get('confidence'),
                    rec.get('weather_conditions')
                ))
            await self._connection.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving PV forecast: {e}")
            return False

    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Retrieve PV forecasts for a date."""
        if not self._connection:
            return []
        try:
            query = """
            SELECT * FROM pv_forecasts 
            WHERE forecast_date = ?
            ORDER BY hour ASC
            """
            async with self._connection.execute(query, (date_str,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error retrieving PV forecasts: {e}")
            return []

    async def backup_data(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            db_path = getattr(self.config, 'db_path', None)
            if db_path and os.path.exists(db_path):
                shutil.copy2(db_path, backup_path)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return False
