# Database Rollout Playbook

## Overview

This playbook guides you through safely enabling the SQLite database storage feature for the GoodWe Dynamic Price Optimiser. The system uses a **composite mode** (dual-write) that writes to both database AND JSON files, ensuring zero data loss during transition.

**Current Status**: Ready for Production  
**Risk Level**: Low (composite mode provides automatic fallback)  
**Estimated Time**: 30 minutes initial deployment + 24-48h monitoring

---

## Important: Path Configuration

The rollout script **auto-detects** the project directory from its location. You don't need to set paths manually unless running from a non-standard location.

**Default Detection:**
- Script detects its own location: `$(dirname "$0")`
- Project dir is parent: `$(dirname "$SCRIPT_DIR")`
- Works in both dev (`/home/user/sources/...`) and production (`/opt/...`)

**Override (if needed):**
```bash
INSTALL_DIR=/custom/path ./scripts/database_rollout.sh preflight
```

**Related Scripts:**
| Script | Purpose |
|--------|---------|
| `scripts/database_rollout.sh` | This playbook's automation |
| `scripts/manage_services.sh` | Service start/stop/restart |

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
- Python 3.10+
- 1GB+ free disk space for database
- Write access to data directory

### Python Dependencies

The database feature requires `aiosqlite`. This is already in `requirements.txt`:

```
# requirements.txt (excerpt)
aiosqlite>=0.19.0
```

**Install dependencies:**

```bash
# Using the rollout script (installs aiosqlite only)
./scripts/database_rollout.sh install-deps

# Or install all project dependencies
pip install -r requirements.txt
```

### Files Involved
| File | Purpose |
|------|---------|
| `config/master_coordinator_config.yaml` | Storage configuration |
| `src/database/sqlite_storage.py` | SQLite implementation |
| `src/database/composite_storage.py` | Dual-write logic |
| `src/database/storage_factory.py` | Storage mode selection |
| `scripts/database_rollout.sh` | Rollout automation script |
| `scripts/manage_services.sh` | Service management |
| `requirements.txt` | Python dependencies |

---

## Quick Start

```bash
# 1. Run all pre-flight checks
./scripts/database_rollout.sh preflight

# 2. Install dependencies if needed (preflight will tell you)
./scripts/database_rollout.sh install-deps

# 3. Create backup
./scripts/database_rollout.sh backup

# 4. Deploy (restarts service)
./scripts/database_rollout.sh deploy

# 5. Verify it's working
./scripts/database_rollout.sh verify

# 6. Get monitoring commands
./scripts/database_rollout.sh monitor
```

---

## Detailed Rollout Steps

### Phase 1: Pre-Flight Checks (15 minutes)

#### 1.1 Verify Data Directory

The script auto-detects your project directory. Verify with:

```bash
./scripts/database_rollout.sh help
# Shows: Project directory: /path/to/your/project
```

Create data directory if needed:

```bash
# For detected project dir
mkdir -p data

# Or explicit path
sudo mkdir -p /opt/goodwe-dynamic-price-optimiser/data
sudo chown -R $(whoami):$(whoami) /opt/goodwe-dynamic-price-optimiser/data
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

#### Systemd Deployment (Recommended)

```bash
# Using manage_services.sh (recommended)
./scripts/manage_services.sh restart

# Or direct systemctl
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
# Database file location (project-relative)
ls -lh data/goodwe_energy.db

# Or use the rollout script
./scripts/database_rollout.sh verify
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

# 2. Restart service (recommended)
./scripts/manage_services.sh restart
# OR
sudo systemctl restart goodwe-master-coordinator
# OR
docker-compose restart
```

### Full Rollback with Data Restore

```bash
# 1. Stop service
./scripts/manage_services.sh stop
# OR: sudo systemctl stop goodwe-master-coordinator

# 2. Restore from backup (adjust path)
tar -xzvf ~/goodwe_backups/backup_*.tar.gz -C .

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

---

## Advanced Topics

### Migration from File-Only to Database

If you're migrating from a long-running file-only installation:

#### Option 1: Fresh Start (Recommended)
Keep historical JSON files as archive, start fresh database:

```bash
# Archive old JSON data
mkdir -p /opt/goodwe-dynamic-price-optimiser/archive
mv /opt/goodwe-dynamic-price-optimiser/out/energy_data/*.json \
   /opt/goodwe-dynamic-price-optimiser/archive/

# Enable composite mode - new data flows to both systems
./scripts/database_rollout.sh deploy
```

#### Option 2: Import Historical Data

If you need historical data in the database:

