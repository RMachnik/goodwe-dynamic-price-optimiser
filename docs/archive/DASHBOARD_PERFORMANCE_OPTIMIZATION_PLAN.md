# Dashboard Performance Optimization Plan

**Status:** Ready for Implementation  
**Date:** 4 December 2025  
**Target:** Reduce dashboard API response times from 3-8s to <100ms

---

## Executive Summary

The dashboard in `src/log_web_server.py` has severe performance issues (3-8s response times) due to:
- **Database connection thread-safety issues** causing race conditions
- **Blocking operations in request handlers** (inverter connections, file I/O, database queries)
- **Silent fallback to slow file reading** instead of using database
- **No background refresh** - every request pays full cost of data collection

This plan implements a **thread-safe, database-first architecture** with background refresh, proper storage abstraction usage, and comprehensive error handling.

### Performance Targets

| Endpoint | Before (Cache Miss) | After (Background Cache) | Improvement |
|----------|---------------------|--------------------------|-------------|
| `/status` | 8.1s | **<100ms** | **81x faster** |
| `/current-state` | 3.2s | **<100ms** | **32x faster** |
| `/metrics` | 6.0s | **<100ms** | **60x faster** |
| `/logs` | 660ms | **<100ms** | **6.6x faster** |
| **Dashboard Load** | **~18s total** | **<500ms total** | **36x faster** |

---

## Phase 0: Fix Critical Thread-Safety & Database Issues

### **Step 0.1: Implement per-thread storage instances for thread safety**

**Problem:** Single shared `aiosqlite` connection used by background thread + multiple Flask request threads causes race conditions and "database locked" errors.

**Solution:** Each thread gets its own storage instance.

**File:** `src/log_web_server.py` lines 120-127

**Replace:**
```python
self.storage = None
self._storage_connected = False
if StorageFactory:
    try:
        self.storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
        logger.info("Storage layer initialized for LogWebServer")
        self._connect_storage_async()
```

**With:**
```python
# Main thread storage (for Flask request handlers)
self.storage = None
self._storage_connected = False

# Background thread will create its own storage instance
self._background_storage = None
self._background_storage_connected = False

if StorageFactory:
    try:
        self.storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
        logger.info("Storage layer initialized for LogWebServer main thread")
        self._connect_storage_async()
    except Exception as e:
        logger.warning(f"Failed to initialize storage layer: {e}. Using file-only fallback.")
```

---

### **Step 0.2: Create dedicated storage connection for background thread**

**File:** `src/log_web_server.py`

Add new method:

```python
def _init_background_storage(self):
    """Initialize separate storage instance for background thread (thread-safety)."""
    if not StorageFactory:
        return
    
    try:
        self._background_storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
        logger.info("Initializing background thread storage connection...")
        
        # Connect in this thread's event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            connected = loop.run_until_complete(self._background_storage.connect())
            self._background_storage_connected = connected
            if connected:
                logger.info("✅ Background storage connected successfully")
            else:
                logger.error("❌ Background storage connection failed")
        finally:
            # Don't close loop - background thread will reuse it
            pass
    except Exception as e:
        logger.error(f"Failed to initialize background storage: {e}", exc_info=True)
        self._background_storage_connected = False
```

---

### **Step 0.3: Add query timeouts to prevent hangs**

**File:** `src/log_web_server.py`

Create helper method:

```python
def _run_async_storage_with_timeout(self, coro, timeout=10.0, use_background=False):
    """Run async storage operation with timeout protection.
    
    Args:
        coro: Coroutine to execute
        timeout: Max execution time in seconds
        use_background: If True, use background thread's storage instance
    """
    storage_instance = self._background_storage if use_background else self.storage
    connected = self._background_storage_connected if use_background else self._storage_connected
    
    if not storage_instance or not connected:
        return None
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Wrap in timeout
            result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
            return result
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Storage query timeout after {timeout}s")
            return None
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Storage query failed: {e}", exc_info=True)
        return None
```

---

### **Step 0.4: Add database migration verification on startup**

**File:** `src/log_web_server.py`

Add method:

```python
def _validate_database_health(self):
    """Validate database has data and is properly migrated."""
    if not self.storage or not self._storage_connected:
        logger.info("📁 Database not available - will use file storage")
        self._storage_has_data = False
        return
    
    try:
        # Test query to check data availability
        now = datetime.now()
        test_start = now - timedelta(hours=24)
        
        start_time = time.time()
        test_data = self._run_async_storage_with_timeout(
            self.storage.get_decisions(test_start, now),
            timeout=5.0
        )
        duration_ms = (time.time() - start_time) * 1000
        
        if test_data is None:
            logger.warning("⚠️ Database query returned None - check connection")
            self._storage_has_data = False
        elif len(test_data) == 0:
            logger.warning("⚠️ Database is EMPTY - run migration script: python scripts/migrate_json_to_db.py")
            self._storage_has_data = False
        else:
            logger.info(f"✅ Database validated: {len(test_data)} decisions available (query: {duration_ms:.0f}ms)")
            self._storage_has_data = True
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        self._storage_has_data = False
```

