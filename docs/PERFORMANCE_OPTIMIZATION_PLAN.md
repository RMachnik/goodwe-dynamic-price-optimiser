# Performance Optimization & Revenue Validation Plan

## Problem Analysis

### 1. Performance Issues ("Cost & Savings" Section Slow)

**Current Implementation:**
- Loads entire month of decision files from disk on every request
- No caching mechanism for frequently accessed data
- `_get_decision_history()` reads up to 50 files sequentially
- Frontend polls `/api/system_metrics` repeatedly causing redundant calculations

**Bottlenecks Identified:**
```python
# In log_web_server.py line ~3000
decision_data = self._get_decision_history(time_range='24h')  # Slow!
all_decisions = decision_data.get('decisions', [])
```

**Root Causes:**
1. **File I/O on every request** - No caching layer
2. **Redundant calculations** - Monthly data recalculated instead of using snapshots
3. **Mixed data sources** - Monthly + recent decisions processed separately
4. **No response caching** - Same data recalculated for every page load

### 2. Battery Selling Revenue Validation (481.35 PLN)

**Current Calculation:**
```python
# From daily_snapshot_manager.py line ~160
selling_revenue = sum(d.get('expected_revenue_pln', d.get('estimated_savings_pln', 0)) 
                     for d in selling_decisions)
```

**Potential Issues:**

#### Issue #1: Revenue Factor Not Applied
```python
# From battery_selling_engine.py line ~613
def _calculate_expected_revenue(self, current_price_pln, selling_duration_hours):
    energy_sold_kwh = selling_power_kw * selling_duration_hours * self.discharge_efficiency
    return energy_sold_kwh * current_price_pln * self.revenue_factor  # ← 80% factor
```

**The revenue_factor (0.8) is applied during opportunity calculation, BUT:**
- If `expected_revenue_pln` in decision files is already the GROSS revenue (100%), not net
- Snapshot aggregation would be overcounting by 25%

#### Issue #2: Double Counting Risk
- Selling sessions may create multiple decision files
- If session updates aren't idempotent, revenue could be counted multiple times

#### Issue #3: Validation Math
```
Expected Revenue Check:
- Energy Sold: 149.60 kWh (from screenshot)
- Sessions: 19
- Revenue: 481.35 PLN
- Implied price: 481.35 / 149.60 = 3.22 PLN/kWh ← TOO HIGH!

If 80% factor applied:
- Gross: 481.35 / 0.8 = 601.69 PLN
- Implied gross price: 601.69 / 149.60 = 4.02 PLN/kWh ← IMPOSSIBLE!

More realistic scenario:
- If actual avg selling price was ~1.0 PLN/kWh:
- Expected gross: 149.60 × 1.0 = 149.60 PLN
- Expected net (80%): 149.60 × 0.8 = 119.68 PLN
- Actual shown: 481.35 PLN
- Ratio: 481.35 / 119.68 = 4.02x ← ~4x overcounting!
```

## Proposed Solutions

### Solution 1: Performance Optimization (Priority: HIGH)

#### A. Implement Response Caching
```python
from functools import lru_cache
from datetime import datetime

class CachedMetrics:
    def __init__(self, ttl_seconds=300):  # 5 min cache
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get_monthly_summary(self, year, month):
        cache_key = f"{year}_{month}"
        now = datetime.now().timestamp()
        
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if now - timestamp < self.ttl:
                return cached_data
        
        # Calculate fresh data
        data = self.snapshot_manager.get_monthly_summary(year, month)
        self.cache[cache_key] = (data, now)
        return data
```

#### B. Eliminate Redundant Decision Loading
```python
# Current (SLOW):
decision_data = self._get_decision_history(time_range='24h')  # Reads 50 files!
monthly_summary = self.snapshot_manager.get_monthly_summary(now.year, now.month)

# Optimized (FAST):
monthly_summary = self.cached_metrics.get_monthly_summary(now.year, now.month)
# Don't load decisions at all for Cost & Savings - use snapshot data only
```

#### C. Optimize Frontend Polling
```javascript
// Current: Poll every ~5 seconds
setInterval(loadCostSavings, 5000);

// Optimized: Poll less frequently for static data
setInterval(loadCostSavings, 60000);  // 1 minute for monthly data
```

**Expected Performance Improvement:**
- **Before**: 2-5 seconds load time (50+ file reads)
- **After**: <100ms load time (1 cached lookup)
- **Improvement**: 20-50x faster

### Solution 2: Revenue Calculation Validation (Priority: CRITICAL)

#### A. Add Revenue Tracking Fields to Decisions
```json
{
  "action": "battery_selling",
  "timestamp": "2025-11-21T07:23:29",
  "energy_sold_kwh": 8.5,
  "selling_price_pln_kwh": 1.074,
  "gross_revenue_pln": 9.13,  // ← NEW: 8.5 × 1.074
  "revenue_factor": 0.8,
  "net_revenue_pln": 7.30,    // ← NEW: 9.13 × 0.8
  "expected_revenue_pln": 7.30  // Use net revenue here
}
```

