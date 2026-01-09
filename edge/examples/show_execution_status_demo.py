#!/usr/bin/env python3
"""
Demo script to show the new execution status feature in the web UI
"""

import requests
import json
from datetime import datetime

def get_recent_decisions():
    """Get recent decisions from the web API"""
    try:
        response = requests.get('http://localhost:8080/decisions', params={'hours': 24})
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching decisions: {e}")
        return None

def analyze_execution_status(decisions):
    """Analyze execution status of decisions"""
    print("🔍 EXECUTION STATUS ANALYSIS")
    print("=" * 50)
    
    if not decisions:
        print("No decisions found")
        return
    
    decisions_list = decisions if isinstance(decisions, list) else [decisions]
    total_decisions = len(decisions_list)
    executed_count = 0
    blocked_count = 0
    wait_count = 0
    
    print(f"Total decisions: {total_decisions}")
    print()
    
    decisions_list = decisions if isinstance(decisions, list) else [decisions]
    for i, decision in enumerate(decisions_list[:10]):  # Show last 10 decisions
        timestamp = decision.get('timestamp', '')
        action = decision.get('action', 'unknown')
        reason = decision.get('reason', '')
        
        # Determine execution status with detailed reasons
        if action == 'wait':
            status = "N/A"
            status_color = "⏸️"
            block_reason = "Wait decision - no execution needed"
            wait_count += 1
        else:
            energy = decision.get('energy_kwh', 0)
            cost = decision.get('estimated_cost_pln', 0)
            savings = decision.get('estimated_savings_pln', 0)
            
            if energy == 0 and cost == 0 and savings == 0:
                status = "BLOCKED"
                status_color = "🚫"
                blocked_count += 1
                
                # Analyze the reason to determine blocking cause
                reason = decision.get('reason', '')
                if 'emergency' in reason.lower() or 'safety' in reason.lower():
                    block_reason = "Emergency safety stop"
                elif 'price' in reason.lower() and 'not optimal' in reason.lower():
                    block_reason = "Price threshold not met"
                elif 'could not determine current price' in reason.lower():
                    block_reason = "Price data unavailable"
                elif 'battery' in reason.lower() and 'safety margin' in reason.lower():
                    block_reason = "Battery safety margin exceeded"
                elif 'grid voltage' in reason.lower() and 'outside safe range' in reason.lower():
                    block_reason = "Grid voltage out of range"
                elif 'communication' in reason.lower() or 'connection' in reason.lower():
                    block_reason = "Communication error"
                elif 'inverter' in reason.lower() and 'error' in reason.lower():
                    block_reason = "Inverter error"
                elif 'timeout' in reason.lower() or 'retry' in reason.lower():
                    block_reason = "Communication timeout"
                elif 'charging' in reason.lower() and 'already' in reason.lower():
                    block_reason = "Already charging"
                elif 'pv' in reason.lower() and 'overproduction' in reason.lower():
                    block_reason = "PV overproduction detected"
                elif 'consumption' in reason.lower() and 'high' in reason.lower():
                    block_reason = "High consumption detected"
                else:
                    block_reason = "Execution blocked by safety system"
            else:
                status = "EXECUTED"
                status_color = "✅"
                block_reason = f"Charged {energy:.2f} kWh for {cost:.2f} PLN"
                executed_count += 1
        
        print(f"{i+1:2d}. {timestamp}")
        print(f"    Action: {action.upper()}")
        print(f"    Status: {status_color} {status}")
        print(f"    Block Reason: {block_reason}")
        print(f"    Original Reason: {reason}")
        
        if action != 'wait':
            print(f"    Energy: {energy:.2f} kWh")
            print(f"    Cost: {cost:.2f} PLN")
            print(f"    Savings: {savings:.2f} PLN")
        print()
    
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"✅ Executed: {executed_count}")
    print(f"🚫 Blocked: {blocked_count}")
    print(f"⏸️ Wait: {wait_count}")
    print()
    
    if blocked_count > 0:
        print("⚠️  Some charging decisions were blocked!")
        print("This usually means:")
        print("  - Emergency safety stops")
        print("  - Price threshold not met")
        print("  - Safety margin exceeded")
        print("  - Communication errors")

def main():
    """Main function"""
    print("GOODWE DYNAMIC PRICE OPTIMISER - EXECUTION STATUS DEMO")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    decisions = get_recent_decisions()
    analyze_execution_status(decisions)
    
    print()
    print("🌐 WEB INTERFACE")
    print("=" * 50)
    print("Visit http://localhost:8080 to see the new execution status!")
    print("Look for the colored badges:")
    print("  ✅ EXECUTED - Decision was successfully executed")
    print("  🚫 BLOCKED - Decision was made but blocked from execution")
    print("  ⏸️ N/A - Wait decision (no execution needed)")

if __name__ == "__main__":
    main()