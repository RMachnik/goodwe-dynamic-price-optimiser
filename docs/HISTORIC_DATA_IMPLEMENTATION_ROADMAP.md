# 🗺️ Historic Data Storage Implementation Roadmap
## Practical Step-by-Step Implementation Guide

**Document Version**: 1.0  
**Created**: 2025-01-09  
**Status**: Implementation Ready  

---

## 🎯 **Quick Start Implementation Plan**

This roadmap provides a practical, step-by-step approach to implementing advanced historic data storage for your GoodWe Dynamic Price Optimiser system. Each phase builds upon the previous one, ensuring minimal disruption to your current operations.

---

## 📋 **Phase 1: Foundation Setup (Week 1-2)**

### **Task 1.1: Database Selection and Setup**
**Priority**: High  
**Estimated Time**: 4-6 hours  
**Dependencies**: None  

#### **1.1.1: Choose Database Stack**
```bash
# Option A: InfluxDB + SQLite (Recommended for simplicity)
- InfluxDB 2.0 for time-series data
- SQLite for relational data (no additional server needed)

# Option B: TimescaleDB + PostgreSQL (Recommended for scalability)
- TimescaleDB for time-series data
- PostgreSQL for relational data

# Option C: Hybrid approach (Current + Enhancement)
- Keep current JSON files for immediate data
- Add InfluxDB for long-term storage
- Gradual migration over time
```

#### **1.1.2: Docker Compose Setup**
```yaml
# Add to docker-compose.yml
services:
  influxdb:
    image: influxdb:2.0
    container_name: goodwe-influxdb
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=goodwe123
      - DOCKER_INFLUXDB_INIT_ORG=goodwe-energy
      - DOCKER_INFLUXDB_INIT_BUCKET=energy_data
    volumes:
      - influxdb_data:/var/lib/influxdb2
      - influxdb_config:/etc/influxdb2
    restart: unless-stopped

  postgresql:
    image: postgres:15
    container_name: goodwe-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=goodwe_energy
      - POSTGRES_USER=goodwe
      - POSTGRES_PASSWORD=goodwe123
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  influxdb_data:
  influxdb_config:
  postgres_data:
```

#### **1.1.3: Configuration Updates**
```yaml
# Add to master_coordinator_config.yaml
data_storage:
  # Current file-based storage (keep for compatibility)
  file_storage:
    enabled: true
    energy_data_dir: "/app/out/energy_data"
    retention_days: 7  # Keep only 7 days in files
  
  # New database storage
  database_storage:
    enabled: true
    timeseries_db:
      type: "influxdb"
      url: "http://influxdb:8086"
      token: "${INFLUXDB_TOKEN}"
      org: "goodwe-energy"
      bucket: "energy_data"
      retention_policy: "30d"
    
    relational_db:
      type: "postgresql"
      host: "postgresql"
      port: 5432
      database: "goodwe_energy"
      username: "goodwe"
      password: "goodwe123"
      ssl_mode: "prefer"
```

### **Task 1.2: Data Abstraction Layer**
**Priority**: High  
**Estimated Time**: 6-8 hours  
**Dependencies**: Task 1.1  

#### **1.2.1: Create Storage Interface**
```python
# src/data_storage/storage_interface.py
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DataStorageInterface(ABC):
    """Abstract interface for data storage operations"""
    
    @abstractmethod
    async def store_energy_data(self, data: Dict[str, Any]) -> bool:
        """Store energy monitoring data"""
        pass
    
    @abstractmethod
    async def get_energy_data(self, 
                            start_time: datetime, 
                            end_time: datetime,
                            device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve energy data for time range"""
        pass
    
    @abstractmethod
    async def store_charging_session(self, session_data: Dict[str, Any]) -> bool:
        """Store charging session data"""
        pass
    
    @abstractmethod
    async def get_charging_sessions(self, 
                                  start_date: datetime,
                                  end_date: datetime) -> List[Dict[str, Any]]:
        """Retrieve charging sessions for date range"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check storage system health"""
        pass
```