#### B. Add Validation Logic to Snapshot Calculation
```python
def _calculate_daily_summary(self, decisions, target_date):
    selling_decisions = [d for d in decisions if self._is_selling_decision(d)]
    
    # Calculate revenue with validation
    selling_revenue_gross = 0
    selling_revenue_net = 0
    
    for decision in selling_decisions:
        # Prefer explicit net_revenue if available
        if 'net_revenue_pln' in decision:
            selling_revenue_net += decision['net_revenue_pln']
        elif 'expected_revenue_pln' in decision:
            # Assume expected_revenue is already net (80%)
            selling_revenue_net += decision['expected_revenue_pln']
        else:
            # Fallback: calculate from energy and price
            energy = decision.get('energy_sold_kwh', 0)
            price = decision.get('selling_price_pln_kwh', 0)
            gross = energy * price
            net = gross * 0.8  # Apply 80% factor
            selling_revenue_net += net
        
        # Log validation info
        logger.debug(f"Selling decision: {energy:.2f} kWh @ {price:.3f} PLN/kWh = {net:.2f} PLN net")
    
    # Validation check
    total_energy_sold = sum(d.get('energy_sold_kwh', 0) for d in selling_decisions)
    if total_energy_sold > 0:
        implied_avg_price = selling_revenue_net / (total_energy_sold * 0.8)
        if implied_avg_price > 2.0:  # Sanity check
            logger.warning(
                f"⚠️ Suspicious selling revenue: {selling_revenue_net:.2f} PLN "
                f"for {total_energy_sold:.2f} kWh implies {implied_avg_price:.2f} PLN/kWh"
            )
```

#### C. Add Revenue Reconciliation Tool
```python
# scripts/validate_selling_revenue.py
def validate_monthly_revenue(year, month):
    """Validate selling revenue calculations"""
    snapshot_mgr = DailySnapshotManager()
    monthly = snapshot_mgr.get_monthly_summary(year, month)
    
    print(f"\n=== Revenue Validation for {year}-{month:02d} ===")
    print(f"Total Energy Sold: {monthly['total_energy_sold_kwh']:.2f} kWh")
    print(f"Selling Revenue: {monthly['selling_revenue_pln']:.2f} PLN")
    print(f"Sessions: {monthly['selling_count']}")
    
    # Calculate implied metrics
    if monthly['total_energy_sold_kwh'] > 0:
        net_price = monthly['selling_revenue_pln'] / monthly['total_energy_sold_kwh']
        gross_price = net_price / 0.8
        
        print(f"\nImplied Net Price: {net_price:.3f} PLN/kWh (80%)")
        print(f"Implied Gross Price: {gross_price:.3f} PLN/kWh (100%)")
        
        # Validate against typical market prices
        if gross_price > 2.0:
            print(f"⚠️  WARNING: Implied price {gross_price:.3f} PLN/kWh is unusually high!")
            print(f"   Expected range: 0.4-1.5 PLN/kWh")
            print(f"   Possible issues:")
            print(f"   - Revenue counted multiple times per session")
            print(f"   - Revenue factor not applied correctly")
            print(f"   - Wrong field used (gross instead of net)")
            return False
        else:
            print(f"✅ Price validation passed")
            return True
```

### Solution 3: Implement Real-time Revenue Tracking

#### A. Add Session State Management
```python
class SellingSessionTracker:
    """Track active selling sessions to prevent double-counting"""
    
    def __init__(self):
        self.active_sessions = {}
        self.completed_sessions = {}
    
    def start_session(self, session_id, initial_data):
        """Record session start"""
        self.active_sessions[session_id] = {
            'start_time': datetime.now(),
            'start_soc': initial_data['soc'],
            'expected_revenue': initial_data['expected_revenue'],
            'recorded': False
        }
    
    def complete_session(self, session_id, actual_data):
        """Record session completion with actual metrics"""
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found in active sessions")
            return
        
        session = self.active_sessions.pop(session_id)
        
        # Only record revenue once
        if not session['recorded']:
            self.completed_sessions[session_id] = {
                'start_time': session['start_time'],
                'end_time': datetime.now(),
                'energy_sold_kwh': actual_data['energy_sold'],
                'net_revenue_pln': actual_data['actual_revenue'],
                'recorded': True
            }
```

## Implementation Priority

### Phase 1: Critical Fixes (Week 1)
1. ✅ **Add revenue validation script** - Diagnose current overcounting
2. ✅ **Fix snapshot calculation** - Ensure net revenue used correctly
3. ✅ **Add logging** - Track revenue calculations for debugging

### Phase 2: Performance (Week 1-2)
1. ✅ **Implement response caching** - 20-50x speedup
2. ✅ **Eliminate redundant file I/O** - Use snapshots exclusively
3. ✅ **Optimize frontend polling** - Reduce server load

### Phase 3: Monitoring (Week 2)
1. ⏳ **Add validation dashboard** - Real-time revenue validation
2. ⏳ **Session tracking** - Prevent double-counting
3. ⏳ **Alerting** - Notify on suspicious metrics

## Testing Plan

### 1. Revenue Validation Tests
```bash
# Check November 2025 data
python scripts/validate_selling_revenue.py 2025 11

# Regenerate snapshots with fixes
python src/daily_snapshot_manager.py create-missing 30

# Verify corrected totals
curl http://localhost:8080/api/monthly_summary/2025/11
```

### 2. Performance Tests
```bash
# Before optimization
time curl http://localhost:8080/api/system_metrics

# After optimization (should be <100ms)
time curl http://localhost:8080/api/system_metrics
```

## Expected Outcomes

### Revenue Correction
- **Before**: 481.35 PLN (likely 3-4x overcounted)
- **After**: ~120-160 PLN (realistic for 149.60 kWh @ 0.8-1.1 PLN/kWh)

### Performance Improvement
- **Before**: 2-5 seconds (50+ file reads)
- **After**: <100ms (cached snapshot)
- **Improvement**: 20-50x faster

### Data Accuracy
- Prevent double-counting of selling sessions
- Consistent application of 80% revenue factor
- Real-time validation and alerting

---

**Created**: 2025-11-21  
**Status**: Proposed  
**Impact**: High - Affects financial tracking accuracy and user experience