**Call this after `_connect_storage_async()` in `__init__()`.**

---

### **Step 0.5: Fix event loop handling in DailySnapshotManager**

**File:** `src/daily_snapshot_manager.py` lines 62-76

**Replace `_run_async()` method with:**

```python
def _run_async(self, coro):
    """Safely run async coroutine from sync context with timeout."""
    try:
        # Check if already in async context
        loop = asyncio.get_running_loop()
        logger.debug("Already in async context, cannot nest event loops")
        return None
    except RuntimeError:
        # No running loop - safe to create new one (Flask/background thread context)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Add 30s timeout for database operations
                result = loop.run_until_complete(asyncio.wait_for(coro, timeout=30.0))
                return result
            except asyncio.TimeoutError:
                logger.error("⏱️ Database operation timeout (30s)")
                return None
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error running async operation: {e}", exc_info=True)
            return None
```

---

### **Step 0.6: Improve storage query logging**

**File:** `src/log_web_server.py` at line 2947

**Replace silent fallback with explicit logging:**

```python
# Replace:
db_decisions = self._run_async_storage(
    self.storage.get_decisions(time_threshold, now) if self.storage else None
)
if db_decisions:
    decisions = db_decisions
    logger.debug(f"Loaded {len(decisions)} decisions from storage layer")

# With:
start_time = time.time()
db_decisions = self._run_async_storage_with_timeout(
    self.storage.get_decisions(time_threshold, now) if self.storage else None,
    timeout=10.0
)
duration_ms = (time.time() - start_time) * 1000

if db_decisions:
    decisions = db_decisions
    logger.info(f"✅ DATABASE: Loaded {len(decisions)} decisions in {duration_ms:.0f}ms")
elif self.storage and self._storage_connected:
    logger.warning(f"⚠️ DATABASE: Query returned no data after {duration_ms:.0f}ms - falling back to files (run migration if needed)")
else:
    logger.info(f"📁 FILES: Database unavailable, using file storage")
```

**Apply similar pattern in:**
- `DailySnapshotManager.create_daily_snapshot()` (lines 100-110)
- `_get_system_metrics()` (line 3119)

---

## Phase 1: Background Refresh Infrastructure

### **Step 1.1: Initialize background cache and threading primitives**

**File:** `src/log_web_server.py` after line 133 in `__init__()`

**Add:**

```python
# Background refresh infrastructure
self._background_cache = {
    'inverter_data': None,
    'price_data': None,
    'metrics_data': None,
    'coordinator_pid': None,
    'coordinator_running': None,
    'data_source': None,
    'last_inverter_refresh': 0,
    'last_price_refresh': 0,
    'last_metrics_refresh': 0,
    'last_pid_check': 0,
    'last_inverter_error': None,
    'last_price_error': None,
    'last_metrics_error': None
}
self._background_cache_lock = threading.Lock()
self._stop_background_thread = threading.Event()
self._background_thread = None
self._cached_coordinator_pid = None

# Storage health tracking
self._storage_has_data = False
self._storage_consecutive_failures = 0
self._storage_last_reconnect_attempt = 0
```

---

### **Step 1.2: Create background refresh thread**

**File:** `src/log_web_server.py`

Add method `_start_background_refresh()`:

```python
def _start_background_refresh(self):
    """Start background data refresh thread."""
    def background_loop():
        threading.current_thread().name = 'background_refresh'
        logger.info("Background refresh thread started")
        
        # Initialize background thread's own storage instance
        self._init_background_storage()
        
        # Pre-build monthly snapshots (non-blocking, happens in background)
        try:
            now = datetime.now()
            logger.info("Pre-building monthly snapshots...")
            self.snapshot_manager.get_monthly_summary(now.year, now.month)
            logger.info("Monthly snapshots ready")
        except Exception as e:
            logger.warning(f"Failed to pre-build snapshots: {e}")
        
        # Read refresh intervals from config
        web_config = self.config.get('web_server', {})
        inverter_interval = max(10, min(600, web_config.get('background_refresh_interval_seconds', 30)))
        price_interval = max(60, min(3600, web_config.get('price_refresh_interval_seconds', 300)))
        metrics_interval = max(30, min(600, web_config.get('metrics_refresh_interval_seconds', 60)))
        pid_interval = max(30, min(300, web_config.get('coordinator_pid_check_interval_seconds', 60)))
        
        logger.info(f"Refresh intervals: inverter={inverter_interval}s, price={price_interval}s, metrics={metrics_interval}s")
        
        last_inverter = last_price = last_metrics = last_pid = 0
        
        while not self._stop_background_thread.is_set():
            try:
                now = time.time()
                
                # Refresh coordinator PID
                if now - last_pid >= pid_interval:
                    self._refresh_coordinator_pid()
                    last_pid = now
                
                # Refresh inverter data
                if now - last_inverter >= inverter_interval:
                    self._refresh_inverter_data()
                    last_inverter = now
                
                # Refresh price data
                if now - last_price >= price_interval:
                    self._refresh_price_data()
                    last_price = now
                
                # Refresh metrics data
                if now - last_metrics >= metrics_interval:
                    self._refresh_metrics_data()
                    last_metrics = now
                
            except Exception as e:
                logger.warning(f"Background refresh error: {e}", exc_info=True)
            
            # Interruptible sleep
            self._stop_background_thread.wait(timeout=5.0)
        
        # Cleanup on exit
        if self._background_storage and self._background_storage_connected:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._background_storage.disconnect())
                    logger.info("Background storage disconnected")
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Error disconnecting background storage: {e}")
        
        logger.info("Background refresh thread stopped")
    
    self._background_thread = threading.Thread(target=background_loop, daemon=True, name='background_refresh')
    self._background_thread.start()
```

