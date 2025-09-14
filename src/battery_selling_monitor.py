#!/usr/bin/env python3
"""
Battery Selling Safety Monitor for GoodWe Dynamic Price Optimiser

This module provides comprehensive safety monitoring for battery energy selling
with real-time safety checks, emergency stop capabilities, and health tracking.

Usage:
    from battery_selling_monitor import BatterySellingMonitor
    
    monitor = BatterySellingMonitor(config)
    safety_status = await monitor.check_safety_conditions(inverter, current_data)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import goodwe
    from goodwe import Inverter, InverterError
except ImportError:
    print("Error: goodwe library not found. Install with: pip install goodwe")
    raise


class SafetyStatus(Enum):
    """Safety status levels"""
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SafetyCheck:
    """Individual safety check result"""
    check_name: str
    status: SafetyStatus
    value: float
    threshold: float
    message: str
    timestamp: datetime


@dataclass
class SafetyReport:
    """Comprehensive safety report"""
    overall_status: SafetyStatus
    checks: List[SafetyCheck]
    recommendations: List[str]
    emergency_stop_required: bool
    timestamp: datetime


class BatterySellingMonitor:
    """Comprehensive safety monitoring for battery energy selling"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the safety monitor with configuration"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Safety thresholds from configuration
        self.safety_config = config.get('battery_selling', {}).get('safety_checks', {})
        
        # Battery temperature limits (GoodWe Lynx-D compliant)
        self.battery_temp_max = self.safety_config.get('battery_temp_max', 50.0)
        self.battery_temp_min = self.safety_config.get('battery_temp_min', -20.0)
        self.battery_temp_warning = 45.0  # Warning at 45°C
        
        # Grid voltage limits
        self.grid_voltage_min = self.safety_config.get('grid_voltage_min', 200.0)
        self.grid_voltage_max = self.safety_config.get('grid_voltage_max', 250.0)
        
        # SOC limits
        self.min_selling_soc = config.get('battery_selling', {}).get('min_battery_soc', 80.0)
        self.safety_margin_soc = config.get('battery_selling', {}).get('safety_margin_soc', 50.0)
        
        # Night hours (preserve battery charge)
        self.night_hours = self.safety_config.get('night_hours', [22, 23, 0, 1, 2, 3, 4, 5])
        
        # Monitoring state
        self.last_safety_check = None
        self.safety_history: List[SafetyReport] = []
        self.emergency_stop_count = 0
        self.warning_count = 0
        
        # Rate limiting for emergency alerts (prevent log spam)
        self.last_emergency_alert = None
        self.emergency_alert_cooldown = timedelta(minutes=5)  # 5-minute cooldown
        
        self.logger.info("Battery Selling Safety Monitor initialized")
        self.logger.info(f"  - Battery temp limits: {self.battery_temp_min}°C to {self.battery_temp_max}°C")
        self.logger.info(f"  - Grid voltage limits: {self.grid_voltage_min}V to {self.grid_voltage_max}V")
        self.logger.info(f"  - SOC limits: {self.min_selling_soc}% min, {self.safety_margin_soc}% safety margin")
    
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
    
    def _is_night_time(self) -> bool:
        """Check if current time is during night hours"""
        current_hour = datetime.now().hour
        return current_hour in self.night_hours
    
    def _check_battery_temperature(self, battery_temp: float) -> SafetyCheck:
        """Check battery temperature safety"""
        if battery_temp >= self.battery_temp_max:
            return SafetyCheck(
                check_name="battery_temperature",
                status=SafetyStatus.EMERGENCY,
                value=battery_temp,
                threshold=self.battery_temp_max,
                message=f"Battery temperature {battery_temp}°C exceeds maximum {self.battery_temp_max}°C - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        elif battery_temp <= self.battery_temp_min:
            return SafetyCheck(
                check_name="battery_temperature",
                status=SafetyStatus.EMERGENCY,
                value=battery_temp,
                threshold=self.battery_temp_min,
                message=f"Battery temperature {battery_temp}°C below minimum {self.battery_temp_min}°C - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        elif battery_temp >= self.battery_temp_warning:
            return SafetyCheck(
                check_name="battery_temperature",
                status=SafetyStatus.WARNING,
                value=battery_temp,
                threshold=self.battery_temp_warning,
                message=f"Battery temperature {battery_temp}°C approaching limit {self.battery_temp_max}°C",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="battery_temperature",
                status=SafetyStatus.SAFE,
                value=battery_temp,
                threshold=self.battery_temp_max,
                message=f"Battery temperature {battery_temp}°C within safe range",
                timestamp=datetime.now()
            )
    
    def _check_battery_soc(self, battery_soc: float) -> SafetyCheck:
        """Check battery SOC safety with data validation"""
        # Data validation - check for invalid readings
        if battery_soc < 0 or battery_soc > 100:
            return SafetyCheck(
                check_name="battery_soc",
                status=SafetyStatus.EMERGENCY,
                value=battery_soc,
                threshold="0-100",
                message=f"Invalid battery SOC reading {battery_soc}% - data validation failed - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        
        if battery_soc <= self.safety_margin_soc:
            return SafetyCheck(
                check_name="battery_soc",
                status=SafetyStatus.EMERGENCY,
                value=battery_soc,
                threshold=self.safety_margin_soc,
                message=f"Battery SOC {battery_soc}% at or below safety margin {self.safety_margin_soc}% - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        elif battery_soc < self.min_selling_soc:
            return SafetyCheck(
                check_name="battery_soc",
                status=SafetyStatus.WARNING,
                value=battery_soc,
                threshold=self.min_selling_soc,
                message=f"Battery SOC {battery_soc}% below minimum selling threshold {self.min_selling_soc}%",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="battery_soc",
                status=SafetyStatus.SAFE,
                value=battery_soc,
                threshold=self.min_selling_soc,
                message=f"Battery SOC {battery_soc}% above minimum selling threshold",
                timestamp=datetime.now()
            )
    
    def _check_grid_voltage(self, grid_voltage: float) -> SafetyCheck:
        """Check grid voltage safety with data validation"""
        # Data validation - check for invalid readings
        if grid_voltage < 0:
            return SafetyCheck(
                check_name="grid_voltage",
                status=SafetyStatus.EMERGENCY,
                value=grid_voltage,
                threshold=">0V",
                message=f"Invalid grid voltage reading {grid_voltage}V - communication error or inverter offline - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        
        if grid_voltage < self.grid_voltage_min or grid_voltage > self.grid_voltage_max:
            return SafetyCheck(
                check_name="grid_voltage",
                status=SafetyStatus.EMERGENCY,
                value=grid_voltage,
                threshold=f"{self.grid_voltage_min}-{self.grid_voltage_max}",
                message=f"Grid voltage {grid_voltage}V outside safe range {self.grid_voltage_min}-{self.grid_voltage_max}V - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="grid_voltage",
                status=SafetyStatus.SAFE,
                value=grid_voltage,
                threshold=f"{self.grid_voltage_min}-{self.grid_voltage_max}",
                message=f"Grid voltage {grid_voltage}V within safe range",
                timestamp=datetime.now()
            )
    
    def _check_night_time(self) -> SafetyCheck:
        """Check if it's night time (preserve battery charge)"""
        if self._is_night_time():
            return SafetyCheck(
                check_name="night_time",
                status=SafetyStatus.WARNING,
                value=datetime.now().hour,
                threshold="night_hours",
                message=f"Night hours detected (hour {datetime.now().hour}) - preserve battery charge",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="night_time",
                status=SafetyStatus.SAFE,
                value=datetime.now().hour,
                threshold="day_hours",
                message="Day hours - battery selling allowed",
                timestamp=datetime.now()
            )
    
    def _check_inverter_errors(self, inverter_data: Dict[str, Any]) -> SafetyCheck:
        """Check for inverter error codes"""
        error_codes = inverter_data.get('error_codes', [])
        if error_codes:
            return SafetyCheck(
                check_name="inverter_errors",
                status=SafetyStatus.EMERGENCY,
                value=len(error_codes),
                threshold=0,
                message=f"Inverter error codes detected: {error_codes} - EMERGENCY STOP",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="inverter_errors",
                status=SafetyStatus.SAFE,
                value=0,
                threshold=0,
                message="No inverter error codes detected",
                timestamp=datetime.now()
            )
    
    def _check_battery_health(self, battery_data: Dict[str, Any]) -> SafetyCheck:
        """Check overall battery health indicators"""
        # Check for any battery health warnings
        health_warnings = []
        
        # Check voltage range
        voltage = self._safe_float(battery_data.get('voltage', 0))
        if voltage < 320 or voltage > 480:  # GoodWe Lynx-D voltage range
            health_warnings.append(f"Voltage {voltage}V outside normal range")
        
        # Check for any other health indicators
        # Add more health checks as needed
        
        if health_warnings:
            return SafetyCheck(
                check_name="battery_health",
                status=SafetyStatus.WARNING,
                value=len(health_warnings),
                threshold=0,
                message=f"Battery health warnings: {'; '.join(health_warnings)}",
                timestamp=datetime.now()
            )
        else:
            return SafetyCheck(
                check_name="battery_health",
                status=SafetyStatus.SAFE,
                value=0,
                threshold=0,
                message="Battery health indicators normal",
                timestamp=datetime.now()
            )
    
    async def check_safety_conditions(self, inverter: Inverter, current_data: Dict[str, Any]) -> SafetyReport:
        """Perform comprehensive safety check with data validation"""
        try:
            # Extract system data with validation
            battery_data = current_data.get('battery', {})
            grid_data = current_data.get('grid', {})
            inverter_data = current_data.get('inverter', {})
            
            # Validate data extraction with type conversion
            battery_soc = self._safe_float(battery_data.get('soc_percent', 0))
            battery_temp = self._safe_float(battery_data.get('temperature', 0))
            grid_voltage = self._safe_float(grid_data.get('voltage', 0))
            
            # Log data validation issues
            if not battery_data:
                self.logger.warning("No battery data available in current_data")
            if not grid_data:
                self.logger.warning("No grid data available in current_data")
            if not inverter_data:
                self.logger.warning("No inverter data available in current_data")
            
            # Perform all safety checks
            checks = [
                self._check_battery_temperature(battery_temp),
                self._check_battery_soc(battery_soc),
                self._check_grid_voltage(grid_voltage),
                self._check_night_time(),
                self._check_inverter_errors(inverter_data),
                self._check_battery_health(battery_data)
            ]
            
            # Determine overall safety status
            emergency_checks = [c for c in checks if c.status == SafetyStatus.EMERGENCY]
            warning_checks = [c for c in checks if c.status == SafetyStatus.WARNING]
            
            if emergency_checks:
                overall_status = SafetyStatus.EMERGENCY
                emergency_stop_required = True
                self.emergency_stop_count += 1
            elif warning_checks:
                overall_status = SafetyStatus.WARNING
                emergency_stop_required = False
                self.warning_count += 1
            else:
                overall_status = SafetyStatus.SAFE
                emergency_stop_required = False
            
            # Generate recommendations
            recommendations = self._generate_recommendations(checks, overall_status)
            
            # Create safety report
            report = SafetyReport(
                overall_status=overall_status,
                checks=checks,
                recommendations=recommendations,
                emergency_stop_required=emergency_stop_required,
                timestamp=datetime.now()
            )
            
            # Store in history
            self.safety_history.append(report)
            self.last_safety_check = report
            
            # Log safety status with rate limiting
            if overall_status == SafetyStatus.EMERGENCY:
                # Rate limiting for emergency alerts
                now = datetime.now()
                should_log = (self.last_emergency_alert is None or 
                             now - self.last_emergency_alert > self.emergency_alert_cooldown)
                
                if should_log:
                    self.logger.error(f"EMERGENCY SAFETY ALERT: {len(emergency_checks)} critical issues detected")
                    for check in emergency_checks:
                        self.logger.error(f"  - {check.check_name}: {check.message}")
                    self.last_emergency_alert = now
                else:
                    # Log at debug level during cooldown
                    self.logger.debug(f"Emergency alert suppressed (cooldown active): {len(emergency_checks)} critical issues")
            elif overall_status == SafetyStatus.WARNING:
                self.logger.warning(f"Safety warning: {len(warning_checks)} issues detected")
                for check in warning_checks:
                    self.logger.warning(f"  - {check.check_name}: {check.message}")
            else:
                self.logger.debug("All safety checks passed")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error during safety check: {e}")
            # Return emergency status on error
            return SafetyReport(
                overall_status=SafetyStatus.EMERGENCY,
                checks=[],
                recommendations=["Safety check failed - investigate immediately"],
                emergency_stop_required=True,
                timestamp=datetime.now()
            )
    
    def _generate_recommendations(self, checks: List[SafetyCheck], overall_status: SafetyStatus) -> List[str]:
        """Generate safety recommendations based on check results"""
        recommendations = []
        
        if overall_status == SafetyStatus.EMERGENCY:
            recommendations.append("IMMEDIATE ACTION REQUIRED: Stop all battery selling operations")
            recommendations.append("Check system for critical safety issues")
            recommendations.append("Contact technical support if issues persist")
        
        elif overall_status == SafetyStatus.WARNING:
            recommendations.append("Monitor system closely for any changes")
            recommendations.append("Consider reducing selling power or stopping if conditions worsen")
        
        # Specific recommendations based on failed checks
        for check in checks:
            if check.status == SafetyStatus.EMERGENCY:
                if check.check_name == "battery_temperature":
                    recommendations.append("Check battery cooling system and ambient temperature")
                elif check.check_name == "battery_soc":
                    recommendations.append("Stop selling immediately and charge battery")
                elif check.check_name == "grid_voltage":
                    recommendations.append("Check grid connection and contact utility if needed")
                elif check.check_name == "inverter_errors":
                    recommendations.append("Check inverter status and reset if necessary")
        
        return recommendations
    
    async def emergency_stop(self, inverter: Inverter) -> bool:
        """Perform emergency stop of all battery selling operations"""
        try:
            self.logger.critical("EMERGENCY STOP: Stopping all battery selling operations")
            
            # Set inverter to safe mode
            await inverter.set_operation_mode(goodwe.OperationMode.GENERAL)
            
            # Disable grid export
            await inverter.set_grid_export_limit(0)
            
            # Log emergency stop
            self.logger.critical(f"Emergency stop completed at {datetime.now()}")
            self.logger.critical(f"Total emergency stops: {self.emergency_stop_count}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")
            return False
    
    def get_safety_status(self) -> Dict[str, Any]:
        """Get current safety status and statistics"""
        return {
            "last_check": self.last_safety_check.timestamp.isoformat() if self.last_safety_check else None,
            "overall_status": self.last_safety_check.overall_status.value if self.last_safety_check else "unknown",
            "emergency_stop_required": self.last_safety_check.emergency_stop_required if self.last_safety_check else False,
            "statistics": {
                "emergency_stops": self.emergency_stop_count,
                "warnings": self.warning_count,
                "total_checks": len(self.safety_history)
            },
            "recent_checks": [
                {
                    "timestamp": report.timestamp.isoformat(),
                    "status": report.overall_status.value,
                    "emergency_stop_required": report.emergency_stop_required,
                    "checks_failed": len([c for c in report.checks if c.status != SafetyStatus.SAFE])
                }
                for report in self.safety_history[-10:]  # Last 10 checks
            ],
            "configuration": {
                "battery_temp_max": self.battery_temp_max,
                "battery_temp_min": self.battery_temp_min,
                "grid_voltage_min": self.grid_voltage_min,
                "grid_voltage_max": self.grid_voltage_max,
                "min_selling_soc": self.min_selling_soc,
                "safety_margin_soc": self.safety_margin_soc,
                "night_hours": self.night_hours
            }
        }
    
    def get_safety_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get safety history for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            {
                "timestamp": report.timestamp.isoformat(),
                "overall_status": report.overall_status.value,
                "emergency_stop_required": report.emergency_stop_required,
                "checks": [
                    {
                        "name": check.check_name,
                        "status": check.status.value,
                        "value": check.value,
                        "threshold": check.threshold,
                        "message": check.message
                    }
                    for check in report.checks
                ],
                "recommendations": report.recommendations
            }
            for report in self.safety_history
            if report.timestamp >= cutoff_time
        ]
    
    def diagnose_communication_issues(self, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """Diagnose potential communication issues with the inverter"""
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "recommendations": []
        }
        
        # Check for missing data
        battery_data = current_data.get('battery', {})
        grid_data = current_data.get('grid', {})
        inverter_data = current_data.get('inverter', {})
        
        if not battery_data:
            diagnosis["issues"].append("No battery data received")
            diagnosis["recommendations"].append("Check inverter communication and battery connection")
        
        if not grid_data:
            diagnosis["issues"].append("No grid data received")
            diagnosis["recommendations"].append("Check inverter communication and grid connection")
        
        if not inverter_data:
            diagnosis["issues"].append("No inverter data received")
            diagnosis["recommendations"].append("Check inverter communication and network connection")
        
        # Check for zero values that might indicate communication issues
        battery_soc = battery_data.get('soc_percent', 0)
        grid_voltage = grid_data.get('voltage', 0)
        
        if battery_soc == 0:
            diagnosis["issues"].append("Battery SOC reading is 0% - possible communication issue")
            diagnosis["recommendations"].append("Verify battery connection and inverter communication")
        
        if grid_voltage == 0:
            diagnosis["issues"].append("Grid voltage reading is 0V - possible communication issue")
            diagnosis["recommendations"].append("Verify grid connection and inverter communication")
        
        return diagnosis
