#!/usr/bin/env python3
"""
Diagnostic script to check why the system is returning mock data instead of real data
"""

import sys
import asyncio
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_inverter_connection():
    """Test direct inverter connection"""
    print("🔌 Testing Direct Inverter Connection")
    print("=" * 50)
    
    try:
        from fast_charge import GoodWeFastCharger
        
        async def test_connection():
            config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
            charger = GoodWeFastCharger(config_path)
            
            print(f"📁 Config path: {config_path}")
            print(f"📋 Config exists: {config_path.exists()}")
            
            if not config_path.exists():
                print("❌ Config file not found!")
                return False
            
            # Test connection
            print("🔗 Attempting to connect to inverter...")
            success = await charger.connect_inverter()
            
            if success:
                print("✅ Inverter connection successful!")
                
                # Test data retrieval
                print("📊 Testing data retrieval...")
                status = await charger.get_inverter_status()
                
                if status:
                    print(f"✅ Data retrieved: {len(status)} sensor values")
                    
                    # Show some key values
                    key_sensors = ['battery_soc', 'ppv', 'house_consumption', 'meter_active_power_total']
                    for sensor in key_sensors:
                        if sensor in status:
                            value = status[sensor].get('value', 'N/A')
                            unit = status[sensor].get('unit', '')
                            print(f"  {sensor}: {value} {unit}")
                    
                    return True
                else:
                    print("❌ No data retrieved from inverter")
                    return False
            else:
                print("❌ Failed to connect to inverter")
                return False
        
        # Run the async test
        return asyncio.run(test_connection())
        
    except Exception as e:
        print(f"❌ Error testing inverter connection: {e}")
        return False

def test_web_server_data_retrieval():
    """Test the web server's data retrieval method"""
    print("\n🌐 Testing Web Server Data Retrieval")
    print("=" * 50)
    
    try:
        from log_web_server import LogWebServer
        
        # Create web server instance
        server = LogWebServer()
        
        print("🔍 Testing _get_real_inverter_data()...")
        real_data = server._get_real_inverter_data()
        
        if real_data:
            print("✅ Real data retrieved successfully!")
            print(f"📊 Data source: {real_data.get('data_source', 'unknown')}")
            print(f"📅 Timestamp: {real_data.get('timestamp', 'unknown')}")
            
            # Show key data
            battery = real_data.get('battery', {})
            pv = real_data.get('pv', {})
            consumption = real_data.get('consumption', {})
            grid = real_data.get('grid', {})
            
            print(f"🔋 Battery SOC: {battery.get('soc_percent', 'N/A')}%")
            print(f"☀️  PV Power: {pv.get('power_w', 'N/A')}W")
            print(f"🏠 Consumption: {consumption.get('power_w', 'N/A')}W")
            print(f"⚡ Grid Power: {grid.get('power_w', 'N/A')}W")
            
            return True
        else:
            print("❌ No real data retrieved")
            return False
            
    except Exception as e:
        print(f"❌ Error testing web server data retrieval: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_current_state_endpoint():
    """Test the current state endpoint"""
    print("\n📡 Testing Current State Endpoint")
    print("=" * 50)
    
    try:
        import requests
        
        response = requests.get('http://192.168.33.13:8080/current-state', timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"📊 Data source: {data.get('data_source', 'unknown')}")
        print(f"📅 Timestamp: {data.get('timestamp', 'unknown')}")
        
        # Show key data
        battery = data.get('battery', {})
        pv = data.get('pv', {})
        consumption = data.get('consumption', {})
        grid = data.get('grid', {})
        
        print(f"🔋 Battery SOC: {battery.get('soc_percent', 'N/A')}%")
        print(f"☀️  PV Power: {pv.get('power_w', 'N/A')}W")
        print(f"🏠 Consumption: {consumption.get('power_w', 'N/A')}W")
        print(f"⚡ Grid Power: {grid.get('power_w', 'N/A')}W")
        
        if data.get('data_source') == 'real':
            print("✅ Endpoint returning REAL data!")
            return True
        else:
            print(f"⚠️  Endpoint returning {data.get('data_source', 'unknown')} data")
            return False
            
    except Exception as e:
        print(f"❌ Error testing endpoint: {e}")
        return False

def check_data_files():
    """Check for recent data files"""
    print("\n📁 Checking Data Files")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    out_dir = project_root / "out"
    
    if not out_dir.exists():
        print("❌ No 'out' directory found")
        return False
    
    # Check for coordinator state files
    state_files = list(out_dir.glob("coordinator_state_*.json"))
    print(f"📄 Found {len(state_files)} coordinator state files")
    
    if state_files:
        latest_file = max(state_files, key=lambda x: x.stat().st_mtime)
        file_age = (Path(__file__).stat().st_mtime - latest_file.stat().st_mtime) / 3600
        print(f"📅 Latest file: {latest_file.name}")
        print(f"⏰ File age: {file_age:.1f} hours")
        
        if file_age < 24:
            print("✅ Recent data file found")
            return True
        else:
            print("⚠️  Data file is old")
            return False
    else:
        print("❌ No coordinator state files found")
        return False

def main():
    """Run all diagnostic tests"""
    print("🔍 GoodWe Data Source Diagnostic")
    print("=" * 60)
    
    tests = [
        ("Direct Inverter Connection", test_inverter_connection),
        ("Web Server Data Retrieval", test_web_server_data_retrieval),
        ("Current State Endpoint", test_current_state_endpoint),
        ("Data Files Check", check_data_files)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    print("\n📋 Test Results Summary")
    print("=" * 30)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if not result:
            all_passed = False
    
    print("\n🎯 Recommendations")
    print("=" * 20)
    
    if all_passed:
        print("🎉 All tests passed! The system should be returning real data.")
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        print("💡 Try restarting the master coordinator and web server:")
        print("   pkill -f master_coordinator")
        print("   pkill -f log_web_server")
        print("   # Then restart both services")

if __name__ == "__main__":
    main()