**Call `_start_background_refresh()` at end of `__init__()`.**

---

### **Step 1.3: Implement coordinator PID caching**

**File:** `src/log_web_server.py`

Add method:

```python
def _refresh_coordinator_pid(self):
    """Refresh coordinator PID cache (called from background thread)."""
    try:
        # Check if cached PID is still valid
        if self._cached_coordinator_pid:
            try:
                proc = psutil.Process(self._cached_coordinator_pid)
                if proc.is_running() and 'master_coordinator.py' in ' '.join(proc.cmdline()):
                    # PID still valid
                    with self._background_cache_lock:
                        self._background_cache['coordinator_pid'] = self._cached_coordinator_pid
                        self._background_cache['coordinator_running'] = True
                        self._background_cache['last_pid_check'] = time.time()
                    return
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Need to find coordinator PID
        coordinator_running = False
        coordinator_pid = None
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and any('master_coordinator.py' in cmd for cmd in proc.info['cmdline']):
                    coordinator_running = True
                    coordinator_pid = proc.info['pid']
                    self._cached_coordinator_pid = coordinator_pid
                    logger.debug(f"Found coordinator PID: {coordinator_pid}")
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        with self._background_cache_lock:
            self._background_cache['coordinator_pid'] = coordinator_pid
            self._background_cache['coordinator_running'] = coordinator_running
            self._background_cache['last_pid_check'] = time.time()
            
    except Exception as e:
        logger.warning(f"Error refreshing coordinator PID: {e}")
```

---

## Phase 2: Price Data Persistence

### **Step 2.1: Add price cache file management**

**File:** `src/log_web_server.py` after line 133 in `__init__()`

**Add:**

```python
self._price_cache_file = Path(__file__).parent.parent / 'data' / 'price_cache.json'
```

---

### **Step 2.2: Create disk cache methods**

**File:** `src/log_web_server.py`

Add methods:

```python
def _load_price_from_disk(self) -> Optional[Dict[str, Any]]:
    """Load price data from disk cache with validation."""
    if not self._price_cache_file.exists():
        return None
    
    try:
        with open(self._price_cache_file, 'r') as f:
            cached = json.load(f)
        
        # Validate freshness (<24 hours)
        cache_age = time.time() - cached.get('cache_timestamp', 0)
        if cache_age > 86400:  # 24 hours
            logger.debug(f"Price disk cache expired (age: {cache_age/3600:.1f}h)")
            return None
        
        # Validate business_date (today or tomorrow for next-day prices)
        cached_date = cached.get('business_date', '')
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        if cached_date not in [today, tomorrow]:
            logger.debug(f"Price disk cache date mismatch: {cached_date} not in [{today}, {tomorrow}]")
            return None
        
        logger.info(f"✅ Loaded price data from disk cache (age: {cache_age/60:.1f}min)")
        return cached.get('price_data')
        
    except Exception as e:
        logger.warning(f"Failed to load price cache from disk: {e}")
        return None

def _save_price_to_disk(self, price_data: Dict[str, Any]):
    """Save price data to disk cache."""
    try:
        self._price_cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        cache_obj = {
            'price_data': price_data,
            'cache_timestamp': time.time(),
            'business_date': datetime.now().strftime('%Y-%m-%d'),
            'created_at': datetime.now().isoformat()
        }
        
        with open(self._price_cache_file, 'w') as f:
            json.dump(cache_obj, f, indent=2)
        
        logger.info("💾 Saved price data to disk cache")
        
    except Exception as e:
        logger.warning(f"Failed to save price cache to disk: {e}")
```

---

## Phase 3: Background Refresh Methods (Thread-Safe)

### **Step 3.1: Price data refresh (database-first)**

**File:** `src/log_web_server.py`

