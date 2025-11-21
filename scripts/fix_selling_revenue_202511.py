#!/usr/bin/env python3
"""
Fix the selling revenue overcounting issue for November 2025
Specifically targeting Nov 19 which shows 3.759 PLN/kWh (should be ~0.94 PLN/kWh)
"""

import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_selling_decisions_for_date(energy_data_dir: Path, target_date: str) -> Dict[str, Any]:
    """Analyze all selling decisions for a specific date"""
    
    # Find all battery_selling_decision files for the date
    pattern = f"battery_selling_decision_{target_date.replace('-', '')}*.json"
    selling_files = list(energy_data_dir.glob(pattern))
    
    logger.info(f"Found {len(selling_files)} selling decision files for {target_date}")
    
    if not selling_files:
        return {
            'date': target_date,
            'file_count': 0,
            'sessions': 0,
            'energy_sold_kwh': 0,
            'gross_revenue_pln': 0,
            'net_revenue_pln': 0
        }
    
    sessions = []
    total_energy = 0
    total_gross_revenue = 0  # Before revenue_factor
    total_net_revenue = 0    # After revenue_factor (expected_revenue_pln)
    
    for filepath in sorted(selling_files):
        try:
            with open(filepath, 'r') as f:
                decision = json.load(f)
            
            # Only count actual selling decisions
            if decision.get('decision') != 'start_selling':
                continue
            
            energy_sold = decision.get('energy_sold_kwh', 0)
            expected_revenue = decision.get('expected_revenue_pln', 0)
            revenue_per_kwh = decision.get('revenue_per_kwh_pln', decision.get('current_price_pln', 0))
            
            # Calculate gross revenue (before revenue_factor)
            gross_revenue = energy_sold * revenue_per_kwh
            
            sessions.append({
                'filename': filepath.name,
                'timestamp': decision.get('timestamp'),
                'energy_sold_kwh': energy_sold,
                'price_pln_kwh': revenue_per_kwh,
                'gross_revenue_pln': gross_revenue,
                'expected_revenue_pln': expected_revenue,
                'implied_factor': expected_revenue / gross_revenue if gross_revenue > 0 else 0
            })
            
            total_energy += energy_sold
            total_gross_revenue += gross_revenue
            total_net_revenue += expected_revenue
            
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
    
    return {
        'date': target_date,
        'file_count': len(selling_files),
        'sessions': sessions,
        'session_count': len(sessions),
        'total_energy_sold_kwh': round(total_energy, 2),
        'total_gross_revenue_pln': round(total_gross_revenue, 2),
        'total_net_revenue_pln': round(total_net_revenue, 2),
        'implied_avg_price': round(total_gross_revenue / total_energy, 4) if total_energy > 0 else 0,
        'implied_net_price': round(total_net_revenue / total_energy, 4) if total_energy > 0 else 0
    }

