#!/usr/bin/env python3
"""
Database Schema Definition for GoodWe Dynamic Price Optimiser
Comprehensive schema for migrating from JSON files to SQLite database
"""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
import sqlite3
import logging

logger = logging.getLogger(__name__)

@dataclass
class EnergyData:
    """Energy data record"""
    timestamp: datetime
    battery_soc: float
    pv_power: float
    grid_power: float
    consumption: float
    price: float
    battery_temp: Optional[float] = None
    battery_voltage: Optional[float] = None
    grid_voltage: Optional[float] = None

@dataclass
class ChargingSession:
    """Charging session record"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    energy_kwh: float
    cost_pln: float
    status: str
    battery_soc_start: float
    battery_soc_end: Optional[float] = None
    charging_source: Optional[str] = None
    pv_contribution_kwh: Optional[float] = None
    grid_contribution_kwh: Optional[float] = None

@dataclass
class DailyStats:
    """Daily statistics record"""
    date: str
    total_consumption: float
    total_pv: float
    total_grid_import: float
    avg_price: float
    charging_sessions: int
    total_energy_charged: float
    total_cost: float

@dataclass
class SystemState:
    """System state record"""
    timestamp: datetime
    state: str
    uptime_seconds: float
    current_data: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    decision_count: int

@dataclass
class BatterySellingSession:
    """Battery selling session record"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    start_soc: float
    end_soc: Optional[float]
    energy_sold_kwh: float
    average_price_pln: float
    revenue_pln: float
    selling_power_w: int
    duration_hours: Optional[float] = None
    safety_checks_passed: bool = True
    risk_level: str = "low"

@dataclass
class CoordinatorDecision:
    """Coordinator decision record"""
    timestamp: datetime
    decision_type: str
    should_charge: bool
    reason: str
    confidence: float
    current_price: float
    cheapest_price: float
    cheapest_hour: int
    battery_soc: float
    pv_power: float
    consumption: float
    decision_score: float

@dataclass
class WeatherData:
    """Weather data record"""
    timestamp: datetime
    source: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    precipitation: Optional[float] = None
    cloud_cover: Optional[int] = None
    solar_irradiance: Optional[float] = None

@dataclass
class PriceForecast:
    """Price forecast record"""
    timestamp: datetime
    forecast_date: str
    hour: int
    price_pln: float
    confidence: float
    source: str

@dataclass
class PVForecast:
    """PV forecast record"""
    timestamp: datetime
    forecast_date: str
    hour: int
    predicted_power_w: float
    confidence: float
    weather_conditions: Optional[str] = None

@dataclass
class PeakHoursData:
    """Peak hours data record"""
    timestamp: datetime
    date: str
    peak_hours: str
    recommended_usage: str
    savings_potential: float

@dataclass
class PriceWindowAnalysis:
    """Price window analysis record"""
    timestamp: datetime
    window_start: datetime
    window_end: datetime
    price_category: str
    savings_pln: float

