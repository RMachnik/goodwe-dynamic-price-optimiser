#!/usr/bin/env python3
"""
Comprehensive charging diagnosis script
"""

import sys
import asyncio
import json
import requests
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_current_status():
    """Check current system status via API"""
    try:
        response = requests.get('http://192.168.33.13:8080/current-state', timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        return None

def check_charging_controller():
    """Check charging controller status"""
    try:
        from automated_price_charging import AutomatedPriceCharger
        
        print("🔧 CHARGING CONTROLLER STATUS:")
        print("-" * 40)
        
        # Initialize charging controller
        config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
        controller = AutomatedPriceCharger(config_path)
        
        # Check if controller is working
        print("✅ Charging controller initialized successfully")
        
        # Check price data
        price_data = controller.fetch_price_data_for_date(datetime.now().strftime('%Y-%m-%d'))
        if price_data:
            print(f"✅ Price data available: {len(price_data)} price points")
            current_price = price_data[0].final_price_pln if price_data else 0
            print(f"💰 Current price: {current_price:.4f} PLN/kWh")
        else:
            print("❌ No price data available")
        
        return True
        
    except Exception as e:
        print(f"❌ Charging controller error: {e}")
        return False

def check_fast_charger():
    """Check fast charger status"""
    try:
        from fast_charge import GoodWeFastCharger
        
        print("\n🔌 FAST CHARGER STATUS:")
        print("-" * 30)
        
        config_path = Path(__file__).parent / "config" / "master_coordinator_config.yaml"
        charger = GoodWeFastCharger(config_path)
        
        async def test_charger():
            # Test connection
            success = await charger.connect_inverter()
            if success:
                print("✅ Inverter connection successful")
                
                # Get charging status
                status = await charger.get_charging_status()
                print(f"📊 Charging status: {status}")
                
                # Check if fast charging is enabled
                try:
                    fast_charging_enabled = await charger.inverter.read_setting('fast_charging')
                    print(f"⚡ Fast charging enabled: {fast_charging_enabled}")
                except:
                    print("⚠️  Could not read fast charging setting")
                
                return True
            else:
                print("❌ Inverter connection failed")
                return False
        
        return asyncio.run(test_charger())
        
    except Exception as e:
        print(f"❌ Fast charger error: {e}")
        return False

def check_safety_conditions():
    """Check safety conditions for charging"""
    print("\n🛡️  SAFETY CONDITIONS:")
    print("-" * 25)
    
    data = check_current_status()
    if not data:
        print("❌ Cannot check safety conditions - no data available")
        return False
    
    battery = data.get('battery', {})
    
    # Check battery SOC
    soc = battery.get('soc_percent', 0)
    if soc < 5:
        print("🚨 CRITICAL: Battery SOC < 5% - immediate charging required!")
        return False
    elif soc < 12:
        print("⚠️  WARNING: Battery SOC < 12% - charging recommended")
    else:
        print(f"✅ Battery SOC OK: {soc}%")
    
    # Check battery temperature
    temp = battery.get('temperature', 0)
    if temp > 50:
        print(f"🚨 CRITICAL: Battery temperature too high: {temp}°C")
        return False
    elif temp > 45:
        print(f"⚠️  WARNING: Battery temperature high: {temp}°C")
    else:
        print(f"✅ Battery temperature OK: {temp}°C")
    
    # Check battery voltage
    voltage = battery.get('voltage', 0)
    if voltage < 320:
        print(f"🚨 CRITICAL: Battery voltage too low: {voltage}V")
        return False
    elif voltage > 480:
        print(f"🚨 CRITICAL: Battery voltage too high: {voltage}V")
        return False
    else:
        print(f"✅ Battery voltage OK: {voltage}V")
    
    return True

def check_charging_thresholds():
    """Check charging decision thresholds"""
    print("\n📊 CHARGING THRESHOLDS:")
    print("-" * 25)
    
    data = check_current_status()
    if not data:
        print("❌ Cannot check thresholds - no data available")
        return
    
    battery = data.get('battery', {})
    pricing = data.get('pricing', {})
    
    soc = battery.get('soc_percent', 0)
    current_price = pricing.get('current_price_pln_kwh', 0)
    
    print(f"🔋 Current SOC: {soc}%")
    print(f"💰 Current Price: {current_price:.4f} PLN/kWh")
    
    # Check thresholds from config
    if soc < 12:
        print("🚨 CRITICAL THRESHOLD: SOC < 12% - should charge immediately")
    elif soc < 40:
        print("⚠️  LOW THRESHOLD: SOC < 40% - charge during low prices")
    elif soc < 70:
        print("ℹ️  MEDIUM THRESHOLD: SOC < 70% - charge during very low prices")
    else:
        print("✅ HIGH SOC: SOC ≥ 70% - charging not needed")
    
    if current_price < 0.3:
        print("💰 VERY LOW PRICE: < 0.3 PLN/kWh - excellent for charging")
    elif current_price < 0.5:
        print("💰 LOW PRICE: < 0.5 PLN/kWh - good for charging")
    elif current_price < 0.7:
        print("💰 MEDIUM PRICE: < 0.7 PLN/kWh - acceptable for charging")
    else:
        print("💰 HIGH PRICE: ≥ 0.7 PLN/kWh - avoid charging unless critical")

def check_recent_logs():
    """Check recent logs for charging decisions"""
    print("\n📋 RECENT LOGS:")
    print("-" * 15)
    
    try:
        log_file = Path(__file__).parent / "logs" / "master_coordinator.log"
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-30:] if len(lines) >= 30 else lines
            
            charging_related = []
            for line in recent_lines:
                if any(keyword in line.lower() for keyword in ['charging', 'decision', 'start', 'stop', 'battery']):
                    charging_related.append(line.strip())
            
            if charging_related:
                print("Recent charging-related log entries:")
                for line in charging_related[-10:]:  # Show last 10
                    print(f"  {line}")
            else:
                print("No recent charging-related log entries found")
        else:
            print("❌ Master coordinator log file not found")
    except Exception as e:
        print(f"❌ Error reading logs: {e}")

