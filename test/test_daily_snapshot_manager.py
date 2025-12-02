#!/usr/bin/env python3
"""
Tests for Daily Snapshot Manager
Tests the daily snapshot system for efficient monthly cost tracking
"""

import unittest
import json
import tempfile
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from daily_snapshot_manager import DailySnapshotManager


class TestDailySnapshotManager(unittest.TestCase):
    """Test cases for the DailySnapshotManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory structure
        self.test_dir = Path(tempfile.mkdtemp())
        self.energy_data_dir = self.test_dir / "out" / "energy_data"
        self.snapshots_dir = self.test_dir / "out" / "daily_snapshots"
        self.energy_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize manager
        self.manager = DailySnapshotManager(self.test_dir)
        
        # Create sample decision files
        self._create_sample_decision_files()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def _create_sample_decision_files(self):
        """Create sample decision files for testing"""
        test_date = date.today() - timedelta(days=1)
        date_str = test_date.strftime('%Y%m%d')
        
        # Create 3 charging decisions for yesterday
        for i in range(3):
            timestamp = datetime.combine(test_date, datetime.min.time()) + timedelta(hours=i*8)
            decision = {
                'timestamp': timestamp.isoformat(),
                'action': 'charge',
                'energy_kwh': 5.0,
                'estimated_cost_pln': 2.8,
                'estimated_savings_pln': 0.5,
                'confidence': 0.85,
                'current_price': 0.56,
                'charging_source': 'grid'
            }
            
            filename = f"charging_decision_{date_str}_{timestamp.strftime('%H%M%S')}.json"
            filepath = self.energy_data_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(decision, f)
        
        # Create 1 wait decision
        timestamp = datetime.combine(test_date, datetime.min.time()) + timedelta(hours=12)
        decision = {
            'timestamp': timestamp.isoformat(),
            'action': 'wait',
            'energy_kwh': 0,
            'estimated_cost_pln': 0,
            'estimated_savings_pln': 0,
            'confidence': 0.9,
            'current_price': 0.85,
            'charging_source': 'none'
        }
        
        filename = f"charging_decision_{date_str}_{timestamp.strftime('%H%M%S')}.json"
        filepath = self.energy_data_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(decision, f)
    
    def test_snapshot_creation(self):
        """Test creating a daily snapshot"""
        test_date = date.today() - timedelta(days=1)
        
        snapshot = self.manager.create_daily_snapshot(test_date)
        
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot['date'], test_date.isoformat())
        self.assertEqual(snapshot['total_decisions'], 4)
        self.assertEqual(snapshot['charging_count'], 3)
        self.assertEqual(snapshot['wait_count'], 1)
        self.assertAlmostEqual(snapshot['total_energy_kwh'], 15.0, places=1)
        self.assertAlmostEqual(snapshot['total_cost_pln'], 8.4, places=1)
    
    def test_snapshot_exists(self):
        """Test checking if snapshot exists"""
        test_date = date.today() - timedelta(days=1)
        
        # Initially should not exist
        self.assertFalse(self.manager.snapshot_exists(test_date))
        
        # Create snapshot
        self.manager.create_daily_snapshot(test_date)
        
        # Now should exist
        self.assertTrue(self.manager.snapshot_exists(test_date))
    
    def test_load_snapshot(self):
        """Test loading an existing snapshot"""
        test_date = date.today() - timedelta(days=1)
        
        # Create snapshot
        created_snapshot = self.manager.create_daily_snapshot(test_date)
        
        # Load snapshot
        loaded_snapshot = self.manager.load_snapshot(test_date)
        
        self.assertIsNotNone(loaded_snapshot)
        self.assertEqual(loaded_snapshot['date'], created_snapshot['date'])
        self.assertEqual(loaded_snapshot['total_decisions'], created_snapshot['total_decisions'])
    
    def test_load_nonexistent_snapshot(self):
        """Test loading a snapshot that doesn't exist"""
        test_date = date.today() - timedelta(days=100)
        
        snapshot = self.manager.load_snapshot(test_date)
        
        self.assertIsNone(snapshot)
    
    def test_monthly_summary_single_day(self):
        """Test getting monthly summary with one day of data"""
        test_date = date.today() - timedelta(days=1)
        
        # Create snapshot for yesterday
        self.manager.create_daily_snapshot(test_date)
        
        # Get monthly summary
        year = test_date.year
        month = test_date.month
        summary = self.manager.get_monthly_summary(year, month)
        
        self.assertEqual(summary['year'], year)
        self.assertEqual(summary['month'], month)
        self.assertGreater(summary['days_with_data'], 0)
        self.assertGreater(summary['total_decisions'], 0)
    
    def test_monthly_summary_no_data(self):
        """Test getting monthly summary with no data"""
        # Get summary for a month with no data
        summary = self.manager.get_monthly_summary(2020, 1)
        
        self.assertEqual(summary['year'], 2020)
        self.assertEqual(summary['month'], 1)
        self.assertEqual(summary['days_with_data'], 0)
        self.assertEqual(summary['total_decisions'], 0)
        self.assertEqual(summary['total_cost_pln'], 0)
    
    def test_create_missing_snapshots(self):
        """Test creating missing snapshots"""
        # Create decision files for 2 days ago
        test_date = date.today() - timedelta(days=2)
        date_str = test_date.strftime('%Y%m%d')
        
        timestamp = datetime.combine(test_date, datetime.min.time())
        decision = {
            'timestamp': timestamp.isoformat(),
            'action': 'charge',
            'energy_kwh': 5.0,
            'estimated_cost_pln': 2.8,
            'estimated_savings_pln': 0.5,
            'confidence': 0.85,
            'current_price': 0.56,
            'charging_source': 'grid'
        }
        
        filename = f"charging_decision_{date_str}_120000.json"
        filepath = self.energy_data_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(decision, f)
        
        # Create missing snapshots
        count = self.manager.create_missing_snapshots(days_back=3)
        
        # Should have created at least 1 (the one we just added data for)
        self.assertGreaterEqual(count, 1)
    
    def test_snapshot_calculation_accuracy(self):
        """Test that snapshot calculations are accurate"""
        test_date = date.today() - timedelta(days=1)
        
        snapshot = self.manager.create_daily_snapshot(test_date)
        
        # Check calculations
        # 3 charging decisions * 5.0 kWh each = 15.0 kWh
        self.assertAlmostEqual(snapshot['total_energy_kwh'], 15.0, places=1)
        
        # 3 charging decisions * 2.8 PLN each = 8.4 PLN
        self.assertAlmostEqual(snapshot['total_cost_pln'], 8.4, places=1)
        
        # Average cost per kWh = 8.4 / 15.0 = 0.56
        self.assertAlmostEqual(snapshot['avg_cost_per_kwh'], 0.56, places=2)
        
        # Average confidence = (3*0.85 + 1*0.9) / 4 = 0.8625
        self.assertAlmostEqual(snapshot['avg_confidence'], 0.8625, places=3)
    
    def test_source_breakdown(self):
        """Test that source breakdown is calculated correctly"""
        test_date = date.today() - timedelta(days=1)
        
        snapshot = self.manager.create_daily_snapshot(test_date)
        
        # All 3 charging decisions should be from 'grid'
        self.assertIn('grid', snapshot['source_breakdown'])
        self.assertEqual(snapshot['source_breakdown']['grid'], 3)
    
    def test_price_statistics(self):
        """Test that price statistics are calculated"""
        test_date = date.today() - timedelta(days=1)
        
        snapshot = self.manager.create_daily_snapshot(test_date)
        
        # Check price stats exist
        self.assertIn('price_stats', snapshot)
        self.assertIn('min', snapshot['price_stats'])
        self.assertIn('max', snapshot['price_stats'])
        self.assertIn('avg', snapshot['price_stats'])
        
        # All charging decisions have price 0.56
        self.assertAlmostEqual(snapshot['price_stats']['avg'], 0.56, places=2)