```bash
# Create import script
python3 << 'EOF'
import asyncio
import json
from pathlib import Path
from database.sqlite_storage import SQLiteStorage
from datetime import datetime

async def import_json_files():
    storage = SQLiteStorage({
        'sqlite': {
            'path': '/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db'
        }
    })
    await storage.connect()
    
    json_dir = Path('/opt/goodwe-dynamic-price-optimiser/out/energy_data')
    imported = 0
    
    for json_file in sorted(json_dir.glob('*.json')):
        print(f'Importing {json_file.name}...')
        with open(json_file) as f:
            data = json.load(f)
            # Import based on file type
            if 'energy_data' in data:
                for record in data['energy_data']:
                    await storage.save_energy_data(record)
                    imported += 1
            elif 'system_state' in data:
                await storage.save_system_state(data['system_state'])
                imported += 1
    
    print(f'Imported {imported} records')
    await storage.disconnect()

asyncio.run(import_json_files())
EOF
```

### Performance Tuning

#### Database Optimization

```bash
# Run after large imports
sqlite3 data/goodwe_energy.db 'VACUUM;'
sqlite3 data/goodwe_energy.db 'ANALYZE;'

# Check database statistics
sqlite3 data/goodwe_energy.db << 'EOF'
SELECT 
    name as table_name,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
FROM sqlite_master m
WHERE type='table';
.quit
EOF
```

#### Query Performance

Monitor slow queries in logs:

```bash
# Find slow database operations (>1 second)
grep -E "took [0-9]+\.[0-9]+ seconds" logs/master_coordinator.log | \
  awk '$5 > 1.0'
```

If you see slow queries:

1. Check table indexes: `sqlite3 data/goodwe_energy.db '.indexes'`
2. Review retention settings (large tables impact performance)
3. Consider running `VACUUM` to reclaim space

### Backup Strategy

#### Automated Backups

Add to crontab:

```bash
# Daily backup at 3 AM
0 3 * * * /opt/goodwe-dynamic-price-optimiser/scripts/database_rollout.sh backup

# Weekly backup to external storage
0 4 * * 0 rsync -av /opt/goodwe-dynamic-price-optimiser/backups/ \
              user@backup-server:/backups/goodwe/
```

#### Restore from Backup

```bash
# Stop service
sudo systemctl stop goodwe-coordinator

# Restore database
cp backups/goodwe_energy.db.backup.YYYYMMDD_HHMMSS \
   data/goodwe_energy.db

# Verify integrity
sqlite3 data/goodwe_energy.db 'PRAGMA integrity_check;'

# Restart service
sudo systemctl start goodwe-coordinator
```

### Data Retention and Cleanup

#### Manual Cleanup

Remove old data to save disk space:

```bash
python3 << 'EOF'
import asyncio
from database.sqlite_storage import SQLiteStorage
from datetime import datetime, timedelta

async def cleanup_old_data():
    storage = SQLiteStorage({
        'sqlite': {
            'path': '/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db'
        }
    })
    await storage.connect()
    
    # Delete energy_data older than 90 days
    cutoff = datetime.now() - timedelta(days=90)
    
    # Execute cleanup
    async with storage._get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM energy_data WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        await conn.commit()
        print(f'Deleted {result.rowcount} old energy_data records')
    
    await storage.disconnect()

asyncio.run(cleanup_old_data())
EOF
```

#### Automated Retention

Configure in `config/master_coordinator_config.yaml`:

```yaml
data_storage:
  file_storage:
    retention_days: 7  # Keep JSON files for 7 days
  database_storage:
    retention_days: 365  # Keep DB data for 1 year
```

---

## Monitoring and Observability

### Key Metrics to Track

| Metric | Command | Healthy Range |
|--------|---------|---------------|
| Database size | `du -sh data/goodwe_energy.db` | < 500MB per month |
| Write latency | `grep "save.*took" logs/master_coordinator.log` | < 100ms |
| Connection pool | `grep "connection pool" logs/master_coordinator.log` | No warnings |
| Storage failures | `grep -i "storage.*error" logs/master_coordinator.log` | Zero |

### Grafana Dashboard (Future)

If you set up Grafana, monitor:

- Storage write latency (p50, p95, p99)
- Database size growth rate
- Failed write attempts
- Composite mode fallback rate

### Health Check Script

```bash
#!/bin/bash
# save as: scripts/storage_health_check.sh

DB_PATH="/opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db"
LOG_PATH="/opt/goodwe-dynamic-price-optimiser/logs/master_coordinator.log"

echo "=== Storage Health Check ==="
echo

# Check database exists and is accessible
if [ -f "$DB_PATH" ]; then
    echo "✅ Database file exists"
    echo "   Size: $(du -h $DB_PATH | cut -f1)"
else
    echo "❌ Database file not found!"
    exit 1
fi

# Check integrity
if sqlite3 "$DB_PATH" 'PRAGMA integrity_check;' | grep -q 'ok'; then
    echo "✅ Database integrity OK"
else
    echo "❌ Database integrity check FAILED!"
    exit 1
fi

# Check recent writes
RECENT_ERRORS=$(grep -i "storage.*error" "$LOG_PATH" | tail -n 10 | wc -l)
if [ "$RECENT_ERRORS" -eq 0 ]; then
    echo "✅ No recent storage errors"
else
    echo "⚠️  Found $RECENT_ERRORS recent storage errors"
fi

# Check table row counts
echo
echo "Table row counts:"
sqlite3 "$DB_PATH" << 'EOF'
SELECT 
    'energy_data: ' || COUNT(*) FROM energy_data
UNION ALL
SELECT 
    'system_state: ' || COUNT(*) FROM system_state
UNION ALL
SELECT 
    'charging_sessions: ' || COUNT(*) FROM charging_sessions;
EOF

echo
echo "=== Health Check Complete ==="
```

