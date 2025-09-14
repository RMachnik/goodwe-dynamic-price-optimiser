#!/usr/bin/env python3
"""
Diagnostic script for GoodWe Dynamic Price Optimiser Safety Issues

This script helps diagnose and troubleshoot emergency safety alerts
by checking system communication, data validity, and configuration.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

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


class SafetyDiagnostic:
    """Diagnostic tool for safety issues"""
    
    def __init__(self, config_path: str = "config/master_coordinator_config.yaml"):
        """Initialize diagnostic tool"""
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration file"""
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def test_inverter_connection(self) -> Dict[str, Any]:
        """Test inverter connection and communication"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "connection_test": "failed",
            "data_quality": "unknown",
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Get inverter config
            inverter_config = self.config.get('inverter', {})
            ip_address = inverter_config.get('ip_address', '192.168.33.15')
            port = inverter_config.get('port', 8899)
            timeout = inverter_config.get('timeout', 1)
            
            self.logger.info(f"Testing connection to inverter at {ip_address}:{port}")
            
            # Create inverter instance
            inverter = Inverter(ip_address, port, timeout)
            
            # Test basic communication
            await inverter.read_device_info()
            result["connection_test"] = "success"
            self.logger.info("✓ Inverter connection successful")
            
            # Test data reading
            runtime_data = await inverter.read_runtime_data()
            
            if runtime_data:
                result["data_quality"] = "good"
                self.logger.info("✓ Runtime data reading successful")
                
                # Check specific values
                battery_soc = runtime_data.get('battery_soc', 0)
                grid_voltage = runtime_data.get('grid_voltage', 0)
                
                self.logger.info(f"  - Battery SOC: {battery_soc}%")
                self.logger.info(f"  - Grid Voltage: {grid_voltage}V")
                
                # Validate readings
                if battery_soc < 0 or battery_soc > 100:
                    result["issues"].append(f"Invalid battery SOC reading: {battery_soc}%")
                    result["recommendations"].append("Check battery connection and BMS communication")
                
                if grid_voltage <= 0:
                    result["issues"].append(f"Invalid grid voltage reading: {grid_voltage}V")
                    result["recommendations"].append("Check grid connection and inverter communication")
                
                if battery_soc <= 50:
                    result["issues"].append(f"Battery SOC critically low: {battery_soc}%")
                    result["recommendations"].append("Charge battery immediately to prevent damage")
                
            else:
                result["data_quality"] = "poor"
                result["issues"].append("No runtime data received from inverter")
                result["recommendations"].append("Check inverter communication and data format")
                
        except InverterError as e:
            result["issues"].append(f"Inverter communication error: {e}")
            result["recommendations"].append("Check inverter IP address, port, and network connectivity")
            self.logger.error(f"✗ Inverter communication failed: {e}")
            
        except Exception as e:
            result["issues"].append(f"Unexpected error: {e}")
            result["recommendations"].append("Check system configuration and dependencies")
            self.logger.error(f"✗ Unexpected error: {e}")
        
        return result
    
    def check_safety_configuration(self) -> Dict[str, Any]:
        """Check safety configuration settings"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "configuration_valid": True,
            "issues": [],
            "recommendations": [],
            "current_settings": {}
        }
        
        try:
            # Get battery selling config
            battery_selling_config = self.config.get('battery_selling', {})
            safety_config = battery_selling_config.get('safety_checks', {})
            
            # Check safety margin SOC
            safety_margin_soc = battery_selling_config.get('safety_margin_soc', 50.0)
            min_selling_soc = battery_selling_config.get('min_battery_soc', 80.0)
            
            result["current_settings"]["safety_margin_soc"] = safety_margin_soc
            result["current_settings"]["min_selling_soc"] = min_selling_soc
            
            if safety_margin_soc >= min_selling_soc:
                result["issues"].append(f"Safety margin SOC ({safety_margin_soc}%) >= min selling SOC ({min_selling_soc}%)")
                result["recommendations"].append("Adjust safety_margin_soc to be lower than min_battery_soc")
                result["configuration_valid"] = False
            
            # Check grid voltage limits
            grid_voltage_min = safety_config.get('grid_voltage_min', 200.0)
            grid_voltage_max = safety_config.get('grid_voltage_max', 250.0)
            
            result["current_settings"]["grid_voltage_min"] = grid_voltage_min
            result["current_settings"]["grid_voltage_max"] = grid_voltage_max
            
            if grid_voltage_min >= grid_voltage_max:
                result["issues"].append(f"Grid voltage min ({grid_voltage_min}V) >= max ({grid_voltage_max}V)")
                result["recommendations"].append("Adjust grid voltage limits")
                result["configuration_valid"] = False
            
            # Check temperature limits
            battery_temp_max = safety_config.get('battery_temp_max', 50.0)
            battery_temp_min = safety_config.get('battery_temp_min', -20.0)
            
            result["current_settings"]["battery_temp_max"] = battery_temp_max
            result["current_settings"]["battery_temp_min"] = battery_temp_min
            
            if battery_temp_min >= battery_temp_max:
                result["issues"].append(f"Battery temp min ({battery_temp_min}°C) >= max ({battery_temp_max}°C)")
                result["recommendations"].append("Adjust battery temperature limits")
                result["configuration_valid"] = False
            
            self.logger.info("✓ Safety configuration check completed")
            
        except Exception as e:
            result["issues"].append(f"Configuration check error: {e}")
            result["recommendations"].append("Check configuration file format and syntax")
            result["configuration_valid"] = False
            self.logger.error(f"✗ Configuration check failed: {e}")
        
        return result
    
    def simulate_safety_monitor(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate safety monitor with test data"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "simulation_results": {},
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Create safety monitor instance
            monitor = BatterySellingMonitor(self.config)
            
            # Simulate safety check with test data
            battery_data = test_data.get('battery', {'soc_percent': 27, 'temperature': 25})
            grid_data = test_data.get('grid', {'voltage': 0})
            inverter_data = test_data.get('inverter', {'error_codes': []})
            
            current_data = {
                'battery': battery_data,
                'grid': grid_data,
                'inverter': inverter_data
            }
            
            # Run individual safety checks
            battery_soc_check = monitor._check_battery_soc(battery_data['soc_percent'])
            grid_voltage_check = monitor._check_grid_voltage(grid_data['voltage'])
            
            result["simulation_results"]["battery_soc_check"] = {
                "status": battery_soc_check.status.value,
                "message": battery_soc_check.message
            }
            
            result["simulation_results"]["grid_voltage_check"] = {
                "status": grid_voltage_check.status.value,
                "message": grid_voltage_check.message
            }
            
            # Analyze results
            if battery_soc_check.status.value == "emergency":
                result["issues"].append("Battery SOC check triggered emergency status")
                result["recommendations"].append("Charge battery immediately or check data reading")
            
            if grid_voltage_check.status.value == "emergency":
                result["issues"].append("Grid voltage check triggered emergency status")
                result["recommendations"].append("Check grid connection or inverter communication")
            
            self.logger.info("✓ Safety monitor simulation completed")
            
        except Exception as e:
            result["issues"].append(f"Simulation error: {e}")
            result["recommendations"].append("Check safety monitor implementation")
            self.logger.error(f"✗ Safety monitor simulation failed: {e}")
        
        return result
    
    async def run_full_diagnosis(self) -> Dict[str, Any]:
        """Run complete diagnostic analysis"""
        self.logger.info("Starting comprehensive safety diagnostic...")
        
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "tests": {},
            "summary": {
                "issues_found": 0,
                "critical_issues": 0,
                "recommendations": []
            }
        }
        
        # Test 1: Inverter connection
        self.logger.info("\n=== Test 1: Inverter Connection ===")
        connection_test = await self.test_inverter_connection()
        diagnosis["tests"]["inverter_connection"] = connection_test
        
        # Test 2: Safety configuration
        self.logger.info("\n=== Test 2: Safety Configuration ===")
        config_test = self.check_safety_configuration()
        diagnosis["tests"]["safety_configuration"] = config_test
        
        # Test 3: Safety monitor simulation
        self.logger.info("\n=== Test 3: Safety Monitor Simulation ===")
        test_data = {
            'battery': {'soc_percent': 27, 'temperature': 25},
            'grid': {'voltage': 0},
            'inverter': {'error_codes': []}
        }
        simulation_test = self.simulate_safety_monitor(test_data)
        diagnosis["tests"]["safety_monitor_simulation"] = simulation_test
        
        # Compile summary
        all_issues = []
        all_recommendations = []
        
        for test_name, test_result in diagnosis["tests"].items():
            if isinstance(test_result, dict):
                all_issues.extend(test_result.get('issues', []))
                all_recommendations.extend(test_result.get('recommendations', []))
        
        diagnosis["summary"]["issues_found"] = len(all_issues)
        diagnosis["summary"]["critical_issues"] = len([i for i in all_issues if 'emergency' in i.lower() or 'critical' in i.lower()])
        diagnosis["summary"]["recommendations"] = list(set(all_recommendations))  # Remove duplicates
        
        # Determine overall status
        if diagnosis["summary"]["critical_issues"] > 0:
            diagnosis["overall_status"] = "critical"
        elif diagnosis["summary"]["issues_found"] > 0:
            diagnosis["overall_status"] = "warning"
        else:
            diagnosis["overall_status"] = "healthy"
        
        return diagnosis
    
    def print_diagnosis_report(self, diagnosis: Dict[str, Any]):
        """Print formatted diagnosis report"""
        print("\n" + "="*60)
        print("GOODWE DYNAMIC PRICE OPTIMISER - SAFETY DIAGNOSTIC REPORT")
        print("="*60)
        print(f"Timestamp: {diagnosis['timestamp']}")
        print(f"Overall Status: {diagnosis['overall_status'].upper()}")
        print(f"Issues Found: {diagnosis['summary']['issues_found']}")
        print(f"Critical Issues: {diagnosis['summary']['critical_issues']}")
        
        print("\n" + "-"*40)
        print("DETAILED FINDINGS")
        print("-"*40)
        
        for test_name, test_result in diagnosis["tests"].items():
            print(f"\n{test_name.replace('_', ' ').title()}:")
            if isinstance(test_result, dict):
                for key, value in test_result.items():
                    if key not in ['timestamp'] and value:
                        if isinstance(value, list) and value:
                            print(f"  {key}: {', '.join(map(str, value))}")
                        elif not isinstance(value, list):
                            print(f"  {key}: {value}")
        
        print("\n" + "-"*40)
        print("RECOMMENDATIONS")
        print("-"*40)
        
        for i, recommendation in enumerate(diagnosis["summary"]["recommendations"], 1):
            print(f"{i}. {recommendation}")
        
        print("\n" + "="*60)


async def main():
    """Main diagnostic function"""
    diagnostic = SafetyDiagnostic()
    
    try:
        diagnosis = await diagnostic.run_full_diagnosis()
        diagnostic.print_diagnosis_report(diagnosis)
        
        # Exit with appropriate code
        if diagnosis["overall_status"] == "critical":
            sys.exit(2)
        elif diagnosis["overall_status"] == "warning":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"Diagnostic failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())