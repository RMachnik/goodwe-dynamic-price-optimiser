# 📊 Historic Data Storage Implementation Plan
## GoodWe Dynamic Price Optimiser - Enhanced Data Persistence Strategy

**Document Version**: 1.0  
**Created**: 2025-01-09  
**Status**: Planning Phase  

---

## 🎯 **Executive Summary**

This document outlines a comprehensive plan for implementing advanced historic data storage solutions for the GoodWe Dynamic Price Optimiser system. The current file-based JSON storage approach will be enhanced with time-series databases, relational databases, and cloud storage solutions to support long-term data retention, advanced analytics, and improved system performance.

---

## 📋 **Current State Analysis**

### **Existing Data Storage Patterns**
1. **In-Memory Storage**: Limited to 24 hours (1440 data points)
2. **JSON Files**: Basic persistence in `out/` directory
3. **Log Files**: Operational data and debugging information
4. **Coordinator State**: System state snapshots

### **Current Limitations**
- ❌ **Data Loss Risk**: In-memory data lost on system restart
- ❌ **Limited Retention**: Only 24 hours of historical data
- ❌ **Poor Query Performance**: No indexing or optimized queries
- ❌ **Storage Inefficiency**: JSON files with redundant data
- ❌ **No Analytics Support**: Limited data analysis capabilities
- ❌ **No Backup Strategy**: No automated backup or recovery

---

## 🚀 **Implementation Plan Overview**

### **Phase 1: Foundation & Architecture (Weeks 1-2)**
- Database schema design and selection
- Data abstraction layer implementation
- Migration tools for existing data
- Configuration management updates

### **Phase 2: Time-Series Database Integration (Weeks 3-4)**
- InfluxDB/TimescaleDB setup and configuration
- Energy data migration and storage
- Real-time data ingestion pipeline
- Query optimization and indexing

### **Phase 3: Relational Database Integration (Weeks 5-6)**
- PostgreSQL/SQLite setup for structured data
- Session and configuration data migration
- Data relationships and constraints
- Backup and recovery procedures

### **Phase 4: Advanced Features (Weeks 7-8)**
- Data compression and archival
- Cloud storage integration
- Analytics and reporting tools
- Performance monitoring and alerting

---

## 🏗️ **Detailed Implementation Plan**

### **1. Database Architecture Design**

#### **1.1 Time-Series Database (Primary)**
**Technology**: InfluxDB 2.0 or TimescaleDB  
**Purpose**: High-frequency energy data storage  
**Data Types**:
- Battery SoC, temperature, charging status
- PV production (current power, daily totals)
- Grid flow (import/export power)
- House consumption patterns
- Electricity pricing data
- Weather data (temperature, irradiance)

**Schema Design**:
```yaml
measurements:
  - energy_data:
      tags: [device_id, data_source, location]
      fields: [battery_soc, battery_temp, pv_power, grid_power, consumption, price]
      timestamp: auto
  - weather_data:
      tags: [location, source]
      fields: [temperature, humidity, irradiance, wind_speed]
      timestamp: auto
  - system_metrics:
      tags: [component, status]
      fields: [cpu_usage, memory_usage, response_time]
      timestamp: auto
```

#### **1.2 Relational Database (Secondary)**
**Technology**: PostgreSQL or SQLite  
**Purpose**: Structured data and relationships  
**Data Types**:
- Charging sessions and schedules
- System configurations
- User preferences and settings
- Analytics reports and summaries
- Alert definitions and history

**Schema Design**:
```sql
-- Charging Sessions
CREATE TABLE charging_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    battery_soc_start INTEGER,
    battery_soc_end INTEGER,
    energy_charged_kwh DECIMAL(10,3),
    average_price_pln DECIMAL(10,4),
    total_cost_pln DECIMAL(10,2),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- System Configurations
CREATE TABLE system_configs (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100),
    config_data JSONB,
    version VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Analytics Reports
CREATE TABLE analytics_reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(50),
    report_date DATE,
    report_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### **2. Data Abstraction Layer**

#### **2.1 Storage Interface Design**
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

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
```

