#!/usr/bin/env python3
"""
Test suite for Multi-Session Charging functionality
Tests the MultiSessionManager and integration with Master Coordinator
"""

import unittest
import asyncio
import json
import tempfile
import shutil
from datetime import datetime, timedelta, time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from multi_session_manager import MultiSessionManager, ChargingSession, DailyChargingPlan
from polish_electricity_analyzer import ChargingWindow

class TestMultiSessionManager(unittest.TestCase):
    """Test cases for MultiSessionManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'multi_session_charging': {
                    'enabled': True,
                    'max_sessions_per_day': 3,
                    'min_session_duration_hours': 1.0,
                    'max_session_duration_hours': 4.0,
                    'min_savings_percent': 15.0,
                    'session_gap_minutes': 30,
                    'daily_planning_time': '06:00'
                }
            }
        }
        
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_dir = None
        
        # Mock the data directory
        with patch('multi_session_manager.Path') as mock_path:
            mock_path.return_value.mkdir = Mock()
            self.manager = MultiSessionManager(self.config)
            self.manager.data_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test MultiSessionManager initialization"""
        self.assertTrue(self.manager.enabled)
        self.assertEqual(self.manager.max_sessions_per_day, 3)
        self.assertEqual(self.manager.min_session_duration_hours, 1.0)
        self.assertEqual(self.manager.max_session_duration_hours, 4.0)
        self.assertEqual(self.manager.min_savings_percent, 15.0)
        self.assertEqual(self.manager.session_gap_minutes, 30)
        self.assertEqual(self.manager.daily_planning_time, '06:00')
        self.assertIsNone(self.manager.current_plan)
        self.assertIsNone(self.manager.active_session)
    
    def test_initialization_disabled(self):
        """Test MultiSessionManager initialization when disabled"""
        config_disabled = {
            'coordinator': {
                'multi_session_charging': {
                    'enabled': False
                }
            }
        }
        
        with patch('multi_session_manager.Path') as mock_path:
            mock_path.return_value.mkdir = Mock()
            manager = MultiSessionManager(config_disabled)
            self.assertFalse(manager.enabled)
    
    @patch('multi_session_manager.PolishElectricityAnalyzer')
    async def test_create_daily_plan_success(self, mock_analyzer_class):
        """Test successful daily plan creation"""
        # Mock price analyzer
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        # Mock charging windows
        mock_windows = [
            ChargingWindow(
                start_time=datetime(2024, 1, 1, 6, 0),
                end_time=datetime(2024, 1, 1, 8, 0),
                duration_minutes=120,
                avg_price=200.0,
                total_cost_per_mwh=200.0,
                savings_per_mwh=50.0
            ),
            ChargingWindow(
                start_time=datetime(2024, 1, 1, 22, 0),
                end_time=datetime(2024, 1, 1, 24, 0),
                duration_minutes=120,
                avg_price=150.0,
                total_cost_per_mwh=150.0,
                savings_per_mwh=100.0
            )
        ]
        mock_analyzer.get_daily_charging_schedule.return_value = mock_windows
        
        # Mock price data fetching
        mock_analyzer.fetch_price_data = AsyncMock(return_value={'prices': []})
        
        # Create plan
        date = datetime(2024, 1, 1).date()
        plan = await self.manager.create_daily_plan(date)
        
        # Verify plan creation
        self.assertIsNotNone(plan)
        self.assertEqual(plan.date, date)
        self.assertEqual(plan.total_sessions, 2)
        self.assertEqual(len(plan.sessions), 2)
        self.assertEqual(plan.status, 'planned')
        
        # Verify sessions
        self.assertEqual(plan.sessions[0].session_id, '20240101_1')
        self.assertEqual(plan.sessions[0].status, 'planned')
        self.assertEqual(plan.sessions[0].priority, 1)
        self.assertEqual(plan.sessions[1].session_id, '20240101_2')
        self.assertEqual(plan.sessions[1].priority, 2)
    
    @patch('multi_session_manager.PolishElectricityAnalyzer')
    async def test_create_daily_plan_no_windows(self, mock_analyzer_class):
        """Test daily plan creation when no optimal windows found"""
        # Mock price analyzer
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.get_daily_charging_schedule.return_value = []
        mock_analyzer.fetch_price_data = AsyncMock(return_value={'prices': []})
        
        # Create plan
        date = datetime(2024, 1, 1).date()
        plan = await self.manager.create_daily_plan(date)
        
        # Verify no plan created
        self.assertIsNone(plan)
    
    @patch('multi_session_manager.PolishElectricityAnalyzer')
    async def test_create_daily_plan_no_price_data(self, mock_analyzer_class):
        """Test daily plan creation when no price data available"""
        # Mock price analyzer
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        mock_analyzer.fetch_price_data = AsyncMock(return_value=None)
        
        # Create plan
        date = datetime(2024, 1, 1).date()
        plan = await self.manager.create_daily_plan(date)
        
        # Verify no plan created
        self.assertIsNone(plan)
    
    async def test_get_next_session_no_plan(self):
        """Test getting next session when no plan exists"""
        session = await self.manager.get_next_session()
        self.assertIsNone(session)
    
    async def test_get_next_session_with_plan(self):
        """Test getting next session with existing plan"""
        # Create mock plan with sessions
        now = datetime.now()
        future_time = now + timedelta(hours=1)
        
        session1 = ChargingSession(
            session_id='test_1',
            start_time=now - timedelta(hours=1),  # Past session
            end_time=now - timedelta(minutes=30),
            duration_hours=1.0,
            target_energy_kwh=3.0,
            status='completed',
            priority=1,
            estimated_cost_pln=0.6,
            estimated_savings_pln=0.15,
            created_at=now
        )
        
        session2 = ChargingSession(
            session_id='test_2',
            start_time=future_time,  # Future session
            end_time=future_time + timedelta(hours=2),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='planned',
            priority=2,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=now
        )
        
        plan = DailyChargingPlan(
            date=now.date(),
            total_sessions=2,
            total_duration_hours=3.0,
            total_estimated_energy_kwh=9.0,
            total_estimated_cost_pln=1.8,
            total_estimated_savings_pln=0.45,
            sessions=[session1, session2],
            created_at=now,
            status='planned'
        )
        
        self.manager.current_plan = plan
        
        # Get next session
        next_session = await self.manager.get_next_session()
        
        # Should return the future session
        self.assertIsNotNone(next_session)
        self.assertEqual(next_session.session_id, 'test_2')
    
    async def test_start_session(self):
        """Test starting a charging session"""
        session = ChargingSession(
            session_id='test_session',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='planned',
            priority=1,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=datetime.now()
        )
        
        # Start session
        result = await self.manager.start_session(session)
        
        # Verify session started
        self.assertTrue(result)
        self.assertEqual(session.status, 'active')
        self.assertIsNotNone(session.started_at)
        self.assertEqual(self.manager.active_session, session)
    
    async def test_complete_session(self):
        """Test completing a charging session"""
        session = ChargingSession(
            session_id='test_session',
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now(),
            duration_hours=1.0,
            target_energy_kwh=3.0,
            status='active',
            priority=1,
            estimated_cost_pln=0.6,
            estimated_savings_pln=0.15,
            created_at=datetime.now(),
            started_at=datetime.now() - timedelta(hours=1)
        )
        
        self.manager.active_session = session
        
        # Complete session
        result = await self.manager.complete_session(session, actual_energy_kwh=2.8, actual_cost_pln=0.55)
        
        # Verify session completed
        self.assertTrue(result)
        self.assertEqual(session.status, 'completed')
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(session.actual_energy_kwh, 2.8)
        self.assertEqual(session.actual_cost_pln, 0.55)
        self.assertIsNone(self.manager.active_session)
        self.assertIn(session, self.manager.session_history)
    
    async def test_cancel_session(self):
        """Test cancelling a charging session"""
        session = ChargingSession(
            session_id='test_session',
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='active',
            priority=1,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=datetime.now()
        )
        
        self.manager.active_session = session
        
        # Cancel session
        result = await self.manager.cancel_session(session, "Test cancellation")
        
        # Verify session cancelled
        self.assertTrue(result)
        self.assertEqual(session.status, 'cancelled')
        self.assertIsNotNone(session.completed_at)
        self.assertIsNone(self.manager.active_session)
    
    def test_get_current_plan_status_no_plan(self):
        """Test getting plan status when no plan exists"""
        status = self.manager.get_current_plan_status()
        
        self.assertFalse(status['has_plan'])
        self.assertEqual(status['status'], 'no_plan')
        self.assertIn('No daily charging plan available', status['message'])
    
    def test_get_current_plan_status_with_plan(self):
        """Test getting plan status with existing plan"""
        now = datetime.now()
        
        # Create mock sessions
        session1 = ChargingSession(
            session_id='test_1',
            start_time=now - timedelta(hours=1),
            end_time=now - timedelta(minutes=30),
            duration_hours=1.0,
            target_energy_kwh=3.0,
            status='completed',
            priority=1,
            estimated_cost_pln=0.6,
            estimated_savings_pln=0.15,
            created_at=now
        )
        
        session2 = ChargingSession(
            session_id='test_2',
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='active',
            priority=2,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=now
        )
        
        session3 = ChargingSession(
            session_id='test_3',
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=5),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='planned',
            priority=3,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=now
        )
        
        plan = DailyChargingPlan(
            date=now.date(),
            total_sessions=3,
            total_duration_hours=5.0,
            total_estimated_energy_kwh=15.0,
            total_estimated_cost_pln=3.0,
            total_estimated_savings_pln=0.75,
            sessions=[session1, session2, session3],
            created_at=now,
            status='active'
        )
        
        self.manager.current_plan = plan
        self.manager.active_session = session2
        
        # Get status
        status = self.manager.get_current_plan_status()
        
        # Verify status
        self.assertTrue(status['has_plan'])
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['total_sessions'], 3)
        self.assertEqual(status['completed_sessions'], 1)
        self.assertEqual(status['active_sessions'], 1)
        self.assertEqual(status['planned_sessions'], 1)
        self.assertEqual(status['total_estimated_savings_pln'], 0.75)
        
        # Verify active session info
        self.assertIsNotNone(status['active_session'])
        self.assertEqual(status['active_session']['session_id'], 'test_2')
        
        # Verify next session info
        self.assertIsNotNone(status['next_session'])
        self.assertEqual(status['next_session']['session_id'], 'test_3')
    
    def test_estimate_energy_for_session(self):
        """Test energy estimation for charging sessions"""
        # Test 1 hour session
        energy_1h = self.manager._estimate_energy_for_session(1.0)
        self.assertEqual(energy_1h, 3.0)  # 1 hour * 3kW = 3kWh
        
        # Test 2 hour session
        energy_2h = self.manager._estimate_energy_for_session(2.0)
        self.assertEqual(energy_2h, 6.0)  # 2 hours * 3kW = 6kWh
    
    def test_calculate_session_cost(self):
        """Test session cost calculation"""
        window = ChargingWindow(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_minutes=120,
            avg_price=200.0,
            total_cost_per_mwh=200.0,
            savings_per_mwh=50.0
        )
        
        cost = self.manager._calculate_session_cost(window)
        expected_cost = 6.0 * (200.0 / 1000.0)  # 6kWh * 0.2 PLN/kWh
        self.assertEqual(cost, expected_cost)
    
    def test_calculate_session_savings(self):
        """Test session savings calculation"""
        window = ChargingWindow(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_minutes=120,
            avg_price=200.0,
            total_cost_per_mwh=200.0,
            savings_per_mwh=50.0
        )
        
        savings = self.manager._calculate_session_savings(window)
        expected_savings = 6.0 * (50.0 / 1000.0)  # 6kWh * 0.05 PLN/kWh
        self.assertEqual(savings, expected_savings)