Add method (note: uses background thread's storage instance):

```python
def _refresh_price_data(self):
    """Refresh price data in background thread (uses background storage instance)."""
    try:
        # Try disk cache first
        cached = self._load_price_from_disk()
        if cached:
            with self._background_cache_lock:
                self._background_cache['price_data'] = cached
                self._background_cache['last_price_refresh'] = time.time()
                self._background_cache['last_price_error'] = None
            return
        
        # Extract logic from _get_real_price_data() - fetch from PSE API
        from automated_price_charging import AutomatedPriceCharger
        
        charger = AutomatedPriceCharger(str(Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"))
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            price_data = loop.run_until_complete(
                asyncio.wait_for(charger.fetch_price_data_for_date(today), timeout=30.0)
            )
        finally:
            loop.close()
        
        if not price_data or 'value' not in price_data:
            raise Exception("Price API returned no data")
        
        # Process price data (calculate cheapest, average, etc.)
        current_price = charger.get_current_price(price_data)
        if current_price is None:
            raise Exception("Could not determine current price")
        
        current_price_kwh = current_price / 1000
        
        # Find cheapest and calculate stats
        prices = []
        for item in price_data['value']:
            market_price = float(item['csdac_pln'])
            try:
                item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            except ValueError:
                item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M:%S')
            
            final_price = charger.calculate_final_price(market_price, item_time)
            final_price_kwh = final_price / 1000
            prices.append((final_price_kwh, item_time.hour))
        
        if not prices:
            raise Exception("No valid prices found")
        
        cheapest_price, cheapest_hour = min(prices, key=lambda x: x[0])
        avg_price = sum(price for price, _ in prices) / len(prices)
        
        result = {
            'current_price_pln_kwh': round(current_price_kwh, 4),
            'cheapest_price_pln_kwh': round(cheapest_price, 4),
            'cheapest_hour': f"{cheapest_hour:02d}:00",
            'average_price_pln_kwh': round(avg_price, 4),
            'price_trend': 'stable',
            'data_source': 'PSE API (CSDAC-PLN)',
            'last_updated': datetime.now().isoformat(),
            'calculation_method': 'tariff_aware'
        }
        
        # Save to disk
        self._save_price_to_disk(result)
        
        # Update background cache
        with self._background_cache_lock:
            self._background_cache['price_data'] = result
            self._background_cache['last_price_refresh'] = time.time()
            self._background_cache['last_price_error'] = None
        
        logger.info(f"✅ Refreshed price data: {current_price_kwh:.4f} PLN/kWh")
        
    except Exception as e:
        logger.warning(f"Price refresh failed: {e}")
        with self._background_cache_lock:
            self._background_cache['last_price_error'] = str(e)
```

---

### **Step 3.2: Inverter data refresh (coordinator state files only)**

**File:** `src/log_web_server.py`

Add method:

```python
def _refresh_inverter_data(self):
    """Refresh inverter data from coordinator state files (no direct inverter connection)."""
    try:
        # Read most recent coordinator state file
        project_root = Path(__file__).parent.parent
        state_files = list((project_root / "out").glob("coordinator_state_*.json"))
        
        if not state_files:
            raise Exception("No coordinator state files found")
        
        latest_file = max(state_files, key=lambda x: x.stat().st_mtime)
        file_age = time.time() - latest_file.stat().st_mtime
        
        if file_age > 120:  # Older than 2 minutes
            raise Exception(f"State file too old: {file_age:.0f}s")
        
        # Read and parse
        content = latest_file.read_text().strip()
        lines = content.split('\n')
        
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                current_data = data.get('current_data', {})
                
                # Convert to dashboard format
                dashboard_data = self._convert_enhanced_data_to_dashboard_format(current_data)
                
                if dashboard_data:
                    with self._background_cache_lock:
                        self._background_cache['inverter_data'] = dashboard_data
                        self._background_cache['last_inverter_refresh'] = time.time()
                        self._background_cache['last_inverter_error'] = None
                        self._background_cache['data_source'] = dashboard_data.get('data_source', 'real')
                    
                    logger.debug(f"✅ Refreshed inverter data from {latest_file.name} (age: {file_age:.1f}s)")
                    return
            except json.JSONDecodeError:
                continue
        
        raise Exception("No valid JSON in state file")
        
    except Exception as e:
        logger.warning(f"Inverter data refresh failed: {e}")
        with self._background_cache_lock:
            self._background_cache['last_inverter_error'] = str(e)
```

---

### **Step 3.3: Metrics data refresh (database-first via background storage)**

**File:** `src/log_web_server.py`

Add method (note: uses `self._background_storage`):

```python
def _refresh_metrics_data(self):
    """Refresh metrics data from database (uses background storage instance)."""
    try:
        start_time = time.time()
        
        # Get monthly summary (database-first)
        now = datetime.now()
        monthly_summary = self.snapshot_manager.get_monthly_summary(now.year, now.month)
        
        # Get recent decisions (last 24h) for efficiency score
        yesterday = now - timedelta(hours=24)
        db_decisions = self._run_async_storage_with_timeout(
            self._background_storage.get_decisions(yesterday, now) if self._background_storage else None,
            timeout=10.0,
            use_background=True
        )
        
        # Calculate efficiency score from recent data
        efficiency_score = 70.0  # Default
        if db_decisions:
            avg_confidence = sum(d.get('confidence', 0) for d in db_decisions) / len(db_decisions) if db_decisions else 0
            efficiency_score = avg_confidence * 100
        
        metrics = {
            'timestamp': now.isoformat(),
            'total_decisions': monthly_summary.get('total_decisions', 0),
            'charging_count': monthly_summary.get('charging_count', 0),
            'wait_count': monthly_summary.get('wait_count', 0),
            'battery_selling_count': 0,
            'total_energy_charged_kwh': monthly_summary.get('total_energy_kwh', 0),
            'total_cost_pln': monthly_summary.get('total_cost_pln', 0),
            'total_savings_pln': monthly_summary.get('total_savings_pln', 0),
            'savings_percentage': monthly_summary.get('savings_percentage', 0),
            'avg_confidence': round(monthly_summary.get('avg_confidence', 0) * 100, 1),
            'avg_cost_per_kwh_pln': monthly_summary.get('avg_cost_per_kwh', 0),
            'efficiency_score': efficiency_score,
            'source_breakdown': monthly_summary.get('source_breakdown', {}),
            'time_range': 'current_month'
        }
        
        duration_ms = (time.time() - start_time) * 1000
        
        with self._background_cache_lock:
            self._background_cache['metrics_data'] = metrics
            self._background_cache['last_metrics_refresh'] = time.time()
            self._background_cache['last_metrics_error'] = None
        
        logger.info(f"✅ Refreshed metrics data in {duration_ms:.0f}ms")
        
    except Exception as e:
        logger.warning(f"Metrics refresh failed: {e}")
        with self._background_cache_lock:
            self._background_cache['last_metrics_error'] = str(e)
```

---

## Phase 4: Optimize DailySnapshotManager

### **Step 4.1: Add monthly summary caching**

**File:** `src/daily_snapshot_manager.py` after line 36 in `__init__()`

**Add:**

```python
self._monthly_cache = {}
self._monthly_cache_lock = threading.Lock()
```

---

### **Step 4.2: Implement cache-first monthly summary**

**File:** `src/daily_snapshot_manager.py` at line 258 in `get_monthly_summary()`

**Add caching at start of method:**

```python
def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
    """Get monthly summary with in-memory caching."""
    
    # Check cache first
    cache_key = f"{year}_{month}"
    with self._monthly_cache_lock:
        if cache_key in self._monthly_cache:
            cached_data, cached_time = self._monthly_cache[cache_key]
            cache_age = time.time() - cached_time
            if cache_age < 300:  # 5 minutes
                logger.debug(f"Returning cached monthly summary (age: {cache_age:.0f}s)")
                return cached_data
    
    # ... existing calculation logic ...
    
    # Cache result before returning (at end of method, before final return)
    with self._monthly_cache_lock:
        self._monthly_cache[cache_key] = (summary, time.time())
    
    return summary
```

---

## Phase 5: Refactor Endpoint Handlers

### **Step 5.1: Optimize `/status` endpoint to use background cache**

**File:** `src/log_web_server.py` at line 824

**Replace `_get_system_status()` with:**

```python
def _get_system_status(self) -> Dict[str, Any]:
    """Get system status from background cache."""
    try:
        # Read from background cache (no blocking operations)
        with self._background_cache_lock:
            coordinator_pid = self._background_cache.get('coordinator_pid')
            coordinator_running = self._background_cache.get('coordinator_running', False)
            data_source = self._background_cache.get('data_source', 'unknown')
            
            # Storage health
            storage_health = {
                'connected': self._storage_connected,
                'has_data': self._storage_has_data,
                'type': 'sqlite' if self.storage else None
            }
            
            # Background worker health
            cache_ages = {
                'inverter_s': time.time() - self._background_cache['last_inverter_refresh'],
                'price_s': time.time() - self._background_cache['last_price_refresh'],
                'metrics_s': time.time() - self._background_cache['last_metrics_refresh']
            }
            
            bg_health = 'healthy'
            if not (self._background_thread and self._background_thread.is_alive()):
                bg_health = 'failed'
            elif any(age > 600 for age in cache_ages.values()):
                bg_health = 'stale'
            
            background_worker = {
                'alive': self._background_thread.is_alive() if self._background_thread else False,
                'cache_ages': cache_ages,
                'health': bg_health,
                'last_errors': {
                    'inverter': self._background_cache['last_inverter_error'],
                    'price': self._background_cache['last_price_error'],
                    'metrics': self._background_cache['last_metrics_error']
                }
            }
        
        # Get log file info (fast - no process iteration)
        log_files = {}
        for log_file in self.log_dir.glob("*.log"):
            stat = log_file.stat()
            log_files[log_file.name] = {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
        
        return {
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'coordinator_running': coordinator_running,
            'coordinator_pid': coordinator_pid,
            'data_source': data_source,
            'log_files': log_files,
            'server_uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0,
            'server_uptime_human': format_uptime_human_readable(time.time() - self.start_time if hasattr(self, 'start_time') else 0),
            'storage': storage_health,
            'background_worker': background_worker
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        return {'status': 'error', 'error': str(e), 'timestamp': datetime.now().isoformat()}
```

---

### **Step 5.2: Modify `_get_real_inverter_data()` to use background cache**

**File:** `src/log_web_server.py` at line 3459

**Replace with:**

```python
def _get_real_inverter_data(self) -> Optional[Dict[str, Any]]:
    """Get inverter data from background cache with staleness detection."""
    try:
        # Check background cache first
        with self._background_cache_lock:
            cached_data = self._background_cache.get('inverter_data')
            last_refresh = self._background_cache.get('last_inverter_refresh', 0)
        
        if cached_data:
            cache_age = time.time() - last_refresh
            
            if cache_age < 300:  # Fresh: <5 min
                cached_data['data_source'] = 'background_cache'
                cached_data['cache_age_seconds'] = cache_age
                return cached_data
            elif cache_age < 600:  # Stale but usable: 5-10 min
                logger.warning(f"⚠️ Inverter cache stale ({cache_age:.0f}s), but returning anyway")
                cached_data['data_source'] = 'background_cache_stale'
                cached_data['cache_age_seconds'] = cache_age
                return cached_data
        
        # Cache too old or missing - fallback to direct file reading
        logger.warning("❌ Inverter background cache unavailable, falling back to file reading")
        
        # ... existing fallback logic (coordinator state files, storage layer) ...
        # Add data_source='fallback_direct' to result
        
    except Exception as e:
        logger.error(f"Error getting inverter data: {e}", exc_info=True)
        return None
```

---

### **Step 5.3: Modify `_get_real_price_data()` to use background cache**

**File:** `src/log_web_server.py` at line 3351

**Replace with:**

```python
def _get_real_price_data(self) -> Optional[Dict[str, Any]]:
    """Get price data from background cache."""
    try:
        # Check background cache first
        with self._background_cache_lock:
            cached_data = self._background_cache.get('price_data')
            last_refresh = self._background_cache.get('last_price_refresh', 0)
        
        if cached_data:
            cache_age = time.time() - last_refresh
            if cache_age < 3600:  # Fresh: <1 hour
                cached_data['data_source'] = 'background_cache'
                return cached_data
        
        # Fallback: try disk cache
        disk_data = self._load_price_from_disk()
        if disk_data:
            disk_data['data_source'] = 'disk_cache'
            return disk_data
        
        logger.warning("⚠️ Price data not available in cache, using fallback")
        return None
        
    except Exception as e:
        logger.error(f"Error getting price data: {e}", exc_info=True)
        return None
```

---

### **Step 5.4: Modify `_get_system_metrics()` to use background cache**

**File:** `src/log_web_server.py` at line 3116

**Replace with:**

```python
def _get_system_metrics(self) -> Dict[str, Any]:
    """Get metrics from background cache."""
    try:
        # Check background cache first
        with self._background_cache_lock:
            cached_data = self._background_cache.get('metrics_data')
            last_refresh = self._background_cache.get('last_metrics_refresh', 0)
        
        if cached_data:
            cache_age = time.time() - last_refresh
            if cache_age < 120:  # Fresh: <2 min
                return cached_data
        
        # Cache miss/stale - calculate directly (will be slow)
        logger.warning(f"⚠️ Metrics cache unavailable, calculating directly")
        
        # ... existing calculation logic using database ...
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        return {'error': str(e)}
```

---

### **Step 5.5: Add systemd logs caching**

**File:** `src/log_web_server.py` at line 548 in `_get_systemd_logs()`

**Add caching:**

```python
def _get_systemd_logs(self, lines: int, level: str = '') -> Response:
    """Get systemd logs with caching."""
    try:
        # Check cache
        cache_key = f'systemd_logs_{lines}_{level}'
        cached = self._get_cached_data(cache_key, ttl=15)
        if cached:
            return jsonify(cached)
        
        # ... existing systemd log reading logic ...
        
        response_dict = {
            'log_file': 'systemd-journal',
            'total_lines': len(all_lines),
            'filtered_lines': len(filtered_lines),
            'returned_lines': len(recent_lines),
            'level_filter': level,
            'lines': [line.rstrip() for line in recent_lines]
        }
        
        # Cache before returning
        self._set_cached_data(cache_key, response_dict)
        
        return jsonify(response_dict)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Phase 6: Configuration

### **Step 6.1: Add dashboard configuration to YAML**

**File:** `config/master_coordinator_config.yaml` in `web_server:` section (after line 368)

**Add:**

```yaml
# Background refresh configuration
background_refresh_interval_seconds: 30    # Inverter data (coordinator state files)
price_refresh_interval_seconds: 300        # Price data (PSE API, 5 min)
metrics_refresh_interval_seconds: 60       # Metrics data (database queries, 1 min)
coordinator_pid_check_interval_seconds: 60 # PID validation (1 min)
cache_staleness_threshold_seconds: 300     # Warn if cache older than this
api_timeout_seconds: 60                    # PSE API timeout
```

**Also add under `price_analysis:` section:**

```yaml
api_timeout_seconds: 60  # For AutomatedPriceCharger
```

---

### **Step 6.2: Configure API timeout in AutomatedPriceCharger**

**File:** `src/automated_price_charging.py`

**Changes:**

1. **Line 73** in `__init__()`:
   ```python
   self.api_timeout = self.config.get('price_analysis', {}).get('api_timeout_seconds', 10)
   ```

2. **Line 2676** in `fetch_price_data_for_date()`:
   ```python
   # Replace: timeout=10
   # With: timeout=self.api_timeout
   ```

3. **Line 1382** in `fetch_today_prices()`:
   ```python
   # Replace: timeout=30
   # With: timeout=self.api_timeout
   ```

---

## Phase 7: Graceful Shutdown

### **Step 7.1: Implement shutdown method**

**File:** `src/log_web_server.py`

Add method:

```python
def shutdown(self):
    """Gracefully shutdown background thread and storage connections."""
    logger.info("Shutting down LogWebServer...")
    
    # Signal background thread to stop
    if self._stop_background_thread:
        self._stop_background_thread.set()
    
    # Wait for background thread to finish
    if self._background_thread and self._background_thread.is_alive():
        logger.info("Waiting for background thread to stop...")
        self._background_thread.join(timeout=5.0)
        if self._background_thread.is_alive():
            logger.warning("Background thread did not stop gracefully")
        else:
            logger.info("Background thread stopped")
    
    # Disconnect main storage
    if self.storage and self._storage_connected:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.storage.disconnect())
                logger.info("Main storage disconnected")
            finally:
                loop.close()
        except Exception as e:
            logger.warning(f"Error disconnecting main storage: {e}")
    
    logger.info("LogWebServer shutdown complete")