#### **2.2 Implementation Classes**
```python
class InfluxDBStorage(DataStorageInterface):
    """InfluxDB implementation for time-series data"""
    
    def __init__(self, config: Dict[str, Any]):
        self.client = InfluxDBClient(
            url=config['url'],
            token=config['token'],
            org=config['org']
        )
        self.bucket = config['bucket']
    
    async def store_energy_data(self, data: Dict[str, Any]) -> bool:
        # Implementation for storing energy data in InfluxDB
        pass

class PostgreSQLStorage(DataStorageInterface):
    """PostgreSQL implementation for relational data"""
    
    def __init__(self, config: Dict[str, Any]):
        self.connection = psycopg2.connect(**config)
    
    async def store_charging_session(self, session_data: Dict[str, Any]) -> bool:
        # Implementation for storing session data in PostgreSQL
        pass
```

### **3. Configuration Management Updates**

#### **3.1 Enhanced Configuration Schema**
```yaml
# Add to master_coordinator_config.yaml
data_storage:
  # Time-series database configuration
  timeseries_db:
    enabled: true
    type: "influxdb"  # or "timescaledb"
    config:
      url: "http://localhost:8086"
      token: "${INFLUXDB_TOKEN}"
      org: "goodwe-energy"
      bucket: "energy_data"
      retention_policy: "30d"  # 30 days retention
    
  # Relational database configuration
  relational_db:
    enabled: true
    type: "postgresql"  # or "sqlite"
    config:
      host: "localhost"
      port: 5432
      database: "goodwe_energy"
      username: "${DB_USERNAME}"
      password: "${DB_PASSWORD}"
      ssl_mode: "prefer"
    
  # Data archival configuration
  archival:
    enabled: true
    strategy: "tiered"  # hot, warm, cold storage
    hot_retention_days: 7
    warm_retention_days: 90
    cold_retention_days: 365
    cloud_storage:
      provider: "aws_s3"  # or "gcp", "azure"
      bucket: "goodwe-energy-archive"
      region: "eu-central-1"
    
  # Backup configuration
  backup:
    enabled: true
    interval_hours: 24
    retention_days: 30
    compression: true
    encryption: true
```

### **4. Migration Strategy**

#### **4.1 Data Migration Tools**
```python
class DataMigrationTool:
    """Tool for migrating existing data to new storage systems"""
    
    def __init__(self, source_dir: str, target_storage: DataStorageInterface):
        self.source_dir = Path(source_dir)
        self.target_storage = target_storage
    
    async def migrate_energy_data(self):
        """Migrate JSON energy data files to time-series database"""
        # Implementation for migrating existing JSON files
        pass
    
    async def migrate_charging_sessions(self):
        """Migrate charging session data to relational database"""
        # Implementation for migrating session data
        pass
    
    async def validate_migration(self):
        """Validate that all data was migrated correctly"""
        # Implementation for data validation
        pass
```

#### **4.2 Migration Steps**
1. **Backup Existing Data**: Create full backup of current data
2. **Setup New Databases**: Install and configure InfluxDB/PostgreSQL
3. **Run Migration Tool**: Migrate historical data
4. **Validate Data**: Ensure data integrity
5. **Update Application**: Switch to new storage layer
6. **Monitor Performance**: Ensure system stability

### **5. Performance Optimization**

#### **5.1 Data Compression**
```python
class DataCompression:
    """Data compression utilities for efficient storage"""
    
    @staticmethod
    def compress_energy_data(data: List[Dict]) -> bytes:
        """Compress energy data using gzip"""
        json_data = json.dumps(data).encode('utf-8')
        return gzip.compress(json_data)
    
    @staticmethod
    def decompress_energy_data(compressed_data: bytes) -> List[Dict]:
        """Decompress energy data"""
        json_data = gzip.decompress(compressed_data)
        return json.loads(json_data.decode('utf-8'))
```

