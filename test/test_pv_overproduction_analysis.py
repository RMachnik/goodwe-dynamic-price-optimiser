#!/usr/bin/env python3
"""
Tests for PV Overproduction Analysis in Multi-Factor Decision Engine
Verifies that the system correctly avoids grid charging when PV > consumption + 500W
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
import pytest

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MultiFactorDecisionEngine


class TestPVOverproductionAnalysis(unittest.IsolatedAsyncioTestCase):
    """Test PV overproduction analysis in the decision engine"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_interval_minutes': 15,
                'health_check_interval_minutes': 5
            },
            'timing_awareness_enabled': False,  # Use legacy scoring for testing
            'pv_consumption_analysis': {
                'pv_overproduction_threshold_w': 500
            }
        }
        # Mock charging controller
        self.mock_charging_controller = MagicMock()
        self.mock_charging_controller.get_current_price.return_value = 200.0  # PLN/MWh
        self.mock_charging_controller.calculate_final_price.return_value = 200.0  # PLN/MWh
        
        self.decision_engine = MultiFactorDecisionEngine(self.config, self.mock_charging_controller)
        
        # Mock price data
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-06 12:00',
                    'csdac_pln': 200.0,  # Low price
                    'business_date': '2025-09-06'
                }
            ]
        }
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_pv_overproduction_no_grid_charging(self):
        """Test that grid charging is avoided when PV overproduction is detected"""
        # Scenario: PV overproduction (PV > consumption + 500W)
        current_data = {
            'battery': {
                'soc_percent': 30,  # Low battery - would normally trigger charging
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 3000,  # High PV production
                'total_power': 3000
            },
            'house_consumption': {
                'current_power_w': 1000,  # Low consumption
                'total_power': 1000
            }
        }
        
        # Net power = 3000 - 1000 = 2000W > 500W threshold
        # Should avoid grid charging despite low battery and low prices
        
        decision = await self.decision_engine.analyze_and_decide(
            current_data,
            self.mock_price_data,
            []
        )
        
        # Should not start charging due to PV overproduction
        self.assertNotEqual(decision['action'], 'start_charging')
        self.assertEqual(decision['action'], 'none')
        
        # PV score should be 0 (overproduction)
        self.assertEqual(decision['scores']['pv'], 0)
        
        # Reasoning should mention PV overproduction
        self.assertIn('PV overproduction', decision['reasoning'])
        self.assertIn('no grid charging needed', decision['reasoning'])
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_pv_overproduction_stop_charging(self):
        """Test that grid charging is stopped when PV overproduction is detected"""
        # Scenario: Currently charging but PV overproduction detected
        current_data = {
            'battery': {
                'soc_percent': 30,
                'charging_status': True,  # Currently charging
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 2500,  # High PV production
                'total_power': 2500
            },
            'house_consumption': {
                'current_power_w': 1000,  # Low consumption
                'total_power': 1000
            }
        }
        
        # Net power = 2500 - 1000 = 1500W > 500W threshold
        # Should stop charging due to PV overproduction
        
        decision = await self.decision_engine.analyze_and_decide(
            current_data,
            self.mock_price_data,
            []
        )
        
        # Should stop charging due to PV overproduction
        self.assertEqual(decision['action'], 'stop_charging')
        
        # PV score should be 0 (overproduction)
        self.assertEqual(decision['scores']['pv'], 0)
        
        # Reasoning should mention stopping due to PV overproduction
        self.assertIn('PV overproduction', decision['reasoning'])
        self.assertIn('Stopping grid charging', decision['reasoning'])
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_pv_deficit_urgent_charging(self):
        """Test that urgent charging is triggered when PV deficit is detected"""
        # Scenario: PV deficit (PV < consumption)
        current_data = {
            'battery': {
                'soc_percent': 30,  # Low battery
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 500,  # Low PV production
                'total_power': 500
            },
            'house_consumption': {
                'current_power_w': 2000,  # High consumption
                'total_power': 2000
            }
        }
        
        # Net power = 500 - 2000 = -1500W (deficit)
        # Should trigger urgent charging
        
        decision = await self.decision_engine.analyze_and_decide(
            current_data,
            self.mock_price_data,
            []
        )
        
        # Should start charging due to PV deficit
        self.assertEqual(decision['action'], 'start_charging')
        
        # PV score should be high (deficit)
        self.assertGreaterEqual(decision['scores']['pv'], 80)
        
        # Reasoning should mention PV deficit
        self.assertIn('PV deficit', decision['reasoning'])
        self.assertIn('urgent charging needed', decision['reasoning'])
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_pv_balanced_conditions(self):
        """Test decision making under balanced PV conditions"""
        # Scenario: PV balanced (PV ≈ consumption)
        current_data = {
            'battery': {
                'soc_percent': 50,  # Medium battery
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 1200,  # Medium PV production
                'total_power': 1200
            },
            'house_consumption': {
                'current_power_w': 1000,  # Medium consumption
                'total_power': 1000
            }
        }
        
        # Net power = 1200 - 1000 = 200W (balanced, below threshold)
        # Should make normal charging decision based on other factors
        
        decision = await self.decision_engine.analyze_and_decide(
            current_data,
            self.mock_price_data,
            []
        )
        
        # PV score should be moderate (balanced)
        self.assertGreater(decision['scores']['pv'], 0)
        self.assertLess(decision['scores']['pv'], 80)
        
        # Reasoning should mention PV production available
        self.assertIn('PV production available', decision['reasoning'])
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_critical_battery_override(self):
        """Test that critical battery level overrides PV overproduction check"""
        # Scenario: Critical battery but PV overproduction
        current_data = {
            'battery': {
                'soc_percent': 10,  # Critical battery level (below 12% threshold)
                'charging_status': False,
                'voltage': 400.0,
                'temperature': 25.0
            },
            'photovoltaic': {
                'current_power_w': 3000,  # High PV production
                'total_power': 3000
            },
            'house_consumption': {
                'current_power_w': 1000,  # Low consumption
                'total_power': 1000
            }
        }
        
        # Net power = 3000 - 1000 = 2000W > 500W threshold
        # But battery is critical (15%) - should override PV overproduction check
        
        decision = await self.decision_engine.analyze_and_decide(
            current_data,
            self.mock_price_data,
            []
        )
        
        # Should start charging despite PV overproduction due to critical battery
        self.assertEqual(decision['action'], 'start_charging')
        
        # PV score should still be 0 (overproduction)
        self.assertEqual(decision['scores']['pv'], 0)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(10)
    async def test_pv_score_calculation_various_scenarios(self):
        """Test PV score calculation for various PV vs consumption scenarios"""
        test_cases = [
            # (pv_power, consumption_power, expected_score_range, description)
            (3000, 1000, (0, 0), "High overproduction"),  # 2000W overproduction
            (1500, 1000, (0, 10), "Moderate overproduction"),  # 500W overproduction
            (1000, 1000, (25, 35), "Balanced"),  # 0W net
            (800, 1000, (50, 60), "Slight deficit"),  # -200W deficit
            (500, 1500, (80, 100), "Medium deficit"),  # -1000W deficit
            (200, 2000, (80, 100), "High deficit"),  # -1800W deficit
        ]
        
        for pv_power, consumption_power, expected_range, description in test_cases:
            with self.subTest(description=description):
                current_data = {
                    'battery': {'soc_percent': 50, 'charging_status': False},
                    'photovoltaic': {'current_power_w': pv_power},
                    'house_consumption': {'current_power_w': consumption_power}
                }
                
                pv_score = self.decision_engine._calculate_pv_score(current_data)
                
                self.assertGreaterEqual(pv_score, expected_range[0], 
                                      f"PV score {pv_score} should be >= {expected_range[0]} for {description}")
                self.assertLessEqual(pv_score, expected_range[1], 
                                   f"PV score {pv_score} should be <= {expected_range[1]} for {description}")


if __name__ == '__main__':
    unittest.main()
