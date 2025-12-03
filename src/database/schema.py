
# SQL Schema Definitions for GoodWe Dynamic Price Optimiser

SCHEMA_VERSION = 2  # Increment when schema changes

# Table: schema_version
# Tracks database schema version for migrations
CREATE_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
"""

# Table: energy_data
# Stores high-frequency energy readings (every 5 mins or less)
CREATE_ENERGY_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS energy_data (
    timestamp TEXT PRIMARY KEY,
    battery_soc REAL,
    pv_power INTEGER,
    grid_power INTEGER,
    house_consumption INTEGER,
    battery_power INTEGER,
    grid_voltage REAL,
    grid_frequency REAL,
    battery_voltage REAL,
    battery_current REAL,
    battery_temperature REAL,
    price_pln REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Table: system_state
# Stores the state of the MasterCoordinator
CREATE_SYSTEM_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS system_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    state TEXT,
    uptime REAL,
    active_modules TEXT,
    last_error TEXT,
    metrics TEXT,  -- JSON stored as text
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Table: coordinator_decisions
# Stores decisions made by the system (charging, discharging, idle)
CREATE_DECISIONS_TABLE = """
CREATE TABLE IF NOT EXISTS coordinator_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    decision_type TEXT,
    action TEXT,
    reason TEXT,
    parameters TEXT, -- JSON stored as text
    source_module TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Table: charging_sessions
# Stores planned and executed charging sessions
CREATE_CHARGING_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS charging_sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    target_soc INTEGER,
    energy_kwh REAL,
    cost_pln REAL,
    status TEXT,
    avg_price REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Table: battery_selling_sessions
# Stores battery selling events
CREATE_SELLING_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS battery_selling_sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    energy_sold_kwh REAL,
    revenue_pln REAL,
    avg_price REAL,
    status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Table: weather_data
# Stores weather observations and forecasts
CREATE_WEATHER_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS weather_data (
    timestamp TEXT NOT NULL,
    source TEXT,
    temperature REAL,
    humidity REAL,
    pressure REAL,
    wind_speed REAL,
    wind_direction REAL,
    cloud_cover REAL,
    solar_irradiance REAL,
    precipitation REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (timestamp)
);
"""

# Table: price_forecasts
# Stores electricity price forecasts
CREATE_PRICE_FORECASTS_TABLE = """
CREATE TABLE IF NOT EXISTS price_forecasts (
    timestamp TEXT NOT NULL,
    forecast_date TEXT NOT NULL,
    hour INTEGER,
    price_pln REAL,
    source TEXT,
    confidence REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (forecast_date, hour, source)
);
"""

# Table: pv_forecasts
# Stores PV power generation forecasts
CREATE_PV_FORECASTS_TABLE = """
CREATE TABLE IF NOT EXISTS pv_forecasts (
    timestamp TEXT NOT NULL,
    forecast_date TEXT NOT NULL,
    hour INTEGER,
    predicted_power_w REAL,
    source TEXT,
    confidence REAL,
    weather_conditions TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (forecast_date, hour, source)
);
"""

# Indexes for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_energy_timestamp ON energy_data(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_state_timestamp ON system_state(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON coordinator_decisions(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_start ON charging_sessions(start_time);",
    "CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_data(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_forecasts(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_pv_timestamp ON pv_forecasts(timestamp);"
]

ALL_TABLES = [
    CREATE_SCHEMA_VERSION_TABLE,  # Must be first for migrations to work
    CREATE_ENERGY_DATA_TABLE,
    CREATE_SYSTEM_STATE_TABLE,
    CREATE_DECISIONS_TABLE,
    CREATE_CHARGING_SESSIONS_TABLE,
    CREATE_SELLING_SESSIONS_TABLE,
    CREATE_WEATHER_DATA_TABLE,
    CREATE_PRICE_FORECASTS_TABLE,
    CREATE_PV_FORECASTS_TABLE
]

# Migration definitions
# Each migration is a tuple: (version, description, list of SQL statements)
# Migrations are applied in order for versions > current db version
MIGRATIONS = [
    # Version 1: Initial schema (no migration needed, tables created via ALL_TABLES)
    (1, "Initial schema", []),
    
    # Version 2: Add price snapshot fields to coordinator_decisions parameters
    # No schema change needed - parameters is JSON field that stores dynamic data
    # This migration just marks that the code now saves additional fields
    (2, "Add price snapshot fields (current_price_pln, energy_kwh, costs) to decisions", []),
]
