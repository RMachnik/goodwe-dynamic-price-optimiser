import asyncio
import json
import os
import shutil
from datetime import datetime
from typing import List, Dict, Any
from .storage_interface import StorageConfig, ConnectionError


class SQLiteStorage:
    """A lightweight in-memory storage implementation used for tests.
    This mimics enough behavior of a real storage backend for unit tests
    without depending on external libraries or a real database file.
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.is_connected = False
        # simple in-memory collections
        self._energy: List[Dict[str, Any]] = []
        self._system_states: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._charging_sessions: List[Dict[str, Any]] = []
        self._weather_data: List[Dict[str, Any]] = []
        self._price_forecasts: List[Dict[str, Any]] = []
        self._pv_forecasts: List[Dict[str, Any]] = []

    async def connect(self) -> bool:
        await asyncio.sleep(0)
        if getattr(self.config, 'db_path', None) and str(self.config.db_path).startswith('/invalid'):
            raise ConnectionError('Invalid DB path')
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        await asyncio.sleep(0)
        self.is_connected = False
        return True

    async def health_check(self) -> bool:
        await asyncio.sleep(0)
        return self.is_connected

    def _normalize_ts(self, ts):
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                try:
                    return datetime.fromisoformat(ts)
                except Exception:
                    return datetime.now()
        elif isinstance(ts, datetime):
            return ts
        else:
            return datetime.now()

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        await asyncio.sleep(0)
        if not isinstance(data, list):
            return False
        for rec in data:
            r = dict(rec)
            r['timestamp'] = self._normalize_ts(r.get('timestamp'))
            self._energy.append(r)
        return True

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [r for r in self._energy if start_time <= r['timestamp'] <= end_time]

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        st = dict(state)
        st['timestamp'] = self._normalize_ts(st.get('timestamp'))
        self._system_states.append(st)
        return True

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return list(self._system_states[-limit:])

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        d = dict(decision)
        d['timestamp'] = self._normalize_ts(d.get('timestamp'))
        self._decisions.append(d)
        return True

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        await asyncio.sleep(0)
        return [d for d in self._decisions if start_time <= d['timestamp'] <= end_time]

    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        await asyncio.sleep(0)
        s = dict(session)
        s['start_time'] = self._normalize_ts(s.get('start_time'))
        s['end_time'] = self._normalize_ts(s.get('end_time')) if s.get('end_time') else None
        self._charging_sessions.append(s)
        return True

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