#### **1.2.2: Implement File Storage (Current System)**
```python
# src/data_storage/file_storage.py
import json
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .storage_interface import DataStorageInterface

class FileStorage(DataStorageInterface):
    """File-based storage implementation (current system)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.energy_data_dir = Path(config['energy_data_dir'])
        self.energy_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Compression settings
        self.compression_enabled = config.get('compression', True)
        self.retention_days = config.get('retention_days', 7)
    
    async def store_energy_data(self, data: Dict[str, Any]) -> bool:
        """Store energy data to compressed JSON file"""
        try:
            timestamp = datetime.now()
            filename = f"energy_data_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            
            if self.compression_enabled:
                filename += ".gz"
                filepath = self.energy_data_dir / filename
                with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                filepath = self.energy_data_dir / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Cleanup old files
            await self._cleanup_old_files()
            
            logger.debug(f"Energy data stored to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store energy data: {e}")
            return False
    
    async def get_energy_data(self, 
                            start_time: datetime, 
                            end_time: datetime,
                            device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve energy data from files"""
        try:
            data_points = []
            
            # Get all files in the time range
            for file_path in self.energy_data_dir.glob("energy_data_*.json*"):
                file_time = self._extract_timestamp_from_filename(file_path.name)
                if start_time <= file_time <= end_time:
                    data = await self._load_file_data(file_path)
                    if data:
                        data_points.append(data)
            
            return sorted(data_points, key=lambda x: x.get('timestamp', ''))
            
        except Exception as e:
            logger.error(f"Failed to retrieve energy data: {e}")
            return []
    
    async def _cleanup_old_files(self):
        """Remove files older than retention period"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        
        for file_path in self.energy_data_dir.glob("energy_data_*.json*"):
            file_time = self._extract_timestamp_from_filename(file_path.name)
            if file_time < cutoff_time:
                file_path.unlink()
                logger.debug(f"Removed old file: {file_path}")
    
    def _extract_timestamp_from_filename(self, filename: str) -> datetime:
        """Extract timestamp from filename"""
        try:
            # Remove .gz extension if present
            if filename.endswith('.gz'):
                filename = filename[:-3]
            
            # Extract timestamp from filename
            timestamp_str = filename.replace('energy_data_', '').replace('.json', '')
            return datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
        except Exception:
            return datetime.min
    
    async def _load_file_data(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load data from file (compressed or uncompressed)"""
        try:
            if file_path.suffix == '.gz':
                with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                    return json.load(f)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return None
```

### **Task 1.3: Update Enhanced Data Collector**
**Priority**: High  
**Estimated Time**: 3-4 hours  
**Dependencies**: Task 1.2  

#### **1.3.1: Modify Enhanced Data Collector**
```python
# Update src/enhanced_data_collector.py
from src.data_storage.storage_interface import DataStorageInterface
from src.data_storage.file_storage import FileStorage

class EnhancedDataCollector:
    def __init__(self, config_path: str):
        # ... existing initialization ...
        
        # Initialize storage system
        self.storage = self._initialize_storage()
    
    def _initialize_storage(self) -> DataStorageInterface:
        """Initialize appropriate storage system"""
        storage_config = self.config.get('data_storage', {})
        
        if storage_config.get('file_storage', {}).get('enabled', True):
            return FileStorage(storage_config['file_storage'])
        else:
            # Future: Add database storage here
            return FileStorage(storage_config['file_storage'])
    
    async def collect_comprehensive_data(self) -> Dict[str, Any]:
        """Collect comprehensive data and store it"""
        # ... existing data collection ...
        
        # Store data using new storage system
        await self.storage.store_energy_data(comprehensive_data)
        
        return comprehensive_data
```

---

## 📊 **Phase 2: Database Integration (Week 3-4)**

### **Task 2.1: InfluxDB Integration**
**Priority**: High  
**Estimated Time**: 8-10 hours  
**Dependencies**: Phase 1 completion  

#### **2.1.1: Install Dependencies**
```bash
# Add to requirements.txt
influxdb-client>=1.30.0
psycopg2-binary>=2.9.0
```

