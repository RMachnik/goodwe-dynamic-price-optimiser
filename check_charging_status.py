#!/usr/bin/env python3
"""
Check why the battery is not charging
"""

import requests
import json
import sys
from pathlib import Path

def get_current_status():
    """Get current system status"""
    try:
        response = requests.get('http://192.168.33.13:8080/current-state', timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error getting current status: {e}")
        return None

def check_charging_conditions():
    """Check various charging conditions"""
    print("🔋 Battery Charging Status Check")
    print("=" * 50)
    
    # Get current status
    data = get_current_status()
    if not data:
        return
    
    print(f"📊 Data Source: {data.get('data_source', 'unknown')}")
    print(f"📅 Timestamp: {data.get('timestamp', 'unknown')}")
    print()
    
    # Battery status
    battery = data.get('battery', {})
    print("🔋 BATTERY STATUS:")
    print(f"  SOC: {battery.get('soc_percent', 'N/A')}%")
    print(f"  Voltage: {battery.get('voltage', 'N/A')}V")
    print(f"  Current: {battery.get('current', 'N/A')}A")
    print(f"  Power: {battery.get('power', 'N/A')}W")
    print(f"  Temperature: {battery.get('temperature', 'N/A')}°C")
    print(f"  Charging Status: {battery.get('charging_status', 'N/A')}")
    print()
    
    # PV status
    pv = data.get('pv', {})
    print("☀️  PV STATUS:")
    print(f"  Power: {pv.get('power_w', 'N/A')}W")
    print(f"  Daily Production: {pv.get('daily_production_kwh', 'N/A')}kWh")
    print()
    
    # Grid status
    grid = data.get('grid', {})
    print("⚡ GRID STATUS:")
    print(f"  Power: {grid.get('power_w', 'N/A')}W")
    print(f"  Flow Direction: {grid.get('flow_direction', 'N/A')}")
    print(f"  Daily Import: {grid.get('daily_import_kwh', 'N/A')}kWh")
    print(f"  Daily Export: {grid.get('daily_export_kwh', 'N/A')}kWh")
    print()
    
    # Pricing status
    pricing = data.get('pricing', {})
    print("💰 PRICING STATUS:")
    print(f"  Current Price: {pricing.get('current_price_pln_kwh', 'N/A')} PLN/kWh")
    print(f"  Cheapest Price: {pricing.get('cheapest_price_pln_kwh', 'N/A')} PLN/kWh")
    print(f"  Cheapest Hour: {pricing.get('cheapest_hour', 'N/A')}")
    print(f"  Price Trend: {pricing.get('price_trend', 'N/A')}")
    print()
    
    # Analyze charging conditions
    print("🔍 CHARGING ANALYSIS:")
    print("-" * 30)
    
    battery_soc = battery.get('soc_percent', 0)
    battery_power = battery.get('power', 0)
    pv_power = pv.get('power_w', 0)
    grid_power = grid.get('power_w', 0)
    current_price = pricing.get('current_price_pln_kwh', 0)
    
    # Check SOC thresholds
    if battery_soc >= 90:
        print("⚠️  Battery SOC is high (≥90%) - charging may not be needed")
    elif battery_soc >= 70:
        print("ℹ️  Battery SOC is medium (70-90%) - charging only during low prices")
    elif battery_soc >= 40:
        print("ℹ️  Battery SOC is low-medium (40-70%) - charging during low/medium prices")
    elif battery_soc >= 12:
        print("⚠️  Battery SOC is low (12-40%) - should charge during low prices")
    else:
        print("🚨 Battery SOC is critical (<12%) - should charge immediately!")
    
    # Check power flow
    if battery_power > 0:
        print(f"✅ Battery is charging: {battery_power}W")
    elif battery_power < 0:
        print(f"📤 Battery is discharging: {abs(battery_power)}W")
    else:
        print("⏸️  Battery is idle (no charging/discharging)")
    
    # Check PV availability
    if pv_power > 1000:
        print(f"☀️  Good PV production: {pv_power}W")
    elif pv_power > 100:
        print(f"☀️  Low PV production: {pv_power}W")
    else:
        print("🌙 No significant PV production")
    
    # Check grid flow
    if grid_power > 0:
        print(f"📥 Grid import: {grid_power}W")
    elif grid_power < 0:
        print(f"📤 Grid export: {abs(grid_power)}W")
    else:
        print("⚖️  Grid balanced")
    
    # Check pricing
    if current_price < 0.3:
        print(f"💰 Very low price: {current_price} PLN/kWh - good for charging")
    elif current_price < 0.5:
        print(f"💰 Low price: {current_price} PLN/kWh - acceptable for charging")
    elif current_price < 0.7:
        print(f"💰 Medium price: {current_price} PLN/kWh - charging depends on SOC")
    else:
        print(f"💰 High price: {current_price} PLN/kWh - avoid charging unless critical")
    
    print()
    print("💡 RECOMMENDATIONS:")
    print("-" * 20)
    
    if battery_soc < 12:
        print("🚨 CRITICAL: Battery SOC is very low - charge immediately regardless of price!")
    elif battery_soc < 40 and current_price < 0.5:
        print("✅ RECOMMENDED: Low SOC + low price = good time to charge")
    elif battery_soc < 70 and current_price < 0.3:
        print("✅ RECOMMENDED: Medium SOC + very low price = good time to charge")
    elif battery_soc >= 90:
        print("ℹ️  INFO: Battery SOC is high - charging not needed")
    elif current_price > 0.7:
        print("⏳ WAIT: Price is high - wait for lower prices unless SOC is critical")
    else:
        print("🤔 UNCLEAR: Check master coordinator logs for decision details")

def check_master_coordinator_logs():
    """Check master coordinator logs for charging decisions"""
    print("\n📋 MASTER COORDINATOR LOGS:")
    print("=" * 40)
    
    try:
        log_file = Path(__file__).parent / "logs" / "master_coordinator.log"
        if log_file.exists():
            # Read last 20 lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-20:] if len(lines) >= 20 else lines
            
            print("Recent log entries:")
            for line in recent_lines:
                if 'charging' in line.lower() or 'decision' in line.lower():
                    print(f"  {line.strip()}")
        else:
            print("❌ Master coordinator log file not found")
    except Exception as e:
        print(f"❌ Error reading logs: {e}")

if __name__ == "__main__":
    check_charging_conditions()
    check_master_coordinator_logs()