#!/usr/bin/env python3
"""
Battery Selling Revenue Validation Tool

Validates monthly selling revenue calculations to detect:
- Double-counting of sessions
- Incorrect revenue factor application
- Suspiciously high implied prices

Usage:
    python scripts/validate_selling_revenue.py [year] [month]
    python scripts/validate_selling_revenue.py           # Current month
    python scripts/validate_selling_revenue.py 2025 11   # November 2025
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from daily_snapshot_manager import DailySnapshotManager

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def validate_selling_decisions(year: int, month: int) -> Dict[str, Any]:
    """Validate all selling decisions for a month"""
    
    # Load decision files directly
    project_root = Path(__file__).parent.parent
    energy_data_dir = project_root / "out" / "energy_data"
    
    # Find all selling decision files for the month
    date_prefix = f"{year}{month:02d}"
    selling_files = list(energy_data_dir.glob(f"battery_selling_decision_{date_prefix}*.json"))
    
    print(f"\n📊 Analyzing {len(selling_files)} selling decision files for {year}-{month:02d}")
    
    if not selling_files:
        print("❌ No selling decision files found")
        return {}
    
    # Parse all decisions
    all_decisions = []
    session_ids = set()
    duplicate_sessions = []
    
    for file_path in sorted(selling_files):
        try:
            with open(file_path, 'r') as f:
                decision = json.load(f)
                all_decisions.append({
                    'file': file_path.name,
                    'data': decision
                })
                
                # Check for session tracking
                session_id = decision.get('session_id')
                if session_id:
                    if session_id in session_ids:
                        duplicate_sessions.append(session_id)
                    session_ids.add(session_id)
                    
        except Exception as e:
            logger.warning(f"Error reading {file_path}: {e}")
    
    # Analyze each decision
    total_energy = 0
    total_revenue_net = 0
    total_revenue_gross = 0
    price_list = []
    
    print(f"\n🔍 Detailed Decision Analysis:")
    print("=" * 80)
    
    for idx, item in enumerate(all_decisions, 1):
        decision = item['data']
        file_name = item['file']
        
        # Extract fields
        energy = decision.get('energy_sold_kwh', decision.get('energy_kwh', 0))
        price = decision.get('selling_price_pln_kwh', decision.get('current_price', 0))
        expected_revenue = decision.get('expected_revenue_pln', 0)
        net_revenue = decision.get('net_revenue_pln')
        gross_revenue = decision.get('gross_revenue_pln')
        revenue_factor = decision.get('revenue_factor', 0.8)
        
        # Calculate gross if not provided
        if gross_revenue is None and energy > 0 and price > 0:
            gross_revenue = energy * price
        
        # Determine net revenue
        if net_revenue is not None:
            actual_net = net_revenue
        elif expected_revenue > 0:
            # Assume expected_revenue is the value to use
            actual_net = expected_revenue
        elif gross_revenue:
            actual_net = gross_revenue * revenue_factor
        else:
            actual_net = 0
        
        # Validate
        if energy > 0 and price > 0:
            implied_net_price = actual_net / energy if energy > 0 else 0
            implied_gross_price = implied_net_price / revenue_factor if revenue_factor > 0 else 0
            
            price_list.append(implied_gross_price)
            
            # Flag suspicious entries
            flag = ""
            if implied_gross_price > 2.0:
                flag = "⚠️  HIGH PRICE"
            elif implied_gross_price < 0.3:
                flag = "⚠️  LOW PRICE"
            
            print(f"{idx:3}. {file_name}")
            print(f"     Energy: {energy:6.2f} kWh | Price: {price:.3f} PLN/kWh")
            print(f"     Net Revenue: {actual_net:7.2f} PLN | Implied Price: {implied_gross_price:.3f} PLN/kWh {flag}")
            
            total_energy += energy
            total_revenue_net += actual_net
            if gross_revenue:
                total_revenue_gross += gross_revenue
        else:
            print(f"{idx:3}. {file_name} - ⚠️  Missing data")
    
    print("=" * 80)
    
    # Summary statistics
    avg_gross_price = (total_revenue_gross / total_energy) if total_energy > 0 else 0
    avg_net_price = (total_revenue_net / total_energy) if total_energy > 0 else 0
    
    validation_result = {
        'total_decisions': len(all_decisions),
        'unique_sessions': len(session_ids),
        'duplicate_sessions': duplicate_sessions,
        'total_energy_sold_kwh': round(total_energy, 2),
        'total_revenue_net_pln': round(total_revenue_net, 2),
        'total_revenue_gross_pln': round(total_revenue_gross, 2),
        'avg_gross_price_pln_kwh': round(avg_gross_price, 3),
        'avg_net_price_pln_kwh': round(avg_net_price, 3),
        'price_range': {
            'min': round(min(price_list), 3) if price_list else 0,
            'max': round(max(price_list), 3) if price_list else 0
        }
    }
    
    return validation_result


def compare_with_snapshot(year: int, month: int, validation: Dict[str, Any]):
    """Compare validation results with snapshot data"""
    
    snapshot_mgr = DailySnapshotManager()
    monthly_summary = snapshot_mgr.get_monthly_summary(year, month)
    
    print(f"\n📈 Snapshot vs Validation Comparison:")
    print("=" * 80)
    
    snapshot_energy = monthly_summary.get('total_energy_sold_kwh', 0)
    snapshot_revenue = monthly_summary.get('selling_revenue_pln', 0)
    snapshot_sessions = monthly_summary.get('selling_count', 0)
    
    validation_energy = validation['total_energy_sold_kwh']
    validation_revenue = validation['total_revenue_net_pln']
    validation_sessions = validation['total_decisions']
    
    print(f"{'Metric':<30} {'Snapshot':<15} {'Validation':<15} {'Diff':<15}")
    print("-" * 80)
    print(f"{'Energy Sold (kWh)':<30} {snapshot_energy:<15.2f} {validation_energy:<15.2f} {validation_energy - snapshot_energy:<15.2f}")
    print(f"{'Revenue (PLN)':<30} {snapshot_revenue:<15.2f} {validation_revenue:<15.2f} {validation_revenue - snapshot_revenue:<15.2f}")
    print(f"{'Sessions/Decisions':<30} {snapshot_sessions:<15} {validation_sessions:<15} {validation_sessions - snapshot_sessions:<15}")
    
    # Calculate discrepancy
    if validation_revenue > 0:
        discrepancy_pct = ((snapshot_revenue - validation_revenue) / validation_revenue) * 100
        print(f"\n{'Revenue Discrepancy:':<30} {discrepancy_pct:+.1f}%")
        
        if abs(discrepancy_pct) > 5:
            print(f"⚠️  WARNING: Significant discrepancy detected!")
            if snapshot_revenue > validation_revenue:
                multiplier = snapshot_revenue / validation_revenue
                print(f"   Snapshot shows {multiplier:.2f}x higher revenue than raw files")
                print(f"   Possible causes:")
                print(f"   - Double-counting of sessions")
                print(f"   - Incorrect aggregation logic")
                print(f"   - Using gross instead of net revenue")
        else:
            print(f"✅ Revenue calculations match within acceptable range")


def validate_monthly_revenue(year: int, month: int):
    """Main validation function"""
    
    print(f"\n{'=' * 80}")
    print(f"🔬 Battery Selling Revenue Validation")
    print(f"   Month: {year}-{month:02d}")
    print(f"{'=' * 80}")
    
    # Step 1: Validate raw decision files
    validation = validate_selling_decisions(year, month)
    
    if not validation:
        return
    
    # Step 2: Display summary
    print(f"\n📊 Summary:")
    print(f"   Total Decisions: {validation['total_decisions']}")
    print(f"   Unique Sessions: {validation['unique_sessions']}")
    print(f"   Energy Sold: {validation['total_energy_sold_kwh']:.2f} kWh")
    print(f"   Net Revenue: {validation['total_revenue_net_pln']:.2f} PLN")
    print(f"   Gross Revenue: {validation['total_revenue_gross_pln']:.2f} PLN")
    print(f"   Avg Gross Price: {validation['avg_gross_price_pln_kwh']:.3f} PLN/kWh")
    print(f"   Avg Net Price: {validation['avg_net_price_pln_kwh']:.3f} PLN/kWh")
    print(f"   Price Range: {validation['price_range']['min']:.3f} - {validation['price_range']['max']:.3f} PLN/kWh")
    
    # Step 3: Validate price sanity
    print(f"\n🔍 Sanity Checks:")
    
    avg_price = validation['avg_gross_price_pln_kwh']
    if avg_price > 2.0:
        print(f"   ❌ FAIL: Average price {avg_price:.3f} PLN/kWh is too high (market max ~1.5)")
        print(f"      This suggests revenue is being overcounted!")
    elif avg_price < 0.3:
        print(f"   ⚠️  WARNING: Average price {avg_price:.3f} PLN/kWh seems low")
    else:
        print(f"   ✅ PASS: Average price {avg_price:.3f} PLN/kWh is within normal range (0.4-1.5)")
    
    # Check for duplicate sessions
    if validation['duplicate_sessions']:
        print(f"   ⚠️  WARNING: Found {len(validation['duplicate_sessions'])} duplicate session IDs")
        print(f"      This may indicate double-counting")
    else:
        print(f"   ✅ PASS: No duplicate sessions detected")
    
    # Step 4: Compare with snapshot
    compare_with_snapshot(year, month, validation)
    
    # Step 5: Recommendations
    print(f"\n💡 Recommendations:")
    
    if validation['avg_gross_price_pln_kwh'] > 2.0:
        print(f"   1. Check snapshot calculation logic in daily_snapshot_manager.py")
        print(f"   2. Verify revenue_factor (80%) is being applied correctly")
        print(f"   3. Ensure each session is only counted once")
        print(f"   4. Regenerate snapshots: python src/daily_snapshot_manager.py create-missing 30")
    else:
        print(f"   ✅ Revenue calculations appear correct")
    
    print(f"\n{'=' * 80}\n")
    
    return validation


if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) > 2:
        year = int(sys.argv[1])
        month = int(sys.argv[2])
    elif len(sys.argv) > 1:
        # Interpret single arg as month for current year
        year = datetime.now().year
        month = int(sys.argv[1])
    else:
        # Default to current month
        now = datetime.now()
        year = now.year
        month = now.month
    
    # Run validation
    validate_monthly_revenue(year, month)