#### **2.1.2: Create InfluxDB Storage Implementation**
```python
# src/data_storage/influxdb_storage.py
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class InfluxDBStorage(DataStorageInterface):
    """InfluxDB implementation for time-series data"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = InfluxDBClient(
            url=config['url'],
            token=config['token'],
            org=config['org']
        )
        self.bucket = config['bucket']
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api()
    
    async def store_energy_data(self, data: Dict[str, Any]) -> bool:
        """Store energy data in InfluxDB"""
        try:
            point = Point("energy_data") \
                .tag("device_id", data.get('system', {}).get('inverter_serial', 'unknown')) \
                .tag("data_source", "goodwe_inverter") \
                .field("battery_soc", data.get('battery', {}).get('soc_percent', 0)) \
                .field("battery_temp", data.get('battery', {}).get('temperature_c', 0)) \
                .field("pv_power_kw", data.get('photovoltaic', {}).get('current_power_kw', 0)) \
                .field("grid_power_kw", data.get('grid', {}).get('current_power_kw', 0)) \
                .field("consumption_kw", data.get('house_consumption', {}).get('current_power_kw', 0)) \
                .field("price_pln", data.get('pricing', {}).get('current_price_pln', 0)) \
                .time(datetime.now())
            
            self.write_api.write(bucket=self.bucket, record=point)
            logger.debug("Energy data stored in InfluxDB")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store energy data in InfluxDB: {e}")
            return False
    
    async def get_energy_data(self, 
                            start_time: datetime, 
                            end_time: datetime,
                            device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve energy data from InfluxDB"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
            |> range(start: {start_time.isoformat()}, stop: {end_time.isoformat()})
            |> filter(fn: (r) => r._measurement == "energy_data")
            '''
            
            if device_id:
                query += f'|> filter(fn: (r) => r.device_id == "{device_id}")'
            
            result = self.query_api.query(org=self.config['org'], query=query)
            
            data_points = []
            for table in result:
                for record in table.records:
                    data_points.append({
                        'timestamp': record.get_time().isoformat(),
                        'device_id': record.values.get('device_id'),
                        'battery_soc': record.values.get('_value'),
                        'field': record.get_field(),
                        'measurement': record.get_measurement()
                    })
            
            return data_points
            
        except Exception as e:
            logger.error(f"Failed to retrieve energy data from InfluxDB: {e}")
            return []
```

### **Task 2.2: PostgreSQL Integration**
**Priority**: Medium  
**Estimated Time**: 6-8 hours  
**Dependencies**: Task 2.1  

#### **2.2.1: Create Database Schema**
```sql
-- src/data_storage/schema.sql
CREATE TABLE IF NOT EXISTS charging_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    battery_soc_start INTEGER NOT NULL,
    battery_soc_end INTEGER,
    energy_charged_kwh DECIMAL(10,3),
    average_price_pln DECIMAL(10,4),
    total_cost_pln DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100) UNIQUE NOT NULL,
    config_data JSONB NOT NULL,
    version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics_reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL,
    report_date DATE NOT NULL,
    report_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_charging_sessions_date ON charging_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_charging_sessions_status ON charging_sessions(status);
CREATE INDEX IF NOT EXISTS idx_analytics_reports_date ON analytics_reports(report_date);
```

