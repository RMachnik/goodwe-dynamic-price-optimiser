# Dashboard Simplification Deployment Notes

## Changes Made

### Summary
Simplified dashboard by removing non-functional Battery Selling features, redundant Metrics tab, and optimizing performance.

### Files Modified
- `src/log_web_server.py` - Main dashboard implementation

### UI Changes

#### Removed Components
1. **Battery Selling Tab** - Removed completely (feature enabled but rarely used - requires 80%+ SOC)
2. **Metrics Tab** - Removed (redundant with Performance Metrics card in Overview)
3. **Battery Selling Status Card** - Removed from Overview tab
4. **Battery Selling Badge** - Removed from Decisions page statistics
5. **Grid Flow Metric** - Removed from Current System State (was showing "N/A")
6. **System Health Indicator** - Removed (was showing "UNKNOWN")

#### Kept Components
- Overview tab with 4 cards:
  - System Status
  - Current System State (8 metrics: Battery SoC, PV Power, House Consumption, L1/L2/L3 Current, Current Price, Cheapest Price)
  - Performance Metrics
  - Cost & Savings
- Decisions tab (with Total, Charging, Wait badges)
- Time Series tab
- Logs tab

### Performance Improvements
- Auto-refresh interval increased from 60s to 120s
- Removed 2 API endpoint calls (`/battery-selling` endpoint removed)
- Reduced DOM complexity by removing unused tabs and cards

### Backend Changes
- Removed `/battery-selling` API endpoint
- Removed `_get_battery_selling_data()` method
- Removed all Battery Selling JavaScript functions

## Deployment Instructions

### For Remote Server (192.168.33.10)

1. **Copy updated file to server:**
   ```bash
   scp src/log_web_server.py rafalmachnik@192.168.33.10:~/sources/goodwe-dynamic-price-optimiser/src/
   ```

2. **SSH to server and restart service:**
   ```bash
   ssh rafalmachnik@192.168.33.10
   cd ~/sources/goodwe-dynamic-price-optimiser
   
   # Restart the service (choose one method):
   
   # Method 1: If running as systemd service
   sudo systemctl restart goodwe-master-coordinator
   
   # Method 2: If running as user service
   systemctl --user restart goodwe-master-coordinator
   
   # Method 3: If running manually
   pkill -f master_coordinator
   ./run_master_coordinator.sh
   ```

3. **Verify the service is running:**
   ```bash
   # Check systemd status
   sudo systemctl status goodwe-master-coordinator
   # or
   systemctl --user status goodwe-master-coordinator
   
   # Check if web server is responding
   curl http://localhost:8080/health
   ```

4. **Test the dashboard:**
   - Navigate to http://192.168.33.10:8080/
   - Verify only 4 tabs are visible: Overview, Decisions, Time Series, Logs
   - Verify Battery Selling tab is gone
   - Verify Metrics tab is gone
   - Check Overview tab shows 8 metrics in Current System State card
   - Check Decisions tab shows only 3 badges: Total, Charging, Wait
   - Verify no console errors

## Testing Checklist

- [ ] Dashboard loads successfully
- [ ] Overview tab displays correctly with 4 cards
- [ ] Current System State shows 8 metrics (no Grid Flow, no System Health)
- [ ] Performance Metrics card displays correctly
- [ ] Cost & Savings card displays correctly
- [ ] Decisions tab loads and shows 3 badges (Total, Charging, Wait)
- [ ] Time Series tab loads chart correctly
- [ ] Logs tab displays logs correctly
- [ ] No "Battery Selling" tab visible
- [ ] No "Metrics" tab visible
- [ ] Auto-refresh works (check after 120 seconds)
- [ ] No 404 errors in browser console
- [ ] Manual refresh button works

## Rollback Instructions

If you need to rollback:
```bash
cd ~/sources/goodwe-dynamic-price-optimiser
git checkout src/log_web_server.py
sudo systemctl restart goodwe-master-coordinator
```

## Notes

- Battery Selling feature is still enabled in the backend (config) but UI is removed since it's rarely active
- The feature requires 80%+ SOC and specific pricing conditions that rarely occur
- If needed in the future, the Battery Selling tab can be re-added
- All backend battery selling logic remains intact

