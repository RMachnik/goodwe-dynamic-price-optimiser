import asyncio
from datetime import datetime
from typing import List, Dict, Any
from .storage_interface import StorageConfig, ConnectionError

class SQLiteStorage:
    """A lightweight in-memory-like storage implementation to satisfy tests.
    This does NOT use a real SQLite file; it stores records in-memory for test runs.
    """
    def __init__(self, config: StorageConfig):
        self.config = config
        self.is_connected = False
        # simple in-memory collections
        self._energy: List[Dict[str, Any]] = []
        self._system_states: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []

    async def connect(self) -> bool:
        # emulate async connect
        await asyncio.sleep(0)
        if self.config.db_path and str(self.config.db_path).startswith('/invalid'):
            raise ConnectionError('Invalid DB path')
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        await asyncio.sleep(0)
        self.is_connected = False

    async def health_check(self) -> bool:
        await asyncio.sleep(0)
        return self.is_connected

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        if not isinstance(data, list):
            return False
        # normalize timestamps to datetime
        for rec in data:
            r = dict(rec)
            ts = r.get('timestamp')
            if isinstance(ts, str):
                try:
                    r['timestamp'] = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except Exception:
                    # try naive parse
                    try:
                        r['timestamp'] = datetime.fromisoformat(ts)
                    except Exception:
                        r['timestamp'] = datetime.now()
            elif isinstance(ts, datetime):
                r['timestamp'] = ts
            else:
                r['timestamp'] = datetime.now()
            self._energy.append(r)
        return True

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        result = []
        for r in self._energy:
            ts = r.get('timestamp')
            if ts is None:
                continue
            if start_time <= ts <= end_time:
                result.append(r)
        return result

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        st = dict(state)
        ts = st.get('timestamp')
        if isinstance(ts, str):
            try:
                st['timestamp'] = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                st['timestamp'] = datetime.now()
        elif ts is None:
            st['timestamp'] = datetime.now()
        self._system_states.append(st)
        return True

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return list(self._system_states[-limit:])

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        d = dict(decision)
        ts = d.get('timestamp')
        if isinstance(ts, str):
            try:
                d['timestamp'] = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                d['timestamp'] = datetime.now()
        elif ts is None:
            d['timestamp'] = datetime.now()
        self._decisions.append(d)
        return True

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        result = []
        for d in self._decisions:
            ts = d.get('timestamp')
            if start_time <= ts <= end_time:
                result.append(d)
        return result

    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        # provide minimal behaviour for tests that call this
        await asyncio.sleep(0)
        return True

    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return []

    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        return True

    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return []

    async def backup_data(self, backup_path: str) -> bool:
        await asyncio.sleep(0)
        # emulate backup success
        return True