#### **2.2.2: Create PostgreSQL Storage Implementation**
```python
# src/data_storage/postgresql_storage.py
import psycopg2
import psycopg2.extras
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PostgreSQLStorage(DataStorageInterface):
    """PostgreSQL implementation for relational data"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        try:
            self.connection = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['username'],
                password=self.config['password']
            )
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def store_charging_session(self, session_data: Dict[str, Any]) -> bool:
        """Store charging session data"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO charging_sessions 
                    (session_id, start_time, end_time, battery_soc_start, battery_soc_end,
                     energy_charged_kwh, average_price_pln, total_cost_pln, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        end_time = EXCLUDED.end_time,
                        battery_soc_end = EXCLUDED.battery_soc_end,
                        energy_charged_kwh = EXCLUDED.energy_charged_kwh,
                        average_price_pln = EXCLUDED.average_price_pln,
                        total_cost_pln = EXCLUDED.total_cost_pln,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                """, (
                    session_data.get('session_id'),
                    session_data.get('start_time'),
                    session_data.get('end_time'),
                    session_data.get('battery_soc_start'),
                    session_data.get('battery_soc_end'),
                    session_data.get('energy_charged_kwh'),
                    session_data.get('average_price_pln'),
                    session_data.get('total_cost_pln'),
                    session_data.get('status', 'active')
                ))
                self.connection.commit()
                logger.debug("Charging session stored in PostgreSQL")
                return True
                
        except Exception as e:
            logger.error(f"Failed to store charging session: {e}")
            self.connection.rollback()
            return False
```

---

## 🔄 **Phase 3: Migration and Testing (Week 5-6)**

### **Task 3.1: Data Migration Tool**
**Priority**: High  
**Estimated Time**: 6-8 hours  
**Dependencies**: Phase 2 completion  

#### **3.1.1: Create Migration Script**
```python
# scripts/migrate_data.py
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta
from src.data_storage.file_storage import FileStorage
from src.data_storage.influxdb_storage import InfluxDBStorage
from src.data_storage.postgresql_storage import PostgreSQLStorage

class DataMigrationTool:
    """Tool for migrating existing data to new storage systems"""
    
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.file_storage = FileStorage(self.config['data_storage']['file_storage'])
        self.influx_storage = InfluxDBStorage(self.config['data_storage']['database_storage']['timeseries_db'])
        self.postgres_storage = PostgreSQLStorage(self.config['data_storage']['database_storage']['relational_db'])
    
    async def migrate_energy_data(self, days_back: int = 30):
        """Migrate energy data from files to InfluxDB"""
        logger.info(f"Starting energy data migration for last {days_back} days")
        
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        # Get data from file storage
        file_data = await self.file_storage.get_energy_data(start_time, end_time)
        
        # Migrate to InfluxDB
        migrated_count = 0
        for data_point in file_data:
            if await self.influx_storage.store_energy_data(data_point):
                migrated_count += 1
        
        logger.info(f"Migrated {migrated_count} energy data points to InfluxDB")
        return migrated_count
    
    async def migrate_charging_sessions(self):
        """Migrate charging session data to PostgreSQL"""
        logger.info("Starting charging session migration")
        
        # Load existing session data from JSON files
        sessions_data = self._load_existing_sessions()
        
        migrated_count = 0
        for session in sessions_data:
            if await self.postgres_storage.store_charging_session(session):
                migrated_count += 1
        
        logger.info(f"Migrated {migrated_count} charging sessions to PostgreSQL")
        return migrated_count
    
    def _load_existing_sessions(self) -> List[Dict]:
        """Load existing charging session data"""
        sessions = []
        
        # Load from battery selling analytics
        analytics_file = Path("out/battery_selling_analytics/session_records.json")
        if analytics_file.exists():
            with open(analytics_file, 'r') as f:
                data = json.load(f)
                for record in data:
                    sessions.append({
                        'session_id': record['session_id'],
                        'start_time': record['start_time'],
                        'end_time': record['end_time'],
                        'battery_soc_start': record['start_soc'],
                        'battery_soc_end': record['end_soc'],
                        'energy_charged_kwh': record['energy_sold_kwh'],
                        'average_price_pln': record['average_price_pln'],
                        'total_cost_pln': record['revenue_pln'],
                        'status': 'completed'
                    })
        
        return sessions

async def main():
    """Main migration function"""
    migration_tool = DataMigrationTool("config/master_coordinator_config.yaml")
    
    # Migrate energy data
    await migration_tool.migrate_energy_data(days_back=30)
    
    # Migrate charging sessions
    await migration_tool.migrate_charging_sessions()
    
    logger.info("Data migration completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
```