#### **5.2 Query Optimization**
```python
class QueryOptimizer:
    """Query optimization for time-series data"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
    
    async def get_aggregated_data(self, 
                                start_time: datetime,
                                end_time: datetime,
                                aggregation: str = "1h") -> List[Dict]:
        """Get aggregated data for better performance"""
        # Implementation for data aggregation
        pass
    
    async def get_trend_data(self, 
                           metric: str,
                           days: int = 30) -> List[Dict]:
        """Get trend data for analytics"""
        # Implementation for trend analysis
        pass
```

### **6. Monitoring and Alerting**

#### **6.1 Data Quality Monitoring**
```python
class DataQualityMonitor:
    """Monitor data quality and integrity"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
    
    async def check_data_completeness(self) -> Dict[str, Any]:
        """Check for missing or incomplete data"""
        # Implementation for data completeness checks
        pass
    
    async def check_data_consistency(self) -> Dict[str, Any]:
        """Check for data consistency issues"""
        # Implementation for data consistency checks
        pass
    
    async def generate_quality_report(self) -> Dict[str, Any]:
        """Generate data quality report"""
        # Implementation for quality reporting
        pass
```

#### **6.2 Performance Monitoring**
```python
class StoragePerformanceMonitor:
    """Monitor storage system performance"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
    
    async def get_storage_metrics(self) -> Dict[str, Any]:
        """Get storage system metrics"""
        # Implementation for storage metrics
        pass
    
    async def check_storage_health(self) -> Dict[str, Any]:
        """Check storage system health"""
        # Implementation for health checks
        pass
```

### **7. API and Integration**

#### **7.1 Data Access API**
```python
class DataAccessAPI:
    """REST API for data access"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
        self.app = FastAPI()
        self._setup_routes()
    
    def _setup_routes(self):
        @self.app.get("/api/energy-data")
        async def get_energy_data(
            start_time: datetime,
            end_time: datetime,
            device_id: Optional[str] = None
        ):
            return await self.storage.get_energy_data(
                start_time, end_time, device_id
            )
        
        @self.app.get("/api/charging-sessions")
        async def get_charging_sessions(
            start_date: datetime,
            end_date: datetime
        ):
            return await self.storage.get_charging_sessions(
                start_date, end_date
            )
```

#### **7.2 WebSocket Real-time Updates**
```python
class RealtimeDataStream:
    """WebSocket for real-time data streaming"""
    
    def __init__(self, storage: DataStorageInterface):
        self.storage = storage
        self.connections = set()
    
    async def broadcast_energy_data(self, data: Dict[str, Any]):
        """Broadcast energy data to connected clients"""
        # Implementation for real-time broadcasting
        pass
```

---

## 📊 **Implementation Timeline**

### **Week 1-2: Foundation**
- [ ] **1.1**: Database selection and setup
- [ ] **1.2**: Data abstraction layer implementation
- [ ] **1.3**: Configuration schema updates
- [ ] **1.4**: Basic migration tools

### **Week 3-4: Time-Series Integration**
- [ ] **2.1**: InfluxDB/TimescaleDB setup
- [ ] **2.2**: Energy data migration
- [ ] **2.3**: Real-time ingestion pipeline
- [ ] **2.4**: Query optimization

### **Week 5-6: Relational Integration**
- [ ] **3.1**: PostgreSQL/SQLite setup
- [ ] **3.2**: Session data migration
- [ ] **3.3**: Data relationships
- [ ] **3.4**: Backup procedures

### **Week 7-8: Advanced Features**
- [ ] **4.1**: Data compression
- [ ] **4.2**: Cloud storage integration
- [ ] **4.3**: Analytics tools
- [ ] **4.4**: Performance monitoring

---

## 🔧 **Technical Requirements**

### **Hardware Requirements**
- **CPU**: 2+ cores (4+ recommended)
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 50GB+ for databases (100GB+ recommended)
- **Network**: Stable internet for cloud integration

