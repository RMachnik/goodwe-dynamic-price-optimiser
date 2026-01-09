#!/usr/bin/env python3
"""
Integration tests for the master coordinator
Tests the complete flow from data collection to decision execution
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock, Mock
from datetime import datetime, timedelta
import sys
import os
import asyncio
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MasterCoordinator, SystemState


class TestMasterCoordinatorIntegration(unittest.TestCase):
    """Integration tests for the master coordinator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_interval_minutes': 15,
                'health_check_interval_minutes': 5,
                'emergency_stop_conditions': {
                    'battery_temp_max': 60.0,
                    'battery_voltage_min': 320.0,
                    'battery_voltage_max': 480.0
                }
            },
            'battery_management': {
                'voltage_range': {'min': 320.0, 'max': 480.0},
                'temperature_thresholds': {'charging_min': 0.0, 'charging_max': 53.0},
                'battery_type': 'LFP'
            }
        }
        
        # Mock price data
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-06 12:00',
                    'csdac_pln': 200.0,
                    'business_date': '2025-09-06'
                }
            ]
        }
        
        # Mock current data
        self.mock_current_data = {
            'battery': {
                'soc_percent': 25,
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 500
            },
            'house_consumption': {
                'current_power_w': 1500
            }
        }
    
    @patch('master_coordinator.EnhancedDataCollector')
    @patch('master_coordinator.AutomatedPriceCharger')
    @patch('master_coordinator.PolishElectricityAnalyzer')
    @pytest.mark.asyncio
    async def test_initialization_success(self, mock_analyzer, mock_charger, mock_collector):
        """Test successful initialization of master coordinator"""
        # Mock successful initialization
        mock_collector_instance = AsyncMock()
        mock_collector_instance.initialize.return_value = True
        mock_collector.return_value = mock_collector_instance
        
        mock_charger_instance = AsyncMock()
        mock_charger_instance.initialize.return_value = True
        mock_charger.return_value = mock_charger_instance
        
        mock_analyzer.return_value = MagicMock()
        
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        result = await coordinator.initialize()
        
        self.assertTrue(result)
        self.assertEqual(coordinator.state, SystemState.MONITORING)
    
    @patch('master_coordinator.EnhancedDataCollector')
    @patch('master_coordinator.AutomatedPriceCharger')
    @patch('master_coordinator.PolishElectricityAnalyzer')
    @pytest.mark.asyncio
    async def test_initialization_failure_data_collector(self, mock_analyzer, mock_charger, mock_collector):
        """Test initialization failure when data collector fails"""
        # Mock data collector failure
        mock_collector_instance = AsyncMock()
        mock_collector_instance.initialize.return_value = False
        mock_collector.return_value = mock_collector_instance
        
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        result = await coordinator.initialize()
        
        self.assertFalse(result)
        self.assertEqual(coordinator.state, SystemState.ERROR)
    
    @patch('master_coordinator.EnhancedDataCollector')
    @patch('master_coordinator.AutomatedPriceCharger')
    @patch('master_coordinator.PolishElectricityAnalyzer')
    @pytest.mark.asyncio
    async def test_initialization_failure_charging_controller(self, mock_analyzer, mock_charger, mock_collector):
        """Test initialization failure when charging controller fails"""
        # Mock data collector success, charging controller failure
        mock_collector_instance = AsyncMock()
        mock_collector_instance.initialize.return_value = True
        mock_collector.return_value = mock_collector_instance
        
        mock_charger_instance = AsyncMock()
        mock_charger_instance.initialize.return_value = False
        mock_charger.return_value = mock_charger_instance
        
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        result = await coordinator.initialize()
        
        self.assertFalse(result)
        self.assertEqual(coordinator.state, SystemState.ERROR)
    
    def test_should_make_decision_timing(self):
        """Test decision timing logic"""
        coordinator = MasterCoordinator()
        coordinator.decision_interval = 900  # 15 minutes
        
        # First decision should be made immediately
        self.assertTrue(coordinator._should_make_decision())
        
        # Set last decision time to 10 minutes ago
        coordinator.last_decision_time = datetime.now() - timedelta(minutes=10)
        self.assertFalse(coordinator._should_make_decision())
        
        # Set last decision time to 20 minutes ago
        coordinator.last_decision_time = datetime.now() - timedelta(minutes=20)
        self.assertTrue(coordinator._should_make_decision())
    
    @patch('master_coordinator.MultiFactorDecisionEngine')
    @pytest.mark.asyncio
    async def test_make_charging_decision_success(self, mock_decision_engine):
        """Test successful charging decision making"""
        # Mock decision engine
        mock_engine_instance = MagicMock()
        mock_engine_instance.analyze_and_decide.return_value = {
            'action': 'start_charging',
            'total_score': 75,
            'scores': {'price': 80, 'battery': 70, 'pv': 60, 'consumption': 50},
            'confidence': 85,
            'reasoning': 'Low prices and battery level',
            'price_data': self.mock_price_data
        }
        mock_decision_engine.return_value = mock_engine_instance
        
        # Mock charging controller
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        coordinator.decision_engine = mock_engine_instance
        coordinator.current_data = self.mock_current_data
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.fetch_today_prices.return_value = self.mock_price_data
        coordinator.charging_controller.start_price_based_charging = AsyncMock(return_value=True)
        
        await coordinator._make_charging_decision()
        
        # Verify decision was made and executed
        mock_engine_instance.analyze_and_decide.assert_called_once()
        coordinator.charging_controller.start_price_based_charging.assert_called_once()
        self.assertEqual(len(coordinator.decision_history), 1)
    
    @patch('master_coordinator.MultiFactorDecisionEngine')
    @pytest.mark.asyncio
    async def test_make_charging_decision_no_price_data(self, mock_decision_engine):
        """Test charging decision when no price data is available"""
        # Mock decision engine
        mock_engine_instance = MagicMock()
        mock_decision_engine.return_value = mock_engine_instance
        
        # Mock charging controller with no price data
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        coordinator.decision_engine = mock_engine_instance
        coordinator.current_data = self.mock_current_data
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.fetch_today_prices.return_value = None
        
        await coordinator._make_charging_decision()
        
        # Verify decision engine was not called
        mock_engine_instance.analyze_and_decide.assert_not_called()
        self.assertEqual(len(coordinator.decision_history), 0)
    
    def test_emergency_conditions_battery_temperature(self):
        """Test emergency conditions for battery temperature"""
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        # Test high temperature
        high_temp_data = self.mock_current_data.copy()
        high_temp_data['battery']['temperature'] = 65.0  # Above max (60.0)
        
        coordinator.current_data = high_temp_data
        result = coordinator._check_emergency_conditions()
        
        self.assertTrue(result)
        
        # Test normal temperature
        normal_temp_data = self.mock_current_data.copy()
        normal_temp_data['battery']['temperature'] = 30.0  # Normal
        
        coordinator.current_data = normal_temp_data
        result = coordinator._check_emergency_conditions()
        
        self.assertFalse(result)
    
    def test_emergency_conditions_battery_voltage(self):
        """Test emergency conditions for battery voltage"""
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        # Test low voltage
        low_voltage_data = self.mock_current_data.copy()
        low_voltage_data['battery']['voltage'] = 300.0  # Below min (320.0)
        
        coordinator.current_data = low_voltage_data
        result = coordinator._check_emergency_conditions()
        
        self.assertTrue(result)
        
        # Test high voltage
        high_voltage_data = self.mock_current_data.copy()
        high_voltage_data['battery']['voltage'] = 500.0  # Above max (480.0)
        
        coordinator.current_data = high_voltage_data
        result = coordinator._check_emergency_conditions()
        
        self.assertTrue(result)
        
        # Test normal voltage
        normal_voltage_data = self.mock_current_data.copy()
        normal_voltage_data['battery']['voltage'] = 400.0  # Normal
        
        coordinator.current_data = normal_voltage_data
        result = coordinator._check_emergency_conditions()
        
        self.assertFalse(result)
    
    def test_goodwe_lynx_d_compliance_check(self):
        """Test GoodWe Lynx-D compliance checking"""
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        coordinator.current_data = self.mock_current_data
        
        compliance = coordinator._check_goodwe_lynx_d_compliance()
        
        # Should be compliant with normal data
        self.assertTrue(compliance['compliant'])
        self.assertEqual(len(compliance['issues']), 0)
        
        # Test non-compliant voltage
        non_compliant_data = self.mock_current_data.copy()
        non_compliant_data['battery']['voltage'] = 300.0  # Below range
        
        coordinator.current_data = non_compliant_data
        compliance = coordinator._check_goodwe_lynx_d_compliance()
        
        self.assertFalse(compliance['compliant'])
        self.assertGreater(len(compliance['issues']), 0)
    
    @pytest.mark.asyncio
    async def test_system_state_update_charging(self):
        """Test system state update when charging"""
        coordinator = MasterCoordinator()
        coordinator.current_data = self.mock_current_data.copy()
        coordinator.current_data['charging'] = {'is_charging': True}
        
        await coordinator._update_system_state()
        
        self.assertEqual(coordinator.state, SystemState.CHARGING)
    
    @pytest.mark.asyncio
    async def test_system_state_update_monitoring(self):
        """Test system state update when not charging"""
        coordinator = MasterCoordinator()
        coordinator.current_data = self.mock_current_data.copy()
        coordinator.current_data['charging'] = {'is_charging': False}
        
        await coordinator._update_system_state()
        
        self.assertEqual(coordinator.state, SystemState.MONITORING)
    
    def test_log_system_status(self):
        """Test system status logging"""
        coordinator = MasterCoordinator()
        coordinator.current_data = self.mock_current_data
        coordinator.state = SystemState.MONITORING
        
        # This should not raise an exception
        coordinator._log_system_status()
    
    def test_get_status(self):
        """Test getting system status"""
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        coordinator.current_data = self.mock_current_data
        coordinator.state = SystemState.MONITORING
        coordinator.is_running = True
        coordinator.start_time = datetime.now() - timedelta(hours=1)
        
        status = coordinator.get_status()
        
        self.assertIn('state', status)
        self.assertIn('is_running', status)
        self.assertIn('uptime_seconds', status)
        self.assertIn('current_data', status)
        self.assertIn('goodwe_lynx_d_compliance', status)
        self.assertIn('safety_status', status)
        
        self.assertEqual(status['state'], 'monitoring')
        self.assertTrue(status['is_running'])
        self.assertGreater(status['uptime_seconds'], 0)


class TestMasterCoordinatorAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for master coordinator"""
    
    @pytest.mark.asyncio
    async def test_emergency_stop(self):
        """Test emergency stop functionality"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.current_data = {'battery': {'voltage': 300.0}}  # Low voltage
        
        await coordinator._emergency_stop()
        
        # Verify charging was stopped
        coordinator.charging_controller.stop_price_based_charging.assert_called_once()
        self.assertEqual(coordinator.state, SystemState.ERROR)
    
    @pytest.mark.asyncio
    async def test_execute_decision_start_charging(self):
        """Test executing start charging decision"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.start_price_based_charging = AsyncMock(return_value=True)
        coordinator.current_data = {'battery': {'soc_percent': 15}}  # Critical battery level
        
        decision = {
            'should_charge': True,
            'reason': 'Test charging decision',
            'priority': 'medium'
        }
        
        await coordinator._execute_smart_decision(decision)
        
        # Verify charging was started with force_start=True (critical battery)
        coordinator.charging_controller.start_price_based_charging.assert_called_once()
        call_args = coordinator.charging_controller.start_price_based_charging.call_args
        self.assertTrue(call_args[1]['force_start'])  # force_start=True
    
    @pytest.mark.asyncio
    async def test_execute_decision_stop_charging(self):
        """Test executing stop charging decision"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.stop_price_based_charging = AsyncMock(return_value=True)
        coordinator.charging_controller.is_charging = True
        # Mock is_charging_session_protected to return False (not protected)
        coordinator.charging_controller.is_charging_session_protected = Mock(return_value=False)
        
        decision = {
            'should_charge': False,
            'reason': 'Test stop charging decision',
            'priority': 'medium'
        }
        
        await coordinator._execute_smart_decision(decision)
        
        # Verify charging was stopped
        coordinator.charging_controller.stop_price_based_charging.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_decision_continue_charging(self):
        """Test executing continue charging decision"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.is_charging = True
        
        decision = {
            'should_charge': True,
            'reason': 'Continue charging',
            'priority': 'medium',
            'price_data': {}
        }
        
        await coordinator._execute_smart_decision(decision)
        
        # Verify charging was started (continue charging means start charging)
        coordinator.charging_controller.start_price_based_charging.assert_called_once_with({}, force_start=True)
        coordinator.charging_controller.stop_price_based_charging.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_decision_no_action(self):
        """Test executing no action decision"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.is_charging = False
        
        decision = {
            'should_charge': False,
            'reason': 'No action needed',
            'priority': 'low'
        }
        
        await coordinator._execute_smart_decision(decision)
        
        # Verify no action was taken
        coordinator.charging_controller.start_price_based_charging.assert_not_called()
        coordinator.charging_controller.stop_price_based_charging.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_decision_stop_charging_protected_session(self):
        """Test that protected charging session is not stopped"""
        coordinator = MasterCoordinator()
        coordinator.charging_controller = AsyncMock()
        coordinator.charging_controller.stop_price_based_charging = AsyncMock(return_value=True)
        coordinator.charging_controller.is_charging = True
        # Mock is_charging_session_protected to return True (protected)
        coordinator.charging_controller.is_charging_session_protected = Mock(return_value=True)
        
        decision = {
            'should_charge': False,
            'reason': 'Test stop charging decision during protected session',
            'priority': 'medium'
        }
        
        await coordinator._execute_smart_decision(decision)
        
        # Verify charging was NOT stopped (session is protected)
        coordinator.charging_controller.stop_price_based_charging.assert_not_called()


if __name__ == '__main__':
    unittest.main()
