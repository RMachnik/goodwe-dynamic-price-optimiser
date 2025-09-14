#!/usr/bin/env python3
"""
Fix Charging Block Script

This script helps resolve the charging block caused by emergency safety alerts.
It checks system status and provides steps to clear the emergency state.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import goodwe
    from goodwe import Inverter, InverterError
    from battery_selling_monitor import BatterySellingMonitor
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


class ChargingBlockFixer:
    """Tool to fix charging blocks caused by emergency safety alerts"""
    
    def __init__(self, config_path: str = "config/master_coordinator_config.yaml"):
        """Initialize the fixer"""
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
    def _load_config(self):
        """Load configuration file"""
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def _setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def check_system_status(self):
        """Check current system status"""
        print("\n" + "="*60)
        print("CHECKING SYSTEM STATUS")
        print("="*60)
        
        try:
            # Get inverter config
            inverter_config = self.config.get('inverter', {})
            ip_address = inverter_config.get('ip_address', '192.168.33.15')
            port = inverter_config.get('port', 8899)
            timeout = inverter_config.get('timeout', 1)
            
            print(f"Inverter: {ip_address}:{port}")
            
            # Create inverter instance
            inverter = Inverter(ip_address, port, timeout)
            
            # Test connection
            await inverter.read_device_info()
            print("✓ Inverter connection: OK")
            
            # Get runtime data
            runtime_data = await inverter.read_runtime_data()
            
            if runtime_data:
                battery_soc = runtime_data.get('battery_soc', 0)
                grid_voltage = runtime_data.get('grid_voltage', 0)
                battery_temp = runtime_data.get('battery_temperature', 0)
                
                print(f"✓ Battery SOC: {battery_soc}%")
                print(f"✓ Grid Voltage: {grid_voltage}V")
                print(f"✓ Battery Temperature: {battery_temp}°C")
                
                # Check if values are valid
                issues = []
                if battery_soc <= 0 or battery_soc > 100:
                    issues.append(f"Invalid battery SOC: {battery_soc}%")
                if grid_voltage <= 0:
                    issues.append(f"Invalid grid voltage: {grid_voltage}V")
                if battery_temp < -20 or battery_temp > 60:
                    issues.append(f"Invalid battery temperature: {battery_temp}°C")
                
                if issues:
                    print("\n⚠️  DATA VALIDATION ISSUES:")
                    for issue in issues:
                        print(f"  - {issue}")
                    return False
                else:
                    print("\n✓ Data validation: OK")
                    return True
            else:
                print("✗ No runtime data received")
                return False
                
        except Exception as e:
            print(f"✗ System check failed: {e}")
            return False
    
    def check_emergency_state(self):
        """Check if system is in emergency state"""
        print("\n" + "="*60)
        print("CHECKING EMERGENCY STATE")
        print("="*60)
        
        try:
            # Check logs for emergency stops
            log_file = Path("logs/master_coordinator_nohup.log")
            if log_file.exists():
                with open(log_file, 'r') as f:
                    content = f.read()
                    
                emergency_count = content.count("Total emergency stops:")
                if emergency_count > 0:
                    print(f"⚠️  Emergency stops detected: {emergency_count}")
                    
                    # Find the latest emergency stop count
                    lines = content.split('\n')
                    latest_emergency = None
                    for line in reversed(lines):
                        if "Total emergency stops:" in line:
                            latest_emergency = line
                            break
                    
                    if latest_emergency:
                        print(f"Latest: {latest_emergency}")
                    
                    return True
                else:
                    print("✓ No emergency stops detected")
                    return False
            else:
                print("✗ Log file not found")
                return False
                
        except Exception as e:
            print(f"✗ Emergency state check failed: {e}")
            return False
    
    def provide_fix_steps(self, has_issues: bool, has_emergency: bool):
        """Provide steps to fix the charging block"""
        print("\n" + "="*60)
        print("FIX STEPS")
        print("="*60)
        
        if has_issues or has_emergency:
            print("🔧 CHARGING BLOCK DETECTED - Follow these steps:")
            print()
            
            print("1. RESTART THE SYSTEM:")
            print("   sudo systemctl restart goodwe-master-coordinator")
            print("   # OR if running manually:")
            print("   # Kill the process and restart")
            print()
            
            print("2. CHECK INVERTER CONNECTION:")
            print("   - Verify inverter IP: 192.168.33.15")
            print("   - Check network connectivity")
            print("   - Ensure inverter is online")
            print()
            
            print("3. VERIFY SYSTEM DATA:")
            print("   - Battery SOC should be 0-100%")
            print("   - Grid voltage should be >0V")
            print("   - Battery temperature should be -20°C to 60°C")
            print()
            
            print("4. CLEAR EMERGENCY STATE:")
            print("   - Restart clears emergency counters")
            print("   - Safety checks will re-evaluate")
            print()
            
            print("5. MONITOR LOGS:")
            print("   tail -f logs/master_coordinator_nohup.log")
            print("   # Look for 'Charging True' instead of 'Charging False'")
            print()
            
            print("6. TEST CHARGING:")
            print("   # After restart, check if charging starts")
            print("   # Price 0.360 PLN/kWh should trigger charging")
            print()
            
        else:
            print("✓ System appears healthy - no fixes needed")
            print()
            print("If charging still shows 0.00 values:")
            print("1. Check if inverter is actually charging")
            print("2. Verify charging power settings")
            print("3. Check for other blocking conditions")
    
    async def run_diagnosis(self):
        """Run complete diagnosis and provide fix steps"""
        print("GOODWE DYNAMIC PRICE OPTIMISER - CHARGING BLOCK DIAGNOSIS")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Check system status
        has_issues = not await self.check_system_status()
        
        # Check emergency state
        has_emergency = self.check_emergency_state()
        
        # Provide fix steps
        self.provide_fix_steps(has_issues, has_emergency)
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        if has_issues or has_emergency:
            print("🚨 CHARGING BLOCKED - Emergency safety alerts active")
            print("💡 SOLUTION: Restart the system to clear emergency state")
            return 1
        else:
            print("✅ System healthy - charging should work")
            return 0


async def main():
    """Main function"""
    fixer = ChargingBlockFixer()
    
    try:
        exit_code = await fixer.run_diagnosis()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"Diagnosis failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())