#!/usr/bin/env python3
"""
Enhanced migration script to transfer existing JSON data to SQLite database.
Handles: charging decisions, battery selling decisions, and coordinator state files.
"""

import asyncio
import json
import os
import glob
import logging
from datetime import datetime
from pathlib import Path
import yaml
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from database.sqlite_storage import SQLiteStorage
from database.storage_interface import StorageConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def migrate_coordinator_decisions(storage: SQLiteStorage, data_dir: str):
    """Migrate charging and battery selling decision files."""
    logger.info(f"Scanning for decision files in {data_dir}...")
    
    # Find all decision files
    charging_files = glob.glob(os.path.join(data_dir, "charging_decision_*.json"))
    selling_files = glob.glob(os.path.join(data_dir, "battery_selling_decision_*.json"))
    
    total_records = 0
    
    # Migrate charging decisions
    for file_path in sorted(charging_files):
        try:
            with open(file_path, 'r') as f:
                decision = json.load(f)
                
                # Prepare decision record
                record = {
                    'timestamp': decision.get('timestamp'),
                    'decision_type': 'charging',
                    'action': decision.get('action'),
                    'reason': decision.get('reason'),
                    'confidence': decision.get('confidence', 0.0),
                    'battery_soc': decision.get('battery_soc'),
                    'current_price': decision.get('current_price'),
                    'estimated_cost': decision.get('estimated_cost_pln', 0.0),
                    'estimated_savings': decision.get('estimated_savings_pln', 0.0),
                    'metadata': json.dumps({
                        'source': decision.get('source'),
                        'duration': decision.get('duration'),
                        'energy_kwh': decision.get('energy_kwh'),
                        'priority': decision.get('priority'),
                        'pv_power': decision.get('pv_power'),
                        'house_consumption': decision.get('house_consumption'),
                        'cheapest_price': decision.get('cheapest_price'),
                        'cheapest_hour': decision.get('cheapest_hour')
                    })
                }
                
                await storage.save_decision(record)
                total_records += 1
                
                if total_records % 100 == 0:
                    logger.info(f"Migrated {total_records} charging decisions...")
                
        except Exception as e:
            logger.error(f"Failed to migrate {file_path}: {e}")
    
    logger.info(f"Total charging decisions migrated: {total_records}")
    
    # Migrate battery selling decisions
    selling_records = 0
    for file_path in sorted(selling_files):
        try:
            with open(file_path, 'r') as f:
                decision = json.load(f)
                
                # Prepare decision record
                record = {
                    'timestamp': decision.get('timestamp'),
                    'decision_type': 'battery_selling',
                    'action': decision.get('action'),
                    'reason': decision.get('reason'),
                    'confidence': decision.get('confidence', 0.0),
                    'battery_soc': decision.get('battery_soc'),
                    'current_price': decision.get('current_price'),
                    'estimated_cost': 0.0,
                    'estimated_savings': decision.get('estimated_revenue_pln', 0.0),
                    'metadata': json.dumps({
                        'source': decision.get('source'),
                        'duration': decision.get('duration'),
                        'energy_kwh': decision.get('energy_kwh'),
                        'priority': decision.get('priority'),
                        'pv_power': decision.get('pv_power'),
                        'house_consumption': decision.get('house_consumption')
                    })
                }
                
                await storage.save_decision(record)
                selling_records += 1
                
                if selling_records % 100 == 0:
                    logger.info(f"Migrated {selling_records} selling decisions...")
                
        except Exception as e:
            logger.error(f"Failed to migrate {file_path}: {e}")
    
    logger.info(f"Total battery selling decisions migrated: {selling_records}")
    return total_records + selling_records

async def migrate_system_state(storage: SQLiteStorage, base_dir: str):
    """Migrate system state files."""
    logger.info(f"Scanning for system state in {base_dir}...")
    files = glob.glob(os.path.join(base_dir, "coordinator_state_*.json"))
    
    total_records = 0
    for file_path in sorted(files):
        try:
            with open(file_path, 'r') as f:
                state = json.load(f)
                
                # Prepare state record
                record = {
                    'timestamp': state.get('timestamp'),
                    'state': state.get('state', 'unknown'),
                    'uptime_seconds': state.get('uptime_seconds', 0),
                    'active_modules': json.dumps(state.get('current_data', {}).get('system', {})),
                    'performance_metrics': json.dumps(state.get('performance_metrics', {})),
                    'metadata': json.dumps({
                        'decision_count': state.get('decision_count', 0),
                        'battery': state.get('current_data', {}).get('battery', {}),
                        'pv': state.get('current_data', {}).get('photovoltaic', {}),
                        'grid': state.get('current_data', {}).get('grid', {}),
                        'house': state.get('current_data', {}).get('house_consumption', {})
                    })
                }
                
                await storage.save_system_state(record)
                total_records += 1
                
                if total_records % 10 == 0:
                    logger.info(f"Migrated {total_records} system states...")
                    
        except Exception as e:
            logger.error(f"Failed to migrate {file_path}: {e}")
            
    logger.info(f"Total system state records migrated: {total_records}")
    return total_records

async def main():
    logger.info("=" * 60)
    logger.info("Historical Data Migration Script")
    logger.info("=" * 60)
    
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # Get database path from config
    db_config = config.get('data_storage', {}).get('database_storage', {}).get('sqlite', {})
    db_path = db_config.get('path', 'data/goodwe_energy.db')
    
    # Make path absolute if relative
    if not os.path.isabs(db_path):
        db_path = str(Path(__file__).parent.parent / db_path)
    
    logger.info(f"Database path: {db_path}")
    
    # Create storage instance with StorageConfig
    storage_config = StorageConfig(
        db_path=db_path,
        connection_pool_size=5,
        max_retries=3,
        retry_delay=0.1
    )
    storage = SQLiteStorage(storage_config)
    
    try:
        logger.info("Connecting to database...")
        await storage.connect()
        logger.info("Connected successfully!")
        
        # Get data directories from config
        file_config = config.get('data_storage', {}).get('file_storage', {})
        energy_dir = file_config.get('energy_data_dir', 'out/energy_data')
        system_state_dir = file_config.get('system_state_dir', 'out/system_state')
        
        # Make paths absolute if relative
        if not os.path.isabs(energy_dir):
            energy_dir = str(Path(__file__).parent.parent / energy_dir)
        if not os.path.isabs(system_state_dir):
            system_state_dir = str(Path(__file__).parent.parent / system_state_dir)
        
        logger.info(f"Energy data directory: {energy_dir}")
        logger.info(f"System state directory: {system_state_dir}")
        
        # Check if directories exist
        if not os.path.exists(energy_dir):
            logger.error(f"Energy data directory not found: {energy_dir}")
            return
        
        start_time = datetime.now()
        
        # Migrate coordinator decisions
        logger.info("\n--- Migrating Coordinator Decisions ---")
        decisions_count = await migrate_coordinator_decisions(storage, energy_dir)
        
        # Migrate system states
        logger.info("\n--- Migrating System States ---")
        states_count = await migrate_system_state(storage, system_state_dir)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Migration Summary:")
        logger.info(f"  Coordinator Decisions: {decisions_count}")
        logger.info(f"  System States: {states_count}")
        logger.info(f"  Total Records: {decisions_count + states_count}")
        logger.info(f"  Time Elapsed: {elapsed:.2f} seconds")
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        
    finally:
        await storage.disconnect()
        logger.info("Database connection closed")

if __name__ == "__main__":
    asyncio.run(main())
