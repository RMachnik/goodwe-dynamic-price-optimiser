# Database Rollout Playbook

## Overview

This playbook guides you through safely enabling the SQLite database storage feature for the GoodWe Dynamic Price Optimiser. The system uses a **composite mode** (dual-write) that writes to both database AND JSON files, ensuring zero data loss during transition.

**Current Status**: Ready for Production  
**Risk Level**: Low (composite mode provides automatic fallback)  
**Estimated Time**: 30 minutes initial deployment + 24-48h monitoring

---

## Architecture

```
┌─────────────────────┐
│  MasterCoordinator  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   StorageFactory    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│        CompositeStorage             │
│  (writes to BOTH, reads from DB)    │
└──────────┬──────────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐  ┌─────────┐
│ SQLite  │  │  JSON   │
│   DB    │  │  Files  │
│(primary)│  │(backup) │
└─────────┘  └─────────┘
```

---

## Pre-Requisites

### System Requirements
- Python 3.10+ with `aiosqlite` package
- 1GB+ free disk space for database
- Write access to data directory

### Files Involved
| File | Purpose |
|------|---------|
| `config/master_coordinator_config.yaml` | Storage configuration |
| `src/database/sqlite_storage.py` | SQLite implementation |
| `src/database/composite_storage.py` | Dual-write logic |
| `src/database/storage_factory.py` | Storage mode selection |
| `scripts/database_rollout.sh` | Rollout automation script |

---

## Quick Start

```bash
# 1. Run all pre-flight checks
./scripts/database_rollout.sh preflight

# 2. Create backup
./scripts/database_rollout.sh backup

# 3. Deploy (restarts service)
./scripts/database_rollout.sh deploy

# 4. Verify it's working
./scripts/database_rollout.sh verify

# 5. Get monitoring commands
./scripts/database_rollout.sh monitor
```

---

## Detailed Rollout Steps

### Phase 1: Pre-Flight Checks (15 minutes)

#### 1.1 Verify Data Directory

```bash
# Create directory if needed
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser/data

# Set ownership
sudo chown -R $(whoami):$(whoami) /opt/goodwe-dynamic-price-optimiser/data

# Verify permissions
ls -la /opt/goodwe-dynamic-price-optimiser/data
```

#### 1.2 Check Disk Space

```bash
df -h /opt/goodwe-dynamic-price-optimiser/data
# Recommend: 1GB+ free
```

#### 1.3 Test Database Write

```bash
python3 -c "
import sqlite3, os
db = '/opt/goodwe-dynamic-price-optimiser/data/test.db'
conn = sqlite3.connect(db)
conn.execute('CREATE TABLE test (id INTEGER)')
conn.close()
os.remove(db)
print('Database write test: PASSED')
"
```

#### 1.4 Verify Configuration

```bash
# Check database is enabled
grep -A5 "database_storage:" config/master_coordinator_config.yaml
```

Expected output:
```yaml
database_storage:
  enabled: true
  sqlite:
    path: "/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db"
```

#### 1.5 Run Automated Pre-Flight

```bash
./scripts/database_rollout.sh preflight
```

---

### Phase 2: Backup (5 minutes)

```bash
# Create timestamped backup
./scripts/database_rollout.sh backup

# Or manually:
cd /opt/goodwe-dynamic-price-optimiser
tar -czvf ~/backup_$(date +%Y%m%d_%H%M%S).tar.gz out/ data/
```

---

### Phase 3: Deploy (10 minutes)

#### Docker Deployment

```bash
cd /opt/goodwe-dynamic-price-optimiser
docker-compose down
docker-compose up -d --build
```

#### Systemd Deployment

```bash
sudo systemctl restart goodwe-master-coordinator
```

#### Manual Deployment

```bash
# Stop current process
pkill -f master_coordinator

# Start with new config
./run_master_coordinator.sh &
```

---

### Phase 4: Verification (10 minutes)

#### 4.1 Check Database Created

```bash
ls -lh /opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db
```

#### 4.2 Check Logs for Initialization

