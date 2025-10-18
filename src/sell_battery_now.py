#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Manual Battery Selling Script

This script enables manual battery selling to the grid with configurable target SOC,
bypassing the automatic battery selling logic for manual control.

Usage:
    python sell_battery_now.py --start --target-soc 45
    python sell_battery_now.py --stop
    python sell_battery_now.py --status

Requirements:
    - goodwe==0.4.8
    - PyYAML
    - asyncio (built-in)
    - logging (built-in)
"""

import asyncio
import argparse
import logging
import sys
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import goodwe
    from goodwe import Inverter, InverterError, OperationMode
except ImportError:
    print("Error: goodwe library not found. Install with: pip install goodwe==0.4.8")
    sys.exit(1)


class BatterySeller:
    """Manual battery selling controller for GoodWe inverters"""
    
    def __init__(self, config_path: str):
        """Initialize the battery seller with configuration"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.inverter: Optional[Inverter] = None
        self.selling_start_time: Optional[datetime] = None
        self.is_selling = False
        self.initial_soc = 0.0
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO'))
        
        # Get the root logger
        root_logger = logging.getLogger()
        
        # Only setup logging if it hasn't been configured yet
        if not root_logger.handlers:
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            
            root_logger.setLevel(log_level)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            
            # File handler
            project_root = Path(__file__).parent.parent
            logs_dir = project_root / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            log_file = logs_dir / 'battery_selling_manual.log'
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        else:
            # Just set the log level if handlers already exist
            root_logger.setLevel(log_level)
    
    async def connect_inverter(self) -> bool:
        """Connect to the GoodWe inverter"""
        inverter_config = self.config['inverter']
        max_retries = inverter_config.get('retries', 3)
        retry_delay = inverter_config.get('retry_delay', 2.0)
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.info(f"Retry attempt {attempt + 1}/{max_retries} for inverter connection...")
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.info(f"Connecting to inverter at {inverter_config['ip_address']}")
                
                self.inverter = await goodwe.connect(
                    host=inverter_config['ip_address'],
                    family=inverter_config.get('family'),
                    timeout=inverter_config.get('timeout', 1),
                    retries=inverter_config.get('retries', 3)
                )
                
                self.logger.info(
                    f"Connected to inverter: {self.inverter.model_name} "
                    f"(Serial: {self.inverter.serial_number})"
                )
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                else:
                    self.logger.error(f"Failed to connect to inverter after {max_retries} attempts: {e}")
        
        return False
    
    async def get_inverter_status(self) -> Dict[str, Any]:
        """Get current inverter status and sensor data"""
        if not self.inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self.inverter.read_runtime_data()
            status = {}
            
            # Extract key sensor values
            for sensor in self.inverter.sensors():
                if sensor.id_ in runtime_data:
                    status[sensor.id_] = {
                        'name': sensor.name,
                        'value': runtime_data[sensor.id_],
                        'unit': sensor.unit
                    }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to read inverter status: {e}")
            return {}
    
    async def check_safety_conditions(self, target_soc: float = 10.0) -> tuple[bool, str]:
        """
        Check if it's safe to start/continue selling
        
        Args:
            target_soc: Minimum SOC target (default 10% absolute minimum)
            
        Returns:
            Tuple of (is_safe, reason_if_not_safe)
        """
        if not self.inverter:
            return False, "Inverter not connected"
        
        try:
            status = await self.get_inverter_status()
            safety_config = self.config.get('battery_management', {})
            
            # Check battery SOC - never go below target or 10% minimum
            absolute_min_soc = 10.0
            min_soc = max(target_soc, absolute_min_soc)
            
            battery_soc = status.get('battery_soc', {}).get('value', 0)
            if battery_soc <= min_soc:
                return False, f"Battery SOC {battery_soc}% at or below minimum threshold {min_soc}%"
            
            # Check battery temperature
            battery_temp = status.get('battery_temperature', {}).get('value', 0)
            temp_thresholds = safety_config.get('temperature_thresholds', {})
            
            temp_max = temp_thresholds.get('discharging_max', 53.0)
            temp_min = temp_thresholds.get('discharging_min', -20.0)
            
            if battery_temp > temp_max:
                return False, f"Battery temperature {battery_temp}°C exceeds maximum {temp_max}°C"
            
            if battery_temp < temp_min:
                return False, f"Battery temperature {battery_temp}°C below minimum {temp_min}°C"
            
            # Check battery voltage
            battery_voltage = status.get('battery_voltage', {}).get('value', 0)
            voltage_range = safety_config.get('voltage_range', {})
            
            voltage_min = voltage_range.get('min', 320.0)
            voltage_max = voltage_range.get('max', 480.0)
            
            if battery_voltage > 0:  # Only check if voltage reading is available
                if battery_voltage < voltage_min:
                    return False, f"Battery voltage {battery_voltage}V below minimum {voltage_min}V"
                
                if battery_voltage > voltage_max:
                    return False, f"Battery voltage {battery_voltage}V exceeds maximum {voltage_max}V"
            
            # Check grid voltage
            grid_voltage = status.get('vgrid', {}).get('value', 0)
            if grid_voltage > 0:  # Only check if voltage reading is available
                emergency_config = self.config.get('coordinator', {}).get('emergency_stop_conditions', {})
                grid_voltage_min = emergency_config.get('grid_voltage_min', 200.0)
                grid_voltage_max = emergency_config.get('grid_voltage_max', 250.0)
                
                if grid_voltage < grid_voltage_min:
                    return False, f"Grid voltage {grid_voltage}V below minimum {grid_voltage_min}V"
                
                if grid_voltage > grid_voltage_max:
                    return False, f"Grid voltage {grid_voltage}V exceeds maximum {grid_voltage_max}V"
            
            return True, "All safety conditions passed"
            
        except Exception as e:
            self.logger.error(f"Failed to check safety conditions: {e}")
            return False, f"Safety check error: {e}"
    
    async def start_selling(self, target_soc: float = 45.0, selling_power_w: int = 5000) -> bool:
        """
        Start battery selling session
        
        Args:
            target_soc: Stop selling when battery reaches this SOC percentage
            selling_power_w: Maximum selling power in Watts
            
        Returns:
            True if selling started successfully, False otherwise
        """
        if not self.inverter:
            self.logger.error("Cannot start selling - inverter not connected")
            return False
        
        try:
            # Get current status
            status = await self.get_inverter_status()
            current_soc = status.get('battery_soc', {}).get('value', 0)
            
            self.logger.info(f"Current battery SOC: {current_soc}%")
            
            # Check if already at or below target
            if current_soc <= target_soc:
                self.logger.warning(f"Battery SOC {current_soc}% already at or below target {target_soc}%")
                return False
            
            # Check safety conditions
            is_safe, safety_reason = await self.check_safety_conditions(target_soc)
            if not is_safe:
                self.logger.error(f"Cannot start selling - safety check failed: {safety_reason}")
                return False
            
            self.logger.info(f"Safety checks passed: {safety_reason}")
            self.logger.info(f"Starting battery selling session:")
            self.logger.info(f"  - Current SOC: {current_soc}%")
            self.logger.info(f"  - Target SOC: {target_soc}%")
            self.logger.info(f"  - Selling Power: {selling_power_w}W")
            self.logger.info(f"  - Expected energy to sell: {(current_soc - target_soc) * 0.1:.2f} kWh (approx)")
            
            # Set inverter to ECO_DISCHARGE mode with power limit and SOC limit
            await self.inverter.set_operation_mode(
                OperationMode.ECO_DISCHARGE,
                selling_power_w,  # Power limit
                int(target_soc)   # Minimum SOC (target)
            )
            
            # Set grid export limit
            await self.inverter.set_grid_export_limit(selling_power_w)
            
            # Set battery depth of discharge limit (100 - target_soc = max DOD)
            battery_dod = 100 - int(target_soc)
            await self.inverter.set_ongrid_battery_dod(battery_dod)
            
            self.is_selling = True
            self.selling_start_time = datetime.now()
            self.initial_soc = current_soc
            
            self.logger.info("✓ Battery selling started successfully")
            self.logger.info(f"  - Inverter mode: ECO_DISCHARGE")
            self.logger.info(f"  - Grid export limit: {selling_power_w}W")
            self.logger.info(f"  - Battery DOD limit: {battery_dod}%")
            
            return True
            
        except InverterError as e:
            self.logger.error(f"Inverter error starting selling: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to start selling: {e}")
            return False
    
    async def stop_selling(self) -> bool:
        """Stop battery selling and restore inverter to normal operation"""
        if not self.inverter:
            self.logger.error("Cannot stop selling - inverter not connected")
            return False
        
        try:
            self.logger.info("Stopping battery selling session...")
            
            # Get final status
            status = await self.get_inverter_status()
            final_soc = status.get('battery_soc', {}).get('value', 0)
            
            # Restore inverter to GENERAL mode
            await self.inverter.set_operation_mode(OperationMode.GENERAL)
            
            # Disable grid export limit (set to 0)
            await self.inverter.set_grid_export_limit(0)
            
            # Reset battery DOD to default (typically 50% for GoodWe Lynx-D)
            await self.inverter.set_ongrid_battery_dod(50)
            
            if self.selling_start_time:
                duration = datetime.now() - self.selling_start_time
                energy_sold = (self.initial_soc - final_soc) * 0.1  # Approximate kWh
                
                self.logger.info("✓ Battery selling stopped successfully")
                self.logger.info(f"  - Initial SOC: {self.initial_soc}%")
                self.logger.info(f"  - Final SOC: {final_soc}%")
                self.logger.info(f"  - Energy sold: ~{energy_sold:.2f} kWh")
                self.logger.info(f"  - Duration: {duration}")
            else:
                self.logger.info("✓ Battery selling stopped successfully")
            
            self.is_selling = False
            self.selling_start_time = None
            
            return True
            
        except InverterError as e:
            self.logger.error(f"Inverter error stopping selling: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to stop selling: {e}")
            return False
    
    async def monitor_selling(self, target_soc: float, check_interval: int = 30) -> None:
        """
        Monitor selling session and automatically stop when target SOC is reached
        
        Args:
            target_soc: Stop when battery reaches this SOC
            check_interval: How often to check status (seconds)
        """
        if not self.inverter or not self.is_selling:
            self.logger.error("No active selling session to monitor")
            return
        
        self.logger.info(f"Monitoring selling session (checking every {check_interval}s)...")
        self.logger.info("Press Ctrl+C to stop selling manually")
        
        try:
            while self.is_selling:
                await asyncio.sleep(check_interval)
                
                # Get current status
                status = await self.get_inverter_status()
                current_soc = status.get('battery_soc', {}).get('value', 0)
                battery_power = status.get('battery_power', {}).get('value', 0)
                grid_power = status.get('grid_power', {}).get('value', 0)
                
                # Calculate progress
                if self.selling_start_time:
                    duration = datetime.now() - self.selling_start_time
                    energy_sold = (self.initial_soc - current_soc) * 0.1
                    
                    self.logger.info(
                        f"Selling progress: SOC {current_soc}% | "
                        f"Battery: {battery_power}W | Grid: {grid_power}W | "
                        f"Sold: ~{energy_sold:.2f} kWh | Duration: {str(duration).split('.')[0]}"
                    )
                
                # Check if target reached
                if current_soc <= target_soc:
                    self.logger.info(f"✓ Target SOC {target_soc}% reached (current: {current_soc}%)")
                    await self.stop_selling()
                    break
                
                # Check safety conditions
                is_safe, safety_reason = await self.check_safety_conditions(target_soc)
                if not is_safe:
                    self.logger.warning(f"Safety condition failed: {safety_reason}")
                    self.logger.warning("Stopping selling for safety")
                    await self.stop_selling()
                    break
                    
        except KeyboardInterrupt:
            self.logger.info("\nKeyboard interrupt received - stopping selling...")
            await self.stop_selling()
        except Exception as e:
            self.logger.error(f"Error during monitoring: {e}")
            await self.stop_selling()
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current selling status"""
        if not self.inverter:
            return {"error": "Inverter not connected"}
        
        try:
            status = await self.get_inverter_status()
            
            result = {
                "is_selling": self.is_selling,
                "battery_soc": status.get('battery_soc', {}).get('value', 0),
                "battery_power": status.get('battery_power', {}).get('value', 0),
                "battery_voltage": status.get('battery_voltage', {}).get('value', 0),
                "battery_temperature": status.get('battery_temperature', {}).get('value', 0),
                "grid_power": status.get('grid_power', {}).get('value', 0),
                "grid_voltage": status.get('vgrid', {}).get('value', 0),
            }
            
            if self.is_selling and self.selling_start_time:
                duration = datetime.now() - self.selling_start_time
                energy_sold = (self.initial_soc - result["battery_soc"]) * 0.1
                result.update({
                    "selling_start_time": self.selling_start_time.isoformat(),
                    "duration": str(duration).split('.')[0],
                    "initial_soc": self.initial_soc,
                    "energy_sold_kwh": round(energy_sold, 2)
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return {"error": str(e)}


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Manual battery selling script for GoodWe inverters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start selling until battery reaches 45%% SOC
  python sell_battery_now.py --start --target-soc 45

  # Start selling with custom power limit
  python sell_battery_now.py --start --target-soc 30 --power 3000

  # Stop current selling session
  python sell_battery_now.py --stop

  # Check selling status
  python sell_battery_now.py --status
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to configuration file (default: config/master_coordinator_config.yaml)'
    )
    
    # Action arguments
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        '--start',
        action='store_true',
        help='Start battery selling session'
    )
    action_group.add_argument(
        '--stop',
        action='store_true',
        help='Stop battery selling session'
    )
    action_group.add_argument(
        '--status',
        action='store_true',
        help='Get current selling status'
    )
    
    # Selling parameters
    parser.add_argument(
        '--target-soc',
        type=float,
        default=45.0,
        help='Target SOC percentage to stop selling (default: 45%%)'
    )
    parser.add_argument(
        '--power',
        type=int,
        default=5000,
        help='Selling power limit in Watts (default: 5000W)'
    )
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Monitor selling session and auto-stop at target (use with --start)'
    )
    parser.add_argument(
        '--check-interval',
        type=int,
        default=30,
        help='Status check interval in seconds when monitoring (default: 30s)'
    )
    
    args = parser.parse_args()
    
    # Validate target SOC
    if args.target_soc < 10 or args.target_soc > 95:
        print("Error: target-soc must be between 10 and 95")
        sys.exit(1)
    
    # Validate power
    if args.power < 100 or args.power > 15000:
        print("Error: power must be between 100 and 15000 Watts")
        sys.exit(1)
    
    # Determine config path
    if args.config is None:
        script_dir = Path(__file__).parent
        config_path = script_dir.parent / "config" / "master_coordinator_config.yaml"
    else:
        config_path = Path(args.config)
    
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    # Create seller instance
    try:
        seller = BatterySeller(str(config_path))
    except Exception as e:
        print(f"Error initializing battery seller: {e}")
        sys.exit(1)
    
    # Connect to inverter
    if not await seller.connect_inverter():
        print("Failed to connect to inverter")
        sys.exit(1)
    
    # Execute requested action
    try:
        if args.start:
            success = await seller.start_selling(args.target_soc, args.power)
            if success:
                if args.monitor:
                    # Monitor until target reached or interrupted
                    await seller.monitor_selling(args.target_soc, args.check_interval)
                else:
                    print(f"\n✓ Selling started successfully")
                    print(f"Run with --status to check progress")
                    print(f"Run with --stop to stop selling")
            else:
                print("\n✗ Failed to start selling")
                sys.exit(1)
                
        elif args.stop:
            success = await seller.stop_selling()
            if not success:
                print("\n✗ Failed to stop selling")
                sys.exit(1)
                
        elif args.status:
            status = await seller.get_status()
            print("\n=== Battery Selling Status ===")
            if "error" in status:
                print(f"Error: {status['error']}")
            else:
                print(f"Is Selling: {status['is_selling']}")
                print(f"Battery SOC: {status['battery_soc']}%")
                print(f"Battery Power: {status['battery_power']}W")
                print(f"Battery Voltage: {status['battery_voltage']}V")
                print(f"Battery Temperature: {status['battery_temperature']}°C")
                print(f"Grid Power: {status['grid_power']}W")
                print(f"Grid Voltage: {status['grid_voltage']}V")
                
                if status['is_selling']:
                    print(f"\n=== Active Selling Session ===")
                    print(f"Start Time: {status.get('selling_start_time', 'N/A')}")
                    print(f"Duration: {status.get('duration', 'N/A')}")
                    print(f"Initial SOC: {status.get('initial_soc', 'N/A')}%")
                    print(f"Energy Sold: ~{status.get('energy_sold_kwh', 0)} kWh")
                    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

