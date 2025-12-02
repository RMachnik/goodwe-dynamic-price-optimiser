#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Enhanced Data Collector
Phase 1, Task 1.1: Add PV production monitoring to data collection

This script extends the basic GoodWe monitoring to collect comprehensive data
including PV production, grid flow, battery status, and consumption patterns.
"""

import asyncio
import json
import logging
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import statistics
import yaml

# Import the GoodWe fast charging functionality
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger
from database.storage_factory import StorageFactory

# Setup logging
import os
from pathlib import Path

# Get the project root directory (parent of src)
project_root = Path(__file__).parent.parent
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Logging configuration moved to main application to avoid duplication
logger = logging.getLogger(__name__)

class EnhancedDataCollector:
    """Enhanced data collection system for GoodWe inverter energy management"""
    
    def __init__(self, config_path: str):
        """Initialize the enhanced data collector"""
        # Support both dict config and file path
        if isinstance(config_path, dict):
            self.config_path = None
            self.config = config_path
        else:
            self.config_path = config_path
            # Load config to initialize storage
            try:
                with open(config_path, 'r') as f:
                    self.config = yaml.safe_load(f)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                self.config = {}
        
        self.goodwe_charger = GoodWeFastCharger(config_path if not isinstance(config_path, dict) else self.config)

        # Initialize storage via factory
        self.storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
        
        # Data storage
        self.current_data: Dict[str, Any] = {}
        self.historical_data: List[Dict[str, Any]] = []
        self.daily_stats: Dict[str, Any] = {}
        
        # Monitoring intervals
        self.monitoring_interval = 20  # seconds
        self.data_save_interval = 300  # 5 minutes
        
    async def initialize(self) -> bool:
        """Initialize the system and connect to inverter"""
        logger.info("Initializing GoodWe Dynamic Price Optimiser...")
        
        # Connect to storage
        if not await self.storage.connect():
            logger.error("Failed to connect to data storage")
            # We continue even if storage fails, as we might have fallback or just in-memory
        
        # Connect to GoodWe inverter
        if not await self.goodwe_charger.connect_inverter():
            logger.error("Failed to connect to GoodWe inverter")
            return False
        
        logger.info("Successfully connected to GoodWe inverter")
        
        # Initialize daily stats
        self._initialize_daily_stats()
        
        return True
    
    def _initialize_daily_stats(self):
        """Initialize daily statistics tracking"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.daily_stats = {
            'date': today,
            'pv_production': {
                'total_kwh': 0.0,
                'peak_power': 0.0,
                'peak_time': None,
                'hours_above_1kw': 0,
                'hours_above_5kw': 0
            },
            'battery': {
                'total_charge_kwh': 0.0,
                'total_discharge_kwh': 0.0,
                'min_soc': 100.0,
                'max_soc': 0.0,
                'charge_cycles': 0
            },
            'grid': {
                'total_import_kwh': 0.0,
                'total_export_kwh': 0.0,
                'peak_import': 0.0,
                'peak_export': 0.0,
                'net_consumption': 0.0
            },
            'house_consumption': {
                'total_kwh': 0.0,
                'peak_power': 0.0,
                'peak_time': None
            }
        }
    
    async def collect_comprehensive_data(self) -> Dict[str, Any]:
        """Collect comprehensive data from the GoodWe inverter"""
        try:
            # Get basic inverter status
            status = await self.goodwe_charger.get_charging_status()
            
            # Get detailed sensor data
            sensor_data = await self.goodwe_charger.get_inverter_status()
            
            # Compile comprehensive data
            comprehensive_data = {
                'timestamp': datetime.now().isoformat(),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                
                # Battery Information
                'battery': {
                    'soc_percent': status.get('current_battery_soc', 'Unknown'),
                    'voltage': sensor_data.get('vbattery1', {}).get('value', 'Unknown'),
                    'current': sensor_data.get('ibattery1', {}).get('value', 'Unknown'),
                    'power_w': sensor_data.get('pbattery1', {}).get('value', 'Unknown'),
                    'power_kw': self._convert_to_kw(sensor_data.get('pbattery1', {}).get('value', 0)),
                    'temperature': sensor_data.get('battery_temperature', {}).get('value', 'Unknown'),
                    'charging_status': status.get('is_charging', False),
                    'fast_charging_enabled': status.get('fast_charging_enabled', False)
                },
                
                # PV System Information
                'photovoltaic': {
                    'current_power_w': sensor_data.get('ppv', {}).get('value', 'Unknown'),
                    'current_power_kw': self._convert_to_kw(sensor_data.get('ppv', {}).get('value', 0)),
                    'pv1_power_w': sensor_data.get('ppv1', {}).get('value', 'Unknown'),
                    'pv2_power_w': sensor_data.get('ppv2', {}).get('value', 'Unknown'),
                    'pv1_voltage': sensor_data.get('vpv1', {}).get('value', 'Unknown'),
                    'pv1_current': sensor_data.get('ipv1', {}).get('value', 'Unknown'),
                    'pv2_voltage': sensor_data.get('vpv2', {}).get('value', 'Unknown'),
                    'pv2_current': sensor_data.get('ipv2', {}).get('value', 'Unknown'),
                    'daily_production_kwh': sensor_data.get('e_day', {}).get('value', 'Unknown'),
                    'efficiency_percent': self._calculate_pv_efficiency(sensor_data)
                },
                
                # Grid Information
                'grid': {
                    'power_w': sensor_data.get('meter_active_power_total', {}).get('value', 'Unknown'),
                    'power_kw': self._convert_to_kw(sensor_data.get('meter_active_power_total', {}).get('value', 0)),
                    'voltage': sensor_data.get('vgrid', {}).get('value', 'Unknown'),  # Add grid voltage for safety checks
                    'flow_direction': self._determine_grid_flow(sensor_data.get('meter_active_power_total', {}).get('value', 0)),
                    'import_rate': self._get_import_rate(sensor_data.get('meter_active_power_total', {}).get('value', 0)),
                    'export_rate': self._get_export_rate(sensor_data.get('meter_active_power_total', {}).get('value', 0)),
                    'l1_current_a': sensor_data.get('igrid', {}).get('value', 'Unknown'),
                    'l2_current_a': sensor_data.get('igrid2', {}).get('value', 'Unknown'),
                    'l3_current_a': sensor_data.get('igrid3', {}).get('value', 'Unknown'),
                    'l1_power': sensor_data.get('meter_active_power1', {}).get('value', 'Unknown'),
                    'l2_power': sensor_data.get('meter_active_power2', {}).get('value', 'Unknown'),
                    'l3_power': sensor_data.get('meter_active_power3', {}).get('value', 'Unknown'),
                    'total_exported_kwh': sensor_data.get('meter_e_total_exp', {}).get('value', 'Unknown'),
                    'total_imported_kwh': sensor_data.get('meter_e_total_imp', {}).get('value', 'Unknown'),
                    'today_exported_kwh': sensor_data.get('e_day_exp', {}).get('value', 'Unknown'),
                    'today_imported_kwh': sensor_data.get('e_day_imp', {}).get('value', 'Unknown')
                },
                
                # House Consumption (direct from inverter)
                'house_consumption': {
                    'current_power_w': sensor_data.get('house_consumption', {}).get('value', 'Unknown'),
                    'current_power_kw': self._convert_to_kw(sensor_data.get('house_consumption', {}).get('value', 0)),
                    'daily_total_kwh': sensor_data.get('e_load_day', {}).get('value', 'Unknown'),
                    'total_consumption_kwh': sensor_data.get('e_load_total', {}).get('value', 'Unknown'),
                    'calculated_power_w': self._calculate_house_consumption(sensor_data),
                    'calculated_power_kw': self._convert_to_kw(self._calculate_house_consumption(sensor_data))
                },
                
                # System Status
                'system': {
                    'inverter_model': self.goodwe_charger.inverter.model_name if self.goodwe_charger.inverter else 'Unknown',
                    'inverter_serial': self.goodwe_charger.inverter.serial_number if self.goodwe_charger.inverter else 'Unknown',
                    'connection_status': 'Connected' if self.goodwe_charger.inverter else 'Disconnected',
                    'last_update': datetime.now().isoformat()
                }
            }
            
            # Add compatibility aliases for backward compatibility
            # Map 'system' to 'inverter' for battery_selling_monitor
            if 'system' in comprehensive_data:
                comprehensive_data['inverter'] = comprehensive_data['system'].copy()
                # Initialize error_codes list if not present
                if 'error_codes' not in comprehensive_data['inverter']:
                    comprehensive_data['inverter']['error_codes'] = []
            
            # Map 'photovoltaic' to 'pv' for backward compatibility
            if 'photovoltaic' in comprehensive_data and 'pv' not in comprehensive_data:
                comprehensive_data['pv'] = {
                    'power': comprehensive_data['photovoltaic'].get('current_power_w', 0),
                    'power_w': comprehensive_data['photovoltaic'].get('current_power_w', 0),
                    'total_power': comprehensive_data['photovoltaic'].get('current_power_w', 0)
                }
            
            # Map 'house_consumption' to 'consumption' for backward compatibility
            if 'house_consumption' in comprehensive_data and 'consumption' not in comprehensive_data:
                comprehensive_data['consumption'] = {
                    'house_consumption': comprehensive_data['house_consumption'].get('current_power_w', 0),
                    'power_w': comprehensive_data['house_consumption'].get('current_power_w', 0),
                    'current_power_w': comprehensive_data['house_consumption'].get('current_power_w', 0)
                }
            
            # Store current data
            self.current_data = comprehensive_data
            
            # Add to historical data
            self.historical_data.append(comprehensive_data)
            
            # Update daily statistics
            self._update_daily_stats(comprehensive_data)
            
            # Limit historical data to last 7 days (30240 data points at 20-second intervals)
            # 7 days × 24 hours × 60 minutes × 60 seconds / 20 seconds = 30,240 data points
            if len(self.historical_data) > 30240:
                self.historical_data = self.historical_data[-30240:]
            
            logger.info(f"Data collected successfully at {comprehensive_data['time']}")
            return comprehensive_data
            
        except Exception as e:
            logger.error(f"Failed to collect comprehensive data: {e}")
            return {}
    
    def _convert_to_kw(self, watts: Any) -> float:
        """Convert watts to kilowatts"""
        try:
            if watts == 'Unknown' or watts is None:
                return 0.0
            return float(watts) / 1000.0
        except (ValueError, TypeError):
            return 0.0
    
    def _get_daily_pv_production(self) -> float:
        """Get daily PV production from historical data (fallback method)"""
        try:
            # Fallback to historical calculation
            today = datetime.now().strftime('%Y-%m-%d')
            daily_data = [d for d in self.historical_data if d.get('date') == today]
            
            total_production = 0.0
            for data in daily_data:
                pv_power = data.get('photovoltaic', {}).get('current_power_kw', 0.0)
                if isinstance(pv_power, (int, float)) and pv_power > 0:
                    # Convert power to energy (assuming 20-second intervals)
                    total_production += pv_power / 180.0  # kWh per 20-second interval
            
            return round(total_production, 3)
        except Exception as e:
            logger.error(f"Failed to get daily PV production: {e}")
            return 0.0
    
    def _calculate_pv_efficiency(self, sensor_data: Dict) -> float:
        """Calculate PV system efficiency (placeholder for now)"""
        # This would need actual PV system specifications
        # For now, return a placeholder value
        return 0.0
    
    def _determine_grid_flow(self, grid_power: Any) -> str:
        """Determine grid flow direction"""
        try:
            if grid_power == 'Unknown' or grid_power is None:
                return 'Unknown'
            
            power = float(grid_power)
            if power > 0:
                return 'Import'  # Grid to house
            elif power < 0:
                return 'Export'  # House to grid
            else:
                return 'Neutral'  # No flow
        except (ValueError, TypeError):
            return 'Unknown'
    
    def _get_import_rate(self, grid_power: Any) -> float:
        """Get grid import rate in kW"""
        try:
            if grid_power == 'Unknown' or grid_power is None:
                return 0.0
            
            power = float(grid_power)
            return max(0, power) / 1000.0  # Only positive values (import)
        except (ValueError, TypeError):
            return 0.0
    
    def _get_export_rate(self, grid_power: Any) -> float:
        """Get grid export rate in kW"""
        try:
            if grid_power == 'Unknown' or grid_power is None:
                return 0.0
            
            power = float(grid_power)
            return max(0, -power) / 1000.0  # Only positive values (export)
        except (ValueError, TypeError):
            return 0.0
    
    def _calculate_house_consumption(self, sensor_data: Dict) -> float:
        """Calculate house consumption based on energy balance"""
        try:
            pv_power = sensor_data.get('pv_power', {}).get('value', 0)
            grid_power = sensor_data.get('grid_power', {}).get('value', 0)
            battery_current = sensor_data.get('battery_current', {}).get('value', 0)
            
            # House consumption = PV production + Grid import - Battery charging
            # Note: This is a simplified calculation
            pv_w = float(pv_power) if pv_power != 'Unknown' else 0
            grid_w = float(grid_power) if grid_power != 'Unknown' else 0
            battery_w = float(battery_current) * 48 if battery_current != 'Unknown' else 0  # Approximate voltage
            
            # Grid power is positive for import, negative for export
            house_consumption = pv_w + max(0, grid_w) + max(0, battery_w)
            
            return max(0, house_consumption)  # Ensure non-negative
            
        except (ValueError, TypeError):
            return 0.0
    
    def _get_daily_house_consumption(self) -> float:
        """Get daily house consumption from historical data (fallback method)"""
        try:
            # Fallback to historical calculation
            today = datetime.now().strftime('%Y-%m-%d')
            daily_data = [d for d in self.historical_data if d.get('date') == today]
            
            total_consumption = 0.0
            for data in daily_data:
                consumption = data.get('house_consumption', {}).get('calculated_power_kw', 0.0)
                if isinstance(consumption, (int, float)) and consumption > 0:
                    # Convert power to energy (assuming 20-second intervals)
                    total_consumption += consumption / 180.0  # kWh per 20-second interval
            
            return round(total_consumption, 3)
        except Exception as e:
            logger.error(f"Failed to get daily house consumption: {e}")
            return 0.0
    
    def _update_daily_stats(self, data: Dict[str, Any]):
        """Update daily statistics with new data"""
        try:
            # PV Production stats
            pv_power = data.get('photovoltaic', {}).get('current_power_kw', 0.0)
            if isinstance(pv_power, (int, float)) and pv_power > 0:
                self.daily_stats['pv_production']['total_kwh'] += pv_power / 180.0  # kWh per 20-second interval
                if pv_power > self.daily_stats['pv_production']['peak_power']:
                    self.daily_stats['pv_production']['peak_power'] = pv_power
                    self.daily_stats['pv_production']['peak_time'] = data.get('time')
                
                if pv_power > 1.0:
                    self.daily_stats['pv_production']['hours_above_1kw'] += 1/180
                if pv_power > 5.0:
                    self.daily_stats['pv_production']['hours_above_5kw'] += 1/180
            
            # Battery stats
            battery_soc = data.get('battery', {}).get('soc_percent', 0)
            if isinstance(battery_soc, (int, float)):
                if battery_soc < self.daily_stats['battery']['min_soc']:
                    self.daily_stats['battery']['min_soc'] = battery_soc
                if battery_soc > self.daily_stats['battery']['max_soc']:
                    self.daily_stats['battery']['max_soc'] = battery_soc
            
            # Track battery charging/discharging
            battery_power = data.get('battery', {}).get('power_kw', 0.0)
            if isinstance(battery_power, (int, float)):
                if battery_power > 0:  # Charging
                    self.daily_stats['battery']['total_charge_kwh'] += battery_power / 180.0
                elif battery_power < 0:  # Discharging
                    self.daily_stats['battery']['total_discharge_kwh'] += abs(battery_power) / 180.0
            
            # Grid stats
            grid_power = data.get('grid', {}).get('power_kw', 0.0)
            if isinstance(grid_power, (int, float)):
                if grid_power > 0:  # Import
                    self.daily_stats['grid']['total_import_kwh'] += grid_power / 180.0
                    if grid_power > self.daily_stats['grid']['peak_import']:
                        self.daily_stats['grid']['peak_import'] = grid_power
                elif grid_power < 0:  # Export
                    self.daily_stats['grid']['total_export_kwh'] += abs(grid_power) / 180.0
                    if abs(grid_power) > self.daily_stats['grid']['peak_export']:
                        self.daily_stats['grid']['peak_export'] = abs(grid_power)
                
                # Calculate net grid consumption (import - export)
                self.daily_stats['grid']['net_consumption'] = self.daily_stats['grid']['total_import_kwh'] - self.daily_stats['grid']['total_export_kwh']
            
            # House consumption stats
            house_power = data.get('house_consumption', {}).get('current_power_kw', 0.0)
            if isinstance(house_power, (int, float)) and house_power > 0:
                self.daily_stats['house_consumption']['total_kwh'] += house_power / 180.0
                if house_power > self.daily_stats['house_consumption']['peak_power']:
                    self.daily_stats['house_consumption']['peak_power'] = house_power
                    self.daily_stats['house_consumption']['peak_time'] = data.get('time')
                    
        except Exception as e:
            logger.error(f"Failed to update daily stats: {e}")
    
    async def save_data_to_file(self):
        """Save collected data to storage (file or database)"""
        try:
            # Prepare data for storage
            if self.current_data:
                # Flatten the nested structure for DB schema compatibility
                flat_data = self._flatten_data_for_storage(self.current_data)
                
                # The storage interface expects a list of dicts
                await self.storage.save_energy_data([flat_data])
                
            logger.info("Data saved to storage")
            
        except Exception as e:
            logger.error(f"Failed to save data to storage: {e}")
    
    def _flatten_data_for_storage(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested data structure to match DB schema"""
        try:
            battery = data.get('battery', {})
            pv = data.get('photovoltaic', {})
            grid = data.get('grid', {})
            consumption = data.get('house_consumption', {})
            
            flat = {
                'timestamp': data.get('timestamp') or data.get('time') or datetime.now().isoformat(),
                'battery_soc': self._safe_float(battery.get('soc_percent')),
                'pv_power': self._safe_int(pv.get('current_power_w')),
                'grid_power': self._safe_int(grid.get('power_w')),
                'house_consumption': self._safe_int(consumption.get('current_power_w')),
                'battery_power': self._safe_int(battery.get('power_w')),
                'grid_voltage': self._safe_float(grid.get('voltage')),
                'grid_frequency': None,  # Not available in current data structure
                'battery_voltage': self._safe_float(battery.get('voltage')),
                'battery_current': self._safe_float(battery.get('current')),
                'battery_temperature': self._safe_float(battery.get('temperature')),
                'price_pln': None  # Will be set by caller if price data available
            }
            return flat
        except Exception as e:
            logger.error(f"Failed to flatten data: {e}")
            return {'timestamp': datetime.now().isoformat()}
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float, returning None for invalid values"""
        if value is None or value == 'Unknown':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int, returning None for invalid values"""
        if value is None or value == 'Unknown':
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current system data"""
        return self.current_data.copy() if self.current_data else {}
    
    def print_current_status(self):
        """Print current system status"""
        if not self.current_data:
            print("No data available")
            return
        
        data = self.current_data
        
        print("\n" + "="*80)
        print("GOODWE DYNAMIC PRICE OPTIMISER - CURRENT STATUS")
        print("="*80)
        print(f"Timestamp: {data.get('timestamp', 'Unknown')}")
        print(f"Inverter: {data.get('system', {}).get('inverter_model', 'Unknown')}")
        print(f"Connection: {data.get('system', {}).get('connection_status', 'Unknown')}")
        print()
        
        # Battery Status
        battery = data.get('battery', {})
        print("🔋 BATTERY STATUS:")
        print(f"  State of Charge: {battery.get('soc_percent', 'Unknown')}%")
        print(f"  Voltage: {battery.get('voltage', 'Unknown')} V")
        print(f"  Current: {battery.get('current', 'Unknown')} A")
        print(f"  Power: {battery.get('power_w', 'Unknown')} W ({battery.get('power_kw', 'Unknown')} kW)")
        print(f"  Temperature: {battery.get('temperature', 'Unknown')}°C")
        print(f"  Charging: {'Yes' if battery.get('charging_status') else 'No'}")
        print(f"  Fast Charging: {'Enabled' if battery.get('fast_charging_enabled') else 'Disabled'}")
        print()
        
        # PV System Status
        pv = data.get('photovoltaic', {})
        print("☀️ PHOTOVOLTAIC SYSTEM:")
        print(f"  Total Power: {pv.get('current_power_w', 'Unknown')} W ({pv.get('current_power_kw', 'Unknown')} kW)")
        print(f"  PV1 Power: {pv.get('pv1_power_w', 'Unknown')} W")
        print(f"  PV2 Power: {pv.get('pv2_power_w', 'Unknown')} W")
        print(f"  PV1 Voltage: {pv.get('pv1_voltage', 'Unknown')} V")
        print(f"  PV1 Current: {pv.get('pv1_current', 'Unknown')} A")
        print(f"  Daily Production: {pv.get('daily_production_kwh', 'Unknown')} kWh")
        print()
        
        # Grid Status
        grid = data.get('grid', {})
        print("⚡ GRID STATUS:")
        print(f"  Total Power: {grid.get('power_w', 'Unknown')} W ({grid.get('power_kw', 'Unknown')} kW)")
        print(f"  L1 Current: {grid.get('l1_current_a', 'Unknown')} A")
        print(f"  L2 Current: {grid.get('l2_current_a', 'Unknown')} A")
        print(f"  L3 Current: {grid.get('l3_current_a', 'Unknown')} A")
        print(f"  L1 Power: {grid.get('l1_power', 'Unknown')} W")
        print(f"  L2 Power: {grid.get('l2_power', 'Unknown')} W")
        print(f"  L3 Power: {grid.get('l3_power', 'Unknown')} W")
        print(f"  Flow Direction: {grid.get('flow_direction', 'Unknown')}")
        print(f"  Total Exported: {grid.get('total_exported_kwh', 'Unknown')} kWh")
        print(f"  Total Imported: {grid.get('total_imported_kwh', 'Unknown')} kWh")
        print(f"  Today Exported: {grid.get('today_exported_kwh', 'Unknown')} kWh")
        print(f"  Today Imported: {grid.get('today_imported_kwh', 'Unknown')} kWh")
        print()
        
        # House Consumption
        house = data.get('house_consumption', {})
        print("🏠 HOUSE CONSUMPTION:")
        print(f"  Current Power: {house.get('current_power_w', 'Unknown')} W ({house.get('current_power_kw', 'Unknown')} kW)")
        print(f"  Daily Total: {house.get('daily_total_kwh', 'Unknown')} kWh")
        print(f"  Total Consumption: {house.get('total_consumption_kwh', 'Unknown')} kWh")
        print(f"  Calculated Power: {house.get('calculated_power_w', 'Unknown')} W ({house.get('calculated_power_kw', 'Unknown')} kW)")
        print()
        
        # Daily Statistics Summary
        print("📊 DAILY STATISTICS:")
        print(f"  PV Production: {self.daily_stats['pv_production']['total_kwh']:.3f} kWh")
        print(f"  House Consumption: {self.daily_stats['house_consumption']['total_kwh']:.3f} kWh")
        print(f"  Grid Import: {self.daily_stats['grid']['total_import_kwh']:.3f} kWh")
        print(f"  Grid Export: {self.daily_stats['grid']['total_export_kwh']:.3f} kWh")
        print(f"  Grid Net: {self.daily_stats['grid']['net_consumption']:.3f} kWh")
        print(f"  Battery Min SoC: {self.daily_stats['battery']['min_soc']:.1f}%")
        print(f"  Battery Max SoC: {self.daily_stats['battery']['max_soc']:.1f}%")
        print(f"  Battery Charged: {self.daily_stats['battery']['total_charge_kwh']:.3f} kWh")
        print(f"  Battery Discharged: {self.daily_stats['battery']['total_discharge_kwh']:.3f} kWh")
        print(f"  PV Peak Power: {self.daily_stats['pv_production']['peak_power']:.2f} kW")
        print(f"  House Peak Power: {self.daily_stats['house_consumption']['peak_power']:.2f} kW")
    
    async def start_monitoring(self, duration_minutes: int = 60):
        """Start continuous monitoring for specified duration"""
        logger.info(f"Starting enhanced data collection for {duration_minutes} minutes")
        logger.info(f"Monitoring interval: {self.monitoring_interval} seconds")
        logger.info(f"Data save interval: {self.data_save_interval} seconds")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        last_save_time = start_time
        
        try:
            while datetime.now() < end_time:
                # Collect data
                await self.collect_comprehensive_data()
                
                # Save data periodically
                if (datetime.now() - last_save_time).total_seconds() >= self.data_save_interval:
                    await self.save_data_to_file()
                    last_save_time = datetime.now()
                
                # Print status every 5 minutes
                if (datetime.now() - start_time).total_seconds() % 300 < self.monitoring_interval:
                    self.print_current_status()
                
                # Wait for next collection
                await asyncio.sleep(self.monitoring_interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring interrupted by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}")
        finally:
            # Final data save
            await self.save_data_to_file()
            logger.info("Enhanced data collection completed")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='GoodWe Dynamic Price Optimiser - Enhanced Data Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in interactive mode (default)
  python enhanced_data_collector.py
  
  # Start continuous monitoring for 30 minutes
  python enhanced_data_collector.py --monitor 30
  
  # Collect single data point and exit
  python enhanced_data_collector.py --single
  
  # Show current status and exit
  python enhanced_data_collector.py --status
  
  # Use custom config file
  python enhanced_data_collector.py --config my_config.yaml --monitor 60
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/master_coordinator_config.yaml',
        help='Configuration file path (default: config/master_coordinator_config.yaml)'
    )
    
    parser.add_argument(
        '--monitor', '-m',
        type=int,
        metavar='MINUTES',
        help='Start continuous monitoring for specified minutes'
    )
    
    parser.add_argument(
        '--single', '-s',
        action='store_true',
        help='Collect single data point and exit'
    )
    
    parser.add_argument(
        '--status', '-t',
        action='store_true',
        help='Show current status and exit'
    )
    
    parser.add_argument(
        '--non-interactive', '-n',
        action='store_true',
        help='Run in non-interactive mode (useful for automation)'
    )
    
    return parser.parse_args()

