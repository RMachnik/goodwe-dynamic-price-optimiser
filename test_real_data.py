#!/usr/bin/env python3
"""
Simple test to check if real data is being retrieved
"""

import sys
import requests
import json
from pathlib import Path

def test_api_response():
    """Test the API response to see if it's returning real or mock data"""
    try:
        print("🔍 Testing API Response...")
        response = requests.get('http://192.168.33.13:8080/current-state', timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"📊 Data Source: {data.get('data_source', 'unknown')}")
        print(f"📅 Timestamp: {data.get('timestamp', 'unknown')}")
        
        # Check if it's real data by looking at the data source
        if data.get('data_source') == 'real':
            print("✅ SUCCESS: API is returning REAL data!")
            
            # Show some real data values
            battery = data.get('battery', {})
            pv = data.get('pv', {})
            consumption = data.get('consumption', {})
            grid = data.get('grid', {})
            
            print(f"🔋 Battery SOC: {battery.get('soc_percent', 'N/A')}%")
            print(f"☀️  PV Power: {pv.get('power_w', 'N/A')}W")
            print(f"🏠 Consumption: {consumption.get('power_w', 'N/A')}W")
            print(f"⚡ Grid Power: {grid.get('power_w', 'N/A')}W")
            
            return True
        else:
            print(f"⚠️  API is returning {data.get('data_source', 'unknown')} data")
            print("This means the system is falling back to mock data.")
            return False
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        return False

def test_direct_inverter():
    """Test direct inverter connection"""
    try:
        print("\n🔌 Testing Direct Inverter Connection...")
        
        # Add src to path
        src_path = Path(__file__).parent / "src"
        sys.path.insert(0, str(src_path))
        
        from fast_charge import GoodWeFastCharger
        import asyncio
        
        async def test():
            config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
            charger = GoodWeFastCharger(config_path)
            
            success = await charger.connect_inverter()
            if success:
                print("✅ Direct inverter connection successful!")
                
                status = await charger.get_inverter_status()
                if status:
                    print(f"📊 Retrieved {len(status)} sensor values")
                    
                    # Show some key values
                    if 'battery_soc' in status:
                        soc = status['battery_soc'].get('value', 'N/A')
                        print(f"🔋 Battery SOC: {soc}%")
                    
                    if 'ppv' in status:
                        pv_power = status['ppv'].get('value', 'N/A')
                        print(f"☀️  PV Power: {pv_power}W")
                    
                    return True
                else:
                    print("❌ No data retrieved from inverter")
                    return False
            else:
                print("❌ Failed to connect to inverter")
                return False
        
        return asyncio.run(test())
        
    except Exception as e:
        print(f"❌ Error testing direct inverter: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Real Data Retrieval")
    print("=" * 40)
    
    # Test API response
    api_success = test_api_response()
    
    # Test direct inverter connection
    inverter_success = test_direct_inverter()
    
    print("\n📋 Results Summary")
    print("=" * 20)
    print(f"API Response: {'✅ Real Data' if api_success else '❌ Mock Data'}")
    print(f"Inverter Connection: {'✅ Working' if inverter_success else '❌ Failed'}")
    
    if not api_success and inverter_success:
        print("\n💡 Recommendation:")
        print("The inverter connection works, but the web server is not using it.")
        print("Try restarting the web server:")
        print("  pkill -f log_web_server")
        print("  python src/log_web_server.py &")
    elif not inverter_success:
        print("\n💡 Recommendation:")
        print("The inverter connection is failing. Check:")
        print("  - Inverter IP address in config")
        print("  - Network connectivity")
        print("  - Inverter power status")