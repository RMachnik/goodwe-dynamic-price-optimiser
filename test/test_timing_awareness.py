#!/usr/bin/env python3
"""
Tests for timing-aware charging decisions
Verifies the critical scenario: Low price window + insufficient PV timing
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MultiFactorDecisionEngine
from pv_forecasting import PVForecaster
from price_window_analyzer import PriceWindowAnalyzer
from hybrid_charging_logic import HybridChargingLogic


class TestTimingAwareness(unittest.TestCase):
    """Test timing-aware charging decisions"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_interval_minutes': 15,
                'health_check_interval_minutes': 5
            },
            'timing_awareness_enabled': True,
            'pv_capacity_kw': 10.0,
            'charging_rate_kw': 3.0,
            'battery_capacity_kwh': 10.0,
            'target_battery_soc': 60.0,
            'critical_battery_threshold': 20.0,
            'low_battery_threshold': 40.0,
            'min_savings_threshold_pln': 50.0,
            'data_directory': 'out/energy_data'
        }
        
        self.decision_engine = MultiFactorDecisionEngine(self.config)
        
        # Mock current data
        self.mock_current_data = {
            'battery': {
                'soc_percent': 30,  # Low battery
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 2000,  # 2 kW current PV
                'current_power_kw': 2.0,
                'daily_production_kwh': 5.0
            },
            'house_consumption': {
                'current_power_w': 1500,  # 1.5 kW consumption
                'current_power_kw': 1.5,
                'daily_total_kwh': 12.0
            }
        }
        
        # Mock price data with low price window
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-07 11:00',
                    'csdac_pln': 150.0,  # Low price
                    'business_date': '2025-09-07'
                },
                {
                    'dtime': '2025-09-07 11:15',
                    'csdac_pln': 160.0,  # Low price
                    'business_date': '2025-09-07'
                },
                {
                    'dtime': '2025-09-07 11:30',
                    'csdac_pln': 170.0,  # Low price
                    'business_date': '2025-09-07'
                },
                {
                    'dtime': '2025-09-07 11:45',
                    'csdac_pln': 180.0,  # Low price
                    'business_date': '2025-09-07'
                },
                {
                    'dtime': '2025-09-07 12:00',
                    'csdac_pln': 200.0,  # Low price
                    'business_date': '2025-09-07'
                },
                {
                    'dtime': '2025-09-07 12:15',
                    'csdac_pln': 400.0,  # High price - window ends
                    'business_date': '2025-09-07'
                }
            ]
        }
    
    def test_critical_scenario_low_price_insufficient_pv_timing(self):
        """Test the critical scenario: Low price window + insufficient PV timing"""
        
        with patch('master_coordinator.datetime') as mock_datetime:
            # Set current time to 11:00 AM (start of low price window)
            mock_datetime.now.return_value = datetime(2025, 9, 7, 11, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            # Mock PV forecasts showing insufficient PV timing
            mock_pv_forecasts = [
                {
                    'timestamp': '2025-09-07T11:00:00',
                    'hour': 11,
                    'hour_offset': 0,
                    'forecasted_power_kw': 2.0,  # Low PV
                    'forecasted_power_w': 2000,
                    'confidence': 0.8,
                    'method': 'historical_pattern'
                },
                {
                    'timestamp': '2025-09-07T12:00:00',
                    'hour': 12,
                    'hour_offset': 1,
                    'forecasted_power_kw': 2.5,  # Still low PV
                    'forecasted_power_w': 2500,
                    'confidence': 0.7,
                    'method': 'historical_pattern'
                },
                {
                    'timestamp': '2025-09-07T13:00:00',
                    'hour': 13,
                    'hour_offset': 2,
                    'forecasted_power_kw': 5.0,  # PV increases but price window ends
                    'forecasted_power_w': 5000,
                    'confidence': 0.6,
                    'method': 'historical_pattern'
                }
            ]
            
            # Mock the PV forecaster
            with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production', return_value=mock_pv_forecasts):
                # Mock the price analyzer
                with patch.object(self.decision_engine.price_analyzer, 'analyze_timing_vs_price') as mock_analyze:
                    mock_analyze.return_value = {
                        'recommendation': 'hybrid_charging',
                        'reason': 'Low price window (1.0h) shorter than PV charging time (2.0h), use grid charging to capture savings',
                        'optimal_window': {
                            'start_time': '2025-09-07T11:00:00',
                            'end_time': '2025-09-07T12:00:00',
                            'duration_hours': 1.0,
                            'avg_price_pln': 170.0,
                            'savings_potential_pln': 100.0
                        },
                        'pv_timing': {
                            'can_charge_with_pv': False,
                            'estimated_time_hours': 2.0,
                            'reason': 'PV can only provide 1.5 kWh, need 3.0 kWh'
                        },
                        'hybrid_recommended': True
                    }
                    
                    # Mock the hybrid logic
                    with patch.object(self.decision_engine.hybrid_logic, 'analyze_and_decide') as mock_hybrid:
                        mock_hybrid.return_value = MagicMock(
                            action='start_hybrid_charging',
                            charging_source='hybrid',
                            duration_hours=1.0,
                            energy_kwh=3.0,
                            estimated_cost_pln=0.5,
                            estimated_savings_pln=2.0,
                            confidence=0.9,
                            reason='Low price window (1.0h) shorter than PV charging time (2.0h), using hybrid approach',
                            start_time=datetime(2025, 9, 7, 11, 0),
                            end_time=datetime(2025, 9, 7, 12, 0),
                            pv_contribution_kwh=1.5,
                            grid_contribution_kwh=1.5
                        )
                        
                        # Test the decision
                        decision = self.decision_engine.analyze_and_decide(
                            self.mock_current_data,
                            self.mock_price_data,
                            []
                        )
                        
                        # Verify the decision
                        self.assertEqual(decision['action'], 'start_charging')
                        self.assertIn('timing_analysis', decision)
                        self.assertEqual(decision['timing_analysis']['charging_source'], 'hybrid')
                        self.assertEqual(decision['timing_analysis']['duration_hours'], 1.0)
                        self.assertEqual(decision['timing_analysis']['pv_contribution_kwh'], 1.5)
                        self.assertEqual(decision['timing_analysis']['grid_contribution_kwh'], 1.5)
                        self.assertIn('hybrid', decision['reasoning'].lower())
    
    def test_pv_charging_when_timing_sufficient(self):
        """Test PV charging when PV timing is sufficient"""
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 11, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            # Mock PV forecasts showing sufficient PV timing
            mock_pv_forecasts = [
                {
                    'timestamp': '2025-09-07T11:00:00',
                    'hour': 11,
                    'hour_offset': 0,
                    'forecasted_power_kw': 5.0,  # High PV
                    'forecasted_power_w': 5000,
                    'confidence': 0.8,
                    'method': 'historical_pattern'
                },
                {
                    'timestamp': '2025-09-07T12:00:00',
                    'hour': 12,
                    'hour_offset': 1,
                    'forecasted_power_kw': 6.0,  # High PV
                    'forecasted_power_w': 6000,
                    'confidence': 0.7,
                    'method': 'historical_pattern'
                }
            ]
            
            with patch.object(self.decision_engine.pv_forecaster, 'forecast_pv_production', return_value=mock_pv_forecasts):
                with patch.object(self.decision_engine.price_analyzer, 'analyze_timing_vs_price') as mock_analyze:
                    mock_analyze.return_value = {
                        'recommendation': 'pv_charging',
                        'reason': 'PV can complete charging in 1.0h during low price window',
                        'optimal_window': {
                            'start_time': '2025-09-07T11:00:00',
                            'end_time': '2025-09-07T12:00:00',
                            'duration_hours': 1.0,
                            'avg_price_pln': 170.0,
                            'savings_potential_pln': 100.0
                        },
                        'pv_timing': {
                            'can_charge_with_pv': True,
                            'estimated_time_hours': 0.8,
                            'reason': 'PV can provide 4.0 kW, charging time: 0.8h'
                        },
                        'hybrid_recommended': False
                    }
                    
                    with patch.object(self.decision_engine.hybrid_logic, 'analyze_and_decide') as mock_hybrid:
                        mock_hybrid.return_value = MagicMock(
                            action='start_pv_charging',
                            charging_source='pv',
                            duration_hours=0.8,
                            energy_kwh=3.0,
                            estimated_cost_pln=0.0,
                            estimated_savings_pln=3.0,
                            confidence=0.9,
                            reason='PV can complete charging in 0.8h during low price window',
                            start_time=datetime(2025, 9, 7, 11, 0),
                            end_time=datetime(2025, 9, 7, 11, 48),
                            pv_contribution_kwh=3.0,
                            grid_contribution_kwh=0.0
                        )
                        
                        decision = self.decision_engine.analyze_and_decide(
                            self.mock_current_data,
                            self.mock_price_data,
                            []
                        )
                        
                        self.assertEqual(decision['action'], 'start_charging')
                        self.assertEqual(decision['timing_analysis']['charging_source'], 'pv')
                        self.assertEqual(decision['timing_analysis']['pv_contribution_kwh'], 3.0)
                        self.assertEqual(decision['timing_analysis']['grid_contribution_kwh'], 0.0)
    
    def test_emergency_charging_critical_battery(self):
        """Test emergency charging for critical battery level"""
        
        # Set battery to critical level
        critical_data = self.mock_current_data.copy()
        critical_data['battery']['soc_percent'] = 15  # Critical level
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 11, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            with patch.object(self.decision_engine.hybrid_logic, 'analyze_and_decide') as mock_hybrid:
                mock_hybrid.return_value = MagicMock(
                    action='start_grid_charging',
                    charging_source='grid',
                    duration_hours=1.5,
                    energy_kwh=4.5,
                    estimated_cost_pln=1.0,
                    estimated_savings_pln=0.0,
                    confidence=1.0,
                    reason='Critical battery level (15%) - charging immediately',
                    start_time=datetime(2025, 9, 7, 11, 0),
                    end_time=datetime(2025, 9, 7, 12, 30),
                    pv_contribution_kwh=0.0,
                    grid_contribution_kwh=4.5
                )
                
                decision = self.decision_engine.analyze_and_decide(
                    critical_data,
                    self.mock_price_data,
                    []
                )
                
                self.assertEqual(decision['action'], 'start_charging')
                self.assertEqual(decision['timing_analysis']['charging_source'], 'grid')
                self.assertIn('critical', decision['reasoning'].lower())
    
    def test_legacy_mode_fallback(self):
        """Test fallback to legacy mode when timing awareness is disabled"""
        
        # Disable timing awareness
        legacy_config = self.config.copy()
        legacy_config['timing_awareness_enabled'] = False
        
        legacy_engine = MultiFactorDecisionEngine(legacy_config)
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 7, 11, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            decision = legacy_engine.analyze_and_decide(
                self.mock_current_data,
                self.mock_price_data,
                []
            )
            
            # Should not have timing analysis
            self.assertNotIn('timing_analysis', decision)
            # Should use legacy scoring
            self.assertIn('scores', decision)
            self.assertIn('total_score', decision)


if __name__ == '__main__':
    unittest.main()