Make executable: `chmod +x scripts/storage_health_check.sh`

---

## Security Considerations

### File Permissions

Ensure only the service user can access database:

```bash
# Set restrictive permissions
chmod 600 /opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db
chown goodwe:goodwe /opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db
```

### Backup Security

Backups contain sensitive data:

```bash
# Encrypt backups
gpg --symmetric --cipher-algo AES256 \
    backups/goodwe_energy.db.backup.YYYYMMDD_HHMMSS

# Store encrypted, delete plaintext
rm backups/goodwe_energy.db.backup.YYYYMMDD_HHMMSS
```

### Network Access

SQLite runs in-process (no network exposure), but:

- Restrict SSH access to deployment machine
- Use firewall rules if running multiple services
- Consider read-only mounts for backup locations

---

## Future Migration: Database-Only Mode

Once composite mode is stable (recommended: 30+ days), switch to database-only:

### Pre-Migration Checklist

- [ ] Composite mode running successfully for 30+ days
- [ ] No storage errors in logs
- [ ] All queries working correctly
- [ ] Backups tested and validated
- [ ] Historical JSON data archived

### Migration Steps

```bash
# 1. Final backup
./scripts/database_rollout.sh backup

# 2. Edit config to disable file storage
sed -i 's/file_storage:$/file_storage:\n    enabled: false/' \
    config/master_coordinator_config.yaml

# 3. Restart service
sudo systemctl restart goodwe-coordinator

# 4. Verify database-only mode
grep "Using storage: database" logs/master_coordinator.log

# 5. Archive JSON files (don't delete yet!)
mkdir -p archive/json_files
mv out/energy_data/*.json archive/json_files/
```

### Validation Period

Keep JSON archive for 30 days after switching to database-only mode. Monitor for:

- Storage errors
- Missing data
- Performance issues

If stable, remove JSON archive after 30 days.

---

## FAQ

### Q: What happens if the database file gets corrupted?

**A:** Composite mode protects you:
1. JSON files continue receiving writes
2. Database errors are logged but don't stop the service
3. Restore from latest backup
4. Optionally reimport from JSON files

### Q: Can I run this on a Raspberry Pi?

**A:** Yes! SQLite is very lightweight:
- Tested on Raspberry Pi 4 (4GB RAM)
- Database size typically < 100MB/month
- CPU usage negligible for normal operations

### Q: How do I query the database directly?

**A:**

```bash
# Interactive mode
sqlite3 /opt/goodwe-dynamic-price-optimiser/data/goodwe_energy.db

# Quick queries
sqlite3 data/goodwe_energy.db "SELECT * FROM energy_data ORDER BY timestamp DESC LIMIT 5;"

# Export to CSV
sqlite3 -header -csv data/goodwe_energy.db \
  "SELECT * FROM energy_data WHERE date(timestamp) = date('now');" \
  > today_energy.csv
```

### Q: What's the difference between composite and dual-write?

**A:** They're the same thing! "Composite mode" writes to both storage backends simultaneously while reading primarily from the database. This ensures zero data loss during transition.

### Q: Can I migrate back to file-only storage?

**A:** Yes, that's the rollback procedure (see "Rollback Procedure" section). Since composite mode writes to both, your JSON files are always current.

### Q: How much disk space will the database use?

**A:** Typical growth:
- ~3-5MB per day (with 5-minute sampling)
- ~100-150MB per month
- With 1-year retention: ~1.2-1.8GB

Use `VACUUM` periodically to reclaim space after deletions.

---

## Related Documentation

- [Database Infrastructure](./DATABASE_INFRASTRUCTURE.md) - Architecture and design
- [Docker Deployment](./DOCKER_DEPLOYMENT.md) - Container setup
- [Master Coordinator](../config/master_coordinator_config.yaml) - Full configuration
- [Storage Factory](../src/database/storage_factory.py) - Storage mode logic

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-02 | Initial playbook created |
| 2025-12-02 | Added rollout script `scripts/database_rollout.sh` |
| 2025-12-02 | Added Advanced Topics, Monitoring, Security, and FAQ sections |
