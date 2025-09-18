#!/usr/bin/env python3
"""
Comprehensive tests for decision filtering functionality
Tests to prevent filtering issues from happening again
"""

import unittest
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Add the src directory to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from log_web_server import LogWebServer


class TestDecisionFilteringComprehensive(unittest.TestCase):
    """Comprehensive tests for decision filtering to prevent issues"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.energy_data_dir = os.path.join(self.temp_dir, 'out', 'energy_data')
        os.makedirs(self.energy_data_dir, exist_ok=True)
        
        self.test_host = '127.0.0.1'
        self.test_port = 8081
        
        # Create test decision data
        self._create_test_decision_data()
    
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_decision_data(self):
        """Create comprehensive test decision data"""
        base_time = datetime.now() - timedelta(hours=2)
        
        # Test Case 1: Charging decisions with action="wait" but charging intent
        charging_decisions_with_wait_action = [
            {
                "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
                "action": "wait",
                "source": "grid",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.8,
                "reason": "Start charging from grid - low price window detected",
                "priority": "high",
                "battery_soc": 45,
                "pv_power": 0,
                "house_consumption": 200,
                "current_price": 0.25,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            },
            {
                "timestamp": (base_time + timedelta(minutes=20)).isoformat(),
                "action": "wait",
                "source": "pv",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.9,
                "reason": "Start PV charging - overproduction available",
                "priority": "medium",
                "battery_soc": 50,
                "pv_power": 3000,
                "house_consumption": 1000,
                "current_price": 0.30,
                "cheapest_price": 0.25,
                "cheapest_hour": 3
            },
            {
                "timestamp": (base_time + timedelta(minutes=30)).isoformat(),
                "action": "start_pv_charging",
                "source": "pv",
                "duration": 120,
                "energy_kwh": 2.5,
                "estimated_cost_pln": 0.75,
                "estimated_savings_pln": 1.25,
                "confidence": 0.95,
                "reason": "PV charging started - optimal conditions",
                "priority": "high",
                "battery_soc": 55,
                "pv_power": 3500,
                "house_consumption": 800,
                "current_price": 0.30,
                "cheapest_price": 0.25,
                "cheapest_hour": 3
            }
        ]
        
        # Test Case 2: Genuine wait decisions
        wait_decisions = [
            {
                "timestamp": (base_time + timedelta(minutes=5)).isoformat(),
                "action": "wait",
                "source": "unknown",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.4,
                "reason": "Wait for better conditions (PV overproduction, lower prices, or higher consumption)",
                "priority": "low",
                "battery_soc": 69,
                "pv_power": 0,
                "house_consumption": 287,
                "current_price": 0.45,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            },
            {
                "timestamp": (base_time + timedelta(minutes=15)).isoformat(),
                "action": "wait",
                "source": "unknown",
                "duration": 0,
                "energy_kwh": 0,
                "estimated_cost_pln": 0,
                "estimated_savings_pln": 0,
                "confidence": 0.3,
                "reason": "Wait for better conditions - current price too high",
                "priority": "low",
                "battery_soc": 68,
                "pv_power": 0,
                "house_consumption": 273,
                "current_price": 0.50,
                "cheapest_price": 0.20,
                "cheapest_hour": 2
            }
        ]
        
        # Test Case 3: Battery selling decisions
        battery_selling_decisions = [
            {
                "timestamp": (base_time + timedelta(minutes=25)).isoformat(),
                "action": "battery_selling",
                "decision": "start_selling",
                "confidence": 0.85,
                "expected_revenue_pln": 2.50,
                "selling_power_w": 2000,
                "estimated_duration_hours": 2.0,
                "reasoning": "High price window detected - optimal for battery selling",
                "safety_checks_passed": True,
                "risk_level": "low",
                "current_price_pln": 0.75,
                "battery_soc": 85,
                "pv_power": 0,
                "house_consumption": 500,
                "energy_sold_kwh": 4.0,
                "revenue_per_kwh_pln": 0.75,
                "safety_status": "safe"
            },
            {
                "timestamp": (base_time + timedelta(minutes=35)).isoformat(),
                "action": "battery_selling",
                "decision": "wait",
                "confidence": 0.0,
                "expected_revenue_pln": 0.0,
                "selling_power_w": 0,
                "estimated_duration_hours": 0.0,
                "reasoning": "Battery SOC (45%) below minimum selling threshold (80%)",
                "safety_checks_passed": True,
                "risk_level": "low",
                "current_price_pln": 0.75,
                "battery_soc": 45,
                "pv_power": 200,
                "house_consumption": 1200,
                "energy_sold_kwh": 0.0,
                "revenue_per_kwh_pln": 0.75,
                "safety_status": "safe"
            }
        ]
        
        # Write charging decision files (these should be categorized as charging)
        for i, decision in enumerate(charging_decisions_with_wait_action):
            filename = f"charging_decision_20250909_{base_time.strftime('%H%M%S')}_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        # Write wait decision files (these should be categorized as wait)
        for i, decision in enumerate(wait_decisions):
            filename = f"charging_decision_20250909_{base_time.strftime('%H%M%S')}_wait_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        # Write battery selling decision files
        for i, decision in enumerate(battery_selling_decisions):
            filename = f"battery_selling_decision_20250909_{base_time.strftime('%H%M%S')}_{i:02d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
    
    def test_charging_filter_returns_only_charging_decisions(self):
        """Test that charging filter returns only charging decisions"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only charging decisions
            history = server._get_decision_history(time_range='24h', decision_type='charging')
            
            # Verify counts
            self.assertEqual(history['charging_count'], 3, "Should have 3 charging decisions")
            self.assertEqual(history['wait_count'], 0, "Should have 0 wait decisions in charging filter")
            self.assertEqual(history['battery_selling_count'], 0, "Should have 0 battery selling decisions in charging filter")
            self.assertEqual(history['total_count'], 3, "Should have 3 total decisions in charging filter")
            
            # Verify all returned decisions are from charging_decision files
            for decision in history['decisions']:
                filename = decision.get('filename', '')
                self.assertTrue(
                    'charging_decision' in filename and 'wait' not in filename,
                    f"All charging filter decisions should be from charging_decision files: {filename}"
                )
    
    def test_wait_filter_returns_only_wait_decisions(self):
        """Test that wait filter returns only wait decisions"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only wait decisions
            history = server._get_decision_history(time_range='24h', decision_type='wait')
            
            # Verify counts
            self.assertEqual(history['charging_count'], 0, "Should have 0 charging decisions in wait filter")
            self.assertEqual(history['wait_count'], 2, "Should have 2 wait decisions in wait filter")
            self.assertEqual(history['battery_selling_count'], 0, "Should have 0 battery selling decisions in wait filter")
            self.assertEqual(history['total_count'], 2, "Should have 2 total decisions in wait filter")
            
            # Verify all returned decisions are genuine wait decisions
            for decision in history['decisions']:
                filename = decision.get('filename', '')
                self.assertTrue(
                    'wait' in filename,
                    f"All wait filter decisions should be from wait files: {filename}"
                )
    
    def test_battery_selling_filter_returns_only_battery_selling_decisions(self):
        """Test that battery selling filter returns only battery selling decisions"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get only battery selling decisions
            history = server._get_decision_history(time_range='24h', decision_type='battery_selling')
            
            # Verify counts
            self.assertEqual(history['charging_count'], 0, "Should have 0 charging decisions in battery selling filter")
            self.assertEqual(history['wait_count'], 0, "Should have 0 wait decisions in battery selling filter")
            self.assertEqual(history['battery_selling_count'], 2, "Should have 2 battery selling decisions in battery selling filter")
            self.assertEqual(history['total_count'], 2, "Should have 2 total decisions in battery selling filter")
            
            # Verify all returned decisions are from battery_selling_decision files
            for decision in history['decisions']:
                filename = decision.get('filename', '')
                self.assertTrue(
                    'battery_selling_decision' in filename,
                    f"All battery selling filter decisions should be from battery_selling_decision files: {filename}"
                )
    
    def test_all_filter_returns_all_decisions_with_correct_categorization(self):
        """Test that all filter returns all decisions with correct categorization"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get all decisions
            history = server._get_decision_history(time_range='24h', decision_type='all')
            
            # Verify counts
            self.assertEqual(history['charging_count'], 3, "Should have 3 charging decisions")
            self.assertEqual(history['wait_count'], 2, "Should have 2 wait decisions")
            self.assertEqual(history['battery_selling_count'], 2, "Should have 2 battery selling decisions")
            self.assertEqual(history['total_count'], 7, "Should have 7 total decisions")
    
    def test_filtering_consistency_across_different_time_ranges(self):
        """Test that filtering works consistently across different time ranges"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test different time ranges
            time_ranges = ['1h', '24h', '7d']
            
            for time_range in time_ranges:
                # Test charging filter
                charging_history = server._get_decision_history(time_range=time_range, decision_type='charging')
                self.assertEqual(charging_history['wait_count'], 0, f"Wait count should be 0 for charging filter with {time_range}")
                self.assertEqual(charging_history['battery_selling_count'], 0, f"Battery selling count should be 0 for charging filter with {time_range}")
                
                # Test wait filter
                wait_history = server._get_decision_history(time_range=time_range, decision_type='wait')
                self.assertEqual(wait_history['charging_count'], 0, f"Charging count should be 0 for wait filter with {time_range}")
                self.assertEqual(wait_history['battery_selling_count'], 0, f"Battery selling count should be 0 for wait filter with {time_range}")
                
                # Test battery selling filter
                battery_history = server._get_decision_history(time_range=time_range, decision_type='battery_selling')
                self.assertEqual(battery_history['charging_count'], 0, f"Charging count should be 0 for battery selling filter with {time_range}")
                self.assertEqual(battery_history['wait_count'], 0, f"Wait count should be 0 for battery selling filter with {time_range}")
    
    def test_decision_categorization_based_on_filename_pattern(self):
        """Test that decision categorization is based on filename pattern, not just action field"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get all decisions
            history = server._get_decision_history(time_range='24h', decision_type='all')
            
            # Verify that decisions are categorized based on filename, not action
            charging_decisions = [d for d in history['decisions'] if 'charging_decision' in d.get('filename', '') and 'wait' not in d.get('filename', '')]
            wait_decisions = [d for d in history['decisions'] if 'wait' in d.get('filename', '')]
            battery_selling_decisions = [d for d in history['decisions'] if 'battery_selling_decision' in d.get('filename', '')]
            
            # Verify counts match expected categorization
            self.assertEqual(len(charging_decisions), 3, "Should have 3 charging decisions from charging_decision files")
            self.assertEqual(len(wait_decisions), 2, "Should have 2 wait decisions from wait files")
            self.assertEqual(len(battery_selling_decisions), 2, "Should have 2 battery selling decisions from battery_selling_decision files")
            
            # Verify all charging decisions are from charging_decision files
            for decision in charging_decisions:
                filename = decision.get('filename', '')
                self.assertTrue('charging_decision' in filename and 'wait' not in filename, 
                              f"Charging decision should be from charging_decision file: {filename}")
            
            # Verify all wait decisions are from wait files
            for decision in wait_decisions:
                filename = decision.get('filename', '')
                self.assertTrue('wait' in filename, f"Wait decision should be from wait file: {filename}")
            
            # Verify all battery selling decisions are from battery_selling_decision files
            for decision in battery_selling_decisions:
                filename = decision.get('filename', '')
                self.assertTrue('battery_selling_decision' in filename, 
                              f"Battery selling decision should be from battery_selling_decision file: {filename}")
    
    def test_filtering_with_malformed_decisions(self):
        """Test that filtering works correctly with malformed decisions"""
        # Create a malformed decision file
        malformed_decision = {
            "timestamp": datetime.now().isoformat(),
            "action": "",  # Empty action
            "reason": "",  # Empty reason
        }
        
        malformed_file = os.path.join(self.energy_data_dir, "charging_decision_malformed.json")
        with open(malformed_file, 'w') as f:
            json.dump(malformed_decision, f, indent=2)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Get all decisions including malformed one
            history = server._get_decision_history(time_range='24h', decision_type='all')
            
            # Malformed decision should be categorized based on filename (charging_decision)
            self.assertEqual(history['charging_count'], 4, "Should include malformed charging decision in charging count")
            self.assertEqual(history['total_count'], 8, "Should have 8 total decisions including malformed")
    
    def test_filtering_edge_cases(self):
        """Test filtering with edge cases"""
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test with invalid decision type - should default to 'all'
            history = server._get_decision_history(time_range='24h', decision_type='invalid_type')
            self.assertEqual(history['total_count'], 7, "Should return all decisions for invalid type")
            self.assertEqual(history['charging_count'], 3, "Should have 3 charging decisions for invalid type")
            self.assertEqual(history['wait_count'], 2, "Should have 2 wait decisions for invalid type")
            self.assertEqual(history['battery_selling_count'], 2, "Should have 2 battery selling decisions for invalid type")
            
            # Test with empty time range
            history = server._get_decision_history(time_range='1s', decision_type='charging')
            # Should return empty or limited results based on time threshold
            self.assertIsInstance(history['total_count'], int, "Should return integer count")
    
    def test_decision_filtering_performance(self):
        """Test that filtering performs well with many decisions"""
        # Create many decision files with charging intent
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(100):
            decision = {
                "timestamp": (base_time + timedelta(minutes=i)).isoformat(),
                "action": "start_pv_charging",
                "reason": f"Start charging from PV - test decision {i}",
                "confidence": 0.5
            }
            
            filename = f"charging_decision_test_{i:03d}.json"
            filepath = os.path.join(self.energy_data_dir, filename)
            with open(filepath, 'w') as f:
                json.dump(decision, f, indent=2)
        
        with patch('log_web_server.Path') as mock_path:
            mock_path.return_value.parent.parent = Path(self.temp_dir)
            
            server = LogWebServer(host=self.test_host, port=self.test_port, log_dir=os.path.join(self.temp_dir, 'logs'))
            
            # Test filtering performance
            import time
            start_time = time.time()
            
            history = server._get_decision_history(time_range='7d', decision_type='charging')
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Should complete within reasonable time (less than 1 second)
            self.assertLess(execution_time, 1.0, f"Filtering should complete within 1 second, took {execution_time:.2f}s")
            
            # Should return correct count (100 new + 3 existing from setup)
            self.assertEqual(history['charging_count'], 103, "Should have 103 charging decisions (100 new + 3 existing)")
            self.assertEqual(history['total_count'], 103, "Should have 103 total decisions (100 new + 3 existing)")


if __name__ == '__main__':
    unittest.main()
