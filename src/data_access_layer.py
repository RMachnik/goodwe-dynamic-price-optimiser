#!/usr/bin/env python3
"""
Data Access Layer for GoodWe Dynamic Price Optimiser
Abstracts storage implementation to support file-based or database-backed storage
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DataStorageConfig:
    """Configuration for data storage backends"""
    mode: str = "file"  # "file" or "database"
    database_config: Optional[Dict[str, Any]] = None
    file_config: Optional[Dict[str, Any]] = None

    @classmethod
    def from_app_config(cls, app_config: Dict[str, Any]) -> 'DataStorageConfig':
        """Create from application configuration"""
        data_config = app_config.get('data_storage', {})

        mode = data_config.get('mode', 'file')
        database_config = data_config.get('database', {})
        file_config = data_config.get('file', {})

        return cls(
            mode=mode,
            database_config=database_config,
            file_config=file_config
        )

class DataAccessInterface(ABC):
    """Abstract interface for data access operations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to storage backend"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from storage backend"""
        pass

    @abstractmethod
    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy data"""
        pass

    @abstractmethod
    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data for time range"""
        pass

    @abstractmethod
    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state"""
        pass

    @abstractmethod
    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system states"""
        pass

    @abstractmethod
    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save coordinator decision"""
        pass

    @abstractmethod
    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get decisions for time range"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check storage health"""
        pass

class FileStorageBackend(DataAccessInterface):
    """File-based storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = Path(config.get('base_path', 'out/energy_data'))
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.is_connected = True

    async def connect(self) -> bool:
        """Connect (always succeeds for file storage)"""
        self.is_connected = True
        return True

    async def disconnect(self) -> bool:
        """Disconnect (always succeeds for file storage)"""
        self.is_connected = True  # File storage is always available
        return True

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy data to JSON files"""
        try:
            if not data:
                return True

            # Save as JSON file with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"energy_data_{timestamp}.json"
            filepath = self.base_path / filename

            # Store file metadata for time range queries
            metadata = {
                'file_timestamp': timestamp,
                'created_at': datetime.now().isoformat(),
                'record_count': len(data),
                'data': data
            }

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

            logger.debug(f"Saved {len(data)} energy data records to file: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save energy data to file: {e}")
            return False

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data from JSON files"""
        try:
            result = []
            if not self.base_path.exists():
                return result

            # Find all energy data files
            pattern = "energy_data_*.json"
            files = list(self.base_path.glob(pattern))

            for filepath in sorted(files):
                try:
                    # Load the file - it contains metadata wrapped data
                    with open(filepath, 'r', encoding='utf-8') as f:
                        file_metadata = json.load(f)

                    if isinstance(file_metadata, dict) and 'data' in file_metadata:
                        data = file_metadata['data']
                        if isinstance(data, list):
                            # Filter by timestamp
                            filtered = []
                            for record in data:
                                record_time = datetime.fromisoformat(record.get('timestamp', '').replace('Z', '+00:00'))
                                if start_time <= record_time <= end_time:
                                    filtered.append(record)
                            result.extend(filtered)

                except Exception as e:
                    logger.warning(f"Failed to load energy data file {filepath}: {e}")

            logger.debug(f"Loaded {len(result)} energy data records from files")
            return result

        except Exception as e:
            logger.error(f"Failed to get energy data from files: {e}")
            return []

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"system_state_{timestamp}.json"
            filepath = self.base_path / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False, default=str)

            logger.debug(f"Saved system state to file: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save system state to file: {e}")
            return False

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system states from files"""
        try:
            result = []
            if not self.base_path.exists():
                return result

            # Find all system state files
            pattern = "system_state_*.json"
            files = list(self.base_path.glob(pattern))

            # Sort by timestamp (newest first)
            def get_file_timestamp(filepath: Path) -> datetime:
                try:
                    timestamp_str = filepath.stem.split('_')[-1]
                    return datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                except:
                    return datetime.min

            files.sort(key=get_file_timestamp, reverse=True)

            # Load up to limit
            for filepath in files[:limit]:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                        result.append(state)
                except Exception as e:
                    logger.warning(f"Failed to load system state file {filepath}: {e}")

            logger.debug(f"Loaded {len(result)} system state records from files")
            return result

        except Exception as e:
            logger.error(f"Failed to get system states from files: {e}")
            return []

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save decision to file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"decision_{timestamp}.json"
            filepath = self.base_path / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(decision, f, indent=2, ensure_ascii=False, default=str)

            logger.debug(f"Saved decision to file: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to save decision to file: {e}")
            return False

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get decisions from files within time range"""
        try:
            result = []
            if not self.base_path.exists():
                return result

            # Find all decision files
            pattern = "decision_*.json"
            files = list(self.base_path.glob(pattern))

            for filepath in files:
                try:
                    # Extract timestamp from filename
                    timestamp_str = filepath.stem.split('_')[-1]
                    file_time = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')

                    # Only load files within time range
                    if start_time <= file_time <= end_time:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            result.append(data)

                except Exception as e:
                    logger.warning(f"Failed to load decision file {filepath}: {e}")

            logger.debug(f"Loaded {len(result)} decisions from files")
            return result

        except Exception as e:
            logger.error(f"Failed to get decisions from files: {e}")
            return []

    async def health_check(self) -> bool:
        """Check file storage health"""
        try:
            # Check if path exists and is writable
            return self.base_path.exists() and os.access(self.base_path, os.W_OK)
        except Exception:
            return False

class DatabaseStorageBackend(DataAccessInterface):
    """Database-backed storage implementation"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        from .database.sqlite_storage import SQLiteStorage
        from .database.storage_interface import StorageConfig

        # Create database config from backend config
        db_config = StorageConfig(
            db_path=config.get('db_path', 'goodwe_energy.db'),
            max_retries=config.get('max_retries', 3),
            retry_delay=config.get('retry_delay', 0.1),
            connection_pool_size=config.get('connection_pool_size', 5),
            batch_size=config.get('batch_size', 10),
            enable_fallback=config.get('enable_fallback', True),
            fallback_to_file=config.get('fallback_to_file', True)
        )

        self.db_storage = SQLiteStorage(db_config)

    async def connect(self) -> bool:
        """Connect to database"""
        return await self.db_storage.connect()

    async def disconnect(self) -> bool:
        """Disconnect from database"""
        return await self.db_storage.disconnect()

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy data to database"""
        return await self.db_storage.save_energy_data(data)

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data from database"""
        return await self.db_storage.get_energy_data(start_time, end_time)

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state to database"""
        return await self.db_storage.save_system_state(state)

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system states from database"""
        return await self.db_storage.get_system_state(limit)

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save decision to database"""
        return await self.db_storage.save_decision(decision)

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get decisions from database"""
        return await self.db_storage.get_decisions(start_time, end_time)

    async def health_check(self) -> bool:
        """Check database health"""
        return await self.db_storage.health_check()