### **Task 3.2: Update Master Coordinator**
**Priority**: High  
**Estimated Time**: 4-5 hours  
**Dependencies**: Task 3.1  

#### **3.2.1: Modify Master Coordinator for Dual Storage**
```python
# Update src/master_coordinator.py
class MasterCoordinator:
    def __init__(self, config_path: str):
        # ... existing initialization ...
        
        # Initialize storage systems
        self.storage_systems = self._initialize_storage_systems()
    
    def _initialize_storage_systems(self) -> List[DataStorageInterface]:
        """Initialize all storage systems"""
        storage_systems = []
        storage_config = self.config.get('data_storage', {})
        
        # File storage (current system)
        if storage_config.get('file_storage', {}).get('enabled', True):
            storage_systems.append(FileStorage(storage_config['file_storage']))
        
        # Database storage (new system)
        if storage_config.get('database_storage', {}).get('enabled', False):
            db_config = storage_config['database_storage']
            
            # Time-series database
            if db_config.get('timeseries_db', {}).get('enabled', False):
                storage_systems.append(InfluxDBStorage(db_config['timeseries_db']))
            
            # Relational database
            if db_config.get('relational_db', {}).get('enabled', False):
                storage_systems.append(PostgreSQLStorage(db_config['relational_db']))
        
        return storage_systems
    
    async def _collect_system_data(self):
        """Collect comprehensive system data and store in all systems"""
        try:
            # ... existing data collection ...
            
            # Store data in all configured storage systems
            for storage in self.storage_systems:
                try:
                    if hasattr(storage, 'store_energy_data'):
                        await storage.store_energy_data(self.current_data)
                except Exception as e:
                    logger.error(f"Failed to store data in {type(storage).__name__}: {e}")
            
            # ... rest of existing method ...
```

---

## 📈 **Phase 4: Advanced Features (Week 7-8)**

### **Task 4.1: Data Analytics and Reporting**
**Priority**: Medium  
**Estimated Time**: 8-10 hours  
**Dependencies**: Phase 3 completion  

#### **4.1.1: Create Analytics Module**
```python
# src/analytics/energy_analytics.py
from typing import Dict, List, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

class EnergyAnalytics:
    """Advanced analytics for energy data"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
    
    async def generate_daily_report(self, date: datetime) -> Dict[str, Any]:
        """Generate daily energy report"""
        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        
        # Get energy data for the day
        energy_data = await self.storage.get_energy_data(start_time, end_time)
        
        if not energy_data:
            return {"error": "No data available for the specified date"}
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(energy_data)
        
        # Calculate daily statistics
        report = {
            "date": date.strftime("%Y-%m-%d"),
            "total_pv_production_kwh": df['pv_power_kw'].sum() / 60,  # Convert to kWh
            "total_consumption_kwh": df['consumption_kw'].sum() / 60,
            "average_battery_soc": df['battery_soc'].mean(),
            "peak_pv_power_kw": df['pv_power_kw'].max(),
            "peak_consumption_kw": df['consumption_kw'].max(),
            "grid_export_kwh": df[df['grid_power_kw'] < 0]['grid_power_kw'].sum() / 60,
            "grid_import_kwh": df[df['grid_power_kw'] > 0]['grid_power_kw'].sum() / 60,
            "data_points": len(df)
        }
        
        return report
    
    async def generate_trend_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Generate trend analysis for specified period"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        energy_data = await self.storage.get_energy_data(start_time, end_time)
        
        if not energy_data:
            return {"error": "No data available for trend analysis"}
        
        df = pd.DataFrame(energy_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Daily aggregation
        daily_stats = df.resample('D').agg({
            'pv_power_kw': 'sum',
            'consumption_kw': 'sum',
            'battery_soc': 'mean',
            'grid_power_kw': 'sum'
        })
        
        # Calculate trends
        trends = {
            "period_days": days,
            "average_daily_pv_kwh": (daily_stats['pv_power_kw'] / 60).mean(),
            "average_daily_consumption_kwh": (daily_stats['consumption_kw'] / 60).mean(),
            "average_battery_soc": daily_stats['battery_soc'].mean(),
            "pv_trend": self._calculate_trend(daily_stats['pv_power_kw']),
            "consumption_trend": self._calculate_trend(daily_stats['consumption_kw']),
            "battery_trend": self._calculate_trend(daily_stats['battery_soc'])
        }
        
        return trends
    
    def _calculate_trend(self, series: pd.Series) -> str:
        """Calculate trend direction for a time series"""
        if len(series) < 2:
            return "insufficient_data"
        
        # Simple linear trend calculation
        x = np.arange(len(series))
        y = series.values
        slope = np.polyfit(x, y, 1)[0]
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"
```

