from typing import Dict, Any, Optional
from .storage_interface import DataStorageInterface, StorageConfig
from .sqlite_storage import SQLiteStorage
from .file_storage import FileStorage
from .composite_storage import CompositeStorage

class StorageFactory:
    """
    Factory for creating storage instances based on configuration.
    """
    
    @staticmethod
    def create_storage(config_dict: Dict[str, Any]) -> DataStorageInterface:
        """
        Create a storage instance based on the provided configuration dictionary.
        
        Expected config structure:
        data_storage:
          file_storage:
            enabled: bool
          database_storage:
            enabled: bool
            sqlite:
              path: str
        """
        
        # Parse config
        file_enabled = config_dict.get('file_storage', {}).get('enabled', True)
        db_config = config_dict.get('database_storage', {})
        db_enabled = db_config.get('enabled', False)
        
        # Create config object
        storage_config = StorageConfig(
            db_path=db_config.get('sqlite', {}).get('path', 'data/goodwe_energy.db'),
            enable_fallback=True,
            fallback_to_file=file_enabled
        )
        
        # Determine storage type
        if db_enabled and file_enabled:
            # Composite mode (DB + File)
            primary = SQLiteStorage(storage_config)
            secondary = FileStorage(storage_config)
            return CompositeStorage(primary, [secondary], storage_config)
            
        elif db_enabled:
            # DB only
            return SQLiteStorage(storage_config)
            
        else:
            # File only (default/legacy)
            return FileStorage(storage_config)