```

---

### **Step 7.2: Integrate into stop() method**

**File:** `src/log_web_server.py` at line 2905

**Modify `stop()` to:**

```python
def stop(self):
    """Stop the web server."""
    logger.info("Stopping log web server")
    self.shutdown()  # Call graceful shutdown
    self._running = False
```

---

### **Step 7.3: Add signal handlers to start() method**

**File:** `src/log_web_server.py` at line 2888 in `start()` method

**Add signal handlers at start:**

```python
def start(self):
    """Start the web server with signal handlers."""
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    self.start_time = time.time()
    self._running = True
    logger.info(f"Starting log web server on {self.host}:{self.port}")
    
    try:
        self.app.run(host=self.host, port=self.port, debug=False, threaded=True)
    except OSError as e:
        if e.errno == 48:
            logger.error(f"Port {self.port} is already in use")
            self.shutdown()
            self._running = False
            raise RuntimeError(f"Port {self.port} is already in use") from e
        else:
            self.shutdown()
            self._running = False
            raise
```

---

## Implementation Checklist

### Phase 0: Critical Fixes (Must Complete First)
- [ ] Step 0.1: Per-thread storage instances
- [ ] Step 0.2: Background storage connection
- [ ] Step 0.3: Query timeout helper
- [ ] Step 0.4: Database health validation
- [ ] Step 0.5: Fix DailySnapshotManager event loops
- [ ] Step 0.6: Improve storage query logging

### Phase 1: Background Infrastructure
- [ ] Step 1.1: Initialize background cache
- [ ] Step 1.2: Create background refresh thread
- [ ] Step 1.3: Implement PID caching

### Phase 2: Price Persistence
- [ ] Step 2.1: Add price cache file path
- [ ] Step 2.2: Create disk cache methods

### Phase 3: Background Refresh Methods
- [ ] Step 3.1: Price data refresh
- [ ] Step 3.2: Inverter data refresh
- [ ] Step 3.3: Metrics data refresh

### Phase 4: DailySnapshotManager
- [ ] Step 4.1: Add monthly cache
- [ ] Step 4.2: Implement cache-first logic

### Phase 5: Endpoint Optimization
- [ ] Step 5.1: Optimize `/status`
- [ ] Step 5.2: Optimize `_get_real_inverter_data()`
- [ ] Step 5.3: Optimize `_get_real_price_data()`
- [ ] Step 5.4: Optimize `_get_system_metrics()`
- [ ] Step 5.5: Add systemd logs caching

### Phase 6: Configuration
- [ ] Step 6.1: Update YAML config
- [ ] Step 6.2: Configure API timeouts

### Phase 7: Graceful Shutdown
- [ ] Step 7.1: Implement shutdown method
- [ ] Step 7.2: Integrate into stop()
- [ ] Step 7.3: Add signal handlers

### Testing & Validation
- [ ] Test: Database migration status (`SELECT COUNT(*) FROM decisions`)
- [ ] Test: Background thread health monitoring via `/status`
- [ ] Test: Cache staleness detection and fallback
- [ ] Test: Concurrent request handling under load (10+ simultaneous requests)
- [ ] Test: Graceful shutdown on SIGTERM
- [ ] Test: Storage thread-safety (no "database locked" errors)
- [ ] Test: Query timeouts work correctly
- [ ] Test: Disk cache persistence survives restart

---

## Key Architecture Decisions

### Thread Safety
- **Main thread** (Flask request handlers) uses `self.storage` instance
- **Background thread** uses `self._background_storage` instance (separate SQLite connection)
- All `self._background_cache` access protected by `self._background_cache_lock`
- No shared database connections between threads

### Database-First Strategy
- Always try database queries first via storage abstraction
- Only fall back to file reading if database returns None/empty
- Clear logging distinguishes: database hit, database empty, database error, file fallback
- Storage health monitored and exposed in `/status` endpoint

### Performance Strategy
- Background thread proactively refreshes data every 30-300s
- Request handlers read from in-memory cache (<100ms)
- Cache staleness detection with warnings
- Graceful degradation on failures

### Error Handling
- All database queries wrapped in timeout (10-30s)
- All file I/O in try/except with logging
- Background thread continues after errors, stores error messages
- Endpoints always respond (cached/fallback data)

---

## Monitoring & Observability

### `/status` Endpoint Enhancements
After implementation, `/status` will include:

```json
{
  "status": "running",
  "coordinator_running": true,
  "coordinator_pid": 12345,
  "data_source": "real",
  "storage": {
    "connected": true,
    "has_data": true,
    "type": "sqlite"
  },
  "background_worker": {
    "alive": true,
    "health": "healthy",
    "cache_ages": {
      "inverter_s": 15,
      "price_s": 120,
      "metrics_s": 45
    },
    "last_errors": {
      "inverter": null,
      "price": null,
      "metrics": null
    }
  }
}
```

### Log Messages to Watch
- ✅ `DATABASE: Loaded X decisions in Yms` - Database working
- ⚠️ `DATABASE: Query returned no data - falling back to files` - Check migration
- ❌ `Storage query timeout after 10s` - Slow query or connection issue
- 📁 `FILES: Database unavailable, using file storage` - Storage initialization failed
- 💾 `Saved price data to disk cache` - Price cache persisted
- 🔄 `Background refresh thread started` - Background worker running

---

## Rollback Plan

If implementation causes issues:

1. **Disable background refresh:**
   ```yaml
   # In config/master_coordinator_config.yaml
   web_server:
     background_refresh_interval_seconds: 999999  # Effectively disable
   ```

2. **Revert to single storage instance:**
   - Comment out `self._background_storage` initialization
   - Use only `self.storage` (original behavior)

3. **Revert to file-only mode:**
   ```yaml
   data_storage:
     database_storage:
       enabled: false  # Disable database entirely
   ```

4. **Full rollback:**
   - Git revert commit
   - Restart service
   - Original 3-8s performance but stable

---

## Post-Implementation Validation

### Success Criteria
- [ ] Dashboard loads in <1 second (all endpoints combined)
- [ ] `/status` responds in <100ms consistently
- [ ] `/current-state` responds in <100ms consistently  
- [ ] `/metrics` responds in <100ms consistently
- [ ] No "database locked" errors in logs for 24 hours
- [ ] Background thread runs continuously without crashes for 24 hours
- [ ] Storage health shows `connected: true, has_data: true`
- [ ] Cache ages stay below staleness thresholds
- [ ] No memory leaks (process memory stable over 24 hours)

### Performance Baseline Comparison

| Metric | Before | Target | Actual |
|--------|--------|--------|--------|
| Dashboard load time | 18s | <1s | ___ |
| `/status` response | 8.1s | <100ms | ___ |
| `/current-state` response | 3.2s | <100ms | ___ |
| `/metrics` response | 6.0s | <100ms | ___ |
| Database queries per request | 2-3 | 0 (cached) | ___ |
| File reads per request | 50+ | 0 (cached) | ___ |

---

## Related Documentation

- Database Migration: `docs/DATABASE_MIGRATION_STATUS.md`
- Storage Abstraction: `docs/INVERTER_ABSTRACTION.md`
- Testing Guide: `docs/TESTING_GUIDE.md`
- Migration Script: `scripts/migrate_json_to_db.py`

---

**END OF PLAN**