def main():
    """Main diagnostic function"""
    print("🔋 COMPREHENSIVE CHARGING DIAGNOSIS")
    print("=" * 50)
    
    # Check current status
    data = check_current_status()
    if data:
        print(f"📊 Data Source: {data.get('data_source', 'unknown')}")
        print(f"📅 Timestamp: {data.get('timestamp', 'unknown')}")
        
        battery = data.get('battery', {})
        print(f"🔋 Battery SOC: {battery.get('soc_percent', 'N/A')}%")
        print(f"⚡ Battery Power: {battery.get('power', 'N/A')}W")
        print(f"🔌 Charging Status: {battery.get('charging_status', 'N/A')}")
    
    # Run all checks
    checks = [
        ("Charging Controller", check_charging_controller),
        ("Fast Charger", check_fast_charger),
        ("Safety Conditions", check_safety_conditions),
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed: {e}")
            results.append((check_name, False))
    
    # Check thresholds and logs
    check_charging_thresholds()
    check_recent_logs()
    
    # Summary
    print("\n📋 DIAGNOSIS SUMMARY:")
    print("=" * 25)
    
    all_good = True
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if not result:
            all_good = False
    
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 20)
    
    if all_good:
        print("🎉 All systems are working correctly!")
        print("If battery is not charging, it may be due to:")
        print("  - High SOC (≥70%) - charging not needed")
        print("  - High electricity prices - waiting for better prices")
        print("  - System is in monitoring mode - check decision logs")
    else:
        print("⚠️  Some issues found. Check the failed components above.")
        print("💡 Try restarting the master coordinator:")
        print("  pkill -f master_coordinator")
        print("  python src/master_coordinator.py --non-interactive &")

if __name__ == "__main__":
    main()