### **Task 4.2: Performance Monitoring**
**Priority**: Medium  
**Estimated Time**: 4-6 hours  
**Dependencies**: Task 4.1  

#### **4.2.1: Create Performance Monitor**
```python
# src/monitoring/storage_monitor.py
import time
from typing import Dict, Any
from datetime import datetime, timedelta
import psutil

class StoragePerformanceMonitor:
    """Monitor storage system performance"""
    
    def __init__(self, storage_systems: List[DataStorageInterface]):
        self.storage_systems = storage_systems
        self.metrics = []
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect performance metrics for all storage systems"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": self._get_system_metrics(),
            "storage_metrics": []
        }
        
        for storage in self.storage_systems:
            storage_metrics = await self._get_storage_metrics(storage)
            metrics["storage_metrics"].append(storage_metrics)
        
        self.metrics.append(metrics)
        
        # Keep only last 1000 metrics
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
        
        return metrics
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system-level metrics"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage_percent": psutil.disk_usage('/').percent,
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
    
    async def _get_storage_metrics(self, storage: DataStorageInterface) -> Dict[str, Any]:
        """Get storage-specific metrics"""
        start_time = time.time()
        
        try:
            # Test storage health
            health = await storage.health_check()
            
            # Measure response time
            response_time = time.time() - start_time
            
            return {
                "storage_type": type(storage).__name__,
                "health": health,
                "response_time_ms": response_time * 1000,
                "status": "healthy" if health.get("status") == "ok" else "unhealthy"
            }
            
        except Exception as e:
            return {
                "storage_type": type(storage).__name__,
                "health": {"status": "error", "message": str(e)},
                "response_time_ms": (time.time() - start_time) * 1000,
                "status": "error"
            }
```

---

## 🧪 **Testing and Validation**

### **Task 5.1: Create Test Suite**
**Priority**: High  
**Estimated Time**: 6-8 hours  
**Dependencies**: All previous phases  

#### **5.1.1: Storage Integration Tests**
```python
# test/test_storage_integration.py
import pytest
import asyncio
from datetime import datetime, timedelta
from src.data_storage.file_storage import FileStorage
from src.data_storage.influxdb_storage import InfluxDBStorage
from src.data_storage.postgresql_storage import PostgreSQLStorage

class TestStorageIntegration:
    """Test storage system integration"""
    
    @pytest.fixture
    def sample_energy_data(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "battery": {
                "soc_percent": 75,
                "temperature_c": 45
            },
            "photovoltaic": {
                "current_power_kw": 5.2
            },
            "grid": {
                "current_power_kw": -1.5
            },
            "house_consumption": {
                "current_power_kw": 3.7
            }
        }
    
    @pytest.mark.asyncio
    async def test_file_storage(self, sample_energy_data):
        """Test file storage functionality"""
        config = {
            "energy_data_dir": "test_data",
            "compression": True,
            "retention_days": 1
        }
        
        storage = FileStorage(config)
        
        # Test storing data
        result = await storage.store_energy_data(sample_energy_data)
        assert result is True
        
        # Test retrieving data
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        data = await storage.get_energy_data(start_time, end_time)
        assert len(data) > 0
    
    @pytest.mark.asyncio
    async def test_influxdb_storage(self, sample_energy_data):
        """Test InfluxDB storage functionality"""
        config = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket"
        }
        
        # Skip if InfluxDB not available
        try:
            storage = InfluxDBStorage(config)
            result = await storage.store_energy_data(sample_energy_data)
            assert result is True
        except Exception:
            pytest.skip("InfluxDB not available")
    
    @pytest.mark.asyncio
    async def test_postgresql_storage(self):
        """Test PostgreSQL storage functionality"""
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "username": "test_user",
            "password": "test_password"
        }
        
        # Skip if PostgreSQL not available
        try:
            storage = PostgreSQLStorage(config)
            session_data = {
                "session_id": "test_session_001",
                "start_time": datetime.now(),
                "battery_soc_start": 50,
                "status": "active"
            }
            result = await storage.store_charging_session(session_data)
            assert result is True
        except Exception:
            pytest.skip("PostgreSQL not available")
```

