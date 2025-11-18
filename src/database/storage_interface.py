from dataclasses import dataclass
from typing import Optional, Dict, Any

class ConnectionError(Exception):
    pass

@dataclass
class StorageConfig:
    db_path: Optional[str] = None
    max_retries: int = 3
    retry_delay: float = 0.1
    connection_pool_size: int = 5
    batch_size: int = 100
    enable_fallback: bool = True
    fallback_to_file: bool = False

