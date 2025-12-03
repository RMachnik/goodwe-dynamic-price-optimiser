#!/usr/bin/env python3
"""
Master Coordinator for GoodWe Enhanced Energy Management System
Orchestrates all components: data collection, decision engine, and action execution

This is the main service that coordinates:
- Enhanced data collection (PV, grid, battery, consumption)
- Multi-factor decision engine (price + PV + consumption + battery)
- Automated charging control
- Price analysis and optimization
- System monitoring and health checks
"""

import asyncio
import json
import logging
import time
import argparse
import signal
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import statistics
from database.storage_factory import StorageFactory
from database.storage_interface import DataStorageInterface

# Import all the component modules
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger
from enhanced_data_collector import EnhancedDataCollector
from automated_price_charging import AutomatedPriceCharger
from log_web_server import LogWebServer
from pv_forecasting import PVForecaster
from price_window_analyzer import PriceWindowAnalyzer
from hybrid_charging_logic import HybridChargingLogic
from weather_data_collector import WeatherDataCollector
from pv_consumption_analyzer import PVConsumptionAnalyzer
from pv_trend_analyzer import PVTrendAnalyzer
from multi_session_manager import MultiSessionManager
from battery_selling_engine import BatterySellingEngine
from battery_selling_monitor import BatterySellingMonitor
from pse_price_forecast_collector import PSEPriceForecastCollector
from pse_peak_hours_collector import PSEPeakHoursCollector