def fix_daily_snapshot(snapshots_dir: Path, target_date: str, correct_revenue: float, correct_energy: float, session_count: int):
    """Fix the daily snapshot for the given date"""
    
    snapshot_file = snapshots_dir / f"daily_snapshot_{target_date.replace('-', '')}.json"
    
    if not snapshot_file.exists():
        logger.error(f"Snapshot file not found: {snapshot_file}")
        return False
    
    try:
        with open(snapshot_file, 'r') as f:
            snapshot = json.load(f)
        
        logger.info(f"\nCurrent snapshot for {target_date}:")
        logger.info(f"  Selling revenue: {snapshot.get('selling_revenue_pln', 0)} PLN")
        logger.info(f"  Energy sold: {snapshot.get('total_energy_sold_kwh', 0)} kWh")
        logger.info(f"  Selling count: {snapshot.get('selling_count', 0)}")
        
        # Update the values
        old_revenue = snapshot.get('selling_revenue_pln', 0)
        old_savings = snapshot.get('total_savings_pln', 0)
        
        snapshot['selling_revenue_pln'] = round(correct_revenue, 2)
        snapshot['total_energy_sold_kwh'] = round(correct_energy, 2)
        snapshot['selling_count'] = session_count
        
        # Update total_savings (subtract old revenue, add new revenue)
        snapshot['total_savings_pln'] = round(old_savings - old_revenue + correct_revenue, 2)
        
        # Backup original
        backup_file = snapshot_file.with_suffix('.json.backup')
        with open(backup_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        # Write corrected snapshot
        with open(snapshot_file, 'w') as f:
            json.dump(snapshot, f, indent=2)
        
        logger.info(f"\n✅ Fixed snapshot for {target_date}:")
        logger.info(f"  Selling revenue: {old_revenue} → {correct_revenue} PLN")
        logger.info(f"  Total savings: {old_savings} → {snapshot['total_savings_pln']} PLN")
        logger.info(f"  Backup saved to: {backup_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fixing snapshot: {e}")
        return False

def main():
    # Paths
    project_root = Path(__file__).parent.parent
    energy_data_dir = project_root / "out" / "energy_data"
    snapshots_dir = project_root / "out" / "daily_snapshots"
    
    if not energy_data_dir.exists():
        logger.error(f"Energy data directory not found: {energy_data_dir}")
        return
    
    print("\n" + "="*80)
    print("🔧 Battery Selling Revenue Fix Tool")
    print("="*80)
    
    # Analyze Nov 19 (the problematic date)
    target_date = "2025-11-19"
    logger.info(f"\n📊 Analyzing selling decisions for {target_date}...")
    
    analysis = analyze_selling_decisions_for_date(energy_data_dir, target_date)
    
    print(f"\n📈 Analysis Results for {target_date}:")
    print(f"  Decision files: {analysis['file_count']}")
    print(f"  Selling sessions: {analysis['session_count']}")
    print(f"  Total energy sold: {analysis['total_energy_sold_kwh']} kWh")
    print(f"  Gross revenue (100%): {analysis['total_gross_revenue_pln']} PLN")
    print(f"  Net revenue (80%): {analysis['total_net_revenue_pln']} PLN")
    print(f"  Implied avg price: {analysis['implied_avg_price']} PLN/kWh")
    print(f"  Implied net price: {analysis['implied_net_price']} PLN/kWh")
    
    if analysis['session_count'] > 0:
        print(f"\n📋 Session Details:")
        for i, session in enumerate(analysis['sessions'][:10], 1):
            print(f"  {i}. {session['timestamp']}: {session['energy_sold_kwh']:.2f} kWh @ {session['price_pln_kwh']:.4f} PLN/kWh")
            print(f"     Gross: {session['gross_revenue_pln']:.2f} PLN, Net: {session['expected_revenue_pln']:.2f} PLN (factor: {session['implied_factor']:.2f})")
    
    # Check current snapshot
    print(f"\n📦 Checking current snapshot...")
    snapshot_file = snapshots_dir / f"daily_snapshot_{target_date.replace('-', '')}.json"
    if snapshot_file.exists():
        with open(snapshot_file, 'r') as f:
            snapshot = json.load(f)
        
        snapshot_revenue = snapshot.get('selling_revenue_pln', 0)
        snapshot_energy = snapshot.get('total_energy_sold_kwh', 0)
        
        print(f"  Snapshot revenue: {snapshot_revenue} PLN")
        print(f"  Snapshot energy: {snapshot_energy} kWh")
        print(f"  Snapshot implied price: {snapshot_revenue / snapshot_energy if snapshot_energy > 0 else 0:.4f} PLN/kWh")
        
        # Check if fix is needed
        if abs(snapshot_revenue - analysis['total_net_revenue_pln']) > 0.01:
            print(f"\n⚠️  MISMATCH DETECTED!")
            print(f"  Expected revenue: {analysis['total_net_revenue_pln']} PLN")
            print(f"  Snapshot shows: {snapshot_revenue} PLN")
            print(f"  Difference: {snapshot_revenue - analysis['total_net_revenue_pln']:.2f} PLN")
            
            response = input(f"\n🔧 Apply fix to {target_date} snapshot? (yes/no): ")
            if response.lower() == 'yes':
                if fix_daily_snapshot(snapshots_dir, target_date, analysis['total_net_revenue_pln'], 
                                     analysis['total_energy_sold_kwh'], analysis['session_count']):
                    print("\n✅ Snapshot fixed successfully!")
                    print("\n📌 Next steps:")
                    print("  1. Regenerate monthly snapshot: python src/daily_snapshot_manager.py create-missing 30")
                    print("  2. Restart web server to see corrected values")
                else:
                    print("\n❌ Failed to fix snapshot")
            else:
                print("\n❌ Fix cancelled")
        else:
            print(f"\n✅ Snapshot is correct!")
    else:
        print(f"  ❌ Snapshot file not found: {snapshot_file}")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
