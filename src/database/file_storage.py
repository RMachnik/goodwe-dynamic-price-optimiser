import json
import os
import logging
import aiofiles
from datetime import datetime
from typing import List, Dict, Any
from .storage_interface import DataStorageInterface, StorageConfig

class FileStorage(DataStorageInterface):
    """
    Legacy file-based storage implementation.
    Maintains backward compatibility with existing JSON file structure.
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        # Default paths matching existing structure
        self.base_dir = "out"
        self.energy_data_dir = os.path.join(self.base_dir, "energy_data")
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Ensure directories exist."""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            os.makedirs(self.energy_data_dir, exist_ok=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to create directories: {e}")
            return False

    async def disconnect(self) -> None:
        """No-op for file storage."""
        pass

    async def health_check(self) -> bool:
        """Check if directories are writable."""
        return os.access(self.base_dir, os.W_OK)

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy readings to daily JSON files."""
        if not data:
            return True
            
        try:
            # Group by date to handle batch spanning multiple days
            by_date = {}
            for item in data:
                ts = item.get('timestamp')
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                date_str = ts.strftime('%Y-%m-%d')
                if date_str not in by_date:
                    by_date[date_str] = []
                
                # Convert datetime back to string for JSON
                item_copy = item.copy()
                item_copy['timestamp'] = ts.isoformat()
                by_date[date_str].append(item_copy)

            for date_str, items in by_date.items():
                filename = os.path.join(self.energy_data_dir, f"energy_data_{date_str}.json")
                
                # Read existing
                existing = []
                if os.path.exists(filename):
                    async with aiofiles.open(filename, 'r') as f:
                        content = await f.read()
                        if content:
                            existing = json.loads(content)
                
                # Append new
                existing.extend(items)
                
                # Write back
                async with aiofiles.open(filename, 'w') as f:
                    await f.write(json.dumps(existing, indent=2))
                    
            return True
        except Exception as e:
            self.logger.error(f"Error saving energy data to file: {e}")
            return False

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical energy data from files."""
        results = []
        try:
            # Iterate through days in range
            current = start_time
            while current <= end_time:
                date_str = current.strftime('%Y-%m-%d')
                filename = os.path.join(self.energy_data_dir, f"energy_data_{date_str}.json")
                
                if os.path.exists(filename):
                    async with aiofiles.open(filename, 'r') as f:
                        content = await f.read()
                        if content:
                            day_data = json.loads(content)
                            # Filter by exact timestamp range
                            for item in day_data:
                                ts = datetime.fromisoformat(item['timestamp'])
                                if start_time <= ts <= end_time:
                                    results.append(item)
                
                # Move to next day
                current = datetime.fromordinal(current.toordinal() + 1)
                
            return results
        except Exception as e:
            self.logger.error(f"Error reading energy data from file: {e}")
            return []

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state to coordinator_state_*.json."""
        try:
            ts = state.get('timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            
            filename = os.path.join(self.base_dir, f"coordinator_state_{ts.strftime('%Y%m%d')}.json")
            
            # Append to file (simulating log-like behavior)
            state_copy = state.copy()
            if isinstance(state_copy.get('timestamp'), datetime):
                state_copy['timestamp'] = state_copy['timestamp'].isoformat()
                
            async with aiofiles.open(filename, 'a') as f:
                await f.write(json.dumps(state_copy) + "\n")
                
            return True
        except Exception as e:
            self.logger.error(f"Error saving system state to file: {e}")
            return False

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent system states from files."""
        # This is inefficient for files, but implemented for completeness
        # In reality, we might just return empty or implement complex globbing
        return []

    async def get_system_state_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve system states within a time range from files."""
        # Not implemented for files
        return []

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save decision to charging_decision_*.json."""
        try:
            ts = decision.get('timestamp')
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
                
            filename = os.path.join(self.base_dir, f"charging_decision_{ts.strftime('%Y%m%d')}.json")
            
            decision_copy = decision.copy()
            if isinstance(decision_copy.get('timestamp'), datetime):
                decision_copy['timestamp'] = decision_copy['timestamp'].isoformat()
                
            async with aiofiles.open(filename, 'a') as f:
                await f.write(json.dumps(decision_copy) + "\n")
                
            return True
        except Exception as e:
            self.logger.error(f"Error saving decision to file: {e}")
            return False

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Not efficiently implemented for files - returns empty."""
        return []

    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        """Save charging session to charging_schedule_*.json."""
        try:
            start_ts = session.get('start_time')
            if isinstance(start_ts, str):
                start_ts = datetime.fromisoformat(start_ts)
                
            filename = os.path.join(self.base_dir, f"charging_schedule_{start_ts.strftime('%Y-%m-%d')}.json")
            
            session_copy = session.copy()
            if isinstance(session_copy.get('start_time'), datetime):
                session_copy['start_time'] = session_copy['start_time'].isoformat()
            if isinstance(session_copy.get('end_time'), datetime):
                session_copy['end_time'] = session_copy['end_time'].isoformat()
                
            async with aiofiles.open(filename, 'w') as f:
                await f.write(json.dumps(session_copy, indent=2))
                
            return True
        except Exception as e:
            self.logger.error(f"Error saving charging session to file: {e}")
            return False

    async def get_charging_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Not efficiently implemented for files - returns empty."""
        return []

    async def save_selling_session(self, session: Dict[str, Any]) -> bool:
        """Save selling session to battery_selling_decision_*.json."""
        try:
            start_ts = session.get('start_time')
            if isinstance(start_ts, str):
                start_ts = datetime.fromisoformat(start_ts)
                
            filename = os.path.join(self.energy_data_dir, f"battery_selling_decision_{start_ts.strftime('%Y%m%d_%H%M%S')}.json")
            
            session_copy = session.copy()
            if isinstance(session_copy.get('start_time'), datetime):
                session_copy['start_time'] = session_copy['start_time'].isoformat()
            if isinstance(session_copy.get('end_time'), datetime):
                session_copy['end_time'] = session_copy['end_time'].isoformat()
                
            async with aiofiles.open(filename, 'w') as f:
                await f.write(json.dumps(session_copy, indent=2))
                
            return True
        except Exception as e:
            self.logger.error(f"Error saving selling session to file: {e}")
            return False

    async def get_selling_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Not efficiently implemented for files - returns empty."""
        return []

    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save weather data to file - stub implementation."""
        # Weather data is typically not saved to files in legacy mode
        return True

    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Not implemented for files - returns empty."""
        return []

    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save price forecast to file - stub implementation."""
        # Forecasts are typically not saved to files in legacy mode
        return True

    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Not implemented for files - returns empty."""
        return []

    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save PV forecast to file - stub implementation."""
        # Forecasts are typically not saved to files in legacy mode
        return True

    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Not implemented for files - returns empty."""
        return []

    async def cleanup_old_data(self, retention_days: int) -> Dict[str, int]:
        """
        Cleanup old JSON files (stub implementation).
        File-based storage typically doesn't implement automatic cleanup.
        
        Returns:
            Empty dictionary as files are not automatically cleaned up
        """
        self.logger.warning("Automatic cleanup not implemented for file storage")
        return {}

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get file storage statistics.
        
        Returns:
            Dictionary with file counts and sizes
        """
        try:
            stats = {}
            
            # Count files in energy_data directory
            if os.path.exists(self.energy_data_dir):
                files = [f for f in os.listdir(self.energy_data_dir) if f.endswith('.json')]
                stats['energy_data_files'] = len(files)
                
                # Calculate total size
                total_size = sum(
                    os.path.getsize(os.path.join(self.energy_data_dir, f)) 
                    for f in files
                )
                stats['total_size_bytes'] = total_size
                stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
            else:
                stats['energy_data_files'] = 0
                stats['total_size_bytes'] = 0
                stats['total_size_mb'] = 0
            
            stats['storage_type'] = 'file'
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting file storage stats: {e}")
            return {}