```bash
grep -i "storage\|sqlite\|database" logs/master_coordinator.log | tail -10
```

Expected:
```
Storage layer initialized for LogWebServer
Connected to SQLite database at /opt/.../goodwe_energy.db (pool_size=5)
```

#### 4.3 Check Data Being Written

```bash
# Wait 5 minutes, then check
sqlite3 data/goodwe_energy.db "SELECT COUNT(*) FROM energy_data;"
sqlite3 data/goodwe_energy.db "SELECT COUNT(*) FROM system_state;"
sqlite3 data/goodwe_energy.db "SELECT COUNT(*) FROM coordinator_decisions;"
```

#### 4.4 Run Automated Verification

```bash
./scripts/database_rollout.sh verify
```

---

### Phase 5: Monitoring (24-48 hours)

#### Key Metrics to Watch

| Metric | Command | Expected |
|--------|---------|----------|
| DB file size | `ls -lh data/*.db` | Growing (MB/day) |
| Write errors | `grep "Error saving" logs/*.log \| wc -l` | 0 |
| Connection failures | `grep "Failed to connect" logs/*.log \| wc -l` | 0 |
| Retry warnings | `grep "retrying" logs/*.log \| wc -l` | Few OK |
| JSON files | `ls out/energy_data/` | Still being created |

#### Monitoring Commands

```bash
# Watch database size
watch -n 60 'ls -lh data/goodwe_energy.db'

# Check for errors
grep -i "error.*storage\|failed.*connect" logs/master_coordinator.log | tail -20

# Check data counts
sqlite3 data/goodwe_energy.db '
  SELECT "energy_data:", COUNT(*) FROM energy_data
  UNION ALL
  SELECT "system_state:", COUNT(*) FROM system_state
  UNION ALL  
  SELECT "decisions:", COUNT(*) FROM coordinator_decisions;
'

# Check latest timestamp
sqlite3 data/goodwe_energy.db 'SELECT MAX(timestamp) FROM energy_data;'

# Check database integrity
sqlite3 data/goodwe_energy.db 'PRAGMA integrity_check;'

# Check WAL mode enabled
sqlite3 data/goodwe_energy.db 'PRAGMA journal_mode;'
# Expected: wal
```

---

## Rollback Procedure

### Quick Rollback (< 5 minutes)

```bash
./scripts/database_rollout.sh rollback
```

### Manual Rollback

```bash
# 1. Edit config to disable database
sed -i 's/enabled: true/enabled: false/' config/master_coordinator_config.yaml

# 2. Restart service
sudo systemctl restart goodwe-master-coordinator
# OR
docker-compose restart
```

### Full Rollback with Data Restore

```bash
# 1. Stop service
sudo systemctl stop goodwe-master-coordinator

# 2. Restore from backup
tar -xzvf ~/backup_*.tar.gz -C /opt/goodwe-dynamic-price-optimiser/

# 3. Disable database in config
# Edit config/master_coordinator_config.yaml:
#   database_storage:
#     enabled: false

# 4. Restart
sudo systemctl start goodwe-master-coordinator
```

---

## Rollback Triggers

Execute rollback if ANY of these occur:

| Condition | Action |
|-----------|--------|
| ❌ Database file not created after 10 min | Rollback |
| ❌ Continuous retry warnings (>10/hour) | Investigate, consider rollback |
| ❌ Storage errors blocking charging decisions | Immediate rollback |
| ❌ Dashboard showing no data | Check logs, consider rollback |
| ❌ System crashes or hangs | Immediate rollback |

---

## Post-Rollout Tasks

### After 24 Hours Stable

1. **Migrate historical data** (optional):
   ```bash
   ./scripts/database_rollout.sh migrate
   # OR
   python scripts/migrate_json_to_db.py
   ```

2. **Verify migration**:
   ```bash
   sqlite3 data/goodwe_energy.db "SELECT MIN(timestamp), MAX(timestamp) FROM energy_data;"
   ```

### After 7 Days Stable

Consider transitioning to **database-only mode**:

