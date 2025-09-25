#!/usr/bin/env python3
"""
Python script to commit the changes using subprocess
"""

import subprocess
import sys
import os

def run_command(cmd, cwd=None):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    """Main function to commit changes"""
    project_dir = "/home/rmachnik/sources/goodwe-dynamic-price-optimiser"
    
    print("📝 Committing fixes for real data retrieval and UI JavaScript errors...")
    print("=" * 70)
    
    # Check git status
    print("🔍 Checking git status...")
    success, stdout, stderr = run_command("git status", cwd=project_dir)
    if success:
        print(stdout)
    else:
        print(f"❌ Error checking git status: {stderr}")
        return False
    
    # Add files
    files_to_add = [
        "src/fast_charge.py",
        "src/log_web_server.py", 
        "test_inverter_connection.py",
        "diagnose_data_sources.py",
        "test_real_data.py",
        "restart_and_test.sh"
    ]
    
    print("\n📋 Adding files to git...")
    for file in files_to_add:
        success, stdout, stderr = run_command(f"git add {file}", cwd=project_dir)
        if success:
            print(f"✅ Added {file}")
        else:
            print(f"❌ Failed to add {file}: {stderr}")
    
    # Commit
    commit_message = """Fix real data retrieval and UI JavaScript errors

🔧 Real Data Retrieval Fix:
- Fixed import path error in _get_real_inverter_data() method
- Changed 'from src.fast_charge import GoodWeFastCharger' to 'from fast_charge import GoodWeFastCharger'
- Added robust path resolution to ensure src directory is in Python path
- System now successfully retrieves real inverter data instead of falling back to mock data

🖥️ UI JavaScript Error Fix:
- Fixed 'Cannot read properties of undefined (reading current_power_w)' error
- Added current_power_w aliases to API response for frontend compatibility
- Added missing flow_direction property to grid data
- Ensured consistent data structure across all data sources

🔌 Inverter Connection Improvements:
- Enhanced error handling with retry logic for inverter connections
- Added automatic reconnection when connection is lost
- Improved logging with attempt tracking
- Added ensure_connection() method for robust connection management

🧪 Testing and Diagnostics:
- Updated test_inverter_connection.py to use correct goodwe.connect() method
- Added diagnose_data_sources.py for comprehensive data source testing
- Added test_real_data.py for simple real data verification
- Added restart_and_test.sh script for easy service restart and testing

These fixes resolve the core issue where the system was returning mock data
instead of real inverter data, and eliminate JavaScript errors in the web dashboard."""
    
    print("\n🚀 Committing changes...")
    success, stdout, stderr = run_command(f'git commit -m "{commit_message}"', cwd=project_dir)
    if success:
        print("✅ Commit successful!")
        print(stdout)
    else:
        print(f"❌ Commit failed: {stderr}")
        return False
    
    # Show commit details
    print("\n📊 Commit details:")
    success, stdout, stderr = run_command("git log --oneline -1", cwd=project_dir)
    if success:
        print(stdout)
    else:
        print(f"❌ Error showing commit details: {stderr}")
    
    print("\n🎉 All changes have been committed successfully!")
    print("\n🌿 To push to remote repository:")
    print("   git push origin main")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)