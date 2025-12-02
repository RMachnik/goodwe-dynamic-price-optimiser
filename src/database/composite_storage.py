import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from .storage_interface import DataStorageInterface, StorageConfig

class CompositeStorage(DataStorageInterface):
    """
    Composite storage implementation that writes to multiple backends
    and reads from the primary backend with fallback.
    """

    def __init__(self, primary: DataStorageInterface, secondaries: List[DataStorageInterface], config: StorageConfig):
        self.primary = primary
        self.secondaries = secondaries
        self.config = config
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Connect to all backends."""
        results = await asyncio.gather(
            self.primary.connect(),
            *[s.connect() for s in self.secondaries],
            return_exceptions=True
        )
        
        # Check primary connection
        primary_ok = isinstance(results[0], bool) and results[0]
        if not primary_ok:
            self.logger.error("Primary storage connection failed")
            
        # We consider it connected if at least one storage is working
        return any(r is True for r in results)

    async def disconnect(self) -> None:
        """Disconnect from all backends."""
        await asyncio.gather(
            self.primary.disconnect(),
            *[s.disconnect() for s in self.secondaries],
            return_exceptions=True
        )

    async def health_check(self) -> bool:
        """Check if primary storage is healthy."""
        return await self.primary.health_check()

    async def _write_to_all(self, method_name: str, *args, **kwargs) -> bool:
        """Helper to write to all backends concurrently."""
        tasks = []
        
        # Primary task
        tasks.append(getattr(self.primary, method_name)(*args, **kwargs))
        
        # Secondary tasks
        for secondary in self.secondaries:
            tasks.append(getattr(secondary, method_name)(*args, **kwargs))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Return True if primary succeeded (or if primary failed but fallback is enabled and secondary succeeded)
        primary_result = results[0]
        if isinstance(primary_result, bool) and primary_result:
            return True
            
        if self.config.enable_fallback:
            # Check if any secondary succeeded
            if any(isinstance(r, bool) and r for r in results[1:]):
                self.logger.warning(f"Primary storage failed for {method_name}, but secondary succeeded.")
                return True
                
        return False

    async def _read_with_fallback(self, method_name: str, *args, **kwargs) -> Any:
        """Helper to read from primary with fallback to secondaries."""
        try:
            result = await getattr(self.primary, method_name)(*args, **kwargs)
            if result:  # If we got data, return it
                return result
        except Exception as e:
            self.logger.warning(f"Primary storage read failed for {method_name}: {e}")
            
        if self.config.enable_fallback:
            for secondary in self.secondaries:
                try:
                    result = await getattr(secondary, method_name)(*args, **kwargs)
                    if result:
                        self.logger.info(f"Fallback read successful from secondary for {method_name}")
                        return result
                except Exception as e:
                    continue
                    
        return []  # Return empty list/dict if all failed

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        return await self._write_to_all('save_energy_data', data)

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_energy_data', start_time, end_time)

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        return await self._write_to_all('save_system_state', state)

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_system_state', limit)

    async def get_system_state_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_system_state_range', start_time, end_time)

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        return await self._write_to_all('save_decision', decision)

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_decisions', start_time, end_time)

    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        return await self._write_to_all('save_charging_session', session)

    async def get_charging_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_charging_sessions', start_time, end_time)

    async def save_selling_session(self, session: Dict[str, Any]) -> bool:
        return await self._write_to_all('save_selling_session', session)

    async def get_selling_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_selling_sessions', start_time, end_time)

    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        return await self._write_to_all('save_weather_data', data)

    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_weather_data', start_time, end_time)

    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        return await self._write_to_all('save_price_forecast', forecast_list)

    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_price_forecasts', date_str)

    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        return await self._write_to_all('save_pv_forecast', forecast_list)

    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        return await self._read_with_fallback('get_pv_forecasts', date_str)
