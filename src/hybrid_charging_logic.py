#!/usr/bin/env python3
"""
Hybrid Charging Logic Module
Implements intelligent hybrid charging decisions (PV + Grid)

This module implements the core logic for determining when to use:
- PV-only charging
- Grid-only charging  
- Hybrid charging (PV + Grid)
- Wait for better conditions

Based on the critical scenario: Low price window + insufficient PV timing
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from pv_forecasting import PVForecaster
from price_window_analyzer import PriceWindowAnalyzer, PriceWindow

logger = logging.getLogger(__name__)

@dataclass
class ChargingDecision:
    """Represents a charging decision with all relevant information"""
    action: str  # 'start_pv_charging', 'start_grid_charging', 'start_hybrid_charging', 'wait'
    charging_source: str  # 'pv', 'grid', 'hybrid', 'none'
    duration_hours: float
    energy_kwh: float
    estimated_cost_pln: float
    estimated_savings_pln: float
    confidence: float
    reason: str
    start_time: datetime
    end_time: datetime
    pv_contribution_kwh: float = 0.0
    grid_contribution_kwh: float = 0.0

class HybridChargingLogic:
    """Implements intelligent hybrid charging decisions"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the hybrid charging logic"""
        self.config = config
        
        # Initialize components
        self.pv_forecaster = PVForecaster(config)
        self.price_analyzer = PriceWindowAnalyzer(config)
        
        # Charging parameters
        self.charging_rate_kw = config.get('charging_rate_kw', 3.0)  # Default 3kW charging
        self.battery_capacity_kwh = config.get('battery_capacity_kwh', 10.0)  # Default 10kWh battery
        self.min_charging_duration_hours = config.get('min_charging_duration_hours', 0.25)  # 15 minutes
        self.max_charging_duration_hours = config.get('max_charging_duration_hours', 4.0)   # 4 hours
        
        # Decision thresholds
        self.min_savings_threshold_pln = config.get('min_savings_threshold_pln', 50.0)
        self.critical_battery_threshold = config.get('critical_battery_threshold', 20.0)  # 20% SOC
        self.low_battery_threshold = config.get('low_battery_threshold', 40.0)  # 40% SOC
        
        # Hybrid charging parameters
        self.pv_charging_efficiency = config.get('pv_charging_efficiency', 0.95)  # 95% efficiency
        self.grid_charging_efficiency = config.get('grid_charging_efficiency', 0.90)  # 90% efficiency
        self.house_consumption_buffer_kw = config.get('house_consumption_buffer_kw', 0.5)  # 500W buffer
    
    def analyze_and_decide(self, current_data: Dict[str, Any], price_data: Dict[str, Any]) -> ChargingDecision:
        """
        Analyze current conditions and make optimal charging decision
        
        Args:
            current_data: Current system data (battery, PV, consumption)
            price_data: Current electricity price data
            
        Returns:
            ChargingDecision with optimal action
        """
        logger.info("Analyzing conditions for optimal charging decision")
        
        # Extract current conditions
        battery_soc = current_data.get('battery', {}).get('soc_percent', 50)
        current_pv_kw = current_data.get('photovoltaic', {}).get('current_power_kw', 0)
        current_consumption_kw = current_data.get('house_consumption', {}).get('current_power_kw', 0)
        
        logger.info(f"Current conditions: Battery {battery_soc}%, PV {current_pv_kw:.1f}kW, Consumption {current_consumption_kw:.1f}kW")
        
        # Calculate energy needed
        energy_needed_kwh = self._calculate_energy_needed(battery_soc)
        
        if energy_needed_kwh <= 0:
            return ChargingDecision(
                action='wait',
                charging_source='none',
                duration_hours=0.0,
                energy_kwh=0.0,
                estimated_cost_pln=0.0,
                estimated_savings_pln=0.0,
                confidence=1.0,
                reason='Battery already at target level',
                start_time=datetime.now(),
                end_time=datetime.now()
            )
        
        # Get PV forecasts
        pv_forecasts = self.pv_forecaster.forecast_pv_production()
        
        # Analyze price windows and timing
        timing_analysis = self.price_analyzer.analyze_timing_vs_price(
            price_data, pv_forecasts, energy_needed_kwh
        )
        
        # Make decision based on analysis
        decision = self._make_charging_decision(
            current_data, price_data, pv_forecasts, timing_analysis, energy_needed_kwh
        )
        
        logger.info(f"Decision: {decision.action} - {decision.reason}")
        return decision
    
    def _calculate_energy_needed(self, battery_soc: float) -> float:
        """Calculate energy needed to reach target SOC"""
        target_soc = self.config.get('target_battery_soc', 60.0)  # Default 60% target
        
        if battery_soc >= target_soc:
            return 0.0
        
        energy_needed_kwh = (target_soc - battery_soc) / 100.0 * self.battery_capacity_kwh
        return max(0.0, energy_needed_kwh)
    
    def _make_charging_decision(self, current_data: Dict[str, Any], price_data: Dict[str, Any],
                               pv_forecasts: List[Dict], timing_analysis: Dict[str, Any],
                               energy_needed_kwh: float) -> ChargingDecision:
        """Make the optimal charging decision based on all factors"""
        
        battery_soc = current_data.get('battery', {}).get('soc_percent', 50)
        current_pv_kw = current_data.get('photovoltaic', {}).get('current_power_kw', 0)
        
        # Critical battery level - charge immediately
        if battery_soc <= self.critical_battery_threshold:
            return self._create_emergency_charging_decision(current_data, price_data, energy_needed_kwh)
        
        # Get optimal price window
        optimal_window_data = timing_analysis.get('optimal_window')
        if not optimal_window_data:
            return self._create_wait_decision("No suitable price window found")
        
        optimal_window = self._create_price_window_from_data(optimal_window_data)
        
        # Analyze PV timing
        pv_timing = timing_analysis.get('pv_timing', {})
        
        # Decision logic based on timing analysis
        recommendation = timing_analysis.get('recommendation', 'wait')
        
        if recommendation == 'pv_charging':
            return self._create_pv_charging_decision(
                current_data, pv_forecasts, optimal_window, energy_needed_kwh
            )
        
        elif recommendation == 'hybrid_charging':
            return self._create_hybrid_charging_decision(
                current_data, price_data, pv_forecasts, optimal_window, energy_needed_kwh
            )
        
        elif recommendation == 'wait_for_better_timing':
            return self._create_wait_decision("Waiting for better timing conditions")
        
        else:  # wait
            return self._create_wait_decision("No optimal charging conditions found")
    
    def _create_emergency_charging_decision(self, current_data: Dict[str, Any], 
                                          price_data: Dict[str, Any], energy_needed_kwh: float) -> ChargingDecision:
        """Create emergency charging decision for critical battery level"""
        logger.warning("Critical battery level - charging immediately")
        
        # Use current price for emergency charging
        current_price = self._get_current_price(price_data)
        
        # Calculate charging time
        charging_time_hours = energy_needed_kwh / self.charging_rate_kw
        
        # Calculate cost
        energy_cost_pln = energy_needed_kwh * (current_price / 1000.0)  # Convert PLN/MWh to PLN/kWh
        estimated_cost_pln = energy_cost_pln / self.grid_charging_efficiency
        
        return ChargingDecision(
            action='start_grid_charging',
            charging_source='grid',
            duration_hours=charging_time_hours,
            energy_kwh=energy_needed_kwh,
            estimated_cost_pln=estimated_cost_pln,
            estimated_savings_pln=0.0,  # No savings for emergency charging
            confidence=1.0,
            reason=f'Critical battery level ({current_data.get("battery", {}).get("soc_percent", 0)}%) - charging immediately',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=charging_time_hours),
            grid_contribution_kwh=energy_needed_kwh
        )
    
    def _create_pv_charging_decision(self, current_data: Dict[str, Any], pv_forecasts: List[Dict],
                                   optimal_window: PriceWindow, energy_needed_kwh: float) -> ChargingDecision:
        """Create PV-only charging decision"""
        logger.info("Creating PV-only charging decision")
        
        # Calculate PV charging time
        pv_timing = self.pv_forecaster.estimate_charging_time_with_pv(energy_needed_kwh, pv_forecasts)
        charging_time_hours = pv_timing['estimated_time_hours']
        
        # Use optimal window timing
        start_time = optimal_window.start_time
        end_time = start_time + timedelta(hours=charging_time_hours)
        
        return ChargingDecision(
            action='start_pv_charging',
            charging_source='pv',
            duration_hours=charging_time_hours,
            energy_kwh=energy_needed_kwh,
            estimated_cost_pln=0.0,  # PV charging is free
            estimated_savings_pln=self._calculate_pv_savings(optimal_window, energy_needed_kwh),
            confidence=pv_timing.get('confidence', 0.8),
            reason=f'PV can complete charging in {charging_time_hours:.1f}h during low price window',
            start_time=start_time,
            end_time=end_time,
            pv_contribution_kwh=energy_needed_kwh
        )
    
    def _create_hybrid_charging_decision(self, current_data: Dict[str, Any], price_data: Dict[str, Any],
                                       pv_forecasts: List[Dict], optimal_window: PriceWindow,
                                       energy_needed_kwh: float) -> ChargingDecision:
        """Create hybrid charging decision (PV + Grid)"""
        logger.info("Creating hybrid charging decision")
        
        # Calculate PV contribution during optimal window
        pv_contribution_kwh = self._calculate_pv_contribution(pv_forecasts, optimal_window)
        grid_contribution_kwh = max(0.0, energy_needed_kwh - pv_contribution_kwh)
        
        # Calculate charging time (limited by optimal window duration)
        charging_time_hours = min(
            optimal_window.duration_hours,
            energy_needed_kwh / self.charging_rate_kw
        )
        
        # Calculate costs
        current_price = self._get_current_price(price_data)
        grid_cost_pln = grid_contribution_kwh * (current_price / 1000.0) / self.grid_charging_efficiency
        
        # Calculate savings
        reference_cost_pln = energy_needed_kwh * (400.0 / 1000.0)  # Reference price 400 PLN/MWh
        estimated_savings_pln = reference_cost_pln - grid_cost_pln
        
        return ChargingDecision(
            action='start_hybrid_charging',
            charging_source='hybrid',
            duration_hours=charging_time_hours,
            energy_kwh=energy_needed_kwh,
            estimated_cost_pln=grid_cost_pln,
            estimated_savings_pln=estimated_savings_pln,
            confidence=0.9,
            reason=f'Low price window ({optimal_window.duration_hours:.1f}h) shorter than PV charging time, using hybrid approach',
            start_time=optimal_window.start_time,
            end_time=optimal_window.end_time,
            pv_contribution_kwh=pv_contribution_kwh,
            grid_contribution_kwh=grid_contribution_kwh
        )
    
    def _create_wait_decision(self, reason: str) -> ChargingDecision:
        """Create wait decision"""
        return ChargingDecision(
            action='wait',
            charging_source='none',
            duration_hours=0.0,
            energy_kwh=0.0,
            estimated_cost_pln=0.0,
            estimated_savings_pln=0.0,
            confidence=0.8,
            reason=reason,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
    
    def _calculate_pv_contribution(self, pv_forecasts: List[Dict], optimal_window: PriceWindow) -> float:
        """Calculate PV energy contribution during optimal window"""
        pv_contribution_kwh = 0.0
        
        for forecast in pv_forecasts:
            forecast_time = datetime.fromisoformat(forecast['timestamp'])
            
            if optimal_window.start_time <= forecast_time < optimal_window.end_time:
                pv_power_kw = forecast['forecasted_power_kw']
                # Assume 80% available for charging (20% for house consumption)
                available_for_charging = pv_power_kw * 0.8
                # Add 1 hour of energy (since forecasts are hourly)
                pv_contribution_kwh += available_for_charging * 1.0
        
        return pv_contribution_kwh
    
    def _calculate_pv_savings(self, optimal_window: PriceWindow, energy_kwh: float) -> float:
        """Calculate savings from PV charging during optimal window"""
        # Calculate what it would cost to charge from grid at optimal window price
        grid_cost_pln = energy_kwh * (optimal_window.avg_price_pln / 1000.0)
        
        # PV charging is free, so this is the savings
        return grid_cost_pln
    
    def _get_current_price(self, price_data: Dict[str, Any]) -> float:
        """Get current electricity price"""
        try:
            current_time = datetime.now()
            for item in price_data['value']:
                item_time = datetime.strptime(item['dtime'], '%Y-%m-%d %H:%M')
                if item_time <= current_time < item_time + timedelta(minutes=15):
                    market_price = float(item['csdac_pln'])
                    return market_price + 0.0892  # Add SC component
            return 400.0  # Default price if not found
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 400.0
    
    def _create_price_window_from_data(self, window_data: Dict[str, Any]) -> PriceWindow:
        """Create PriceWindow object from analysis data"""
        return PriceWindow(
            start_time=datetime.fromisoformat(window_data['start_time']),
            end_time=datetime.fromisoformat(window_data['end_time']),
            duration_hours=window_data['duration_hours'],
            avg_price_pln=window_data['avg_price_pln'],
            min_price_pln=window_data['avg_price_pln'],  # Simplified
            max_price_pln=window_data['avg_price_pln'],  # Simplified
            price_category='low',  # Simplified
            savings_potential_pln=window_data['savings_potential_pln']
        )
    
    def save_decision_data(self, decision: ChargingDecision, filename: str = None):
        """Save charging decision data to file"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"charging_decision_{timestamp}.json"
        
        decision_data = {
            'timestamp': datetime.now().isoformat(),
            'action': decision.action,
            'charging_source': decision.charging_source,
            'duration_hours': decision.duration_hours,
            'energy_kwh': decision.energy_kwh,
            'estimated_cost_pln': decision.estimated_cost_pln,
            'estimated_savings_pln': decision.estimated_savings_pln,
            'confidence': decision.confidence,
            'reason': decision.reason,
            'start_time': decision.start_time.isoformat(),
            'end_time': decision.end_time.isoformat(),
            'pv_contribution_kwh': decision.pv_contribution_kwh,
            'grid_contribution_kwh': decision.grid_contribution_kwh
        }
        
        try:
            data_dir = Path(self.config.get('data_directory', 'out/energy_data'))
            data_dir.mkdir(exist_ok=True)
            filepath = data_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(decision_data, f, indent=2)
            logger.info(f"Saved charging decision data to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save decision data: {e}")


def create_hybrid_charging_logic(config: Dict[str, Any]) -> HybridChargingLogic:
    """Create a hybrid charging logic instance"""
    return HybridChargingLogic(config)