class TestMultiSessionIntegration(unittest.TestCase):
    """Test integration with Master Coordinator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'multi_session_charging': {
                    'enabled': True,
                    'max_sessions_per_day': 3,
                    'min_session_duration_hours': 1.0,
                    'max_session_duration_hours': 4.0,
                    'min_savings_percent': 15.0,
                    'session_gap_minutes': 30,
                    'daily_planning_time': '06:00'
                }
            }
        }
    
    @patch('master_coordinator.MultiSessionManager')
    @patch('master_coordinator.AutomatedPriceCharger')
    @patch('master_coordinator.EnhancedDataCollector')
    async def test_master_coordinator_multi_session_integration(self, mock_data_collector, mock_charger, mock_multi_session):
        """Test Master Coordinator integration with multi-session manager"""
        # Mock components
        mock_data_collector.return_value.initialize = AsyncMock(return_value=True)
        mock_charger.return_value.initialize = AsyncMock(return_value=True)
        mock_charger.return_value.is_charging = False
        mock_charger.return_value.fetch_price_data_for_date = Mock(return_value={'prices': []})
        mock_charger.return_value.make_smart_charging_decision = Mock(return_value={
            'should_charge': False,
            'reason': 'Test decision',
            'confidence': 0.8,
            'priority': 'low'
        })
        
        # Mock multi-session manager
        mock_multi_session.return_value.enabled = True
        mock_multi_session.return_value.current_plan = None
        mock_multi_session.return_value.active_session = None
        
        # Import and create coordinator
        from master_coordinator import MasterCoordinator
        
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        
        # Test initialization
        result = await coordinator.initialize()
        self.assertTrue(result)
        
        # Verify multi-session manager was initialized
        self.assertIsNotNone(coordinator.multi_session_manager)
    
    @patch('master_coordinator.MultiSessionManager')
    async def test_handle_multi_session_logic(self, mock_multi_session_class):
        """Test multi-session logic handling"""
        # Mock multi-session manager
        mock_manager = Mock()
        mock_multi_session_class.return_value = mock_manager
        mock_manager.enabled = True
        mock_manager.current_plan = None
        mock_manager.active_session = None
        mock_manager.daily_planning_time = '06:00'
        mock_manager.get_next_session = AsyncMock(return_value=None)
        mock_manager.create_daily_plan = AsyncMock()
        mock_manager.start_session = AsyncMock()
        mock_manager.complete_session = AsyncMock()
        
        # Mock charging controller
        mock_charger = Mock()
        mock_charger.is_charging = False
        mock_charger.fetch_price_data_for_date = Mock(return_value={'prices': []})
        mock_charger.start_price_based_charging = AsyncMock()
        mock_charger.stop_price_based_charging = AsyncMock()
        
        # Import and create coordinator
        from master_coordinator import MasterCoordinator
        
        coordinator = MasterCoordinator()
        coordinator.config = self.config
        coordinator.multi_session_manager = mock_manager
        coordinator.charging_controller = mock_charger
        
        # Test with current time at planning time
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 6, 0)
            mock_datetime.strftime = datetime.strftime
            
            await coordinator._handle_multi_session_logic()
            
            # Verify daily plan creation was called
            mock_manager.create_daily_plan.assert_called_once()


class TestChargingSession(unittest.TestCase):
    """Test ChargingSession dataclass"""
    
    def test_charging_session_creation(self):
        """Test ChargingSession creation"""
        now = datetime.now()
        session = ChargingSession(
            session_id='test_session',
            start_time=now,
            end_time=now + timedelta(hours=2),
            duration_hours=2.0,
            target_energy_kwh=6.0,
            status='planned',
            priority=1,
            estimated_cost_pln=1.2,
            estimated_savings_pln=0.3,
            created_at=now
        )
        
        self.assertEqual(session.session_id, 'test_session')
        self.assertEqual(session.duration_hours, 2.0)
        self.assertEqual(session.target_energy_kwh, 6.0)
        self.assertEqual(session.status, 'planned')
        self.assertEqual(session.priority, 1)
        self.assertEqual(session.estimated_cost_pln, 1.2)
        self.assertEqual(session.estimated_savings_pln, 0.3)
        self.assertIsNone(session.started_at)
        self.assertIsNone(session.completed_at)


class TestDailyChargingPlan(unittest.TestCase):
    """Test DailyChargingPlan dataclass"""
    
    def test_daily_plan_creation(self):
        """Test DailyChargingPlan creation"""
        now = datetime.now()
        sessions = [
            ChargingSession(
                session_id='test_1',
                start_time=now,
                end_time=now + timedelta(hours=2),
                duration_hours=2.0,
                target_energy_kwh=6.0,
                status='planned',
                priority=1,
                estimated_cost_pln=1.2,
                estimated_savings_pln=0.3,
                created_at=now
            )
        ]
        
        plan = DailyChargingPlan(
            date=now.date(),
            total_sessions=1,
            total_duration_hours=2.0,
            total_estimated_energy_kwh=6.0,
            total_estimated_cost_pln=1.2,
            total_estimated_savings_pln=0.3,
            sessions=sessions,
            created_at=now,
            status='planned'
        )
        
        self.assertEqual(plan.date, now.date())
        self.assertEqual(plan.total_sessions, 1)
        self.assertEqual(plan.total_duration_hours, 2.0)
        self.assertEqual(plan.total_estimated_energy_kwh, 6.0)
        self.assertEqual(plan.total_estimated_cost_pln, 1.2)
        self.assertEqual(plan.total_estimated_savings_pln, 0.3)
        self.assertEqual(len(plan.sessions), 1)
        self.assertEqual(plan.status, 'planned')


if __name__ == '__main__':
    # Run async tests
    async def run_async_tests():
        """Run async test methods"""
        test_suite = unittest.TestLoader().loadTestsFromTestCase(TestMultiSessionManager)
        test_suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestMultiSessionIntegration))
        test_suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestChargingSession))
        test_suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDailyChargingPlan))
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        return result.wasSuccessful()
    
    # Run the tests
    success = asyncio.run(run_async_tests())
    sys.exit(0 if success else 1)
