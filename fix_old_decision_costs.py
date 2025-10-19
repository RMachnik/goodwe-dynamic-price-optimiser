#!/usr/bin/env python3
"""
Fix old decision files that have incorrect costs (1000x too low)
This script multiplies estimated_cost_pln by 1000 to correct the bug
"""

import json
import glob
from pathlib import Path
import shutil
from datetime import datetime

# Directories
project_root = Path(__file__).parent
energy_data_dir = project_root / "out" / "energy_data"
backup_dir = project_root / "out" / "energy_data_backup"

def main():
    # Create backup directory
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"🔧 Fixing old decision files with incorrect costs...")
    print(f"📂 Directory: {energy_data_dir}")
    print(f"💾 Backup: {backup_dir}")
    print()
    
    # Find all charging decision files
    decision_files = list(energy_data_dir.glob("charging_decision_*.json"))
    
    if not decision_files:
        print("❌ No decision files found!")
        return
    
    print(f"Found {len(decision_files)} decision files")
    print()
    
    fixed_count = 0
    skipped_count = 0
    
    for file_path in sorted(decision_files):
        try:
            # Read the file
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check if it's a charge decision with cost data
            if data.get('action') != 'charge':
                skipped_count += 1
                continue
            
            old_cost = data.get('estimated_cost_pln', 0)
            energy_kwh = data.get('energy_kwh', 0)
            
            # Skip if no cost or energy
            if old_cost == 0 or energy_kwh == 0:
                skipped_count += 1
                continue
            
            # Calculate what the cost should be based on current_price
            current_price = data.get('current_price', 0)
            if current_price > 0:
                expected_cost = energy_kwh * current_price
                ratio = old_cost / expected_cost if expected_cost > 0 else 0
                
                # If the cost is suspiciously low (less than 1% of expected), fix it
                if ratio < 0.01:
                    # Backup original file
                    backup_file = backup_dir / f"{file_path.stem}_{backup_timestamp}.json"
                    shutil.copy2(file_path, backup_file)
                    
                    # Fix the cost (multiply by 1000)
                    new_cost = old_cost * 1000
                    data['estimated_cost_pln'] = new_cost
                    
                    # Also recalculate savings
                    reference_price = 0.4  # PLN/kWh
                    reference_cost = energy_kwh * reference_price
                    data['estimated_savings_pln'] = max(0, reference_cost - new_cost)
                    
                    # Write back to file
                    with open(file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    print(f"✅ Fixed: {file_path.name}")
                    print(f"   Energy: {energy_kwh:.2f} kWh, Price: {current_price:.4f} PLN/kWh")
                    print(f"   Old cost: {old_cost:.6f} PLN → New cost: {new_cost:.4f} PLN")
                    fixed_count += 1
                else:
                    # Cost seems correct, skip
                    skipped_count += 1
            else:
                skipped_count += 1
                
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
    
    print()
    print(f"📊 Summary:")
    print(f"   Fixed: {fixed_count} files")
    print(f"   Skipped: {skipped_count} files (wait decisions or already correct)")
    print(f"   Backup location: {backup_dir}")
    print()
    print("✅ Done! Restart the dashboard to see corrected values.")

if __name__ == '__main__':
    main()