```yaml
# config/master_coordinator_config.yaml
data_storage:
  file_storage:
    enabled: false  # Disable file storage
  database_storage:
    enabled: true   # Keep database
```

⚠️ **Warning**: Only do this after:
- 7+ days of successful composite operation
- Verified backup strategy works
- Confirmed all data is in database

---

## Troubleshooting

### Database File Not Created

```bash
# Check directory permissions
ls -la /opt/goodwe-dynamic-price-optimiser/data/

# Check logs for errors
grep -i "error\|failed" logs/master_coordinator.log | grep -i storage

# Test manual creation
python3 -c "import sqlite3; sqlite3.connect('data/test.db')"
```

### "Database is locked" Errors

```bash
# Check for multiple processes
ps aux | grep coordinator

# Check WAL mode
sqlite3 data/goodwe_energy.db 'PRAGMA journal_mode;'
# Should be: wal

# Increase busy timeout (in config)
# sqlite.timeout: 30.0
```

### No Data in Database

```bash
# Check if composite storage is working
grep "CompositeStorage\|_write_to_all" logs/master_coordinator.log

# Check if primary (DB) or secondary (file) succeeded
grep "Primary.*failed\|secondary succeeded" logs/master_coordinator.log
```

### Dashboard Not Showing Data

```bash
# Check LogWebServer storage connection
grep "Storage layer initialized\|_storage_connected" logs/master_coordinator.log

# Test storage query manually
python3 -c "
import asyncio
from database.storage_factory import StorageFactory

async def test():
    storage = StorageFactory.create_storage({})
    await storage.connect()
    states = await storage.get_system_state(limit=5)
    print(f'Got {len(states)} states')

asyncio.run(test())
"
```

---

## Configuration Reference

### Full Storage Configuration

```yaml
# config/master_coordinator_config.yaml

data_storage:
  # File storage (legacy JSON files)
  file_storage:
    enabled: true
    energy_data_dir: "/opt/goodwe-dynamic-price-optimiser/out/energy_data"
    state_dir: "/opt/goodwe-dynamic-price-optimiser/out"
    retention_days: 7
  
  # Database storage (SQLite)
  database_storage:
    enabled: true
    sqlite:
      path: "/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db"
      connection_pool_size: 5
      timeout: 30.0
      max_retries: 3
      retry_delay: 0.1
```

### Storage Modes

| file_storage | database_storage | Mode | Use Case |
|--------------|------------------|------|----------|
| `true` | `false` | File only | Legacy, rollback |
| `true` | `true` | **Composite** | Transition (recommended) |
| `false` | `true` | DB only | Production (after validation) |

---

## Database Schema

### Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `energy_data` | Energy readings | timestamp, battery_soc, pv_power, grid_power |
| `system_state` | Coordinator state | timestamp, state, uptime, active_modules |
| `coordinator_decisions` | Charging decisions | timestamp, decision_type, action, reason |
| `charging_sessions` | Charging sessions | session_id, start_time, end_time, energy_kwh |
| `battery_selling_sessions` | Selling sessions | session_id, start_time, revenue_pln |
| `weather_data` | Weather observations | timestamp, temperature, cloud_cover |
| `price_forecasts` | Price predictions | forecast_date, hour, price_pln |
| `pv_forecasts` | PV predictions | forecast_date, hour, predicted_power_w |

### Inspect Schema

```bash
sqlite3 data/goodwe_energy.db '.schema'
```

---

## Support

### Logs to Collect for Issues

```bash
# Create support bundle
tar -czvf support_bundle.tar.gz \
  logs/master_coordinator.log \
  config/master_coordinator_config.yaml \
  data/goodwe_energy.db
```

### Key Log Patterns

```bash
# Storage initialization
grep -i "storage" logs/master_coordinator.log | head -20

# Connection issues
grep -i "connect\|retry" logs/master_coordinator.log | tail -20

# Write errors
grep -i "error saving\|failed to save" logs/master_coordinator.log
```

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-02 | Initial playbook created |
| 2025-12-02 | Added rollout script `scripts/database_rollout.sh` |
