from typing import Dict, Any, Optional
from .storage_interface import DataStorageInterface, StorageConfig
from .sqlite_storage import SQLiteStorage

class StorageFactory:
    """
    Factory for creating storage instances based on configuration.
    Database-only storage (file storage deprecated December 2024).
    """
    
    @staticmethod
    def create_storage(config_dict: Dict[str, Any]) -> DataStorageInterface:
        """
        Create a storage instance based on the provided configuration dictionary.
        
        Expected config structure:
        data_storage:
          database_storage:
            enabled: bool
            sqlite:
              path: str
        """
        
        # Parse config
        db_config = config_dict.get('database_storage', {})
        db_enabled = db_config.get('enabled', False)
        
        # Create config object
        storage_config = StorageConfig(
            db_path=db_config.get('sqlite', {}).get('path', 'data/goodwe_energy.db'),
            enable_fallback=False,
            fallback_to_file=False
        )
        
        # Use database storage only
        if db_enabled:
            return SQLiteStorage(storage_config)
        else:
            raise ValueError(
                "Database storage must be enabled. File-only mode is deprecated as of December 2024. "
                "Please set data_storage.database_storage.enabled: true in your config."
            )