### **Software Requirements**
- **Database**: InfluxDB 2.0+ or TimescaleDB 2.0+
- **Database**: PostgreSQL 13+ or SQLite 3.35+
- **Python**: 3.9+ with required packages
- **Docker**: 20.10+ (for containerized deployment)

### **Dependencies**
```txt
# Time-series database
influxdb-client>=1.30.0
# or
timescaledb-api>=0.1.0

# Relational database
psycopg2-binary>=2.9.0
# or
sqlite3 (built-in)

# Data processing
pandas>=1.5.0
numpy>=1.24.0
pydantic>=1.10.0

# API framework
fastapi>=0.95.0
uvicorn>=0.20.0
websockets>=11.0.0

# Cloud storage
boto3>=1.26.0  # AWS S3
# or
google-cloud-storage>=2.7.0  # GCP
# or
azure-storage-blob>=12.14.0  # Azure
```

---

## 📈 **Expected Benefits**

### **Performance Improvements**
- ✅ **Query Speed**: 10-100x faster data queries
- ✅ **Storage Efficiency**: 50-80% reduction in storage space
- ✅ **Memory Usage**: 70% reduction in memory consumption
- ✅ **Data Retention**: Years of historical data vs. 24 hours

### **Functional Improvements**
- ✅ **Advanced Analytics**: Complex data analysis capabilities
- ✅ **Real-time Monitoring**: Live data streaming and alerts
- ✅ **Data Integrity**: ACID compliance and data validation
- ✅ **Scalability**: Support for multiple devices and locations

### **Operational Improvements**
- ✅ **Automated Backups**: Scheduled and automated data protection
- ✅ **Disaster Recovery**: Point-in-time recovery capabilities
- ✅ **Monitoring**: Comprehensive system health monitoring
- ✅ **Maintenance**: Automated data archival and cleanup

---

## 🚨 **Risk Mitigation**

### **Technical Risks**
- **Database Migration**: Risk of data loss during migration
  - *Mitigation*: Comprehensive backup and validation procedures
- **Performance Impact**: Potential system slowdown during implementation
  - *Mitigation*: Gradual rollout and performance monitoring
- **Data Corruption**: Risk of data integrity issues
  - *Mitigation*: Data validation and consistency checks

### **Operational Risks**
- **Downtime**: System unavailability during implementation
  - *Mitigation*: Blue-green deployment strategy
- **Learning Curve**: Team training on new technologies
  - *Mitigation*: Comprehensive documentation and training
- **Cost Increase**: Additional infrastructure costs
  - *Mitigation*: Cost-benefit analysis and optimization

---

## 📚 **Documentation and Training**

### **Technical Documentation**
- [ ] Database schema documentation
- [ ] API reference documentation
- [ ] Migration procedures
- [ ] Troubleshooting guides
- [ ] Performance tuning guides

### **User Training**
- [ ] System administrator training
- [ ] Data analyst training
- [ ] Developer training
- [ ] End-user training

---

## 🎯 **Success Metrics**

### **Performance Metrics**
- Data query response time < 100ms
- Data ingestion rate > 1000 points/second
- Storage efficiency > 80% compression
- System uptime > 99.9%

### **Functional Metrics**
- Data retention period > 1 year
- Data completeness > 99%
- Data accuracy > 99.9%
- Backup success rate > 99%

### **Business Metrics**
- Reduced operational costs
- Improved system reliability
- Enhanced analytics capabilities
- Better decision-making support

---

## 📞 **Next Steps**

1. **Review and Approve Plan**: Stakeholder review and approval
2. **Resource Allocation**: Assign team members and budget
3. **Environment Setup**: Prepare development and testing environments
4. **Implementation Start**: Begin with Phase 1 (Foundation)
5. **Regular Reviews**: Weekly progress reviews and adjustments

---

**Document Status**: Ready for Review  
**Next Review Date**: 2025-01-16  
**Approval Required**: System Architect, Project Manager  

---

*This document will be updated as the implementation progresses and requirements evolve.*
