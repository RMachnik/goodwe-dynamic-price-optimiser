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

# Import all the component modules
import sys
from pathlib import Path

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from fast_charge import GoodWeFastCharger
from enhanced_data_collector import EnhancedDataCollector
from automated_price_charging import AutomatedPriceCharger
from polish_electricity_analyzer import PolishElectricityAnalyzer
from log_web_server import LogWebServer
from pv_forecasting import PVForecaster
from price_window_analyzer import PriceWindowAnalyzer
from hybrid_charging_logic import HybridChargingLogic
from weather_data_collector import WeatherDataCollector
from pv_consumption_analyzer import PVConsumptionAnalyzer
from pv_trend_analyzer import PVTrendAnalyzer
from multi_session_manager import MultiSessionManager

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
        
        # Component managers
        self.data_collector = None
        self.price_analyzer = None
        self.charging_controller = None
        self.decision_engine = None
        self.log_web_server = None
        self.web_server_thread = None
        self.weather_collector = None
        self.pv_consumption_analyzer = None
        self.multi_session_manager = None
        
        # System data
        self.current_data = {}
        self.historical_data = []
        self.decision_history = []
        self.performance_metrics = {}
        
        # Configuration
        self.config = self._load_config()
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
            # Initialize data collector
            logger.info("Initializing Enhanced Data Collector...")
            self.data_collector = EnhancedDataCollector(self.config_path)
            if not await self.data_collector.initialize():
                logger.error("Failed to initialize data collector")
                return False
            
            # Initialize price analyzer
            logger.info("Initializing Price Analyzer...")
            self.price_analyzer = PolishElectricityAnalyzer()
            
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
            
            # Initialize decision engine
            logger.info("Initializing Decision Engine...")
            self.decision_engine = MultiFactorDecisionEngine(self.config)
            
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
            
            # Initialize multi-session manager
            logger.info("Initializing Multi-Session Manager...")
            self.multi_session_manager = MultiSessionManager(self.config)
            logger.info("Multi-Session Manager initialized successfully")
            
            # Initialize log web server
            logger.info("Initializing Log Web Server...")
            web_server_config = self.config.get('web_server', {})
            web_host = web_server_config.get('host', '0.0.0.0')
            web_port = web_server_config.get('port', 8080)
            web_enabled = web_server_config.get('enabled', True)
            
            if web_enabled:
                self.log_web_server = LogWebServer(host=web_host, port=web_port, log_dir=str(logs_dir))
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
                battery_voltage = self.current_data.get('battery', {}).get('voltage', 0)
                voltage_min = emergency_config.get('battery_voltage_min', 320.0)
                
                if battery_voltage < voltage_min:
                    logger.info("Undervoltage detected - enabling auto-reboot when voltage recovers")
                    # The GoodWe Lynx-D will auto-reboot when voltage returns to safe level
                    
        except Exception as e:
            logger.error(f"Failed to stop charging during emergency: {e}")
    
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
        voltage = battery_data.get('voltage', 0)
        voltage_min = battery_config.get('voltage_range', {}).get('min', 320.0)
        voltage_max = battery_config.get('voltage_range', {}).get('max', 480.0)
        
        if voltage < voltage_min or voltage > voltage_max:
            compliance_status["compliant"] = False
            compliance_status["issues"].append(f"Battery voltage {voltage}V outside GoodWe Lynx-D range ({voltage_min}V - {voltage_max}V)")
        
        # Check temperature compliance (0°C - 53°C for charging)
        temperature = battery_data.get('temperature', 0)
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
        """Make intelligent charging decision using enhanced smart strategy with multi-session support"""
        try:
            logger.info("Making charging decision...")
            
            # Check if multi-session charging is enabled and handle session management
            if self.multi_session_manager and self.multi_session_manager.enabled:
                await self._handle_multi_session_logic()
            
            # Get current price data
            price_data = self.charging_controller.fetch_price_data_for_date(
                datetime.now().strftime('%Y-%m-%d')
            )
            if not price_data:
                logger.warning("No price data available, skipping decision")
                return
            
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
            
            # Get current price data for the decision
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
                    
                    for item in current_price_data['value']:
                        item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                        if item_time <= current_time < item_time + timedelta(minutes=15):
                            current_price = float(item['csdac_pln']) + 0.0892  # SC component
                            break
                    
                    # Find cheapest price
                    prices = [(float(item['csdac_pln']) + 0.0892, datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M').hour) 
                             for item in current_price_data['value']]
                    if prices:
                        cheapest_price, cheapest_hour = min(prices, key=lambda x: x[0])
                        
                except Exception as e:
                    logger.warning(f"Failed to extract price data: {e}")
            
            # Prepare decision data for dashboard
            decision_data = {
                'timestamp': decision_record['timestamp'].isoformat(),
                'action': 'charge' if decision_record['decision'].get('should_charge', False) else 'wait',
                'source': decision_record['decision'].get('charging_source', 'grid'),  # Default to grid
                'duration': decision_record['decision'].get('charging_time_hours', 0),
                'energy_kwh': decision_record['decision'].get('energy_needed', 0),
                'estimated_cost_pln': decision_record['decision'].get('estimated_cost', 0),
                'estimated_savings_pln': 0,  # Not calculated in basic decision
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
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(decision_data, f, indent=2)
            
            logger.debug(f"Decision saved to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save decision to file: {e}")
    
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
    
    async def _execute_smart_decision(self, decision: Dict[str, Any]):
        """Execute the smart charging decision"""
        should_charge = decision.get('should_charge', False)
        reason = decision.get('reason', 'Unknown')
        priority = decision.get('priority', 'low')
        
        if should_charge:
            logger.info(f"Executing decision: Start charging - {reason}")
            # Check if this is a critical battery situation (force start)
            battery_data = self.current_data.get('battery', {})
            battery_soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
            force_start = battery_soc <= 20 or priority == 'critical'
            
            await self.charging_controller.start_price_based_charging(
                decision.get('price_data', {}), 
                force_start=force_start
            )
        else:
            logger.info(f"Executing decision: No action needed - {reason}")
            # Stop charging if currently charging
            if self.charging_controller.is_charging:
                await self.charging_controller.stop_price_based_charging()
    
    async def _execute_decision(self, decision: Dict[str, Any]):
        """Execute the charging decision"""
        action = decision.get('action', 'none')
        
        if action == 'start_charging':
            logger.info("Executing decision: Start charging")
            # Check if this is a critical battery situation (force start)
            battery_data = self.current_data.get('battery', {})
            battery_soc = battery_data.get('soc_percent', battery_data.get('soc', 50))
            force_start = battery_soc <= 5  # Emergency battery level only
            
            await self.charging_controller.start_price_based_charging(
                decision.get('price_data'), 
                force_start=force_start
            )
            
        elif action == 'stop_charging':
            logger.info("Executing decision: Stop charging")
            await self.charging_controller.stop_price_based_charging()
            
        elif action == 'continue_charging':
            logger.info("Executing decision: Continue charging")
            # No action needed, charging continues
            
        elif action == 'none':
            logger.info("Executing decision: No action needed")
            
        else:
            logger.warning(f"Unknown decision action: {action}")
    
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
        pv_production = self.current_data.get('pv', {}).get('total_power', 0)
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
        """Log current system status"""
        if not self.current_data:
            return
        
        battery_soc = self.current_data.get('battery', {}).get('soc_percent', 0)
        pv_power = self.current_data.get('photovoltaic', {}).get('current_power_w', 0)
        charging_status = self.current_data.get('battery', {}).get('charging_status', False)
        
        logger.info(f"Status - State: {self.state.value}, "
                   f"Battery: {battery_soc}%, "
                   f"PV: {pv_power}W, "
                   f"Charging: {charging_status}")
    
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
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the decision engine"""
        self.config = config
        self.coordinator_config = config.get('coordinator', {})
        
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
    
    def analyze_and_decide(self, current_data: Dict, price_data: Dict, historical_data: List) -> Dict[str, Any]:
        """Analyze current situation and make charging decision with timing awareness"""
        
        # Use timing-aware decision if enabled
        if self.timing_awareness_enabled:
            return self._analyze_and_decide_with_timing(current_data, price_data, historical_data)
        
        # Fallback to original scoring algorithm
        return self._analyze_and_decide_legacy(current_data, price_data, historical_data)
    
    def _analyze_and_decide_with_timing(self, current_data: Dict, price_data: Dict, historical_data: List) -> Dict[str, Any]:
        """Analyze and decide using timing-aware hybrid charging logic with weather integration and PV vs consumption analysis"""
        logger.info("Using timing-aware decision engine with weather integration and PV vs consumption analysis")
        
        try:
            # Get weather-enhanced PV forecast
            pv_forecast = self._get_weather_enhanced_pv_forecast(current_data)
            
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
            charging_decision = self.hybrid_logic.analyze_and_decide(current_data, price_data)
            
            # Apply weather-aware timing recommendation
            action = self._apply_weather_aware_timing(
                charging_decision.action, timing_recommendation, pv_trend_analysis, current_data
            )
            
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
    
    def _get_weather_enhanced_pv_forecast(self, current_data: Dict) -> List[Dict]:
        """Get PV forecast enhanced with weather data"""
        if not self.weather_enabled or 'weather' not in current_data:
            return self.pv_forecaster.forecast_pv_production()
        
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
        for item in price_data['value']:
            item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
            if item_time <= current_time < item_time + timedelta(minutes=15):
                # Calculate final price (market price + SC component)
                market_price = float(item['csdac_pln'])
                current_price = market_price + 0.0892  # SC component
                break
        
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
        critical_threshold = self.config.get('battery_management', {}).get('soc_thresholds', {}).get('critical', 20)
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
        
        # High score and not charging - start charging
        if total_score >= 70 and not is_charging:
            return 'start_charging'
        
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