class DataAccessLayer:
    """Unified data access layer supporting file and database backends"""

    def __init__(self, config: DataStorageConfig):
        self.config = config
        self.backend = None
        self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the appropriate backend based on configuration"""
        if self.config.mode == "database":
            logger.info("Initializing database storage backend")
            self.backend = DatabaseStorageBackend(self.config.database_config or {})
        else:
            logger.info("Initializing file storage backend")
            self.backend = FileStorageBackend(self.config.file_config or {
                'base_path': 'out/energy_data'
            })

    async def connect(self) -> bool:
        """Connect to the configured storage backend"""
        if not self.backend:
            await self._initialize_backend()
        return await self.backend.connect() if self.backend else False

    async def disconnect(self) -> bool:
        """Disconnect from storage backend"""
        return await self.backend.disconnect() if self.backend else True

    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save energy data"""
        return await self.backend.save_energy_data(data) if self.backend else False

    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data for time range"""
        return await self.backend.get_energy_data(start_time, end_time) if self.backend else []

    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state"""
        return await self.backend.save_system_state(state) if self.backend else False

    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system states"""
        return await self.backend.get_system_state(limit) if self.backend else []

    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save coordinator decision"""
        return await self.backend.save_decision(decision) if self.backend else False

    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get decisions for time range"""
        return await self.backend.get_decisions(start_time, end_time) if self.backend else []

    def switch_backend(self, mode: str):
        """Switch storage backend at runtime"""
        self.config.mode = mode
        logger.info(f"Switching storage backend to: {mode}")
        self._initialize_backend()

    def get_backend_mode(self) -> str:
        """Get current backend mode"""
        return self.config.mode

    def get_backend_info(self) -> Dict[str, Any]:
        """Get backend information"""
        return {
            'mode': self.config.mode,
            'backend_type': type(self.backend).__name__ if self.backend else 'None',
            'is_connected': getattr(self.backend, 'is_connected', False) if self.backend else False
        }

    async def health_check(self) -> bool:
        """Check storage health"""
        return await self.backend.health_check() if self.backend else False

# Factory function for easy access
def create_data_access_layer(config_dict: Dict[str, Any]) -> DataAccessLayer:
    """Create data access layer from configuration dictionary"""
    storage_config = DataStorageConfig.from_app_config(config_dict)
    return DataAccessLayer(storage_config)
