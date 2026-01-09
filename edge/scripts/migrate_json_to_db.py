#!/usr/bin/env python3
"""
Migration script to transfer existing JSON data to SQLite database.
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

from database.storage_factory import StorageFactory
from database.sqlite_storage import SQLiteStorage

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def migrate_energy_data(storage: SQLiteStorage, data_dir: str):
    """Migrate energy data files."""
    logger.info(f"Scanning for energy data in {data_dir}...")
    files = glob.glob(os.path.join(data_dir, "energy_data_*.json"))
    
    total_records = 0
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    continue
                
                # Process in batches
                batch_size = 100
                for i in range(0, len(data), batch_size):
                    batch = data[i:i+batch_size]
                    await storage.save_energy_data(batch)
                    
                total_records += len(data)
                logger.info(f"Migrated {len(data)} records from {os.path.basename(file_path)}")
                
        except Exception as e:
            logger.error(f"Failed to migrate {file_path}: {e}")
            
    logger.info(f"Total energy records migrated: {total_records}")

async def migrate_system_state(storage: SQLiteStorage, base_dir: str):
    """Migrate system state files."""
    logger.info(f"Scanning for system state in {base_dir}...")
    files = glob.glob(os.path.join(base_dir, "coordinator_state_*.json"))
    
    total_records = 0
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                # These files are often line-delimited JSON
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        state = json.loads(line)
                        await storage.save_system_state(state)
                        total_records += 1
                    except json.JSONDecodeError:
                        continue
                        
            logger.info(f"Migrated records from {os.path.basename(file_path)}")
                
        except Exception as e:
            logger.error(f"Failed to migrate {file_path}: {e}")
            
    logger.info(f"Total system state records migrated: {total_records}")

async def main():
    # Load config
    config_path = Path(__file__).parent.parent / "config" / "master_coordinator_config.yaml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # Initialize DB storage directly (we want to write to DB regardless of config)
    db_config = config.get('data_storage', {}).get('database_storage', {}).get('sqlite', {})
    db_path = db_config.get('path', 'data/goodwe_energy.db')
    
    # Create storage config manually
    from database.storage_interface import StorageConfig
    storage_config = StorageConfig(db_path=db_path)
    storage = SQLiteStorage(storage_config)
    
    if not await storage.connect():
        logger.error("Failed to connect to database")
        return

    try:
        # Get data directories from config
        file_config = config.get('data_storage', {}).get('file_storage', {})
        energy_dir = file_config.get('energy_data_dir', 'out/energy_data')
        base_dir = os.path.dirname(energy_dir) # Assuming standard structure
        
        await migrate_energy_data(storage, energy_dir)
        await migrate_system_state(storage, base_dir)
        
        logger.info("Migration completed successfully")
        
    finally:
        await storage.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
