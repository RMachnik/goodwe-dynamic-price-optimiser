# Database Migration Status

**Last Updated:** 2025-12-02 22:41 UTC  
**Status:** ✅ DEPLOYED - Composite Mode Active  
**Deployed By:** AI Assistant via GitHub Copilot CLI  

---

## Quick Status Check

```bash
# Service status
sudo systemctl status goodwe-master-coordinator

# Database exists and size
ls -lh data/goodwe_energy.db*

# Row counts
sqlite3 data/goodwe_energy.db "SELECT COUNT(*) FROM energy_data;"

# Recent logs
sudo journalctl -u goodwe-master-coordinator -n 20 --no-pager
```

---

## Current State

### What's Running
- **Mode:** Composite (writes to both database + JSON files)
- **Database:** SQLite at `data/goodwe_energy.db` (96KB initial size)
- **Service:** goodwe-master-coordinator (PID: 63253)
- **Started:** 2025-12-02 22:34:51 CET

### Configuration
```yaml
data_storage:
  file_storage:
    enabled: true       # Backup writes
  database_storage:
    enabled: true       # Primary writes
```

### Dependencies Installed
- `aiosqlite 0.21.0` - SQLite async driver
- `aiofiles 25.1.0` - Async file operations
- Both installed in: `/home/rmachnik/.venv/goodwe/`

### Backups Available
```
/home/rmachnik/goodwe_backups/backup_20251202_222121.tar.gz (188 bytes)
/home/rmachnik/goodwe_backups/backup_20251202_223041.tar.gz (564K)
```

---

## Timeline

| Time (UTC) | Action | Status |
|------------|--------|--------|
| 21:11 | Pre-flight checks | ✅ Passed |
| 22:20 | Dependencies installed | ✅ Complete |
| 22:21 | First backup created | ✅ Complete |
| 22:30 | Second backup created | ✅ Complete |
| 22:34 | Service deployed | ✅ Running |
| 22:35 | Database created | ✅ Operational |
| 22:39 | Verification completed | ✅ Verified |

---

## Monitoring Schedule

### Daily (First Week)
- [ ] Check service is running
- [ ] Check database size growth
- [ ] Check for errors in logs
- [ ] Verify data collection

### Weekly
- [ ] Review database growth rate
- [ ] Check backup integrity
- [ ] Review log patterns

### Monthly
- [ ] Run VACUUM on database
- [ ] Archive old JSON files
- [ ] Review retention settings

---

## Milestones

- **Day 1-2** (2025-12-02 to 2025-12-04): ✅ Initial deployment, active monitoring
- **Day 7** (2025-12-09): First week review
- **Day 30** (2026-01-02): Evaluate database-only mode migration
- **Day 60** (2026-02-01): Consider JSON file archive/cleanup

---

## Important Notes

1. **Composite Mode Safety:** System writes to BOTH database and JSON files. If database fails, JSON files continue working.

2. **Service Uses Venv:** Python environment at `/home/rmachnik/.venv/goodwe/` - install packages there.

3. **Sudo Password:** `machnicek99` (for service restart/management)

4. **SSH Key Password:** `machnicek99` (for git operations)

5. **Working Directory:** `/home/rmachnik/sources/goodwe-dynamic-price-optimiser`

---

## Quick Actions

### Restart Service
```bash
sudo systemctl restart goodwe-master-coordinator
```

### Check Database
```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
sqlite3 data/goodwe_energy.db "SELECT * FROM energy_data ORDER BY timestamp DESC LIMIT 5;"
```

### View Live Logs
```bash
sudo journalctl -u goodwe-master-coordinator -f
```

### Create Backup
```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
./scripts/database_rollout.sh backup
```

### Rollback (Emergency)
```bash
cd /home/rmachnik/sources/goodwe-dynamic-price-optimiser
./scripts/database_rollout.sh rollback
```

---

## Troubleshooting

### Database Not Growing?
```bash
# Check if data collector is running
sudo journalctl -u goodwe-master-coordinator | grep -i "data saved"

# Force WAL checkpoint
sqlite3 data/goodwe_energy.db "PRAGMA wal_checkpoint(FULL);"

# Check row counts
sqlite3 data/goodwe_energy.db "SELECT COUNT(*) FROM energy_data;"
```

### Service Won't Start?
```bash
# Check logs
sudo journalctl -u goodwe-master-coordinator -n 50

# Check for missing dependencies
/home/rmachnik/.venv/goodwe/bin/python -c "import aiosqlite, aiofiles; print('OK')"

# Force kill and restart
sudo systemctl kill goodwe-master-coordinator
sudo systemctl start goodwe-master-coordinator
```

### Database Corrupted?
```bash
# Check integrity
sqlite3 data/goodwe_energy.db "PRAGMA integrity_check;"

# Restore from backup (stops service first)
sudo systemctl stop goodwe-master-coordinator
cp /home/rmachnik/goodwe_backups/backup_20251202_223041.tar.gz .
tar -xzf backup_20251202_223041.tar.gz
sudo systemctl start goodwe-master-coordinator
```

---

## Documentation References

- Full playbook: `docs/DATABASE_ROLLOUT_PLAYBOOK.md`
- Database infrastructure: `docs/DATABASE_INFRASTRUCTURE.md`
- Configuration: `config/master_coordinator_config.yaml`
- Rollout script: `scripts/database_rollout.sh`

---

## Contact & Support

If you need to resume this migration or troubleshoot:

1. Read this file first for current state
2. Check `docs/DATABASE_ROLLOUT_PLAYBOOK.md` Section "Rollout History"
3. Run verification commands above
4. Check service logs for errors

**Everything you need to resume is documented here and in the playbook.**