# Setup logging
project_root = Path(__file__).parent.parent
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'master_coordinator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemState(Enum):
    """System operational states"""
    INITIALIZING = "initializing"
    MONITORING = "monitoring"
    CHARGING = "charging"
    OPTIMIZING = "optimizing"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class MasterCoordinator:
    """Master coordinator for the entire energy management system"""
    
    def __init__(self, config_path: str = None):
        """Initialize the master coordinator"""
        if config_path is None:
            current_dir = Path(__file__).parent.parent
            self.config_path = str(current_dir / "config" / "master_coordinator_config.yaml")
        else:
            self.config_path = config_path
            
        # System state
        self.state = SystemState.INITIALIZING
        self.is_running = False
        self.start_time = None
        self.last_decision_time = None
        self.health_check_interval = 300  # 5 minutes
        self.decision_interval = 900  # 15 minutes
        self.multi_session_hold = False
        
        # Component managers
        self.data_collector = None
        self.charging_controller = None
        self.decision_engine = None
        self.log_web_server = None
        self.web_server_thread = None
        self.weather_collector = None
        self.pv_consumption_analyzer = None
        self.multi_session_manager = None
        self.battery_selling_engine = None
        self.battery_selling_monitor = None
        self.forecast_collector = None
        self.peak_hours_collector = None
        
        # System data
        self.current_data = {}
        self.historical_data = []
        self.decision_history = []
        self.performance_metrics = {}
        self.last_save_time = datetime.now()  # Track last data save time
        
        # Configuration
        self.config = self._load_config()
        
        # Initialize storage
        self.storage: Optional[DataStorageInterface] = None
        try:
            self.storage = StorageFactory.create_storage(self.config.get('data_storage', {}))
        except Exception as e:
            logger.error(f"Failed to create storage: {e}")
            
        self._setup_logging()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            import yaml
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Add coordinator-specific configuration defaults (only if not present)
            if 'coordinator' not in config:
                config['coordinator'] = {}
            
            # Set defaults only for missing keys
            config['coordinator'].setdefault('decision_interval_minutes', 15)
            config['coordinator'].setdefault('health_check_interval_minutes', 5)
            config['coordinator'].setdefault('data_retention_days', 30)
            config['coordinator'].setdefault('max_charging_sessions_per_day', 4)
            
            # Set emergency stop defaults only if not present
            if 'emergency_stop_conditions' not in config['coordinator']:
                config['coordinator']['emergency_stop_conditions'] = {
                    'battery_temp_max': 60.0,
                    'battery_voltage_min': 45.0,
                    'battery_voltage_max': 58.0,
                    'grid_voltage_min': 200.0,
                    'grid_voltage_max': 250.0
                }
            
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        logging.getLogger().setLevel(getattr(logging, log_level.upper()))
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.is_running = False
    
    async def initialize(self) -> bool:
        """Initialize all system components"""
        logger.info("Initializing Master Coordinator...")
        
        try:
            # Initialize storage connection
            if self.storage:
                if not await self.storage.connect():
                    logger.error("Failed to connect to storage")
                    # We continue even if storage fails, as it might be optional or have fallback
            
            # Initialize data collector
            logger.info("Initializing Enhanced Data Collector...")
            self.data_collector = EnhancedDataCollector(self.config_path)
            if not await self.data_collector.initialize():
                logger.error("Failed to initialize data collector")
                return False
            
            # Price analysis is now handled by AutomatedPriceCharger
            logger.info("Price analysis handled by AutomatedPriceCharger...")
            
            # Initialize charging controller
            logger.info("Initializing Charging Controller...")
            self.charging_controller = AutomatedPriceCharger(self.config_path)
            if not await self.charging_controller.initialize():
                logger.error("Failed to initialize charging controller")
                return False
            
            # Initialize weather data collector
            logger.info("Initializing Weather Data Collector...")
            weather_enabled = self.config.get('weather_integration', {}).get('enabled', True)
            if weather_enabled:
                self.weather_collector = WeatherDataCollector(self.config)
                logger.info("Weather Data Collector initialized successfully")
            else:
                logger.info("Weather integration disabled in configuration")
            
            # Initialize PSE Price Forecast Collector
            logger.info("Initializing PSE Price Forecast Collector...")
            forecast_enabled = self.config.get('pse_price_forecast', {}).get('enabled', True)
            if forecast_enabled:
                self.forecast_collector = PSEPriceForecastCollector(self.config)
                logger.info("PSE Price Forecast Collector initialized successfully")
            else:
                logger.info("PSE price forecast disabled in configuration")

            # Initialize PSE Peak Hours Collector (Kompas)
            logger.info("Initializing PSE Peak Hours Collector...")
            peak_enabled = self.config.get('pse_peak_hours', {}).get('enabled', False)
            if peak_enabled:
                self.peak_hours_collector = PSEPeakHoursCollector(self.config)
                logger.info("PSE Peak Hours Collector initialized successfully")
            else:
                logger.info("PSE peak hours disabled in configuration")
            
            # Initialize decision engine
            logger.info("Initializing Decision Engine...")
            self.decision_engine = MultiFactorDecisionEngine(self.config, self.charging_controller)
            
            # Initialize PV vs consumption analyzer
            logger.info("Initializing PV vs Consumption Analyzer...")
            self.pv_consumption_analyzer = PVConsumptionAnalyzer(self.config)
            logger.info("PV vs Consumption Analyzer initialized successfully")
            
            # Set weather collector in PV forecaster if available
            if self.decision_engine and hasattr(self.decision_engine, 'pv_forecaster') and self.weather_collector:
                self.decision_engine.pv_forecaster.set_weather_collector(self.weather_collector)
                logger.info("Weather collector integrated with PV forecaster")
            
            # Set PV consumption analyzer in decision engine
            if self.decision_engine and self.pv_consumption_analyzer:
                self.decision_engine.pv_consumption_analyzer = self.pv_consumption_analyzer
                logger.info("PV consumption analyzer integrated with decision engine")
            
            # Set forecast collector in decision engine
            if self.decision_engine and self.forecast_collector:
                self.decision_engine.forecast_collector = self.forecast_collector
                logger.info("PSE Price Forecast Collector integrated with decision engine")

            # Set peak hours collector in decision engine
            if self.decision_engine and self.peak_hours_collector:
                self.decision_engine.peak_hours_collector = self.peak_hours_collector
                logger.info("PSE Peak Hours Collector integrated with decision engine")
            
            # Initialize multi-session manager with storage support
            logger.info("Initializing Multi-Session Manager...")
            self.multi_session_manager = MultiSessionManager(self.config, storage=self.storage)
            logger.info("Multi-Session Manager initialized successfully")
            
            # Initialize battery selling engine
            battery_selling_enabled = self.config.get('battery_selling', {}).get('enabled', False)
            if battery_selling_enabled:
                logger.info("Initializing Battery Selling Engine...")
                # Pass only the battery_selling config section
                battery_selling_config = self.config.get('battery_selling', {})
                self.battery_selling_engine = BatterySellingEngine(battery_selling_config)
                self.battery_selling_monitor = BatterySellingMonitor(battery_selling_config)
                logger.info("Battery Selling Engine initialized successfully")
                
                # Ensure inverter is in safe state on startup
                if self.charging_controller and self.charging_controller.goodwe_charger.inverter:
                    await self.battery_selling_engine.ensure_safe_state(
                        self.charging_controller.goodwe_charger.inverter
                    )
            else:
                logger.info("Battery selling disabled in configuration")
            
            # Initialize log web server
            logger.info("Initializing Log Web Server...")
            web_server_config = self.config.get('web_server', {})
            web_host = web_server_config.get('host', '0.0.0.0')
            web_port = web_server_config.get('port', 8080)
            web_enabled = web_server_config.get('enabled', True)
            
            if web_enabled:
                self.log_web_server = LogWebServer(
                    host=web_host, 
                    port=web_port, 
                    log_dir=str(logs_dir),
                    config=self.config
                )
                # Start web server in a separate thread
                self.web_server_thread = threading.Thread(
                    target=self.log_web_server.start,
                    daemon=True,
                    name="LogWebServer"
                )
                self.web_server_thread.start()
                logger.info(f"Log web server started on {web_host}:{web_port}")
            else:
                logger.info("Log web server disabled in configuration")
            
            self.state = SystemState.MONITORING
            logger.info("Master Coordinator initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Master Coordinator: {e}")
            self.state = SystemState.ERROR
            return False
    
    async def start(self):
        """Start the master coordinator service"""
        if not await self.initialize():
            logger.error("Failed to initialize, cannot start service")
            return
        
        self.is_running = True
        self.start_time = datetime.now()
        logger.info("Master Coordinator started successfully")
        
        try:
            # Start main coordination loop
            await self._coordination_loop()
        except Exception as e:
            logger.error(f"Error in coordination loop: {e}")
            self.state = SystemState.ERROR
        finally:
            await self.shutdown()
    
    async def _coordination_loop(self):
        """Main coordination loop"""
        logger.info("Starting coordination loop...")
        
        while self.is_running:
            try:
                # Collect current data
                await self._collect_system_data()
                
                # Perform health checks
                await self._perform_health_checks()
                
                # Make decisions if needed
                if self._should_make_decision():
                    await self._make_charging_decision()
                
                # Update system state
                await self._update_system_state()
                
                # Log system status
                self._log_system_status()
                
                # Wait before next iteration
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in coordination loop: {e}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _collect_system_data(self):
        """Collect comprehensive system data including weather"""
        try:
            # Collect weather data if enabled
            if self.weather_collector:
                try:
                    weather_data = await self.weather_collector.collect_weather_data()
                    if weather_data:
                        self.current_data['weather'] = weather_data
                        logger.debug("Weather data collected successfully")
                    else:
                        logger.warning("No weather data collected")
                except Exception as e:
                    logger.error(f"Failed to collect weather data: {e}")
            
            # Collect data from all sources
            await self.data_collector.collect_comprehensive_data()
            self.current_data.update(self.data_collector.get_current_data())
            
            # Save data to storage periodically (every 5 minutes)
            if (datetime.now() - self.last_save_time).total_seconds() >= 300:
                try:
                    await self.data_collector.save_data_to_file()
                    await self._save_system_state()
                    self.last_save_time = datetime.now()
                    logger.debug("Data saved to storage")
                except Exception as e:
                    logger.error(f"Failed to save data to storage: {e}")
            
            # Update PV vs consumption analyzer with current data
            if self.pv_consumption_analyzer:
                self.pv_consumption_analyzer.update_consumption_history(self.current_data)
            
            # Store historical data
            self.historical_data.append({
                'timestamp': datetime.now(),
                'data': self.current_data.copy()
            })
            
            # Keep only last 24 hours of data
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.historical_data = [
                entry for entry in self.historical_data 
                if entry['timestamp'] > cutoff_time
            ]
            
        except Exception as e:
            logger.error(f"Failed to collect system data: {e}")
    
    async def _perform_health_checks(self):
        """Perform system health checks (GoodWe Lynx-D compliant)"""
        try:
            # Check inverter connectivity
            if not self.charging_controller.goodwe_charger.is_connected():
                logger.warning("Inverter connection lost, attempting to reconnect...")
                await self.charging_controller.goodwe_charger.connect_inverter()
            
            # Check GoodWe Lynx-D compliance
            compliance = self._check_goodwe_lynx_d_compliance()
            if not compliance["compliant"]:
                logger.error(f"GoodWe Lynx-D compliance issues: {compliance['issues']}")
                if compliance["issues"]:  # Only stop for critical issues, not warnings
                    await self._emergency_stop()
                    return
            
            # Log compliance warnings
            if compliance["warnings"]:
                for warning in compliance["warnings"]:
                    logger.warning(f"GoodWe Lynx-D compliance warning: {warning}")
            
            # Check emergency conditions
            if self._check_emergency_conditions():
                logger.critical("Emergency conditions detected, stopping all operations")
                await self._emergency_stop()
                return
            
            # Check system performance
            self._update_performance_metrics()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def _check_emergency_conditions(self) -> bool:
        """Check for emergency stop conditions (GoodWe Lynx-D compliant)"""
        if not self.current_data:
            return False
        
        emergency_config = self.config.get('coordinator', {}).get('emergency_stop_conditions', {})
        battery_data = self.current_data.get('battery', {})
        
        # Check battery temperature (GoodWe Lynx-D: 0°C to 53°C for charging)
        battery_temp = battery_data.get('temperature', 0)
        temp_max = emergency_config.get('battery_temp_max', 53.0)
        temp_min = emergency_config.get('battery_temp_min', 0.0)
        
        if battery_temp > temp_max:
            logger.critical(f"Battery temperature too high: {battery_temp}°C (max: {temp_max}°C)")
            return True
        if battery_temp < temp_min:
            logger.critical(f"Battery temperature too low for charging: {battery_temp}°C (min: {temp_min}°C)")
            return True
        
        # Check battery voltage (GoodWe Lynx-D: 320V to 480V)
        battery_voltage = battery_data.get('voltage', 0)
        voltage_min = emergency_config.get('battery_voltage_min', 320.0)
        voltage_max = emergency_config.get('battery_voltage_max', 480.0)
        
        # Debug logging (can be removed in production)
        logger.debug(f"Emergency check - voltage: {battery_voltage}V, min: {voltage_min}V, max: {voltage_max}V")
        
        if battery_voltage < voltage_min:
            logger.critical(f"Battery voltage too low: {battery_voltage}V (min: {voltage_min}V)")
            return True
        if battery_voltage > voltage_max:
            logger.critical(f"Battery voltage too high: {battery_voltage}V (max: {voltage_max}V)")
            return True
        
        # Check for temperature warning (GoodWe Lynx-D specific)
        temp_warning = emergency_config.get('battery_temp_warning', 50.0)
        if battery_temp > temp_warning:
            logger.warning(f"Battery temperature warning: {battery_temp}°C (warning threshold: {temp_warning}°C)")
        
        return False
    
    async def _emergency_stop(self):
        """Emergency stop all operations (GoodWe Lynx-D compliant)"""
        logger.critical("EMERGENCY STOP INITIATED - GoodWe Lynx-D Safety Protocol")
        self.state = SystemState.ERROR
        
        try:
            # Stop charging immediately
            await self.charging_controller.stop_price_based_charging()
            logger.info("Emergency stop: Charging stopped")
            
            # Check for undervoltage condition and enable auto-reboot if configured
            emergency_config = self.config.get('coordinator', {}).get('emergency_stop_conditions', {})
            if emergency_config.get('undervoltage_reboot', False):
                battery_voltage = self._safe_float(self.current_data.get('battery', {}).get('voltage', 0))
                voltage_min = emergency_config.get('battery_voltage_min', 320.0)
                
                if battery_voltage < voltage_min:
                    logger.info("Undervoltage detected - enabling auto-reboot when voltage recovers")
                    # The GoodWe Lynx-D will auto-reboot when voltage returns to safe level
                    
        except Exception as e:
            logger.error(f"Failed to stop charging during emergency: {e}")
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float, handling strings and None"""
        if value is None:
            return 0.0
        if isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0
    
    def _check_goodwe_lynx_d_compliance(self) -> Dict[str, Any]:
        """Check GoodWe Lynx-D specific compliance and safety features"""
        if not self.current_data:
            return {"compliant": False, "issues": ["No data available"]}
        
        battery_data = self.current_data.get('battery', {})
        battery_config = self.config.get('battery_management', {})
        
        compliance_status = {
            "compliant": True,
            "issues": [],
            "warnings": [],
            "features": {
                "bms_integration": battery_config.get('bms_integration', False),
                "vde_2510_50_compliance": battery_config.get('vde_2510_50_compliance', False),
                "auto_reboot_undervoltage": battery_config.get('auto_reboot_undervoltage', False)
            }
        }
        
        # Check voltage range compliance (320V - 480V)
        voltage = self._safe_float(battery_data.get('voltage', 0))
        voltage_min = battery_config.get('voltage_range', {}).get('min', 320.0)
        voltage_max = battery_config.get('voltage_range', {}).get('max', 480.0)
        
        if voltage < voltage_min or voltage > voltage_max:
            compliance_status["compliant"] = False
            compliance_status["issues"].append(f"Battery voltage {voltage}V outside GoodWe Lynx-D range ({voltage_min}V - {voltage_max}V)")
        
        # Check temperature compliance (0°C - 53°C for charging)
        temperature = self._safe_float(battery_data.get('temperature', 0))
        temp_min = battery_config.get('temperature_thresholds', {}).get('charging_min', 0.0)
        temp_max = battery_config.get('temperature_thresholds', {}).get('charging_max', 53.0)
        
        if temperature < temp_min or temperature > temp_max:
            compliance_status["compliant"] = False
            compliance_status["issues"].append(f"Battery temperature {temperature}°C outside GoodWe Lynx-D range ({temp_min}°C - {temp_max}°C)")
        
        # Check for LFP battery type
        battery_type = battery_config.get('battery_type', '')
        if battery_type != 'LFP':
            compliance_status["warnings"].append(f"Battery type {battery_type} - GoodWe Lynx-D uses LFP technology")
        
        return compliance_status
    
    def _should_make_decision(self) -> bool:
        """Determine if it's time to make a charging decision"""
        if not self.last_decision_time:
            return True
        
        time_since_last = datetime.now() - self.last_decision_time
        return time_since_last.total_seconds() >= self.decision_interval
    
    async def _make_charging_decision(self):
        """Make intelligent charging decision using enhanced smart strategy with multi-session support and battery selling"""
        try:
            logger.info("Making charging decision...")
            
            # Check if multi-session charging is enabled and handle session management
            if self.multi_session_manager and self.multi_session_manager.enabled:
                await self._handle_multi_session_logic()
            
            # Get current price data using AutomatedPriceCharger (has correct SC calculation)
            price_data = self.charging_controller.fetch_price_data_for_date(
                datetime.now().strftime('%Y-%m-%d')
            )
            if not price_data:
                logger.warning("No price data available, skipping decision")
                return
            
            # Check battery selling opportunities if enabled
            if self.battery_selling_engine and self.battery_selling_monitor:
                await self._handle_battery_selling_logic(price_data)
            
            # Use smart charging strategy
            decision = self.charging_controller.make_smart_charging_decision(
                current_data=self.current_data,
                price_data=price_data
            )
            
            # Execute decision
            await self._execute_smart_decision(decision)
            
            # Record decision
            decision_record = {
                'timestamp': datetime.now(),
                'decision': decision,
                'reasoning': decision.get('reason', ''),
                'confidence': decision.get('confidence', 0),
                'priority': decision.get('priority', 'unknown')
            }
            self.decision_history.append(decision_record)
            
            # Save decision to file for dashboard
            await self._save_decision_to_file(decision_record)
            
            self.last_decision_time = datetime.now()
            logger.info(f"Decision made: {decision.get('should_charge', False)} - {decision.get('reason', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to make charging decision: {e}")
    
    async def _save_decision_to_file(self, decision_record: Dict[str, Any]):
        """Save decision data to file for dashboard consumption"""
        try:
            import json
            from pathlib import Path
            
            # Create energy_data directory if it doesn't exist
            project_root = Path(__file__).parent.parent
            energy_data_dir = project_root / "out" / "energy_data"
            energy_data_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = decision_record['timestamp'].strftime('%Y%m%d_%H%M%S')
            filename = f"charging_decision_{timestamp}.json"
            file_path = energy_data_dir / filename
            
            # Get current price data for the decision using AutomatedPriceCharger
            current_price_data = self.charging_controller.fetch_price_data_for_date(
                decision_record['timestamp'].strftime('%Y-%m-%d')
            )
            
            # Extract price information
            current_price = 0
            cheapest_price = 0
            cheapest_hour = 0
            
            if current_price_data and 'value' in current_price_data:
                try:
                    # Get current price
                    now = decision_record['timestamp']
                    current_time = now.replace(second=0, microsecond=0)
                    
                    # Use AutomatedPriceCharger for consistent price calculation
                    current_price = self.charging_controller.get_current_price(current_price_data)
                    if current_price:
                        current_price = current_price / 1000  # Convert PLN/MWh to PLN/kWh
                    
                    # Find cheapest price using AutomatedPriceCharger
                    prices = []
                    for item in current_price_data['value']:
                        market_price = float(item['csdac_pln'])
                        item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                        final_price = self.charging_controller.calculate_final_price(market_price, item_time)
                        final_price_kwh = final_price / 1000  # Convert PLN/MWh to PLN/kWh
                        prices.append((final_price_kwh, item_time.hour))
                    if prices:
                        cheapest_price, cheapest_hour = min(prices, key=lambda x: x[0])
                        # Calculate daily average for savings reference
                        daily_avg_price = sum(p[0] for p in prices) / len(prices)
                    else:
                        daily_avg_price = 0.4  # Fallback default
                        
                except Exception as e:
                    logger.warning(f"Failed to extract price data: {e}")
            
            # Calculate energy and cost for charging decisions
            should_charge = decision_record['decision'].get('should_charge', False)
            energy_kwh = 0
            estimated_cost_pln = 0
            estimated_savings_pln = 0
            
            if should_charge:
                # Check if this is a partial charge with explicit energy requirement
                if decision_record['decision'].get('partial_charge', False):
                    # Use the actual values from partial charging decision
                    energy_kwh = decision_record['decision'].get('required_kwh', 0)
                    target_soc = decision_record['decision'].get('target_soc', 80)
                    
                    logger.debug(f"Partial charge decision: {energy_kwh:.2f} kWh to {target_soc}% SOC")
                else:
                    # Calculate energy needed based on battery capacity and current SOC
                    battery_capacity = self.config.get('battery_management', {}).get('capacity_kwh', 20.0)
                    current_soc = self.current_data.get('battery', {}).get('soc_percent', 0)
                    target_soc = 80.0  # Target 80% SOC
                    energy_needed = battery_capacity * (target_soc - current_soc) / 100.0
                    energy_kwh = max(0, min(energy_needed, 5.0))  # Cap at 5kWh per decision
                
                # Calculate cost based on current price
                if current_price > 0 and energy_kwh > 0:
                    # current_price is already in PLN/kWh (converted on line 623)
                    estimated_cost_pln = energy_kwh * current_price
                    
                    # Calculate savings compared to daily average price (smart vs dumb charging)
                    reference_price = daily_avg_price if 'daily_avg_price' in locals() and daily_avg_price > 0 else 0.60
                    reference_cost = energy_kwh * reference_price
                    estimated_savings_pln = max(0, reference_cost - estimated_cost_pln)
            
            # Prepare decision data for dashboard
            decision_data = {
                'timestamp': decision_record['timestamp'].isoformat(),
                'action': 'charge' if should_charge else 'wait',
                'source': decision_record['decision'].get('charging_source', 'grid'),  # Default to grid
                'duration': decision_record['decision'].get('charging_time_hours', 0),
                'energy_kwh': energy_kwh,
                'estimated_cost_pln': estimated_cost_pln,
                'estimated_savings_pln': estimated_savings_pln,
                'confidence': decision_record['confidence'],
                'reason': decision_record['reasoning'],
                'priority': decision_record['priority'],
                'battery_soc': self.current_data.get('battery', {}).get('soc_percent', 0),
                'pv_power': self.current_data.get('photovoltaic', {}).get('current_power_w', 0),
                'house_consumption': self.current_data.get('house_consumption', {}).get('current_power_w', 0),
                'current_price': current_price,
                'cheapest_price': cheapest_price,
                'cheapest_hour': cheapest_hour
            }
            
            # Save to storage
            if self.storage:
                # Add decision_type for storage schema
                decision_data['decision_type'] = 'charging'
                logger.info(f"Storage type: {type(self.storage).__name__}, attempting to save decision to storage: {decision_data.get('timestamp')}, action={decision_data.get('action')}")
                result = await self.storage.save_decision(decision_data)
                if result:
                    logger.info(f"✅ Decision saved to storage successfully")
                else:
                    logger.error(f"❌ Failed to save decision to storage (returned False)")
            else:
                # Fallback to file
                with open(file_path, 'w') as f:
                    json.dump(decision_data, f, indent=2)
                logger.debug(f"Decision saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save decision to file: {e}")
    
    async def _save_battery_selling_decision(self, selling_opportunity, current_price_pln: float, success: bool = True, error_msg: str = None):
        """Save battery selling decision data to file for dashboard consumption"""
        try:
            import json
            from pathlib import Path
            
            # Create energy_data directory if it doesn't exist
            project_root = Path(__file__).parent.parent
            energy_data_dir = project_root / "out" / "energy_data"
            energy_data_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"battery_selling_decision_{timestamp}.json"
            file_path = energy_data_dir / filename
            
            # Prepare selling decision data for dashboard
            selling_data = {
                'timestamp': datetime.now().isoformat(),
                'action': 'battery_selling',
                'decision': selling_opportunity.decision.value,
                'confidence': selling_opportunity.confidence,
                'expected_revenue_pln': selling_opportunity.expected_revenue_pln,
                'selling_power_w': selling_opportunity.selling_power_w,
                'estimated_duration_hours': selling_opportunity.estimated_duration_hours,
                'reasoning': selling_opportunity.reasoning,
                'safety_checks_passed': selling_opportunity.safety_checks_passed,
                'risk_level': selling_opportunity.risk_level,
                'current_price_pln': current_price_pln,
                'battery_soc': self.current_data.get('battery', {}).get('soc_percent', 0),
                'pv_power': self.current_data.get('photovoltaic', {}).get('current_power_w', 0),
                'house_consumption': self.current_data.get('house_consumption', {}).get('current_power_w', 0),
                'energy_sold_kwh': selling_opportunity.estimated_duration_hours * (selling_opportunity.selling_power_w / 1000),
                'revenue_per_kwh_pln': current_price_pln,
                'safety_status': self.current_data.get('battery_selling_safety', {}).get('overall_status', 'unknown'),
                'execution_success': success,
                'execution_error': error_msg
            }
            
            # Save to storage
            if self.storage:
                # Add type for storage schema
                selling_data['type'] = 'selling'
                await self.storage.save_decision(selling_data)
                logger.debug(f"Battery selling decision saved to storage")
            else:
                # Fallback to file
                with open(file_path, 'w') as f:
                    json.dump(selling_data, f, indent=2)
                logger.debug(f"Battery selling decision saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save battery selling decision to file: {e}")
    
    async def _handle_multi_session_logic(self):
        """Handle multi-session charging logic"""
        try:
            now = datetime.now()
            
            # Check if we need to create a daily plan
            if not self.multi_session_manager.current_plan:
                # Check if it's time to plan (default 06:00)
                planning_time = self.multi_session_manager.daily_planning_time
                if now.strftime('%H:%M') == planning_time:
                    logger.info("Creating daily charging plan...")
                    await self.multi_session_manager.create_daily_plan(now.date())
            
            # Check for active session completion
            if self.multi_session_manager.active_session:
                session = self.multi_session_manager.active_session
                if now >= session.end_time:
                    logger.info(f"Completing scheduled session {session.session_id}")
                    await self.multi_session_manager.complete_session(session)
                    # Stop charging if active
                    if self.charging_controller.is_charging:
                        await self.charging_controller.stop_price_based_charging()
            
            # Check for next session start
            next_session = await self.multi_session_manager.get_next_session()
            if next_session and now >= next_session.start_time:
                logger.info(f"Starting scheduled session {next_session.session_id}")
                await self.multi_session_manager.start_session(next_session)
                # Start charging if not already charging
                if not self.charging_controller.is_charging:
                    price_data = self.charging_controller.fetch_price_data_for_date(
                        now.strftime('%Y-%m-%d')
                    )
                    if price_data:
                        await self.charging_controller.start_price_based_charging(price_data)
            
        except Exception as e:
            logger.error(f"Failed to handle multi-session logic: {e}")
    
    async def _handle_battery_selling_logic(self, price_data: Dict[str, Any]):
        """Handle battery selling logic and decisions"""
        try:
            if not self.battery_selling_engine or not self.battery_selling_monitor:
                return
            
            # Get current price for selling analysis
            current_price_pln = 0
            if price_data and 'value' in price_data:
                try:
                    now = datetime.now()
                    current_time = now.replace(second=0, microsecond=0)
                    
                    # Use AutomatedPriceCharger for consistent price calculation
                    current_price_pln = self.charging_controller.get_current_price(price_data)
                    if current_price_pln:
                        current_price_pln = current_price_pln / 1000  # Convert PLN/MWh to PLN/kWh
                except Exception as e:
                    logger.warning(f"Failed to extract current price for selling: {e}")
                    return
            
            # Prepare price data for selling engine
            selling_price_data = {
                'current_price_pln': current_price_pln,
                'price_data': price_data
            }
            
            # Prepare normalized current_data with inverter key for safety monitor
            # Map 'system' to 'inverter' for backward compatibility
            normalized_current_data = self.current_data.copy()
            if 'system' in normalized_current_data and 'inverter' not in normalized_current_data:
                normalized_current_data['inverter'] = normalized_current_data['system'].copy()
                # Add error_codes if available from inverter status
                if hasattr(self.charging_controller.goodwe_charger.inverter, 'error_codes'):
                    try:
                        normalized_current_data['inverter']['error_codes'] = []
                    except Exception:
                        pass
            
            # Update active sessions (stop if completed)
            await self.battery_selling_engine.update_active_sessions(
                self.charging_controller.goodwe_charger.inverter, normalized_current_data
            )
            
            # Check safety conditions first
            safety_report = await self.battery_selling_monitor.check_safety_conditions(
                self.charging_controller.goodwe_charger.inverter, normalized_current_data
            )
            
            if safety_report.emergency_stop_required:
                logger.warning("Emergency stop required - stopping all battery selling operations")
                await self.battery_selling_monitor.emergency_stop(self.charging_controller.goodwe_charger.inverter)
                return
            
            # Prepare data in the format expected by battery selling engine
            # Map from enhanced_data_collector format (photovoltaic, house_consumption) to expected format (pv, consumption)
            battery_data = self.current_data.get('battery', {})
            pv_data = self.current_data.get('photovoltaic', {}) or self.current_data.get('pv', {})
            consumption_data = self.current_data.get('house_consumption', {}) or self.current_data.get('consumption', {})
            grid_data = self.current_data.get('grid', {})
            
            selling_data = {
                'battery': {
                    'soc_percent': battery_data.get('soc_percent', 0),
                    'charging_status': battery_data.get('charging_status', False),
                    'current': battery_data.get('current', 0),
                    'power': battery_data.get('power', 0) or battery_data.get('power_w', 0),
                    'temperature': battery_data.get('temperature', 25)
                },
                'pv': {
                    'power_w': pv_data.get('current_power_w', 0) or pv_data.get('power_w', 0) or pv_data.get('power', 0)
                },
                'consumption': {
                    'power_w': consumption_data.get('current_power_w', 0) or consumption_data.get('power_w', 0) or consumption_data.get('house_consumption', 0)
                },
                'grid': {
                    'power': grid_data.get('power', 0) or grid_data.get('power_w', 0),
                    'voltage': grid_data.get('voltage', 0)
                }
            }
            
            # Analyze selling opportunity
            selling_opportunity = await self.battery_selling_engine.analyze_selling_opportunity(
                selling_data, selling_price_data
            )
            
            # Log selling analysis
            logger.info(f"Battery selling analysis: {selling_opportunity.decision.value}")
            logger.info(f"  - Confidence: {selling_opportunity.confidence:.2f}")
            logger.info(f"  - Expected revenue: {selling_opportunity.expected_revenue_pln:.2f} PLN")
            logger.info(f"  - Reasoning: {selling_opportunity.reasoning}")
            
            # Execute selling decision
            if selling_opportunity.decision.value == "start_selling":
                if selling_opportunity.safety_checks_passed:
                    success = await self.battery_selling_engine.start_selling_session(
                        self.charging_controller.goodwe_charger.inverter, selling_opportunity
                    )
                    if success:
                        logger.info("Battery selling session started successfully")
                    else:
                        logger.error("Failed to start battery selling session")
                else:
                    logger.warning("Cannot start selling - safety checks failed")
            
            elif selling_opportunity.decision.value == "stop_selling":
                # Stop any active selling sessions
                for session in self.battery_selling_engine.active_sessions:
                    await self.battery_selling_engine.stop_selling_session(
                        self.charging_controller.goodwe_charger.inverter, session.session_id
                    )
                logger.info("Battery selling sessions stopped")
            
            # Update system data with selling status
            self.current_data['battery_selling'] = self.battery_selling_engine.get_selling_status()
            self.current_data['battery_selling_safety'] = self.battery_selling_monitor.get_safety_status()
            
            # Save battery selling decision if selling occurred
            if selling_opportunity.decision.value == "start_selling":
                # Determine success based on whether session was started
                # If we are here, we tried to start. Check if session was added.
                # Note: This logic assumes _handle_battery_selling_logic is called sequentially
                success = False
                error_msg = None
                
                # Check if a session was just added
                # This is a bit heuristic but works for now
                if self.battery_selling_engine.active_sessions:
                    latest_session = self.battery_selling_engine.active_sessions[-1]
                    if (datetime.now() - latest_session.start_time).total_seconds() < 60:
                        success = True
                
                if not success:
                    error_msg = "Inverter command failed or safety check blocked execution"
                
                await self._save_battery_selling_decision(selling_opportunity, current_price_pln, success, error_msg)
            
            # Ensure inverter returns to safe defaults when not actively selling
            if not self.battery_selling_engine.active_sessions:
                try:
                    await self.battery_selling_engine.ensure_safe_state(self.charging_controller.goodwe_charger.inverter)
                except Exception as ensure_exc:
                    logger.warning(f"Failed to reset inverter safe state after selling: {ensure_exc}")
 
        except Exception as e:
            logger.error(f"Failed to handle battery selling logic: {e}")
    
    async def _execute_smart_decision(self, decision: Dict[str, Any]):
        """Execute the smart charging decision"""
        should_charge = decision.get('should_charge', False)
        reason = decision.get('reason', 'Unknown')
        priority = decision.get('priority', 'low')
        
        # Get SOC for logging
        battery_data = self.current_data.get('battery', {})
        battery_soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
        
        # If we've recently decided to wait, enforce a short cooldown to prevent flapping
        now = datetime.now()
        if hasattr(self, '_wait_cooldown_until') and self._wait_cooldown_until:
            if now < self._wait_cooldown_until and should_charge and priority not in ['critical', 'emergency']:
                logger.info(
                    f"Cooldown active until {self._wait_cooldown_until.strftime('%H:%M')}; "
                    f"skipping start despite decision (priority: {priority})"
                )
                should_charge = False

        if should_charge:
            logger.info(f"Executing decision: Start charging at SOC {battery_soc}% - {reason}")
            # Check if this is a critical battery situation (force start)
            force_start = battery_soc <= 20 or priority == 'critical'
            
            # Always force start if decision was made to charge (decision engine already validated)
            if not force_start:
                force_start = True
                logger.info(f"Decision to charge validated by engine (SOC: {battery_soc}%, Priority: {priority})")
            
            await self.charging_controller.start_price_based_charging(
                decision.get('price_data', {}), 
                force_start=force_start
            )
        else:
            logger.info(f"Executing decision: No action needed at SOC {battery_soc}% - {reason}")
            # Ensure charging is stopped when waiting for a better window
            waiting_for_window = bool(decision.get('next_window')) or decision.get('waiting', False)
            is_currently_charging = False
            try:
                is_currently_charging = getattr(self.charging_controller, 'is_charging', False)
            except Exception:
                is_currently_charging = False
            
            if self.charging_controller:
                # Check if this is a protected charging session (shouldn't be interrupted)
                is_protected = False
                try:
                    is_protected = self.charging_controller.is_charging_session_protected()
                except Exception:
                    is_protected = False
                
                if is_protected:
                    logger.info(f"🛡️ Charging session protected - not stopping despite wait decision (SOC {battery_soc}%)")
                    return
                
                # Always stop if we are currently charging and decision says do not charge
                if is_currently_charging:
                    try:
                        logger.info(f"⛔ Stopping charging: decision says wait, currently charging (SOC {battery_soc}%)")
                        await self.charging_controller.stop_price_based_charging()
                    except Exception as e:
                        logger.warning(f"Stop charging command failed: {e}")
                # If not currently charging, only enforce stop when explicitly waiting for a better window
                elif waiting_for_window:
                    try:
                        logger.debug(f"Ensuring stopped state: waiting for window at {decision.get('next_window', 'unknown')}")
                        await self.charging_controller.stop_price_based_charging()
                    except Exception as e:
                        logger.warning(f"Stop charging command failed: {e}")
            # Set a short cooldown to avoid immediately starting after a wait decision
            # Exceptions: critical/emergency decisions can override cooldown
            if waiting_for_window and priority not in ['critical', 'emergency']:
                # Default 15-minute cooldown
                self._wait_cooldown_until = now + timedelta(minutes=15)
                logger.info(
                    f"Wait decision applied; starting cooldown until {self._wait_cooldown_until.strftime('%H:%M')}"
                )
    
    async def _execute_decision(self, decision: Dict[str, Any]):
        """Execute the charging decision"""
        action = decision.get('action', 'none')
        
        # Get SOC for logging
        battery_data = self.current_data.get('battery', {})
        battery_soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
        
        if action == 'start_charging':
            logger.info(f"Executing decision: Start charging at SOC {battery_soc}%")
            force_start = battery_soc <= 5  # Emergency battery level only
            
            # If decision was made by smart charging system, trust it and force start
            # This prevents re-checking price when decision was already made with proper analysis
            if decision.get('priority') in ['medium', 'high', 'critical', 'emergency']:
                force_start = True
                logger.info(f"Trusting smart charging decision (SOC: {battery_soc}%, Priority: {decision.get('priority')})")
            
            # Always force start if decision was made to charge (decision engine already validated)
            if not force_start:
                force_start = True
                logger.info(f"Decision validated by engine (SOC: {battery_soc}%)")
            
            result = await self.charging_controller.start_price_based_charging(
                decision.get('price_data', {}), 
                force_start=force_start
            )
            
            if not result:
                logger.warning(f"Charging execution blocked at SOC {battery_soc}% - See charging controller logs for details")
            
        elif action == 'stop_charging':
            logger.info(f"Executing decision: Stop charging at SOC {battery_soc}%")
            await self.charging_controller.stop_price_based_charging()
            
        elif action == 'continue_charging':
            logger.info(f"Executing decision: Continue charging at SOC {battery_soc}%")
            # No action needed, charging continues
            
        elif action == 'none':
            logger.info(f"Executing decision: No action needed at SOC {battery_soc}%")
            
        else:
            logger.warning(f"Unknown decision action: {action} at SOC {battery_soc}%")
    
    async def _update_system_state(self):
        """Update system state based on current conditions"""
        if not self.current_data:
            return
        
        # Check if currently charging
        charging_status = self.current_data.get('charging', {}).get('is_charging', False)
        
        if charging_status:
            self.state = SystemState.CHARGING
        else:
            self.state = SystemState.MONITORING
    
    def _update_performance_metrics(self):
        """Update system performance metrics"""
        if not self.current_data:
            return
        
        # Calculate efficiency metrics
        # Use compatibility layer: check both 'photovoltaic' and 'pv' keys
        pv_data = self.current_data.get('photovoltaic', {}) or self.current_data.get('pv', {})
        pv_production = pv_data.get('total_power', 0) or pv_data.get('current_power_w', 0) or pv_data.get('power_w', 0)
        battery_charging = self.current_data.get('battery', {}).get('charging_power', 0)
        grid_import = self.current_data.get('grid', {}).get('import_power', 0)
        
        # Update metrics
        self.performance_metrics.update({
            'pv_efficiency': pv_production,
            'battery_utilization': battery_charging,
            'grid_dependency': grid_import,
            'last_update': datetime.now()
        })
    
    def _log_system_status(self):
        """Log current system status with deduplication"""
        if not self.current_data:
            return
        
        battery_soc = self.current_data.get('battery', {}).get('soc_percent', 0)
        pv_power = self.current_data.get('photovoltaic', {}).get('current_power_w', 0)
        charging_status = self.current_data.get('battery', {}).get('charging_status', False)
        
        status_msg = (f"Status - State: {self.state.value}, "
                     f"Battery: {battery_soc}%, "
                     f"PV: {pv_power}W, "
                     f"Charging: {charging_status}")
        
        # Only log if status has changed or every 5 minutes
        current_time = time.time()
        if not hasattr(self, '_last_status_log_time'):
            self._last_status_log_time = 0
            self._last_status_msg = ""
        
        if (status_msg != self._last_status_msg or 
            current_time - self._last_status_log_time > 300):  # 5 minutes
            logger.info(status_msg)
            self._last_status_log_time = current_time
            self._last_status_msg = status_msg
    
    async def shutdown(self):
        """Gracefully shutdown the coordinator"""
        logger.info("Shutting down Master Coordinator...")
        
        try:
            # Stop charging if active
            if self.state == SystemState.CHARGING:
                await self.charging_controller.stop_price_based_charging()
                logger.info("Charging stopped during shutdown")
            
            # Save final data
            await self._save_system_state()
            
            # Disconnect storage
            if self.storage:
                await self.storage.disconnect()
            
            logger.info("Master Coordinator shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _save_system_state(self):
        """Save current system state to file"""
        try:
            state_data = {
                'timestamp': datetime.now().isoformat(),
                'state': self.state.value,
                'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
                'current_data': self.current_data,
                'performance_metrics': self.performance_metrics,
                'decision_count': len(self.decision_history)
            }
            
            if self.storage:
                await self.storage.save_system_state(state_data)
                logger.info("System state saved to storage")
            else:
                state_file = project_root / "out" / f"coordinator_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                state_file.parent.mkdir(exist_ok=True)
                
                with open(state_file, 'w') as f:
                    json.dump(state_data, f, indent=2, default=str)
                
                logger.info(f"System state saved to {state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save system state: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status (GoodWe Lynx-D compliant)"""
        compliance = self._check_goodwe_lynx_d_compliance()
        
        status = {
            'state': self.state.value,
            'is_running': self.is_running,
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'last_decision': self.last_decision_time.isoformat() if self.last_decision_time else None,
            'current_data': self.current_data,
            'performance_metrics': self.performance_metrics,
            'decision_count': len(self.decision_history),
            'goodwe_lynx_d_compliance': compliance,
            'safety_status': {
                'emergency_conditions_ok': not self._check_emergency_conditions(),
                'battery_voltage_range': f"{self.config.get('battery_management', {}).get('voltage_range', {}).get('min', 320)}V - {self.config.get('battery_management', {}).get('voltage_range', {}).get('max', 480)}V",
                'battery_temp_range': f"{self.config.get('battery_management', {}).get('temperature_thresholds', {}).get('charging_min', 0)}°C - {self.config.get('battery_management', {}).get('temperature_thresholds', {}).get('charging_max', 53)}°C",
                'battery_type': self.config.get('battery_management', {}).get('battery_type', 'LFP'),
                'vde_2510_50_compliant': self.config.get('battery_management', {}).get('vde_2510_50_compliance', True)
            }
        }
        
        # Add multi-session status if available
        if self.multi_session_manager:
            status['multi_session_status'] = self.multi_session_manager.get_current_plan_status()
        
        return status
    


class MultiFactorDecisionEngine:
    """Multi-factor decision engine for intelligent charging decisions with timing awareness"""
    
    def __init__(self, config: Dict[str, Any], charging_controller=None):
        """Initialize the decision engine"""
        self.config = config
        self.charging_controller = charging_controller
        self.coordinator_config = config.get('coordinator', {})
        
        # Validate G14dynamic tariff configuration
        tariff_config = config.get('electricity_tariff', {})
        tariff_type = tariff_config.get('tariff_type', 'g12w')
        if tariff_type == 'g14dynamic':
            pse_enabled = config.get('pse_peak_hours', {}).get('enabled', False)
            if not pse_enabled:
                logger.error("G14dynamic tariff requires PSE Peak Hours (Kompas) to be enabled!")
                logger.error("Please set pse_peak_hours.enabled = true in configuration")
                raise ValueError("G14dynamic tariff requires pse_peak_hours.enabled = true")
            logger.info("G14dynamic tariff detected - PSE Peak Hours integration enabled")
        
        # Decision weights (from project plan)
        self.weights = {
            'price': 0.40,      # 40% weight
            'battery': 0.25,    # 25% weight
            'pv': 0.20,         # 20% weight
            'consumption': 0.15  # 15% weight
        }
        
        # Initialize timing-aware components
        self.pv_forecaster = PVForecaster(config)
        self.price_analyzer = PriceWindowAnalyzer(config)
        self.hybrid_logic = HybridChargingLogic(config)
        self.peak_hours_collector = None  # Will be set by MasterCoordinator
        
        # Timing awareness flag
        self.timing_awareness_enabled = config.get('timing_awareness_enabled', True)
        
        # Weather integration
        self.weather_enabled = config.get('weather_integration', {}).get('enabled', True)
        self.weather_weights = {
            'solar_irradiance': 0.6,
            'cloud_cover': 0.4
        }
        
        # PV vs consumption analysis
        from pv_consumption_analyzer import PVConsumptionAnalyzer
        self.pv_consumption_analyzer = PVConsumptionAnalyzer(config)
        
        # PV trend analysis for weather-aware decisions
        self.pv_trend_analyzer = PVTrendAnalyzer(config)
        
        # PSE Price Forecast integration
        self.forecast_collector = None  # Will be set by MasterCoordinator
    
    async def analyze_and_decide(self, current_data: Dict, price_data: Dict, historical_data: List) -> Dict[str, Any]:
        """Analyze current situation and make charging decision with timing awareness"""
        
        # Use timing-aware decision if enabled
        if self.timing_awareness_enabled:
            return await self._analyze_and_decide_with_timing(current_data, price_data, historical_data)
        
        # Fallback to original scoring algorithm
        return self._analyze_and_decide_legacy(current_data, price_data, historical_data)
    
    async def _analyze_and_decide_with_timing(self, current_data: Dict, price_data: Dict, historical_data: List) -> Dict[str, Any]:
        """Analyze and decide using timing-aware hybrid charging logic with weather integration and PV vs consumption analysis"""
        logger.info("Using timing-aware decision engine with weather integration and PV vs consumption analysis")
        
        try:
            # Get PSE price forecasts if available
            forecast_data = []
            forecast_enhanced_analysis = None
            if self.forecast_collector and self.forecast_collector.is_forecast_available():
                logger.info("Using PSE price forecasts for enhanced decision making")
                forecast_data = self.forecast_collector.fetch_price_forecast()
                
                # Enhanced price analysis with forecasts
                if forecast_data:
                    forecast_enhanced_analysis = self.price_analyzer.analyze_with_forecast(
                        current_data, price_data, forecast_data
                    )
                    logger.info(f"Forecast-enhanced analysis completed with {len(forecast_data)} forecast points")
            else:
                logger.debug("No forecast data available, using standard analysis")
            
            # Get weather-enhanced PV forecast
            pv_forecast = await self._get_weather_enhanced_pv_forecast(current_data)
            
            # Analyze PV trend for weather-aware decisions
            weather_data = current_data.get('weather')
            pv_trend_analysis = self.pv_trend_analyzer.analyze_pv_trend(current_data, pv_forecast, weather_data)
            
            # Analyze PV vs consumption balance
            power_balance = None
            charging_recommendation = None
            night_charging_recommendation = None
            battery_discharge_recommendation = None
            timing_recommendation = None
            
            if self.pv_consumption_analyzer:
                power_balance = self.pv_consumption_analyzer.analyze_power_balance(current_data)
                battery_soc = current_data.get('battery', {}).get('soc_percent', 0)
                current_consumption_kw = current_data.get('house_consumption', {}).get('current_power_kw', 0)
                
                # Standard charging timing analysis
                charging_recommendation = self.pv_consumption_analyzer.analyze_charging_timing(
                    power_balance, battery_soc, pv_forecast, price_data, weather_data
                )
                
                # Weather-aware timing recommendation
                timing_recommendation = self.pv_trend_analyzer.analyze_timing_recommendation(
                    pv_trend_analysis, price_data, battery_soc, current_consumption_kw
                )
                
                # Night charging strategy for high price day preparation
                night_charging_recommendation = self.pv_consumption_analyzer.analyze_night_charging_strategy(
                    battery_soc, pv_forecast, price_data, weather_data
                )
                
                # Battery discharge strategy during high price periods
                battery_discharge_recommendation = self.pv_consumption_analyzer.analyze_battery_discharge_strategy(
                    battery_soc, current_data, pv_forecast, price_data
                )
            
            # Use hybrid charging logic for optimal decision
            charging_decision = await self.hybrid_logic.analyze_and_decide(current_data, price_data)
            
            # Apply weather-aware timing recommendation
            action = self._apply_weather_aware_timing(
                charging_decision.action, timing_recommendation, pv_trend_analysis, current_data
            )

            # Soft policy from Kompas (Peak Hours): optionally adjust action
            action = self._apply_peak_hours_policy(action)
            
            # Calculate scores for compatibility with weather enhancement
            price_score = self._calculate_price_score(price_data)
            battery_score = self._calculate_battery_score(current_data)
            pv_score = self._calculate_weather_enhanced_pv_score(current_data)
            consumption_score = self._calculate_consumption_score(current_data, historical_data)
            
            total_score = (
                price_score * self.weights['price'] +
                battery_score * self.weights['battery'] +
                pv_score * self.weights['pv'] +
                consumption_score * self.weights['consumption']
            )
            
            return {
                'action': action,
                'total_score': total_score,
                'scores': {
                    'price': price_score,
                    'battery': battery_score,
                    'pv': pv_score,
                    'consumption': consumption_score
                },
                'confidence': charging_decision.confidence,
                'reasoning': charging_decision.reason,
                'power_balance': power_balance,
                'charging_recommendation': charging_recommendation,
                'night_charging_recommendation': night_charging_recommendation,
                'battery_discharge_recommendation': battery_discharge_recommendation,
                'price_data': price_data,
                'weather_data': current_data.get('weather', {}),
                'pv_forecast': pv_forecast,
                'timing_analysis': {
                    'charging_source': charging_decision.charging_source,
                    'duration_hours': charging_decision.duration_hours,
                    'energy_kwh': charging_decision.energy_kwh,
                    'estimated_cost_pln': charging_decision.estimated_cost_pln,
                    'estimated_savings_pln': charging_decision.estimated_savings_pln,
                    'pv_contribution_kwh': charging_decision.pv_contribution_kwh,
                    'grid_contribution_kwh': charging_decision.grid_contribution_kwh,
                    'start_time': charging_decision.start_time.isoformat(),
                    'end_time': charging_decision.end_time.isoformat()
                },
                'kompas': self._get_peak_status_summary(),
                'weather_aware_analysis': {
                    'pv_trend': {
                        'trend_direction': pv_trend_analysis.trend_direction,
                        'trend_strength': pv_trend_analysis.trend_strength,
                        'current_pv_kw': pv_trend_analysis.current_pv_kw,
                        'forecasted_pv_kw': pv_trend_analysis.forecasted_pv_kw,
                        'peak_pv_kw': pv_trend_analysis.peak_pv_kw,
                        'confidence': pv_trend_analysis.confidence,
                        'time_to_peak_hours': pv_trend_analysis.time_to_peak_hours,
                        'weather_factor': pv_trend_analysis.weather_factor,
                        'recommendation': pv_trend_analysis.recommendation
                    },
                    'timing_recommendation': {
                        'should_wait': timing_recommendation.should_wait if timing_recommendation else False,
                        'wait_reason': timing_recommendation.wait_reason if timing_recommendation else 'No timing analysis',
                        'estimated_wait_time_hours': timing_recommendation.estimated_wait_time_hours if timing_recommendation else 0.0,
                        'expected_pv_improvement_kw': timing_recommendation.expected_pv_improvement_kw if timing_recommendation else 0.0,
                        'confidence': timing_recommendation.confidence if timing_recommendation else 0.0,
                        'alternative_action': timing_recommendation.alternative_action if timing_recommendation else 'charge_now'
                    }
                },
                'forecast_analysis': {
                    'forecast_available': bool(forecast_data),
                    'forecast_enhanced': forecast_enhanced_analysis is not None,
                    'forecast_data': forecast_enhanced_analysis if forecast_enhanced_analysis else None,
                    'forecast_confidence': self.forecast_collector.get_forecast_confidence() if self.forecast_collector else 0.0,
                    'forecast_statistics': self.forecast_collector.get_forecast_statistics() if self.forecast_collector else None
                }
            }
            
        except Exception as e:
            logger.error(f"Error in weather-enhanced timing-aware decision: {e}")
            # Fallback to legacy decision
            return self._analyze_and_decide_legacy(current_data, price_data, historical_data)
    
    def _analyze_and_decide_legacy(self, current_data: Dict, price_data: Dict, historical_data: List) -> Dict[str, Any]:
        """Original scoring-based decision algorithm"""
        logger.info("Using legacy scoring-based decision engine")
        
        # Calculate individual scores
        price_score = self._calculate_price_score(price_data)
        battery_score = self._calculate_battery_score(current_data)
        pv_score = self._calculate_pv_score(current_data)
        consumption_score = self._calculate_consumption_score(current_data, historical_data)
        
        # Calculate weighted total score
        total_score = (
            price_score * self.weights['price'] +
            battery_score * self.weights['battery'] +
            pv_score * self.weights['pv'] +
            consumption_score * self.weights['consumption']
        )
        
        # Determine action based on score
        action = self._determine_action(total_score, current_data)
        
        # Calculate confidence
        confidence = self._calculate_confidence(price_score, battery_score, pv_score, consumption_score)
        
        return {
            'action': action,
            'total_score': total_score,
            'scores': {
                'price': price_score,
                'battery': battery_score,
                'pv': pv_score,
                'consumption': consumption_score
            },
            'confidence': confidence,
            'reasoning': self._generate_reasoning(price_score, battery_score, pv_score, consumption_score, action),
            'price_data': price_data
        }
    
    def _apply_weather_aware_timing(self, original_action: str, timing_recommendation, 
                                  pv_trend_analysis, current_data: Dict) -> str:
        """Apply weather-aware timing recommendations to charging decisions"""
        try:
            if not timing_recommendation:
                return self._convert_charging_action(original_action)
            
            battery_soc = current_data.get('battery', {}).get('soc_percent', 50)
            
            # Emergency battery level - always charge regardless of timing recommendation
            if battery_soc <= 5:
                logger.info("Emergency battery level - overriding timing recommendation")
                return 'start_charging'
            
            # Critical battery level - override weather recommendations and charge immediately
            if battery_soc <= 20:  # Critical threshold should match config
                logger.info("Critical battery level - overriding weather recommendation to charge immediately")
                return 'start_charging'
            
            # Apply timing recommendation
            if timing_recommendation.should_wait:
                logger.info(f"Weather-aware decision: Waiting for PV improvement - {timing_recommendation.wait_reason}")
                return 'none'  # Wait for better PV conditions
            else:
                logger.info(f"Weather-aware decision: Charging now - {timing_recommendation.wait_reason}")
                # If timing recommendation says don't wait, force charging regardless of hybrid logic
                return 'start_charging'
                
        except Exception as e:
            logger.error(f"Error applying weather-aware timing: {e}")
            return self._convert_charging_action(original_action)
    
    def _convert_charging_action(self, hybrid_action: str) -> str:
        """Convert hybrid charging action to legacy action format"""
        action_mapping = {
            'start_pv_charging': 'start_charging',
            'start_grid_charging': 'start_charging',
            'start_hybrid_charging': 'start_charging',
            'wait': 'none'
        }
        return action_mapping.get(hybrid_action, 'none')

    def _apply_peak_hours_policy(self, action: str) -> str:
        """Adjust action based on Kompas (Peak Hours) policy if configured.

        - WYMAGANE OGRANICZANIE (code 3): block grid charging -> return 'none'
        - ZALECANE OSZCZĘDZANIE (code 2): prefer wait -> return 'none' if action is start
        - NORMALNE/ZALECANE UŻYTKOWANIE (codes 1/0): informational only (no hard change)
        """
        try:
            if not getattr(self, 'peak_hours_collector', None):
                return action
            
            # Get SOC for logging (if available)
            battery_soc = None
            if hasattr(self, 'current_data') and self.current_data:
                battery_data = self.current_data.get('battery', {})
                battery_soc = battery_data.get('soc_percent', battery_data.get('soc', None))
            
            # Determine current hour status
            status = self.peak_hours_collector.get_status_for_time(datetime.now())
            if not status:
                return action

            if status.code == 3:  # WYMAGANE OGRANICZANIE
                if action.startswith('start'):
                    soc_info = f" (SOC: {battery_soc}%)" if battery_soc is not None else ""
                    logger.warning(f"🚫 Kompas WYMAGANE OGRANICZANIE: Blocking grid charging{soc_info}, Peak hours code 3")
                    logger.warning(f"   Reason: Required reduction period - grid charging not allowed regardless of price or battery level")
                    return 'none'
            elif status.code == 2:  # ZALECANE OSZCZĘDZANIE
                if action.startswith('start'):
                    soc_info = f" (SOC: {battery_soc}%)" if battery_soc is not None else ""
                    logger.info(f"⚠️  Kompas ZALECANE OSZCZĘDZANIE: Deferring charging start{soc_info}, Peak hours code 2")
                    logger.info(f"   Reason: Recommended to save energy and reduce grid load during this period")
                    return 'none'
            # codes 1 (NORMALNE) and 0 (ZALECANE) -> no strict change
            return action
        except Exception as e:
            logger.debug(f"Peak Hours policy application failed: {e}")
            return action

    def _get_peak_status_summary(self) -> Dict[str, Any]:
        """Return current hour Kompas status for telemetry in decision output."""
        try:
            if not getattr(self, 'peak_hours_collector', None):
                return {'available': False}
            status = self.peak_hours_collector.get_status_for_time(datetime.now())
            if not status:
                return {'available': False}
            return {
                'available': True,
                'time': status.time.isoformat(),
                'code': status.code,
                'label': status.label,
            }
        except Exception:
            return {'available': False}
    
    async def _get_weather_enhanced_pv_forecast(self, current_data: Dict) -> List[Dict]:
        """Get PV forecast enhanced with weather data"""
        if not self.weather_enabled or 'weather' not in current_data:
            return await self.pv_forecaster.forecast_pv_production()
        
        # Use weather-based PV forecasting
        return self.pv_forecaster.forecast_pv_production_with_weather()
    
    def _calculate_weather_enhanced_pv_score(self, current_data: Dict) -> float:
        """Enhanced PV scoring with weather data"""
        pv_data = current_data.get('photovoltaic', {})
        pv_power = pv_data.get('current_power_w', 0)
        
        # Base PV scoring
        base_score = self._calculate_pv_score(current_data)
        
        # Weather enhancement
        if self.weather_enabled and 'weather' in current_data:
            weather_score = self._calculate_weather_pv_score(current_data['weather'])
            # Blend base and weather scores
            return (base_score * 0.7) + (weather_score * 0.3)
        
        return base_score
    
    def _calculate_weather_pv_score(self, weather_data: Dict) -> float:
        """Calculate PV score based on weather conditions"""
        if not weather_data or 'forecast' not in weather_data:
            return 50  # Neutral score
        
        forecast = weather_data['forecast']
        solar_data = forecast.get('solar_irradiance', {})
        
        # Get current hour's solar irradiance
        current_hour = datetime.now().hour
        if current_hour < len(solar_data.get('ghi', [])):
            current_ghi = solar_data['ghi'][current_hour]
            cloud_cover = forecast['cloud_cover']['total'][current_hour] if current_hour < len(forecast['cloud_cover']['total']) else 0
            
            # Score based on solar irradiance and cloud cover
            if current_ghi > 800 and cloud_cover < 25:
                return 100  # Excellent conditions
            elif current_ghi > 400 and cloud_cover < 50:
                return 75   # Good conditions
            elif current_ghi > 200 and cloud_cover < 75:
                return 50   # Moderate conditions
            else:
                return 25   # Poor conditions
        
        return 50  # Default neutral score
    
    def _calculate_price_score(self, price_data: Dict) -> float:
        """Calculate price-based score (0-100)"""
        if not price_data or 'value' not in price_data:
            return 50  # Neutral score if no price data
        
        # Get current time and find matching price
        now = datetime.now()
        current_time = now.replace(second=0, microsecond=0)
        
        # Find the current 15-minute period price
        current_price = None
        # Use AutomatedPriceCharger for consistent price calculation
        current_price = self.charging_controller.get_current_price(price_data)
        if current_price:
            current_price = current_price / 1000  # Convert PLN/MWh to PLN/kWh
        
        if current_price is None:
            return 50  # Neutral score if no current price found
        
        # Price scoring: 0-200 PLN = 100, 600+ PLN = 0
        if current_price <= 200:
            return 100
        elif current_price <= 400:
            return 80
        elif current_price <= 600:
            return 40
        else:
            return 0
    
    def _calculate_battery_score(self, current_data: Dict) -> float:
        """Calculate battery-based score (0-100)"""
        battery_data = current_data.get('battery', {})
        soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
        
        # Battery scoring: 0-20% = 100, 90-100% = 0
        if soc <= 20:
            return 100  # Critical - charge immediately
        elif soc <= 40:
            return 80   # Low - charge during low/medium prices
        elif soc <= 70:
            return 40   # Medium - charge during low prices only
        elif soc <= 90:
            return 10   # High - charge during very low prices only
        else:
            return 0    # Full - no charging needed
    
    def _calculate_pv_score(self, current_data: Dict) -> float:
        """Calculate PV production score (0-100) with consumption analysis"""
        pv_data = current_data.get('photovoltaic', {})
        consumption_data = current_data.get('house_consumption', {})
        
        pv_power = pv_data.get('current_power_w', 0)
        consumption_power = consumption_data.get('current_power_w', 0)
        
        # Calculate net power (PV - Consumption)
        net_power = pv_power - consumption_power
        
        # Get overproduction threshold from config
        overproduction_threshold = self.config.get('pv_consumption_analysis', {}).get('pv_overproduction_threshold_w', 500)
        
        # PV vs Consumption scoring logic:
        # - If PV overproduction (net > threshold): Score = 0 (no grid charging needed)
        # - If PV deficit (net < 0): Score = 100 (urgent charging needed)
        # - If PV balanced (0 < net < threshold): Score based on deficit amount
        
        if net_power > overproduction_threshold:
            # PV overproduction - no grid charging needed
            return 0
        elif net_power < 0:
            # PV deficit - urgent charging needed
            deficit = abs(net_power)
            if deficit >= 2000:  # High deficit
                return 100
            elif deficit >= 1000:  # Medium deficit
                return 80
            else:  # Low deficit
                return 60
        else:
            # PV balanced or slight overproduction
            if net_power >= overproduction_threshold * 0.5:  # Close to overproduction
                return 10
            elif net_power >= 0:  # Balanced
                return 30
            else:  # Slight deficit
                return 50
    
    def _calculate_consumption_score(self, current_data: Dict, historical_data: List) -> float:
        """Calculate consumption-based score (0-100)"""
        consumption_data = current_data.get('house_consumption', {})
        current_consumption = consumption_data.get('current_power_w', 0)
        
        # Simple consumption scoring based on current load
        if current_consumption >= 3000:  # High consumption
            return 100  # Charge to support high consumption
        elif current_consumption >= 1000:  # Medium consumption
            return 60
        elif current_consumption >= 100:   # Low consumption
            return 30
        else:  # Very low consumption
            return 0
    
    def _determine_action(self, total_score: float, current_data: Dict) -> str:
        """Determine charging action based on total score with PV overproduction analysis"""
        battery_data = current_data.get('battery', {})
        battery_soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
        is_charging = battery_data.get('charging_status', False)
        
        # Critical battery level - charge immediately (highest priority)
        critical_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('critical', 12)
        if battery_soc <= critical_threshold:
            return 'start_charging'
        
        # Check for PV overproduction
        pv_data = current_data.get('photovoltaic', {})
        consumption_data = current_data.get('house_consumption', {})
        pv_power = pv_data.get('current_power_w', 0)
        consumption_power = consumption_data.get('current_power_w', 0)
        net_power = pv_power - consumption_power
        
        # Get overproduction threshold from config
        overproduction_threshold = self.config.get('pv_consumption_analysis', {}).get('pv_overproduction_threshold_w', 500)
        
        # PV Overproduction Check: Avoid grid charging when PV > consumption + threshold
        if net_power > overproduction_threshold:
            # PV overproduction detected - avoid grid charging
            if is_charging:
                return 'stop_charging'  # Stop grid charging during PV overproduction
            else:
                return 'none'  # No grid charging needed during PV overproduction
        
        # PV Deficit Check: Start charging if significant PV deficit and low battery
        if net_power < -1000 and battery_soc <= 40:  # Significant deficit and low battery
            if not is_charging:
                return 'start_charging'  # Start charging due to PV deficit
        
        # High score - start or continue charging
        if total_score >= 70:
            if not is_charging:
                return 'start_charging'
            else:
                return 'continue_charging'
        
        # Low score and currently charging - stop charging
        if total_score <= 30 and is_charging:
            return 'stop_charging'
        
        # Medium score and currently charging - continue
        if 30 < total_score < 70 and is_charging:
            return 'continue_charging'
        
        # Default - no action
        return 'none'
    
    def _calculate_confidence(self, price_score: float, battery_score: float, pv_score: float, consumption_score: float) -> float:
        """Calculate decision confidence (0-100)"""
        # Confidence based on how clear the signals are
        scores = [price_score, battery_score, pv_score, consumption_score]
        score_variance = statistics.variance(scores) if len(scores) > 1 else 0
        
        # Lower variance = higher confidence
        confidence = max(0, 100 - (score_variance / 10))
        return min(100, confidence)
    
    def _generate_reasoning(self, price_score: float, battery_score: float, pv_score: float, consumption_score: float, action: str) -> str:
        """Generate human-readable reasoning for the decision with PV overproduction analysis"""
        reasons = []
        
        if price_score >= 80:
            reasons.append("Low electricity prices")
        elif price_score <= 20:
            reasons.append("High electricity prices")
        
        if battery_score >= 80:
            reasons.append("Low battery level")
        elif battery_score <= 20:
            reasons.append("Battery nearly full")
        
        # Enhanced PV reasoning with overproduction analysis
        if pv_score == 0:
            reasons.append("PV overproduction - no grid charging needed")
        elif pv_score <= 20:
            reasons.append("High PV production")
        elif pv_score >= 80:
            reasons.append("PV deficit - urgent charging needed")
        elif pv_score >= 60:
            reasons.append("PV insufficient for consumption")
        else:
            reasons.append("PV production available")
        
        if consumption_score >= 80:
            reasons.append("High consumption expected")
        elif consumption_score <= 20:
            reasons.append("Low consumption expected")
        
        # Add action-specific reasoning
        if action == 'stop_charging' and pv_score == 0:
            reasons.append("Stopping grid charging due to PV overproduction")
        elif action == 'start_charging' and pv_score >= 80:
            reasons.append("Starting charging due to PV deficit")
        
        if not reasons:
            reasons.append("Balanced conditions")
        
        return f"Decision based on: {', '.join(reasons)}"


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Master Coordinator for GoodWe Enhanced Energy Management System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the master coordinator service
  python master_coordinator.py
  
  # Start with custom config
  python master_coordinator.py --config my_config.yaml
  
  # Show current status
  python master_coordinator.py --status
  
  # Run in test mode (single decision cycle)
  python master_coordinator.py --test
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/master_coordinator_config.yaml',
        help='Configuration file path (default: config/master_coordinator_config.yaml)'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Show current system status and exit'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Run in test mode (single decision cycle)'
    )
    
    parser.add_argument(
        '--non-interactive', '-n',
        action='store_true',
        help='Run in non-interactive mode (useful for systemd)'
    )
    
    return parser.parse_args()


async def main():
    """Main function"""
    args = parse_arguments()
    
    # Check if config file exists
    if not Path(args.config).exists():
        print(f"Configuration file {args.config} not found!")
        print("Please ensure the GoodWe inverter configuration is set up first.")
        return
    
    # Initialize coordinator
    coordinator = MasterCoordinator(args.config)
    
    if args.status:
        # Show status and exit
        if await coordinator.initialize():
            status = coordinator.get_status()
            print("\n" + "="*60)
            print("GOODWE MASTER COORDINATOR STATUS")
            print("="*60)
            print(f"State: {status['state']}")
            print(f"Running: {status['is_running']}")
            print(f"Uptime: {status['uptime_seconds']:.0f} seconds")
            print(f"Last Decision: {status['last_decision']}")
            print(f"Decision Count: {status['decision_count']}")
            print("\nCurrent Data:")
            if status['current_data']:
                for key, value in status['current_data'].items():
                    print(f"  {key}: {value}")
            else:
                print("  No data available")
        else:
            print("Failed to initialize coordinator")
        return
    
    if args.test:
        # Test mode - single decision cycle
        print("Running in test mode...")
        if await coordinator.initialize():
            await coordinator._collect_system_data()
            await coordinator._make_charging_decision()
            status = coordinator.get_status()
            print(f"Test completed. Status: {status['state']}")
        else:
            print("Failed to initialize coordinator")
        return
    
    # Normal operation - start the coordinator
    print("Starting GoodWe Master Coordinator...")
    print("Press Ctrl+C to stop")
    
    try:
        await coordinator.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Fatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
