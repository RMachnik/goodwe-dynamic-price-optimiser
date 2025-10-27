"""
GoodWe Inverter Adapter

Adapter implementation for GoodWe inverters using the goodwe Python library.
Implements all port interfaces to provide vendor-specific functionality.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import goodwe
    from goodwe import Inverter, InverterError, OperationMode as GoodWeOperationMode
    GOODWE_AVAILABLE = True
except ImportError:
    GOODWE_AVAILABLE = False
    print("Warning: goodwe library not available. Install with: pip install goodwe")

from ..ports.inverter_port import InverterPort
from ..models.operation_mode import OperationMode
from ..models.inverter_config import InverterConfig, SafetyConfig
from ..models.inverter_data import InverterStatus, InverterState, SensorReading, InverterCapabilities
from ..models.battery_status import BatteryStatus, BatteryData, BatteryCapabilities
from ..ports.data_collector_port import PVData, GridData, ConsumptionData, ComprehensiveData


class GoodWeInverterAdapter(InverterPort):
    """
    GoodWe inverter adapter implementing the InverterPort interface.
    
    This adapter wraps the goodwe Python library to provide vendor-agnostic
    access to GoodWe inverters (ET, ES, DT families).
    """
    
    # Operation mode mapping: Generic -> GoodWe
    OPERATION_MODE_MAP = {
        OperationMode.GENERAL: GoodWeOperationMode.GENERAL,
        OperationMode.OFF_GRID: GoodWeOperationMode.OFF_GRID,
        OperationMode.BACKUP: GoodWeOperationMode.BACKUP,
        OperationMode.ECO: GoodWeOperationMode.ECO,
        OperationMode.ECO_CHARGE: GoodWeOperationMode.ECO_CHARGE,
        OperationMode.ECO_DISCHARGE: GoodWeOperationMode.ECO_DISCHARGE,
    }
    
    def __init__(self):
        """Initialize GoodWe adapter."""
        if not GOODWE_AVAILABLE:
            raise ImportError("goodwe library not available")
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self._inverter: Optional[Inverter] = None
        self._config: Optional[InverterConfig] = None
        self._is_charging = False
        self._charging_start_time: Optional[datetime] = None
    
    @property
    def vendor_name(self) -> str:
        """Get vendor name."""
        return "goodwe"
    
    @property
    def model_name(self) -> str:
        """Get inverter model name."""
        if self._inverter:
            return self._inverter.model_name
        return ""
    
    @property
    def serial_number(self) -> str:
        """Get inverter serial number."""
        if self._inverter:
            return self._inverter.serial_number
        return ""
    
    async def connect(self, config: InverterConfig) -> bool:
        """
        Connect to GoodWe inverter.
        
        Args:
            config: Inverter configuration
            
        Returns:
            True if connection successful
        """
        self._config = config
        
        # Validate vendor
        if config.vendor.lower() != "goodwe":
            raise ValueError(f"Invalid vendor for GoodWe adapter: {config.vendor}")
        
        # Extract GoodWe-specific config
        family = config.vendor_config.get('family', 'ET')
        comm_addr = config.vendor_config.get('comm_addr', None)
        
        # Retry connection logic
        for attempt in range(config.retries):
            try:
                if attempt > 0:
                    self.logger.info(f"Retry attempt {attempt + 1}/{config.retries}...")
                    await asyncio.sleep(config.retry_delay)
                else:
                    self.logger.info(f"Connecting to GoodWe inverter at {config.ip_address}")
                
                # Connect to inverter
                self._inverter = await goodwe.connect(
                    host=config.ip_address,
                    family=family,
                    timeout=int(config.timeout),
                    retries=1,  # We handle retries at this level
                    comm_addr=comm_addr
                )
                
                self.logger.info(
                    f"Connected to {self._inverter.model_name} "
                    f"(Serial: {self._inverter.serial_number})"
                )
                return True
                
            except Exception as e:
                if attempt < config.retries - 1:
                    self.logger.warning(
                        f"Connection attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {config.retry_delay}s..."
                    )
                else:
                    self.logger.error(
                        f"Failed to connect after {config.retries} attempts: {e}"
                    )
        
        return False
    
    async def disconnect(self) -> None:
        """Disconnect from inverter."""
        self._inverter = None
        self._config = None
        self._is_charging = False
        self._charging_start_time = None
        self.logger.info("Disconnected from inverter")
    
    def is_connected(self) -> bool:
        """Check if inverter is connected."""
        return self._inverter is not None
    
    async def get_status(self) -> InverterStatus:
        """Get current inverter status."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # Build sensor readings
            sensors = {}
            for sensor in self._inverter.sensors():
                if sensor.id_ in runtime_data:
                    sensors[sensor.id_] = SensorReading(
                        sensor_id=sensor.id_,
                        name=sensor.name,
                        value=runtime_data[sensor.id_],
                        unit=sensor.unit,
                        timestamp=datetime.now()
                    )
            
            # Determine inverter state (simplified)
            state = InverterState.NORMAL if sensors else InverterState.UNKNOWN
            
            return InverterStatus(
                model_name=self._inverter.model_name,
                serial_number=self._inverter.serial_number,
                firmware_version=getattr(self._inverter, 'firmware', 'unknown'),
                state=state,
                is_connected=True,
                timestamp=datetime.now(),
                sensors=sensors
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get inverter status: {e}")
            raise RuntimeError(f"Failed to get status: {e}")
    
    async def get_battery_status(self) -> BatteryStatus:
        """Get current battery status."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # Extract battery data from runtime
            soc = runtime_data.get('battery_soc', 0.0)
            voltage = runtime_data.get('vbattery1', 0.0)
            current = runtime_data.get('ibattery1', 0.0)
            power = runtime_data.get('pbattery1', 0.0)
            temperature = runtime_data.get('battery_temperature', 25.0)
            
            # Determine charging/discharging state
            # Negative current = charging, Positive = discharging
            is_charging = current < 0
            is_discharging = current > 0
            
            return BatteryStatus(
                soc_percent=float(soc),
                voltage=float(voltage),
                current=float(current),
                power=float(power),
                temperature=float(temperature),
                is_charging=is_charging,
                is_discharging=is_discharging,
                timestamp=datetime.now(),
                health_status="good"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get battery status: {e}")
            raise RuntimeError(f"Failed to get battery status: {e}")
    
    async def read_runtime_data(self) -> Dict[str, Any]:
        """
        Read all runtime data from inverter.
        
        Returns raw sensor data for backward compatibility.
        """
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # Build status dict matching existing format
            status = {}
            for sensor in self._inverter.sensors():
                if sensor.id_ in runtime_data:
                    status[sensor.id_] = {
                        'name': sensor.name,
                        'value': runtime_data[sensor.id_],
                        'unit': sensor.unit
                    }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to read runtime data: {e}")
            return {}
    
    async def check_safety_conditions(
        self, 
        safety_config: SafetyConfig
    ) -> tuple[bool, list[str]]:
        """Check if current conditions are safe."""
        if not self._inverter:
            return False, ["Inverter not connected"]
        
        issues = []
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # Check battery temperature
            battery_temp = runtime_data.get('battery_temperature', 0)
            if battery_temp < safety_config.battery_temp_min:
                issues.append(f"Battery temp too low: {battery_temp}°C")
            if battery_temp > safety_config.battery_temp_max:
                issues.append(f"Battery temp too high: {battery_temp}°C")
            
            # Check battery SOC
            battery_soc = runtime_data.get('battery_soc', 0)
            if battery_soc < safety_config.min_battery_soc:
                issues.append(f"Battery SOC too low: {battery_soc}%")
            
            # Check battery voltage
            battery_voltage = runtime_data.get('vbattery1', 0)
            if battery_voltage < safety_config.battery_voltage_min:
                issues.append(f"Battery voltage too low: {battery_voltage}V")
            if battery_voltage > safety_config.battery_voltage_max:
                issues.append(f"Battery voltage too high: {battery_voltage}V")
            
            # Check grid voltage
            grid_voltage = runtime_data.get('vgrid', 0)
            if grid_voltage > 0:  # Only check if grid connected
                if grid_voltage < safety_config.grid_voltage_min:
                    issues.append(f"Grid voltage too low: {grid_voltage}V")
                if grid_voltage > safety_config.grid_voltage_max:
                    issues.append(f"Grid voltage too high: {grid_voltage}V")
            
            is_safe = len(issues) == 0
            return is_safe, issues
            
        except Exception as e:
            self.logger.error(f"Safety check failed: {e}")
            return False, [f"Safety check error: {e}"]
    
    # Command Executor Port Implementation
    
    async def set_operation_mode(
        self,
        mode: OperationMode,
        power_w: int = 0,
        min_soc: int = 0
    ) -> bool:
        """Set inverter operation mode."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            # Map generic mode to GoodWe mode
            if mode not in self.OPERATION_MODE_MAP:
                self.logger.error(f"Unsupported operation mode: {mode}")
                return False
            
            goodwe_mode = self.OPERATION_MODE_MAP[mode]
            
            # Set operation mode with parameters
            await self._inverter.set_operation_mode(
                goodwe_mode,
                power_w if power_w > 0 else None,
                min_soc if min_soc > 0 else None
            )
            
            self.logger.info(f"Operation mode set to {mode}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set operation mode: {e}")
            return False
    
    async def start_charging(self, power_pct: int, target_soc: int) -> bool:
        """Start battery charging."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        if not (0 <= power_pct <= 100):
            raise ValueError(f"Power percentage out of range: {power_pct}")
        if not (0 <= target_soc <= 100):
            raise ValueError(f"Target SOC out of range: {target_soc}")
        
        try:
            # Enable fast charging
            await self._inverter.write_setting('fast_charging', 1)
            self.logger.info("Fast charging enabled")
            
            # Set charging power
            await self._inverter.write_setting('fast_charging_power', power_pct)
            self.logger.info(f"Charging power set to {power_pct}%")
            
            # Set target SOC
            await self._inverter.write_setting('fast_charging_soc', target_soc)
            self.logger.info(f"Target SOC set to {target_soc}%")
            
            self._is_charging = True
            self._charging_start_time = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start charging: {e}")
            return False
    
    async def stop_charging(self) -> bool:
        """Stop battery charging."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            # Disable fast charging
            await self._inverter.write_setting('fast_charging', 0)
            
            self._is_charging = False
            self._charging_start_time = None
            
            self.logger.info("Charging stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop charging: {e}")
            return False
    
    async def set_grid_export_limit(self, power_w: int) -> bool:
        """Set grid export power limit."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            await self._inverter.set_grid_export_limit(power_w)
            self.logger.info(f"Grid export limit set to {power_w}W")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set grid export limit: {e}")
            return False
    
    async def set_battery_dod(self, depth_pct: int) -> bool:
        """Set battery Depth of Discharge limit."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        if not (0 <= depth_pct <= 100):
            raise ValueError(f"DoD percentage out of range: {depth_pct}")
        
        try:
            await self._inverter.set_ongrid_battery_dod(depth_pct)
            self.logger.info(f"Battery DoD set to {depth_pct}%")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set battery DoD: {e}")
            return False
    
    async def emergency_stop(self) -> bool:
        """Execute emergency stop."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            # Set to GENERAL mode
            await self._inverter.set_operation_mode(GoodWeOperationMode.GENERAL)
            
            # Disable grid export
            await self._inverter.set_grid_export_limit(0)
            
            # Stop charging
            if self._is_charging:
                await self.stop_charging()
            
            self.logger.warning("Emergency stop executed")
            return True
            
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
            return False
    
    # Data Collector Port Implementation
    
    async def collect_battery_data(self) -> BatteryData:
        """Collect battery data."""
        battery_status = await self.get_battery_status()
        
        # Get daily statistics if available
        try:
            runtime_data = await self._inverter.read_runtime_data()
            daily_charge = runtime_data.get('e_bat_charge_total', 0.0)
            daily_discharge = runtime_data.get('e_bat_discharge_total', 0.0)
        except:
            daily_charge = 0.0
            daily_discharge = 0.0
        
        return BatteryData(
            status=battery_status,
            daily_charge_kwh=float(daily_charge),
            daily_discharge_kwh=float(daily_discharge)
        )
    
    async def collect_pv_data(self) -> PVData:
        """Collect PV data."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # PV power
            ppv = runtime_data.get('ppv', 0.0)
            ppv1 = runtime_data.get('ppv1', 0.0)
            ppv2 = runtime_data.get('ppv2', 0.0)
            
            # PV voltage and current
            vpv1 = runtime_data.get('vpv1', 0.0)
            vpv2 = runtime_data.get('vpv2', 0.0)
            ipv1 = runtime_data.get('ipv1', 0.0)
            ipv2 = runtime_data.get('ipv2', 0.0)
            
            # Daily generation
            e_day = runtime_data.get('e_day', 0.0)
            
            return PVData(
                current_power_w=float(ppv),
                current_power_kw=float(ppv) / 1000.0,
                daily_generation_kwh=float(e_day),
                string1_power_w=float(ppv1),
                string2_power_w=float(ppv2),
                string1_voltage_v=float(vpv1),
                string2_voltage_v=float(vpv2),
                string1_current_a=float(ipv1),
                string2_current_a=float(ipv2)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect PV data: {e}")
            raise RuntimeError(f"Failed to collect PV data: {e}")
    
    async def collect_grid_data(self) -> GridData:
        """Collect grid data."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # Grid power (negative = export, positive = import)
            pgrid = runtime_data.get('pgrid', 0.0)
            
            # Grid voltage and frequency
            vgrid = runtime_data.get('vgrid', 0.0)
            fgrid = runtime_data.get('fgrid', 0.0)
            
            # Phase currents
            igrid = runtime_data.get('igrid', 0.0)
            igrid2 = runtime_data.get('igrid2', 0.0)
            igrid3 = runtime_data.get('igrid3', 0.0)
            
            # Daily totals
            e_grid_in = runtime_data.get('e_grid_in_total', 0.0)
            e_grid_out = runtime_data.get('e_grid_out_total', 0.0)
            
            return GridData(
                current_power_w=float(pgrid),
                current_power_kw=float(pgrid) / 1000.0,
                daily_import_kwh=float(e_grid_in),
                daily_export_kwh=float(e_grid_out),
                voltage=float(vgrid),
                frequency=float(fgrid),
                phase1_current_a=float(igrid),
                phase2_current_a=float(igrid2),
                phase3_current_a=float(igrid3)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect grid data: {e}")
            raise RuntimeError(f"Failed to collect grid data: {e}")
    
    async def collect_consumption_data(self) -> ConsumptionData:
        """Collect consumption data."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            runtime_data = await self._inverter.read_runtime_data()
            
            # House consumption (calculated or direct sensor)
            house_consumption = runtime_data.get('house_consumption', 0.0)
            e_load_day = runtime_data.get('e_load_day', 0.0)
            
            return ConsumptionData(
                current_power_w=float(house_consumption),
                current_power_kw=float(house_consumption) / 1000.0,
                daily_consumption_kwh=float(e_load_day)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect consumption data: {e}")
            raise RuntimeError(f"Failed to collect consumption data: {e}")
    
    async def collect_comprehensive_data(self) -> ComprehensiveData:
        """Collect all system data."""
        if not self._inverter:
            raise RuntimeError("Inverter not connected")
        
        try:
            # Collect all data types
            battery_data = await self.collect_battery_data()
            pv_data = await self.collect_pv_data()
            grid_data = await self.collect_grid_data()
            consumption_data = await self.collect_consumption_data()
            runtime_data = await self._inverter.read_runtime_data()
            
            now = datetime.now()
            
            # Build comprehensive data structure matching existing format
            return ComprehensiveData(
                timestamp=now.isoformat(),
                date=now.strftime('%Y-%m-%d'),
                time=now.strftime('%H:%M:%S'),
                battery={
                    'soc_percent': battery_data.status.soc_percent,
                    'voltage': battery_data.status.voltage,
                    'current': battery_data.status.current,
                    'power_w': battery_data.status.power,
                    'power_kw': battery_data.status.power_kw,
                    'temperature': battery_data.status.temperature,
                    'charging_status': battery_data.status.is_charging,
                    'fast_charging_enabled': self._is_charging
                },
                photovoltaic={
                    'current_power_w': pv_data.current_power_w,
                    'current_power_kw': pv_data.current_power_kw,
                    'daily_generation_kwh': pv_data.daily_generation_kwh,
                    'string1_power_w': pv_data.string1_power_w,
                    'string2_power_w': pv_data.string2_power_w,
                    'efficiency_percent': pv_data.efficiency_percent
                },
                grid={
                    'current_power_w': grid_data.current_power_w,
                    'current_power_kw': grid_data.current_power_kw,
                    'daily_import_kwh': grid_data.daily_import_kwh,
                    'daily_export_kwh': grid_data.daily_export_kwh,
                    'voltage': grid_data.voltage,
                    'frequency': grid_data.frequency,
                    'phase1_current_a': grid_data.phase1_current_a,
                    'phase2_current_a': grid_data.phase2_current_a,
                    'phase3_current_a': grid_data.phase3_current_a
                },
                house_consumption={
                    'current_power_w': consumption_data.current_power_w,
                    'current_power_kw': consumption_data.current_power_kw,
                    'daily_consumption_kwh': consumption_data.daily_consumption_kwh
                },
                inverter={
                    'model': self.model_name,
                    'serial': self.serial_number,
                    'temperature': runtime_data.get('temperature', 0.0),
                    'status': 'normal'
                },
                daily_totals={
                    'pv_generation_kwh': pv_data.daily_generation_kwh,
                    'grid_import_kwh': grid_data.daily_import_kwh,
                    'grid_export_kwh': grid_data.daily_export_kwh,
                    'consumption_kwh': consumption_data.daily_consumption_kwh,
                    'battery_charge_kwh': battery_data.daily_charge_kwh,
                    'battery_discharge_kwh': battery_data.daily_discharge_kwh
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to collect comprehensive data: {e}")
            raise RuntimeError(f"Failed to collect comprehensive data: {e}")