class TestMonthlyAggregation(unittest.TestCase):
    """Test cases for monthly aggregation logic"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.energy_data_dir = self.test_dir / "out" / "energy_data"
        self.energy_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.manager = DailySnapshotManager(self.test_dir)
        
        # Create decision files for multiple days
        self._create_multi_day_data()
    
    def tearDown(self):
        """Clean up test fixtures"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def _create_multi_day_data(self):
        """Create decision files for multiple days in the same month"""
        # Use a fixed test date that ensures all 3 days are in the same month
        # Use the 5th day of current month to ensure 3 previous days exist
        today = date.today()
        
        # If we're in the first few days of the month, use last month
        if today.day <= 4:
            if today.month == 1:
                test_month = 12
                test_year = today.year - 1
            else:
                test_month = today.month - 1
                test_year = today.year
            # Use a safe day in the middle of that month
            base_date = date(test_year, test_month, 15)
        else:
            # Use current month, ensure we have at least 3 days before today
            base_date = today - timedelta(days=1)
        
        # Create data for 3 consecutive days ending with base_date
        for days_before in range(2, -1, -1):  # 2, 1, 0
            test_date = base_date - timedelta(days=days_before)
            date_str = test_date.strftime('%Y%m%d')
            
            # Create 2 decisions per day
            for i in range(2):
                timestamp = datetime.combine(test_date, datetime.min.time()) + timedelta(hours=i*12)
                decision = {
                    'timestamp': timestamp.isoformat(),
                    'action': 'charge',
                    'energy_kwh': 5.0,
                    'estimated_cost_pln': 2.5,
                    'estimated_savings_pln': 0.5,
                    'confidence': 0.8,
                    'current_price': 0.5,
                    'charging_source': 'grid'
                }
                
                filename = f"charging_decision_{date_str}_{timestamp.strftime('%H%M%S')}.json"
                filepath = self.energy_data_dir / filename
                
                with open(filepath, 'w') as f:
                    json.dump(decision, f)
    
    def test_monthly_aggregation(self):
        """Test aggregating multiple days into monthly summary"""
        # Use the same logic as _create_multi_day_data to determine the test date
        today = date.today()
        
        if today.day <= 4:
            if today.month == 1:
                test_month = 12
                test_year = today.year - 1
            else:
                test_month = today.month - 1
                test_year = today.year
        else:
            test_year = today.year
            test_month = today.month
        
        summary = self.manager.get_monthly_summary(test_year, test_month)
        
        # Should have data from 3 days
        self.assertGreaterEqual(summary['days_with_data'], 3)
        
        # Total energy = 3 days * 2 decisions * 5.0 kWh = 30.0 kWh
        self.assertAlmostEqual(summary['total_energy_kwh'], 30.0, places=1)
        
        # Total cost = 3 days * 2 decisions * 2.5 PLN = 15.0 PLN
        self.assertAlmostEqual(summary['total_cost_pln'], 15.0, places=1)
    
    def test_monthly_summary_structure(self):
        """Test that monthly summary has correct structure"""
        # Use the same logic as _create_multi_day_data to determine the test date
        today = date.today()
        
        if today.day <= 4:
            if today.month == 1:
                month = 12
                year = today.year - 1
            else:
                month = today.month - 1
                year = today.year
        else:
            year = today.year
            month = today.month
        
        summary = self.manager.get_monthly_summary(year, month)
        
        # Check all required fields exist
        required_fields = [
            'year', 'month', 'month_name', 'total_decisions', 'charging_count',
            'wait_count', 'total_energy_kwh', 'total_cost_pln', 'total_savings_pln',
            'avg_cost_per_kwh', 'savings_percentage', 'avg_confidence',
            'days_with_data', 'source_breakdown'
        ]
        
        for field in required_fields:
            self.assertIn(field, summary, f"Missing field: {field}")


if __name__ == '__main__':
    unittest.main()