---

## 📋 **Implementation Checklist**

### **Phase 1: Foundation (Week 1-2)**
- [ ] **1.1**: Choose database stack (InfluxDB + SQLite recommended)
- [ ] **1.2**: Update Docker Compose configuration
- [ ] **1.3**: Create data storage interface
- [ ] **1.4**: Implement file storage with compression
- [ ] **1.5**: Update enhanced data collector
- [ ] **1.6**: Test file storage functionality

### **Phase 2: Database Integration (Week 3-4)**
- [ ] **2.1**: Install database dependencies
- [ ] **2.2**: Create InfluxDB storage implementation
- [ ] **2.3**: Create PostgreSQL storage implementation
- [ ] **2.4**: Create database schemas
- [ ] **2.5**: Test database connections
- [ ] **2.6**: Implement health checks

### **Phase 3: Migration and Testing (Week 5-6)**
- [ ] **3.1**: Create data migration tool
- [ ] **3.2**: Migrate existing data
- [ ] **3.3**: Update master coordinator for dual storage
- [ ] **3.4**: Create comprehensive test suite
- [ ] **3.5**: Validate data integrity
- [ ] **3.6**: Performance testing

### **Phase 4: Advanced Features (Week 7-8)**
- [ ] **4.1**: Create analytics module
- [ ] **4.2**: Implement performance monitoring
- [ ] **4.3**: Create reporting system
- [ ] **4.4**: Add data archival features
- [ ] **4.5**: Implement backup procedures
- [ ] **4.6**: Create monitoring dashboard

---

## 🚀 **Quick Start Commands**

### **1. Start with File Storage Enhancement**
```bash
# Update configuration
cp config/master_coordinator_config.yaml config/master_coordinator_config.yaml.backup

# Add new storage configuration
# (Edit config file to add data_storage section)

# Test the enhanced file storage
python -m src.enhanced_data_collector --test-storage
```

### **2. Add Database Storage**
```bash
# Start databases with Docker
docker-compose up -d influxdb postgresql

# Run migration
python scripts/migrate_data.py

# Test database connections
python -m src.data_storage.test_connections
```

### **3. Enable Dual Storage**
```bash
# Update configuration to enable both storage systems
# (Edit config file to enable database_storage)

# Restart master coordinator
./scripts/docker_manage.sh restart

# Monitor storage performance
python -m src.monitoring.storage_monitor
```

---

## 📞 **Support and Maintenance**

### **Regular Maintenance Tasks**
- **Daily**: Check storage health and performance
- **Weekly**: Review data quality and completeness
- **Monthly**: Analyze storage usage and optimize
- **Quarterly**: Review and update retention policies

### **Troubleshooting Guide**
- **Connection Issues**: Check database connectivity and credentials
- **Performance Issues**: Monitor query performance and optimize
- **Data Quality**: Validate data integrity and completeness
- **Storage Space**: Monitor disk usage and cleanup old data

---

**Document Status**: Ready for Implementation  
**Next Steps**: Begin with Phase 1 (Foundation Setup)  
**Estimated Total Time**: 6-8 weeks for full implementation  

---

*This roadmap provides a practical, step-by-step approach to implementing advanced historic data storage. Each phase can be implemented independently, allowing for gradual migration and testing.*
