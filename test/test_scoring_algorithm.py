#!/usr/bin/env python3
"""
Tests for the multi-factor decision engine scoring algorithm
Verifies that the scoring system correctly calculates scores and makes decisions
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from master_coordinator import MultiFactorDecisionEngine


class TestScoringAlgorithm(unittest.TestCase):
    """Test the multi-factor decision engine scoring algorithm"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'coordinator': {
                'decision_interval_minutes': 15,
                'health_check_interval_minutes': 5
            },
            'timing_awareness_enabled': False  # Disable timing awareness for legacy tests
        }
        self.decision_engine = MultiFactorDecisionEngine(self.config)
        
        # Mock price data
        self.mock_price_data = {
            'value': [
                {
                    'dtime': '2025-09-06 12:00',
                    'csdac_pln': 200.0,  # Low price
                    'business_date': '2025-09-06'
                },
                {
                    'dtime': '2025-09-06 12:15',
                    'csdac_pln': 200.0,
                    'business_date': '2025-09-06'
                }
            ]
        }
        
        # Mock current data
        self.mock_current_data = {
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
    
    def test_price_score_calculation_low_price(self):
        """Test price score calculation for low prices"""
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            score = self.decision_engine._calculate_price_score(self.mock_price_data)
            
            # Low price (200 PLN + 0.0892 SC = 200.0892 PLN) should give score (80)
            self.assertEqual(score, 80)
    
    def test_price_score_calculation_medium_price(self):
        """Test price score calculation for medium prices"""
        # Update price data with medium price
        medium_price_data = self.mock_price_data.copy()
        medium_price_data['value'][0]['csdac_pln'] = 300.0  # Medium price
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            score = self.decision_engine._calculate_price_score(medium_price_data)
            
            # Medium price (300 PLN + 0.0892 SC = 300.0892 PLN) should give score (80)
            self.assertEqual(score, 80)
    
    def test_price_score_calculation_high_price(self):
        """Test price score calculation for high prices"""
        # Update price data with high price
        high_price_data = self.mock_price_data.copy()
        high_price_data['value'][0]['csdac_pln'] = 500.0  # High price
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            score = self.decision_engine._calculate_price_score(high_price_data)
            
            # High price (500 PLN) should give medium score (40)
            self.assertEqual(score, 40)
    
    def test_price_score_calculation_very_high_price(self):
        """Test price score calculation for very high prices"""
        # Update price data with very high price
        very_high_price_data = self.mock_price_data.copy()
        very_high_price_data['value'][0]['csdac_pln'] = 700.0  # Very high price
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            score = self.decision_engine._calculate_price_score(very_high_price_data)
            
            # Very high price (700 PLN) should give low score (0)
            self.assertEqual(score, 0)
    
    def test_battery_score_calculation_critical(self):
        """Test battery score calculation for critical battery level"""
        critical_battery_data = self.mock_current_data.copy()
        critical_battery_data['battery']['soc_percent'] = 15  # Critical level
        
        score = self.decision_engine._calculate_battery_score(critical_battery_data)
        
        # Critical battery (15%) should give maximum score (100)
        self.assertEqual(score, 100)
    
    def test_battery_score_calculation_low(self):
        """Test battery score calculation for low battery level"""
        low_battery_data = self.mock_current_data.copy()
        low_battery_data['battery']['soc_percent'] = 35  # Low level
        
        score = self.decision_engine._calculate_battery_score(low_battery_data)
        
        # Low battery (35%) should give high score (80)
        self.assertEqual(score, 80)
    
    def test_battery_score_calculation_medium(self):
        """Test battery score calculation for medium battery level"""
        medium_battery_data = self.mock_current_data.copy()
        medium_battery_data['battery']['soc_percent'] = 60  # Medium level
        
        score = self.decision_engine._calculate_battery_score(medium_battery_data)
        
        # Medium battery (60%) should give medium score (40)
        self.assertEqual(score, 40)
    
    def test_battery_score_calculation_high(self):
        """Test battery score calculation for high battery level"""
        high_battery_data = self.mock_current_data.copy()
        high_battery_data['battery']['soc_percent'] = 85  # High level
        
        score = self.decision_engine._calculate_battery_score(high_battery_data)
        
        # High battery (85%) should give low score (10)
        self.assertEqual(score, 10)
    
    def test_battery_score_calculation_full(self):
        """Test battery score calculation for full battery"""
        full_battery_data = self.mock_current_data.copy()
        full_battery_data['battery']['soc_percent'] = 95  # Full battery
        
        score = self.decision_engine._calculate_battery_score(full_battery_data)
        
        # Full battery (95%) should give minimum score (0)
        self.assertEqual(score, 0)
    
    def test_pv_score_calculation_no_production(self):
        """Test PV score calculation for no production"""
        no_pv_data = self.mock_current_data.copy()
        no_pv_data['photovoltaic']['current_power_w'] = 0  # No PV production
        
        score = self.decision_engine._calculate_pv_score(no_pv_data)
        
        # No PV production should give maximum score (100)
        self.assertEqual(score, 100)
    
    def test_pv_score_calculation_low_production(self):
        """Test PV score calculation for low production with deficit"""
        low_pv_data = self.mock_current_data.copy()
        low_pv_data['photovoltaic']['current_power_w'] = 200  # Low PV production
        low_pv_data['house_consumption']['current_power_w'] = 2000  # High consumption
        # Net power: 200 - 2000 = -1800W (high deficit)
        
        score = self.decision_engine._calculate_pv_score(low_pv_data)
        
        # High deficit should give high score (80)
        self.assertEqual(score, 80)
    
    def test_pv_score_calculation_medium_production(self):
        """Test PV score calculation for medium production with balanced consumption"""
        medium_pv_data = self.mock_current_data.copy()
        medium_pv_data['photovoltaic']['current_power_w'] = 1500  # Medium PV production
        medium_pv_data['house_consumption']['current_power_w'] = 1500  # Balanced consumption
        # Net power: 1500 - 1500 = 0W (balanced)
        
        score = self.decision_engine._calculate_pv_score(medium_pv_data)
        
        # Balanced should give medium score (30)
        self.assertEqual(score, 30)
    
    def test_pv_score_calculation_high_production(self):
        """Test PV score calculation for high production"""
        high_pv_data = self.mock_current_data.copy()
        high_pv_data['photovoltaic']['current_power_w'] = 4000  # High PV production
        
        score = self.decision_engine._calculate_pv_score(high_pv_data)
        
        # High PV production should give minimum score (0)
        self.assertEqual(score, 0)
    
    def test_consumption_score_calculation_high_consumption(self):
        """Test consumption score calculation for high consumption"""
        high_consumption_data = self.mock_current_data.copy()
        high_consumption_data['house_consumption']['current_power_w'] = 4000  # High consumption
        
        score = self.decision_engine._calculate_consumption_score(high_consumption_data, [])
        
        # High consumption should give maximum score (100)
        self.assertEqual(score, 100)
    
    def test_consumption_score_calculation_medium_consumption(self):
        """Test consumption score calculation for medium consumption"""
        medium_consumption_data = self.mock_current_data.copy()
        medium_consumption_data['house_consumption']['current_power_w'] = 1500  # Medium consumption
        
        score = self.decision_engine._calculate_consumption_score(medium_consumption_data, [])
        
        # Medium consumption should give medium score (60)
        self.assertEqual(score, 60)
    
    def test_consumption_score_calculation_low_consumption(self):
        """Test consumption score calculation for low consumption"""
        low_consumption_data = self.mock_current_data.copy()
        low_consumption_data['house_consumption']['current_power_w'] = 200  # Low consumption
        
        score = self.decision_engine._calculate_consumption_score(low_consumption_data, [])
        
        # Low consumption should give low score (30)
        self.assertEqual(score, 30)
    
    def test_consumption_score_calculation_very_low_consumption(self):
        """Test consumption score calculation for very low consumption"""
        very_low_consumption_data = self.mock_current_data.copy()
        very_low_consumption_data['house_consumption']['current_power_w'] = 50  # Very low consumption
        
        score = self.decision_engine._calculate_consumption_score(very_low_consumption_data, [])
        
        # Very low consumption should give minimum score (0)
        self.assertEqual(score, 0)
    
    def test_weighted_total_score_calculation(self):
        """Test weighted total score calculation"""
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            # Calculate expected weighted score based on actual scoring logic
            # Price: 200 PLN + 0.0892 = 200.0892 PLN → 80
            # Battery: 30% SOC → 80
            # PV: 500W - 2000W consumption = -1500W deficit → 80 (medium deficit)
            # Consumption: 2000W → 60 (medium consumption)
            expected_score = (
                80 * 0.40 +  # price
                80 * 0.25 +  # battery
                80 * 0.20 +  # pv (deficit)
                60 * 0.15    # consumption
            )
            
            # Test the decision engine
            decision = self.decision_engine.analyze_and_decide(
                self.mock_current_data,
                self.mock_price_data,
                []
            )
            
            # Verify the total score matches expected calculation
            self.assertAlmostEqual(decision['total_score'], expected_score, places=2)
    
    def test_decision_action_critical_battery(self):
        """Test decision action for critical battery level"""
        critical_battery_data = self.mock_current_data.copy()
        critical_battery_data['battery']['soc_percent'] = 15  # Critical level
        
        decision = self.decision_engine.analyze_and_decide(
            critical_battery_data,
            self.mock_price_data,
            []
        )
        
        # Critical battery should always result in start_charging
        self.assertEqual(decision['action'], 'start_charging')
    
    def test_decision_action_high_score_not_charging(self):
        """Test decision action for high score when not charging"""
        high_score_data = self.mock_current_data.copy()
        high_score_data['battery']['soc_percent'] = 30  # Low battery
        high_score_data['battery']['charging_status'] = False  # Not charging
        
        # Use low price data for high price score
        low_price_data = self.mock_price_data.copy()
        low_price_data['value'][0]['csdac_pln'] = 150.0  # Very low price
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            decision = self.decision_engine.analyze_and_decide(
                high_score_data,
                low_price_data,
                []
            )
            
            # Score 81 and not charging should result in start_charging (above 70 threshold)
            self.assertEqual(decision['action'], 'start_charging')
    
    def test_decision_action_low_score_charging(self):
        """Test decision action for low score when charging"""
        low_score_data = self.mock_current_data.copy()
        low_score_data['battery']['soc_percent'] = 90  # High battery
        low_score_data['battery']['charging_status'] = True  # Currently charging
        
        # Use high price data for low price score
        high_price_data = self.mock_price_data.copy()
        high_price_data['value'][0]['csdac_pln'] = 700.0  # Very high price
        
        with patch('master_coordinator.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 9, 6, 12, 0)
            mock_datetime.strftime = datetime.strftime
            mock_datetime.strptime = datetime.strptime
            mock_datetime.timedelta = timedelta
            
            decision = self.decision_engine.analyze_and_decide(
                low_score_data,
                high_price_data,
                []
            )
            
            # Low score and charging should result in stop_charging
            self.assertEqual(decision['action'], 'stop_charging')
    
    def test_decision_action_medium_score_charging(self):
        """Test decision action for medium score when charging"""
        medium_score_data = self.mock_current_data.copy()
        medium_score_data['battery']['soc_percent'] = 60  # Medium battery
        medium_score_data['battery']['charging_status'] = True  # Currently charging
        
        # Use medium price data
        medium_price_data = self.mock_price_data.copy()
        medium_price_data['value'][0]['csdac_pln'] = 400.0  # Medium price
        
        decision = self.decision_engine.analyze_and_decide(
            medium_score_data,
            medium_price_data,
            []
        )
        
        # Medium score and charging should result in continue_charging
        self.assertEqual(decision['action'], 'continue_charging')
    
    def test_decision_action_no_action_needed(self):
        """Test decision action when no action is needed"""
        no_action_data = self.mock_current_data.copy()
        no_action_data['battery']['soc_percent'] = 80  # High battery
        no_action_data['battery']['charging_status'] = False  # Not charging
        
        # Use high price data for low price score
        high_price_data = self.mock_price_data.copy()
        high_price_data['value'][0]['csdac_pln'] = 600.0  # High price
        
        decision = self.decision_engine.analyze_and_decide(
            no_action_data,
            high_price_data,
            []
        )
        
        # High battery, not charging, and high prices should result in no action
        self.assertEqual(decision['action'], 'none')
    
    def test_confidence_calculation(self):
        """Test confidence calculation"""
        decision = self.decision_engine.analyze_and_decide(
            self.mock_current_data,
            self.mock_price_data,
            []
        )
        
        # Confidence should be between 0 and 100
        self.assertGreaterEqual(decision['confidence'], 0)
        self.assertLessEqual(decision['confidence'], 100)
    
    def test_reasoning_generation(self):
        """Test reasoning generation"""
        decision = self.decision_engine.analyze_and_decide(
            self.mock_current_data,
            self.mock_price_data,
            []
        )
        
        # Reasoning should be a non-empty string
        self.assertIsInstance(decision['reasoning'], str)
        self.assertGreater(len(decision['reasoning']), 0)
        self.assertIn('Decision based on:', decision['reasoning'])
    
    def test_no_price_data_handling(self):
        """Test handling when no price data is available"""
        decision = self.decision_engine.analyze_and_decide(
            self.mock_current_data,
            None,  # No price data
            []
        )
        
        # Should still make a decision (price score will be neutral)
        self.assertIsNotNone(decision)
        self.assertIn('action', decision)
        self.assertEqual(decision['scores']['price'], 50)  # Neutral score


if __name__ == '__main__':
    unittest.main()
