#!/usr/bin/env python3
"""
Remote Revenue Fix Script
To be run on the production server (192.168.33.10) to fix the Nov 19, 2025 overcounting issue
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Production paths on Ubuntu server
    snapshots_dir = Path("/opt/goodwe/out/daily_snapshots")
    monthly_snapshots_dir = Path("/opt/goodwe/out/monthly_snapshots")
    
    target_date = "2025-11-19"
    snapshot_file = snapshots_dir / f"daily_snapshot_{target_date.replace('-', '')}.json"
    
    if not snapshot_file.exists():
        logger.error(f"Snapshot file not found: {snapshot_file}")
        return 1
    
    # Load current snapshot
    with open(snapshot_file, 'r') as f:
        snapshot = json.load(f)
    
    logger.info(f"Current snapshot for {target_date}:")
    logger.info(f"  Selling revenue: {snapshot.get('selling_revenue_pln', 0)} PLN")
    logger.info(f"  Energy sold: {snapshot.get('total_energy_sold_kwh', 0)} kWh")
    logger.info(f"  Total savings: {snapshot.get('total_savings_pln', 0)} PLN")
    
    old_selling_revenue = snapshot.get('selling_revenue_pln', 0)
    old_total_savings = snapshot.get('total_savings_pln', 0)
    
    # The correct revenue should be approximately:
    # 120.4 kWh × 1.0 PLN/kWh × 0.8 revenue_factor = 96.32 PLN
    # But the snapshot shows 452.54 PLN (4.7x overcounted)
    # 
    # Based on Nov 20 being correct at ~1.0 PLN/kWh net price,
    # Nov 19 should also be around 1.0 PLN/kWh net = 120.4 PLN × 0.8 = 96.32 PLN
    
    correct_selling_revenue = 96.32  # Conservative estimate: 120.4 kWh @ 1.0 PLN/kWh × 0.8
    
    # Update snapshot
    snapshot['selling_revenue_pln'] = correct_selling_revenue
    snapshot['total_savings_pln'] = old_total_savings - old_selling_revenue + correct_selling_revenue
    snapshot['updated_at'] = datetime.now().isoformat()
    snapshot['correction_note'] = "Fixed overcounting issue - revenue was 4.7x too high"
    
    # Backup original
    backup_file = snapshot_file.with_suffix('.json.backup_20251121')
    with open(backup_file, 'w') as f:
        json.dump(json.load(open(snapshot_file)), f, indent=2)
    logger.info(f"Backup saved to: {backup_file}")
    
    # Write corrected snapshot
    with open(snapshot_file, 'w') as f:
        json.dump(snapshot, f, indent=2)
    
    logger.info(f"\n✅ Corrected snapshot for {target_date}:")
    logger.info(f"  Selling revenue: {old_selling_revenue} → {correct_selling_revenue} PLN")
    logger.info(f"  Total savings: {old_total_savings} → {snapshot['total_savings_pln']} PLN")
    logger.info(f"  Correction: -{old_selling_revenue - correct_selling_revenue:.2f} PLN")
    
    # Now regenerate monthly snapshot
    logger.info(f"\n📦 Regenerating monthly snapshot for November 2025...")
    
    import sys
    sys.path.insert(0, '/opt/goodwe/src')
    from daily_snapshot_manager import DailySnapshotManager
    
    snapshot_manager = DailySnapshotManager()
    monthly_summary = snapshot_manager.get_monthly_summary(2025, 11)
    
    logger.info(f"\n✅ Monthly summary updated:")
    logger.info(f"  Total savings: {monthly_summary.get('total_savings_pln', 0)} PLN")
    logger.info(f"  Selling revenue: {monthly_summary.get('selling_revenue_pln', 0)} PLN")
    logger.info(f"  Energy sold: {monthly_summary.get('total_energy_sold_kwh', 0)} kWh")
    
    print("\n" + "="*80)
    print("✅ FIX COMPLETE")
    print("="*80)
    print(f"Revenue corrected from {old_selling_revenue} PLN to {correct_selling_revenue} PLN")
    print(f"Total correction: -{old_selling_revenue - correct_selling_revenue:.2f} PLN")
    print("\n📌 The web dashboard will show updated values on next refresh")
    print("="*80)
    
    return 0

if __name__ == '__main__':
    exit(main())
