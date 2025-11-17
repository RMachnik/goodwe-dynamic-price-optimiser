#!/usr/bin/env python3
"""
Comprehensive Test Suite for Battery Energy Selling Functionality

This test suite covers all aspects of battery energy selling including:
- Decision engine logic
- Safety monitoring
- GoodWe integration
- Revenue tracking
- Performance analytics

Run with: python -m pytest test/test_battery_selling.py -v
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import sys

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from battery_selling_engine import BatterySellingEngine, SellingDecision, SellingOpportunity
from battery_selling_monitor import BatterySellingMonitor, SafetyStatus, SafetyCheck


class TestBatterySellingEngine:
    """Test battery selling decision engine"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'battery_selling': {
                'enabled': True,
                'min_selling_price_pln': 0.50,
                'min_battery_soc': 80.0,
                'safety_margin_soc': 50.0,
                'max_daily_cycles': 2,
                'peak_hours': [17, 18, 19, 20, 21],
                'grid_export_limit_w': 5000,
                'battery_dod_limit': 50
            }
        }
    
    @pytest.fixture
    def engine(self, config):
        """Battery selling engine instance"""
        return BatterySellingEngine(config)
    
    def test_initialization(self, engine):
        """Test engine initialization"""
        assert engine.min_selling_soc == 80.0
        assert engine.safety_margin_soc == 50.0
        assert engine.min_selling_price_pln == 0.50
        assert engine.max_daily_cycles == 2
        assert engine.battery_capacity_kwh == 20.0
        assert engine.usable_energy_per_cycle == 6.0  # 30% of 20kWh
        assert engine.net_sellable_energy == 5.7  # 6.0 * 0.95 efficiency
    
    def test_safety_conditions_check(self, engine):
        """Test safety conditions checking"""
        # Test safe conditions
        safe_data = {
            'battery': {'soc_percent': 85, 'temperature': 25},
            'grid': {'voltage': 230}
        }
        
        # Mock day time to avoid night time check
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # 2 PM
            is_safe, reason = engine._check_safety_conditions(safe_data)
            assert is_safe
            assert "All safety conditions passed" in reason
        
        # Test SOC too low
        low_soc_data = {
            'battery': {'soc_percent': 45, 'temperature': 25},
            'grid': {'voltage': 230}
        }
        is_safe, reason = engine._check_safety_conditions(low_soc_data)
        assert not is_safe
        assert "below safety margin" in reason
        
        # Test temperature too high
        high_temp_data = {
            'battery': {'soc_percent': 85, 'temperature': 55},
            'grid': {'voltage': 230}
        }
        is_safe, reason = engine._check_safety_conditions(high_temp_data)
        assert not is_safe
        assert "temperature" in reason and "too high" in reason
        
        # Test grid voltage out of range
        bad_voltage_data = {
            'battery': {'soc_percent': 85, 'temperature': 25},
            'grid': {'voltage': 180}
        }
        is_safe, reason = engine._check_safety_conditions(bad_voltage_data)
        assert not is_safe
        assert "Grid voltage" in reason
    
    def test_night_time_check(self, engine):
        """Test night time detection"""
        # Mock night hour
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 23  # 11 PM
            assert engine._is_night_time()
            
            mock_datetime.now.return_value.hour = 14  # 2 PM
            assert not engine._is_night_time()
    
    def test_peak_hour_check(self, engine):
        """Test peak hour detection"""
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 18  # 6 PM (peak hour)
            assert engine._is_peak_hour()
            
            mock_datetime.now.return_value.hour = 10  # 10 AM (not peak)
            assert not engine._is_peak_hour()
    
    def test_revenue_calculation(self, engine):
        """Test revenue calculation"""
        revenue = engine._calculate_expected_revenue(0.60, 2.0)  # 0.60 PLN/kWh, 2 hours
        expected = 5.0 * 2.0 * 0.95 * 0.60  # 5kW * 2h * 0.95 efficiency * 0.60 PLN/kWh
        assert abs(revenue - expected) < 0.01
    
    def test_confidence_calculation(self, engine):
        """Test confidence score calculation"""
        # High confidence scenario
        confidence = engine._calculate_confidence(90, 0.80, 1500)
        assert confidence > 0.7
        
        # Low confidence scenario
        confidence = engine._calculate_confidence(60, 0.30, 200)
        assert confidence < 0.5
    
    def test_risk_assessment(self, engine):
        """Test risk level assessment"""
        # Low risk
        risk = engine._assess_risk_level(90, 0.80, 1.0)
        assert risk == "low"
        
        # High risk
        risk = engine._assess_risk_level(70, 0.30, 5.0)
        assert risk == "high"
    
    @pytest.mark.asyncio
    async def test_selling_opportunity_analysis(self, engine):
        """Test selling opportunity analysis"""
        # Good selling opportunity
        current_data = {
            'battery': {'soc_percent': 90, 'temperature': 25},  # Higher SOC for better confidence
            'pv': {'power_w': 500},  # Lower PV for higher deficit
            'consumption': {'power_w': 3000},  # Higher consumption for higher deficit
            'grid': {'voltage': 230}  # Add grid voltage for safety check
        }
        price_data = {'current_price_pln': 0.80}  # Higher price for better confidence
        
        # Mock day time to avoid night time check
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # 2 PM
            opportunity = await engine.analyze_selling_opportunity(current_data, price_data)
            
            assert opportunity.decision == SellingDecision.START_SELLING
            assert opportunity.safety_checks_passed
            assert opportunity.expected_revenue_pln > 0
            assert opportunity.selling_power_w > 0
        
        # Poor selling opportunity (low SOC)
        current_data['battery']['soc_percent'] = 70
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # 2 PM
            opportunity = await engine.analyze_selling_opportunity(current_data, price_data)
            
            assert opportunity.decision == SellingDecision.WAIT
            # Phase 2: Updated to match new dynamic threshold messaging
            assert "below" in opportunity.reasoning and "threshold" in opportunity.reasoning
        
        # Poor selling opportunity (low price)
        current_data['battery']['soc_percent'] = 85
        price_data['current_price_pln'] = 0.30
        with patch('battery_selling_engine.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # 2 PM
            opportunity = await engine.analyze_selling_opportunity(current_data, price_data)
            
            assert opportunity.decision == SellingDecision.WAIT
            assert "below minimum" in opportunity.reasoning
    
    def test_daily_cycle_reset(self, engine):
        """Test daily cycle counter reset"""
        # Set some cycles
        engine.daily_cycles = 2
        engine.last_cycle_reset = datetime.now().date()
        
        # Same day - no reset
        engine._reset_daily_cycles()
        assert engine.daily_cycles == 2
        
        # Next day - reset
        engine.last_cycle_reset = datetime.now().date() - timedelta(days=1)
        engine._reset_daily_cycles()
        assert engine.daily_cycles == 0
    
    def test_selling_status(self, engine):
        """Test selling status reporting"""
        status = engine.get_selling_status()
        
        assert 'active_sessions' in status
        assert 'daily_cycles' in status
        assert 'configuration' in status
        assert status['active_sessions'] == 0
        assert status['daily_cycles'] == 0
    
    def test_revenue_estimate(self, engine):
        """Test revenue estimation"""
        estimate = engine.get_revenue_estimate()
        
        assert 'daily_revenue_pln' in estimate
        assert 'monthly_revenue_pln' in estimate
        assert 'annual_revenue_pln' in estimate
        assert estimate['annual_revenue_pln'] > 0


class TestBatterySellingMonitor:
    """Test battery selling safety monitor"""
    
    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'battery_selling': {
                'safety_checks': {
                    'battery_temp_max': 50.0,
                    'battery_temp_min': -20.0,
                    'grid_voltage_min': 200.0,
                    'grid_voltage_max': 250.0,
                    'night_hours': [22, 23, 0, 1, 2, 3, 4, 5]
                }
            }
        }
    
    @pytest.fixture
    def monitor(self, config):
        """Battery selling monitor instance"""
        return BatterySellingMonitor(config)
    
    def test_initialization(self, monitor):
        """Test monitor initialization"""
        assert monitor.battery_temp_max == 50.0
        assert monitor.battery_temp_min == -20.0
        assert monitor.grid_voltage_min == 200.0
        assert monitor.grid_voltage_max == 250.0
        assert len(monitor.night_hours) == 8
    
    def test_battery_temperature_check(self, monitor):
        """Test battery temperature safety check"""
        # Safe temperature
        check = monitor._check_battery_temperature(25.0)
        assert check.status == SafetyStatus.SAFE
        
        # Warning temperature
        check = monitor._check_battery_temperature(47.0)
        assert check.status == SafetyStatus.WARNING
        
        # Critical temperature
        check = monitor._check_battery_temperature(55.0)
        assert check.status == SafetyStatus.EMERGENCY
        
        # Too cold
        check = monitor._check_battery_temperature(-25.0)
        assert check.status == SafetyStatus.EMERGENCY
    
    def test_battery_soc_check(self, monitor):
        """Test battery SOC safety check"""
        # Safe SOC
        check = monitor._check_battery_soc(85.0)
        assert check.status == SafetyStatus.SAFE
        
        # Warning SOC
        check = monitor._check_battery_soc(75.0)
        assert check.status == SafetyStatus.WARNING
        
        # Critical SOC
        check = monitor._check_battery_soc(45.0)
        assert check.status == SafetyStatus.EMERGENCY
    
    def test_grid_voltage_check(self, monitor):
        """Test grid voltage safety check"""
        # Safe voltage
        check = monitor._check_grid_voltage(230.0)
        assert check.status == SafetyStatus.SAFE
        
        # Critical voltage (too low)
        check = monitor._check_grid_voltage(180.0)
        assert check.status == SafetyStatus.EMERGENCY
        
        # Critical voltage (too high)
        check = monitor._check_grid_voltage(260.0)
        assert check.status == SafetyStatus.EMERGENCY
    
    def test_night_time_check(self, monitor):
        """Test night time detection"""
        with patch('battery_selling_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 23  # Night hour
            check = monitor._check_night_time()
            assert check.status == SafetyStatus.WARNING
            
            mock_datetime.now.return_value.hour = 14  # Day hour
            check = monitor._check_night_time()
            assert check.status == SafetyStatus.SAFE
    
    def test_inverter_errors_check(self, monitor):
        """Test inverter error detection"""
        # No errors
        check = monitor._check_inverter_errors({'error_codes': []})
        assert check.status == SafetyStatus.SAFE
        
        # With errors
        check = monitor._check_inverter_errors({'error_codes': ['E001', 'E002']})
        assert check.status == SafetyStatus.EMERGENCY
    
    def test_battery_health_check(self, monitor):
        """Test battery health check"""
        # Healthy battery
        check = monitor._check_battery_health({'voltage': 400})
        assert check.status == SafetyStatus.SAFE
        
        # Unhealthy battery
        check = monitor._check_battery_health({'voltage': 300})
        assert check.status == SafetyStatus.WARNING
    
    @pytest.mark.asyncio
    async def test_safety_conditions_check(self, monitor):
        """Test comprehensive safety check"""
        # Mock inverter
        mock_inverter = Mock()
        
        # Safe conditions
        current_data = {
            'battery': {'soc_percent': 85, 'temperature': 25, 'voltage': 400},
            'grid': {'voltage': 230},
            'inverter': {'error_codes': []}
        }
        
        # Mock day time to avoid night time warning
        with patch('battery_selling_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value.hour = 14  # 2 PM
            report = await monitor.check_safety_conditions(mock_inverter, current_data)
            
            assert report.overall_status == SafetyStatus.SAFE
            assert not report.emergency_stop_required
            assert len(report.checks) > 0
        
        # Emergency conditions
        current_data['battery']['temperature'] = 55
        report = await monitor.check_safety_conditions(mock_inverter, current_data)
        
        assert report.overall_status == SafetyStatus.EMERGENCY
        assert report.emergency_stop_required
    
    def test_safety_status(self, monitor):
        """Test safety status reporting"""
        status = monitor.get_safety_status()
        
        assert 'last_check' in status
        assert 'overall_status' in status
        assert 'statistics' in status
        assert 'configuration' in status


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
