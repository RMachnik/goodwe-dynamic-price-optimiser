from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from datetime import datetime

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
    # Data retention settings (in days, 0 = no retention/keep forever)
    retention_days: int = 30
    enable_auto_cleanup: bool = False

class DataStorageInterface(ABC):
    """Abstract base class for data storage implementations."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the storage backend."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the storage backend."""
        pass
        
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if storage is healthy and accessible."""
        pass

    @abstractmethod
    async def save_energy_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save a batch of energy readings."""
        pass

    @abstractmethod
    async def get_energy_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical energy data."""
        pass

    @abstractmethod
    async def save_system_state(self, state: Dict[str, Any]) -> bool:
        """Save MasterCoordinator state."""
        pass

    @abstractmethod
    async def get_system_state(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent system states."""
        pass

    @abstractmethod
    async def get_system_state_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve system states within a time range."""
        pass

    @abstractmethod
    async def save_decision(self, decision: Dict[str, Any]) -> bool:
        """Save charging/discharging decisions."""
        pass

    @abstractmethod
    async def get_decisions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve historical decisions."""
        pass
        
    @abstractmethod
    async def save_charging_session(self, session: Dict[str, Any]) -> bool:
        """Save or update a charging session."""
        pass
        
    @abstractmethod
    async def get_charging_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve charging sessions."""
        pass

    @abstractmethod
    async def save_selling_session(self, session: Dict[str, Any]) -> bool:
        """Save or update a battery selling session."""
        pass
        
    @abstractmethod
    async def get_selling_sessions(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve battery selling sessions."""
        pass

    @abstractmethod
    async def save_weather_data(self, data: List[Dict[str, Any]]) -> bool:
        """Save weather observations."""
        pass
        
    @abstractmethod
    async def get_weather_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Retrieve weather data."""
        pass

    @abstractmethod
    async def save_price_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save price forecast data."""
        pass
        
    @abstractmethod
    async def get_price_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Retrieve price forecasts for a date."""
        pass

    @abstractmethod
    async def save_pv_forecast(self, forecast_list: List[Dict[str, Any]]) -> bool:
        """Save PV forecast data."""
        pass
        
    @abstractmethod
    async def get_pv_forecasts(self, date_str: str) -> List[Dict[str, Any]]:
        """Retrieve PV forecasts for a date."""
        pass

    @abstractmethod
    async def cleanup_old_data(self, retention_days: int) -> Dict[str, int]:
        """
        Remove data older than retention_days.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Dictionary with count of deleted rows per table
        """
        pass

    @abstractmethod
    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics (row counts, size, etc.).
        
        Returns:
            Dictionary with database statistics
        """
        pass


