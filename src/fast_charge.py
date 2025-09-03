#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Fast Charging Script

This script triggers fast charging on GoodWe inverters with safety checks
and monitoring capabilities.

Usage:
    python fast_charge.py [--config CONFIG_FILE] [--start|--stop|--status]

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
    from goodwe import Inverter, InverterError
except ImportError:
    print("Error: goodwe library not found. Install with: pip install goodwe==0.4.8")
    sys.exit(1)


class GoodWeFastCharger:
    """GoodWe Inverter Fast Charging Controller"""
    
    def __init__(self, config_path: str):
        """Initialize the fast charger with configuration"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.inverter: Optional[Inverter] = None
        self.charging_start_time: Optional[datetime] = None
        self.is_charging = False
        
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
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler if enabled
        if log_config.get('log_to_file', False):
            # Get the project root directory (parent of src)
            project_root = Path(__file__).parent.parent
            logs_dir = project_root / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            log_file = log_config.get('log_file', str(logs_dir / 'fast_charge.log'))
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    
    async def connect_inverter(self) -> bool:
        """Connect to the GoodWe inverter"""
        try:
            inverter_config = self.config['inverter']
            
            self.logger.info(f"Connecting to inverter at {inverter_config['ip_address']}")
            
            self.inverter = await goodwe.connect(
                host=inverter_config['ip_address'],
                family=inverter_config['family'],
                timeout=inverter_config['timeout'],
                retries=inverter_config['retries']
            )
            
            self.logger.info(
                f"Connected to inverter: {self.inverter.model_name} "
                f"(Serial: {self.inverter.serial_number})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to inverter: {e}")
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
    
    async def check_safety_conditions(self) -> bool:
        """Check if it's safe to start charging"""
        if not self.inverter:
            return False
        
        try:
            status = await self.get_inverter_status()
            safety_config = self.config.get('safety', {})
            
            # Check battery temperature
            max_temp = safety_config.get('max_battery_temp', 0)
            if max_temp > 0:
                battery_temp = status.get('battery_temperature', {}).get('value', 0)
                if battery_temp > max_temp:
                    self.logger.warning(f"Battery temperature too high: {battery_temp}°C")
                    return False
            
            # Check minimum battery SoC
            min_soc = safety_config.get('min_battery_soc', 0)
            if min_soc > 0:
                battery_soc = status.get('battery_soc', {}).get('value', 0)
                if battery_soc < min_soc:
                    self.logger.warning(f"Battery SoC too low: {battery_soc}%")
                    return False
            
            # Check grid power usage
            max_grid_power = safety_config.get('max_grid_power', 0)
            if max_grid_power > 0:
                grid_power = status.get('grid_power', {}).get('value', 0)
                if abs(grid_power) > max_grid_power:
                    self.logger.warning(f"Grid power usage too high: {grid_power}W")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Safety check failed: {e}")
            return False
    
    async def start_fast_charging(self) -> bool:
        """Start fast charging on the inverter"""
        if not self.inverter:
            self.logger.error("Inverter not connected")
            return False
        
        try:
            # Check safety conditions
            if not await self.check_safety_conditions():
                self.logger.error("Safety conditions not met, cannot start charging")
                return False
            
            fast_charging_config = self.config.get('fast_charging', {})
            
            # Enable fast charging
            if fast_charging_config.get('enable', True):
                await self.inverter.write_setting('fast_charging', 1)
                self.logger.info("Fast charging enabled")
            
            # Set charging power
            power_percentage = fast_charging_config.get('power_percentage', 80)
            await self.inverter.write_setting('fast_charging_power', power_percentage)
            self.logger.info(f"Charging power set to {power_percentage}%")
            
            # Set target SoC
            target_soc = fast_charging_config.get('target_soc', 90)
            await self.inverter.write_setting('fast_charging_soc', target_soc)
            self.logger.info(f"Target SoC set to {target_soc}%")
            
            self.is_charging = True
            self.charging_start_time = datetime.now()
            
            self.logger.info("Fast charging started successfully")
            await self._send_notification("Fast charging started")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start fast charging: {e}")
            return False
    
    async def stop_fast_charging(self) -> bool:
        """Stop fast charging on the inverter"""
        if not self.inverter:
            self.logger.error("Inverter not connected")
            return False
        
        try:
            # Disable fast charging
            await self.inverter.write_setting('fast_charging', 0)
            
            self.is_charging = False
            charging_duration = None
            if self.charging_start_time:
                charging_duration = datetime.now() - self.charging_start_time
            
            self.logger.info("Fast charging stopped")
            if charging_duration:
                self.logger.info(f"Total charging time: {charging_duration}")
            
            await self._send_notification("Fast charging stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop fast charging: {e}")
            return False
    
    async def get_charging_status(self) -> Dict[str, Any]:
        """Get current charging status"""
        if not self.inverter:
            return {'error': 'Inverter not connected'}
        
        try:
            status = await self.get_inverter_status()
            
            # Get fast charging settings
            fast_charging_enabled = await self.inverter.read_setting('fast_charging')
            fast_charging_power = await self.inverter.read_setting('fast_charging_power')
            fast_charging_soc = await self.inverter.read_setting('fast_charging_soc')
            
            charging_info = {
                'is_charging': self.is_charging,
                'fast_charging_enabled': fast_charging_enabled == 1,
                'charging_power_percentage': fast_charging_power,
                'target_soc_percentage': fast_charging_soc,
                'current_battery_soc': status.get('battery_soc', {}).get('value', 'Unknown'),
                'battery_voltage': status.get('battery_voltage', {}).get('value', 'Unknown'),
                'battery_current': status.get('battery_current', {}).get('value', 'Unknown'),
                'grid_power': status.get('grid_power', {}).get('value', 'Unknown'),
                'pv_power': status.get('pv_power', {}).get('value', 'Unknown'),
                'timestamp': datetime.now().isoformat()
            }
            
            if self.charging_start_time:
                charging_info['charging_start_time'] = self.charging_start_time.isoformat()
                charging_info['charging_duration'] = str(datetime.now() - self.charging_start_time)
            
            return charging_info
            
        except Exception as e:
            self.logger.error(f"Failed to get charging status: {e}")
            return {'error': str(e)}
    
    async def monitor_charging(self, duration_minutes: int = 0):
        """Monitor charging progress"""
        if not self.is_charging:
            self.logger.error("Charging not active")
            return
        
        self.logger.info("Starting charging monitoring...")
        start_time = datetime.now()
        
        try:
            while self.is_charging:
                # Check if max time reached
                if duration_minutes > 0:
                    elapsed = datetime.now() - start_time
                    if elapsed.total_seconds() > duration_minutes * 60:
                        self.logger.info("Maximum charging time reached, stopping...")
                        await self.stop_fast_charging()
                        break
                
                # Get current status
                status = await self.get_charging_status()
                if 'error' not in status:
                    battery_soc = status.get('current_battery_soc', 0)
                    target_soc = status.get('target_soc_percentage', 0)
                    
                    self.logger.info(f"Battery SoC: {battery_soc}% / Target: {target_soc}%")
                    
                    # Check if target SoC reached
                    if battery_soc >= target_soc:
                        self.logger.info("Target SoC reached, stopping charging...")
                        await self.stop_fast_charging()
                        break
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except KeyboardInterrupt:
            self.logger.info("Monitoring interrupted by user")
            await self.stop_fast_charging()
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            await self.stop_fast_charging()
    
    async def _send_notification(self, message: str):
        """Send notification about charging status"""
        if not self.config.get('notifications', {}).get('enabled', False):
            return
        
        # Simple webhook notification
        webhook_url = self.config.get('notifications', {}).get('webhook_url', '')
        if webhook_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    payload = {
                        'text': f"GoodWe Inverter: {message}",
                        'timestamp': datetime.now().isoformat()
                    }
                    async with session.post(webhook_url, json=payload) as response:
                        if response.status == 200:
                            self.logger.info("Notification sent successfully")
                        else:
                            self.logger.warning(f"Notification failed: {response.status}")
            except Exception as e:
                self.logger.warning(f"Failed to send notification: {e}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='GoodWe Dynamic Price Optimiser - Fast Charging Control')
    parser.add_argument('--config', '-c', default='../config/fast_charge_config.yaml',
                       help='Configuration file path (default: ../config/fast_charge_config.yaml)')
    parser.add_argument('--start', action='store_true', help='Start fast charging')
    parser.add_argument('--stop', action='store_true', help='Stop fast charging')
    parser.add_argument('--status', action='store_true', help='Show charging status')
    parser.add_argument('--monitor', action='store_true', help='Monitor charging progress')
    
    args = parser.parse_args()
    
    try:
        # Initialize charger
        charger = GoodWeFastCharger(args.config)
        
        # Connect to inverter
        if not await charger.connect_inverter():
            print("Failed to connect to inverter")
            return 1
        
        # Handle commands
        if args.start:
            if await charger.start_fast_charging():
                print("Fast charging started successfully")
                if args.monitor:
                    await charger.monitor_charging()
            else:
                print("Failed to start fast charging")
                return 1
                
        elif args.stop:
            if await charger.stop_fast_charging():
                print("Fast charging stopped successfully")
            else:
                print("Failed to stop fast charging")
                return 1
                
        elif args.status:
            status = await charger.get_charging_status()
            print("\nCharging Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
                
        elif args.monitor:
            print("Monitoring charging status...")
            await charger.monitor_charging()
            
        else:
            # Show current status by default
            status = await charger.get_charging_status()
            print("\nCurrent Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

