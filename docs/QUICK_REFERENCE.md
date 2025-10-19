# Quick Reference - Monthly Tracking System

## 🚀 Deploy to Server

```bash
./deploy_monthly_tracking.sh
```

## 📊 View Dashboard

```
http://192.168.33.10:8080/
```

## 🔧 Common Commands

### Create Snapshots
```bash
# Create snapshots for last 30 days
python3 src/daily_snapshot_manager.py create-missing 30

# Create snapshot for specific date
python3 src/daily_snapshot_manager.py create 2025-10-15
```

### Get Monthly Summary
```bash
# Current month
python3 src/daily_snapshot_manager.py monthly 2025 10

# Or via API
curl http://192.168.33.10:8080/monthly-summary
```

### Compare Months
```bash
curl http://192.168.33.10:8080/monthly-comparison | python3 -m json.tool
```

## ⚡ Performance Check

```bash
# Test dashboard load time
time curl -s http://192.168.33.10:8080/metrics > /dev/null

# Should be < 1 second
```

## 🔄 Restart Service

```bash
sudo systemctl restart goodwe-master-coordinator
sudo systemctl status goodwe-master-coordinator
```

## 📈 Check Snapshots

```bash
# List all snapshots
ls -lh out/daily_snapshots/

# View a snapshot
cat out/daily_snapshots/snapshot_20251019.json | python3 -m json.tool
```

## 🧪 Run Tests

```bash
# Run snapshot manager tests
python3 test/test_daily_snapshot_manager.py

# Should show: Ran 12 tests in 0.XXXs - OK
```

## 📅 Setup Automation

```bash
# Add to crontab (runs daily at 1 AM)
crontab -e

# Add this line:
0 1 * * * cd ~/sources/goodwe-dynamic-price-optimiser && python3 src/daily_snapshot_manager.py create-missing 1 >> logs/snapshot_creation.log 2>&1
```

## 🐛 Troubleshooting

### Dashboard slow?
```bash
# Recreate snapshots
python3 src/daily_snapshot_manager.py create-missing 90
sudo systemctl restart goodwe-master-coordinator
```

### Old costs showing?
```bash
# Restart service to clear cache
sudo systemctl restart goodwe-master-coordinator
```

### Missing data?
```bash
# Check if decision files exist
ls -la out/energy_data/charging_decision_*.json | head

# Check if snapshots exist
ls -la out/daily_snapshots/

# Recreate if needed
python3 src/daily_snapshot_manager.py create-missing 90
```

## 📞 API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/monthly-summary` | Current month | `curl http://192.168.33.10:8080/monthly-summary` |
| `/monthly-summary?year=2025&month=9` | Specific month | `curl "http://192.168.33.10:8080/monthly-summary?year=2025&month=9"` |
| `/monthly-comparison` | Current vs previous | `curl http://192.168.33.10:8080/monthly-comparison` |
| `/metrics` | Dashboard metrics | `curl http://192.168.33.10:8080/metrics` |

## 📁 Important Files

| File | Purpose |
|------|---------|
| `src/daily_snapshot_manager.py` | Snapshot creation & management |
| `src/log_web_server.py` | Web server with monthly endpoints |
| `out/daily_snapshots/` | Stored daily summaries |
| `out/energy_data/` | Raw decision files |
| `MONTHLY_TRACKING_IMPLEMENTATION.md` | Full documentation |

## 🎯 What Changed

- ✅ Dashboard now shows **current month** costs (not 7-day)
- ✅ **10x faster** loading (<1s instead of 10s)
- ✅ New **monthly comparison** API
- ✅ **Daily snapshots** for efficient data access
- ✅ Matches your **monthly invoicing** cycle

## 💡 Tips

1. **Run snapshots daily** via cron for best performance
2. **Check logs** if something seems wrong: `tail -f logs/master_coordinator.log`
3. **Snapshots are immutable** - safe to recreate anytime
4. **Today's data is live** - not cached in snapshots
5. **First month** might show partial data (since October 19)

## 📖 More Info

- **Full docs**: `MONTHLY_TRACKING_IMPLEMENTATION.md`
- **Summary**: `IMPLEMENTATION_SUMMARY.md`
- **Tests**: `test/test_daily_snapshot_manager.py`