class DatabaseSchema:
    """Database schema management"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Connect to database"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from database"""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def create_tables(self):
        """Create all database tables"""
        if not self.connection:
            logger.error("No database connection")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # Energy data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS energy_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    battery_soc REAL NOT NULL,
                    pv_power REAL NOT NULL,
                    grid_power REAL NOT NULL,
                    consumption REAL NOT NULL,
                    price REAL NOT NULL,
                    battery_temp REAL,
                    battery_voltage REAL,
                    grid_voltage REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Charging sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS charging_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(50) UNIQUE NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    energy_kwh REAL NOT NULL,
                    cost_pln REAL NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    battery_soc_start REAL NOT NULL,
                    battery_soc_end REAL,
                    charging_source VARCHAR(20),
                    pv_contribution_kwh REAL,
                    grid_contribution_kwh REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Daily stats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    total_consumption REAL NOT NULL,
                    total_pv REAL NOT NULL,
                    total_grid_import REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    charging_sessions INTEGER NOT NULL,
                    total_energy_charged REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # System state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    state VARCHAR(20) NOT NULL,
                    uptime_seconds REAL NOT NULL,
                    current_data TEXT NOT NULL,
                    performance_metrics TEXT NOT NULL,
                    decision_count INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Battery selling sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS battery_selling_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id VARCHAR(50) UNIQUE NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    start_soc REAL NOT NULL,
                    end_soc REAL,
                    energy_sold_kwh REAL NOT NULL,
                    average_price_pln REAL NOT NULL,
                    revenue_pln REAL NOT NULL,
                    selling_power_w INTEGER NOT NULL,
                    duration_hours REAL,
                    safety_checks_passed BOOLEAN DEFAULT 1,
                    risk_level VARCHAR(10) DEFAULT 'low',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Coordinator decisions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coordinator_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    decision_type VARCHAR(20) NOT NULL,
                    should_charge BOOLEAN NOT NULL,
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    current_price REAL NOT NULL,
                    cheapest_price REAL NOT NULL,
                    cheapest_hour INTEGER NOT NULL,
                    battery_soc REAL NOT NULL,
                    pv_power REAL NOT NULL,
                    consumption REAL NOT NULL,
                    decision_score REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Weather data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    source VARCHAR(20) NOT NULL,
                    temperature REAL,
                    humidity REAL,
                    pressure REAL,
                    wind_speed REAL,
                    wind_direction REAL,
                    precipitation REAL,
                    cloud_cover INTEGER,
                    solar_irradiance REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Price forecasts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    forecast_date DATE NOT NULL,
                    hour INTEGER NOT NULL,
                    price_pln REAL NOT NULL,
                    confidence REAL NOT NULL,
                    source VARCHAR(20) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # PV forecasts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pv_forecasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    forecast_date DATE NOT NULL,
                    hour INTEGER NOT NULL,
                    predicted_power_w REAL NOT NULL,
                    confidence REAL NOT NULL,
                    weather_conditions TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Peak hours data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS peak_hours_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    date DATE NOT NULL,
                    peak_hours TEXT NOT NULL,
                    recommended_usage TEXT NOT NULL,
                    savings_potential REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Price window analysis table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_window_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    window_start DATETIME NOT NULL,
                    window_end DATETIME NOT NULL,
                    price_category VARCHAR(20) NOT NULL,
                    savings_pln REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
            logger.info("All database tables created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return False
    
    def create_indexes(self):
        """Create database indexes for performance"""
        if not self.connection:
            logger.error("No database connection")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # Create indexes for time-based queries
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_energy_data_timestamp ON energy_data(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_charging_sessions_start_time ON charging_sessions(start_time)",
                "CREATE INDEX IF NOT EXISTS idx_system_state_timestamp ON system_state(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_battery_selling_start_time ON battery_selling_sessions(start_time)",
                "CREATE INDEX IF NOT EXISTS idx_coordinator_decisions_timestamp ON coordinator_decisions(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_weather_data_timestamp ON weather_data(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_price_forecasts_date_hour ON price_forecasts(forecast_date, hour)",
                "CREATE INDEX IF NOT EXISTS idx_pv_forecasts_date_hour ON pv_forecasts(forecast_date, hour)",
                "CREATE INDEX IF NOT EXISTS idx_peak_hours_date ON peak_hours_data(date)",
                "CREATE INDEX IF NOT EXISTS idx_price_window_timestamp ON price_window_analysis(timestamp)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            self.connection.commit()
            logger.info("All database indexes created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
            return False
    
    def verify_schema(self):
        """Verify that all tables exist and have correct structure"""
        if not self.connection:
            logger.error("No database connection")
            return False
        
        try:
            cursor = self.connection.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'energy_data', 'charging_sessions', 'daily_stats', 'system_state',
                'battery_selling_sessions', 'coordinator_decisions', 'weather_data',
                'price_forecasts', 'pv_forecasts', 'peak_hours_data', 'price_window_analysis'
            ]
            
            missing_tables = [table for table in expected_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"Missing tables: {missing_tables}")
                return False
            
            logger.info("Database schema verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify schema: {e}")
            return False

