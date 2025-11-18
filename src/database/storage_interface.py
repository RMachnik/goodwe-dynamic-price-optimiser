#!/usr/bin/env python3
"""
Storage Interface for GoodWe Dynamic Price Optimiser
Abstract interface for different storage backends with error handling and retry logic
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import backoff
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StorageConfig:
    """Storage configuration"""
    db_path: str
    max_retries: int = 3
    retry_delay: float = 1.0
    connection_pool_size: int = 10
    batch_size: int = 100
    enable_fallback: bool = True
    fallback_to_file: bool = True

class StorageError(Exception):
    """Base storage error"""
    pass

class ConnectionError(StorageError):
    """Database connection error"""
    pass

class QueryError(StorageError):
    """Database query error"""
    pass

class MigrationError(StorageError):
    """Data migration error"""
    pass

class StorageInterface(ABC):
    """Abstract storage interface"""
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self.is_connected = False
        self.connection_pool = []
        self.fallback_enabled = config.enable_fallback
        self.retry_count = 0
        self.max_retries = config.max_retries
    
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
    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        """Save charging session"""
        pass
    
    @abstractmethod
    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save system state"""
        pass
    
    @abstractmethod
    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save coordinator decision"""
        pass
    
    @abstractmethod
    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save weather data"""
        pass
    
    @abstractmethod
    async def save_price_forecast(self, forecast: List[Dict[str, Any]]) -> bool:
        """Save price forecast"""
        pass
    
    @abstractmethod
    async def save_pv_forecast(self, forecast: List[Dict[str, Any]]) -> bool:
        """Save PV forecast"""
        pass
    
    @abstractmethod
    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get energy data for time range"""
        pass
    
    @abstractmethod
    async def get_charging_sessions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get charging sessions for date range"""
        pass
    
    @abstractmethod
    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent system state"""
        pass
    
    @abstractmethod
    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get coordinator decisions for time range"""
        pass
    
    @abstractmethod
    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get weather data for time range"""
        pass
    
    @abstractmethod
    async def get_price_forecasts(self, date: str) -> List[Dict[str, Any]]:
        """Get price forecasts for date"""
        pass
    
    @abstractmethod
    async def get_pv_forecasts(self, date: str) -> List[Dict[str, Any]]:
        """Get PV forecasts for date"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check storage health"""
        pass
    
    @abstractmethod
    async def backup_data(self, backup_path: str) -> bool:
        """Backup data"""
        pass
    
    @abstractmethod
    async def restore_data(self, backup_path: str) -> bool:
        """Restore data from backup"""
        pass

class RetryMixin:
    """Mixin for retry logic"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_count = 0
        self.max_retries = getattr(self, 'max_retries', 3)
    
    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, QueryError),
        max_tries=3,
        base=2,
        max_value=10
    )
    async def _retry_operation(self, operation, *args, **kwargs):
        """Retry operation with exponential backoff"""
        try:
            return await operation(*args, **kwargs)
        except Exception as e:
            self.retry_count += 1
            if self.retry_count >= self.max_retries:
                logger.error(f"Operation failed after {self.max_retries} retries: {e}")
                raise
            logger.warning(f"Operation failed, retrying ({self.retry_count}/{self.max_retries}): {e}")
            raise
    
    def _reset_retry_count(self):
        """Reset retry count"""
        self.retry_count = 0

class CircuitBreakerMixin:
    """Mixin for circuit breaker pattern"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failure_count = 0
        self.failure_threshold = 5
        self.recovery_timeout = 60  # seconds
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def _check_circuit_breaker(self):
        """Check circuit breaker state"""
        if self.state == "OPEN":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker: HALF_OPEN - testing connection")
            else:
                raise ConnectionError("Circuit breaker is OPEN - too many failures")
        elif self.state == "HALF_OPEN":
            # Test connection
            if not await self.health_check():
                self.state = "OPEN"
                self.last_failure_time = datetime.now()
                raise ConnectionError("Circuit breaker: HALF_OPEN test failed")
            else:
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("Circuit breaker: CLOSED - connection restored")
    
    def _record_success(self):
        """Record successful operation"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit breaker: OPEN - {self.failure_count} consecutive failures")

class FallbackMixin:
    """Mixin for fallback to file storage"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_enabled = getattr(self, 'fallback_enabled', True)
        self.fallback_path = "out/fallback_data"
    
    async def _fallback_to_file(self, data: Any, filename: str):
        """Fallback to file storage"""
        if not self.fallback_enabled:
            return False
        
        try:
            import json
            from pathlib import Path
            
            fallback_dir = Path(self.fallback_path)
            fallback_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = fallback_dir / f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.warning(f"Data saved to fallback file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Fallback to file failed: {e}")
            return False
    
    async def _load_from_fallback(self, filename_pattern: str) -> List[Dict[str, Any]]:
        """Load data from fallback files"""
        if not self.fallback_enabled:
            return []
        
        try:
            import json
            from pathlib import Path
            import glob
            
            fallback_dir = Path(self.fallback_path)
            if not fallback_dir.exists():
                return []
            
            files = glob.glob(str(fallback_dir / f"{filename_pattern}*.json"))
            data = []
            
            for file_path in sorted(files):
                try:
                    with open(file_path, 'r') as f:
                        file_data = json.load(f)
                        if isinstance(file_data, list):
                            data.extend(file_data)
                        else:
                            data.append(file_data)
                except Exception as e:
                    logger.warning(f"Failed to load fallback file {file_path}: {e}")
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to load from fallback: {e}")
            return []

class StorageManager:
    """Storage manager with error handling and monitoring"""
    
    def __init__(self, storage: StorageInterface):
        self.storage = storage
        self.operation_count = 0
        self.error_count = 0
        self.last_operation_time = None
    
    async def execute_with_monitoring(self, operation, *args, **kwargs):
        """Execute operation with monitoring"""
        start_time = datetime.now()
        self.operation_count += 1
        
        try:
            result = await operation(*args, **kwargs)
            self.last_operation_time = datetime.now()
            return result
        except Exception as e:
            self.error_count += 1
            logger.error(f"Operation failed: {e}")
            raise
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            if duration > 5.0:  # Log slow operations
                logger.warning(f"Slow operation: {operation.__name__} took {duration:.2f}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        return {
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(self.operation_count, 1),
            'last_operation_time': self.last_operation_time,
            'is_connected': getattr(self.storage, 'is_connected', False)
        }