async def main():
    """Main function to demonstrate the enhanced data collector"""
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Configuration
    config_file = args.config
    
    if not Path(config_file).exists():
        print(f"Configuration file {config_file} not found!")
        print("Please ensure the GoodWe inverter configuration is set up first.")
        return
    
    # Initialize enhanced data collector
    collector = EnhancedDataCollector(config_file)
    
    if not await collector.initialize():
        print("Failed to initialize GoodWe Dynamic Price Optimiser")
        return
    
    # Show current status
    print("GoodWe Dynamic Price Optimiser initialized successfully!")
    print("Collecting initial data...")
    
    # Collect initial data
    await collector.collect_comprehensive_data()
    collector.print_current_status()
    
    # Handle command-line arguments
    if args.monitor:
        print(f"\n🚀 Starting continuous monitoring for {args.monitor} minutes...")
        print("Press Ctrl+C to stop early")
        await collector.start_monitoring(args.monitor)
        return
        
    elif args.single:
        print("\n📊 Collecting new data point...")
        await collector.collect_comprehensive_data()
        collector.print_current_status()
        return
        
    elif args.status:
        print("\n📊 Current Status:")
        collector.print_current_status()
        return
        
    elif args.non_interactive:
        print("\nRunning in non-interactive mode. Use --help for available options.")
        return
    
    # If no specific action requested, show interactive menu
    print("\n" + "="*80)
    print("ENHANCED DATA COLLECTOR OPTIONS:")
    print("1. Start continuous monitoring (60 minutes)")
    print("2. Collect single data point")
    print("3. Show current status")
    print("4. Save current data to files")
    print("5. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-5): ").strip()
            
            if choice == "1":
                print("Starting continuous monitoring for 60 minutes...")
                print("Press Ctrl+C to stop early")
                await collector.start_monitoring(60)
                break
                
            elif choice == "2":
                print("Collecting new data point...")
                await collector.collect_comprehensive_data()
                collector.print_current_status()
                
            elif choice == "3":
                collector.print_current_status()
                
            elif choice == "4":
                print("Saving data to files...")
                await collector.save_data_to_file()
                print("Data saved successfully!")
                
            elif choice == "5":
                print("Exiting...")
                break
                
            else:
                print("Invalid choice. Please enter 1-5.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
