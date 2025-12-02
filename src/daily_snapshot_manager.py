#!/usr/bin/env python3
"""
Daily Snapshot Manager
Creates and manages daily summaries of charging decisions to avoid recalculating historical data.
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class DailySnapshotManager:
    """Manages daily snapshots of charging metrics"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the snapshot manager
        
        Args:
            project_root: Root directory of the project. If None, auto-detect.
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent
        
        self.project_root = project_root
        self.energy_data_dir = project_root / "out" / "energy_data"
        self.snapshots_dir = project_root / "out" / "daily_snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        self.monthly_snapshots_dir = project_root / "out" / "monthly_snapshots"
        self.monthly_snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Snapshot manager initialized. Snapshots dir: {self.snapshots_dir}")
    
    def get_snapshot_path(self, target_date: date) -> Path:
        """Get the path for a snapshot file for a given date"""
        return self.snapshots_dir / f"snapshot_{target_date.strftime('%Y%m%d')}.json"
    
    def snapshot_exists(self, target_date: date) -> bool:
        """Check if a snapshot exists for a given date"""
        return self.get_snapshot_path(target_date).exists()
    
    def create_daily_snapshot(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Create a daily snapshot for the given date
        
        Args:
            target_date: The date to create a snapshot for
            
        Returns:
            Snapshot data dictionary or None if no data found
        """
        logger.info(f"Creating daily snapshot for {target_date}")
        
        # Find all decision files for this date
        date_str = target_date.strftime('%Y%m%d')
        charging_files = list(self.energy_data_dir.glob(f"charging_decision_{date_str}_*.json"))
        selling_files = list(self.energy_data_dir.glob(f"battery_selling_decision_{date_str}_*.json"))
        
        decision_files = charging_files + selling_files
        
        if not decision_files:
            logger.info(f"No decision files found for {target_date}")
            return None
        
        # Process all decisions for this day
        decisions = []
        for file_path in sorted(decision_files):
            try:
                with open(file_path, 'r') as f:
                    decision_data = json.load(f)
                    decisions.append(decision_data)
            except Exception as e:
                logger.warning(f"Error reading decision file {file_path}: {e}")
                continue
        
        if not decisions:
            return None
        
        # Calculate daily summary
        snapshot = self._calculate_daily_summary(decisions, target_date)
        
        # Save snapshot to file
        snapshot_path = self.get_snapshot_path(target_date)
        try:
            with open(snapshot_path, 'w') as f:
                json.dump(snapshot, f, indent=2)
            logger.info(f"Saved snapshot for {target_date} to {snapshot_path}")
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
        
        return snapshot
    
    def _calculate_daily_summary(self, decisions: List[Dict[str, Any]], target_date: date) -> Dict[str, Any]:
        """Calculate summary metrics for a day's decisions"""
        
        # Categorize decisions
        charging_decisions = []
        wait_decisions = []
        selling_decisions = []
        
        for decision in decisions:
            action = decision.get('action', '')
            # Check for battery selling
            if action == 'battery_selling' or decision.get('decision') == 'battery_selling' or 'battery_selling' in str(decision.get('filename', '')):
                selling_decisions.append(decision)
            elif action in ['charge', 'charging', 'start_pv_charging', 'start_grid_charging']:
                charging_decisions.append(decision)
            elif action == 'wait':
                wait_decisions.append(decision)
            else:
                wait_decisions.append(decision)
        
        # Calculate aggregated metrics
        total_decisions = len(decisions)
        
        # Charging metrics
        total_energy_charged = sum(d.get('energy_kwh', 0) for d in charging_decisions)
        charging_cost = sum(d.get('estimated_cost_pln', 0) for d in charging_decisions)
        charging_savings = sum(d.get('estimated_savings_pln', 0) for d in charging_decisions)
        
        # Selling metrics
        # Map fields: energy_sold_kwh -> energy, expected_revenue_pln -> savings (revenue)
        total_energy_sold = sum(d.get('energy_sold_kwh', d.get('energy_kwh', 0)) for d in selling_decisions)
        selling_revenue = sum(d.get('expected_revenue_pln', d.get('estimated_savings_pln', 0)) for d in selling_decisions)
        
        # Total metrics (Net)
        # Cost is charging cost (positive). Revenue reduces net cost.
        # Savings is charging savings + selling revenue.
        total_cost = charging_cost
        total_savings = charging_savings + selling_revenue
        
        avg_confidence = sum(d.get('confidence', 0) for d in decisions) / total_decisions if total_decisions > 0 else 0
        
        # Calculate source breakdown
        source_breakdown = {}
        for decision in charging_decisions:
            source = decision.get('charging_source', 'unknown')
            source_breakdown[source] = source_breakdown.get(source, 0) + 1
        
        # Add selling to breakdown
        if selling_decisions:
            source_breakdown['battery_selling'] = len(selling_decisions)
        
        # Price statistics (from charging decisions only for now, as selling has different price logic)
        prices = [d.get('current_price', 0) for d in charging_decisions if d.get('current_price', 0) > 0]
        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0
        avg_price = sum(prices) / len(prices) if prices else 0
        
        snapshot = {
            'date': target_date.isoformat(),
            'created_at': datetime.now().isoformat(),
            'total_decisions': total_decisions,
            'charging_count': len(charging_decisions),
            'wait_count': len(wait_decisions),
            'selling_count': len(selling_decisions),
            'total_energy_kwh': round(total_energy_charged, 2),
            'total_energy_sold_kwh': round(total_energy_sold, 2),
            'total_cost_pln': round(total_cost, 2),
            'total_savings_pln': round(total_savings, 2),
            'selling_revenue_pln': round(selling_revenue, 2),
            'avg_confidence': round(avg_confidence, 4),
            'avg_cost_per_kwh': round(total_cost / total_energy_charged, 4) if total_energy_charged > 0 else 0,
            'source_breakdown': source_breakdown,
            'price_stats': {
                'min': round(min_price, 4),
                'max': round(max_price, 4),
                'avg': round(avg_price, 4)
            },
            'file_count': len(decisions)
        }
        
        return snapshot
    
    def load_snapshot(self, target_date: date) -> Optional[Dict[str, Any]]:
        """Load a snapshot for a given date
        
        Args:
            target_date: The date to load snapshot for
            
        Returns:
            Snapshot data or None if not found
        """
        snapshot_path = self.get_snapshot_path(target_date)
        
        if not snapshot_path.exists():
            return None
        
        try:
            with open(snapshot_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading snapshot from {snapshot_path}: {e}")
            return None
    
    def get_monthly_snapshot_path(self, year: int, month: int) -> Path:
        """Get the path for a monthly snapshot file"""
        return self.monthly_snapshots_dir / f"monthly_snapshot_{year}{month:02d}.json"

    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Get aggregated summary for a given month using snapshots
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
            
        Returns:
            Monthly summary dictionary
        """
        # Check if this is a past month
        today = date.today()
        is_past_month = (year < today.year) or (year == today.year and month < today.month)
        
        # If past month, try to load from monthly snapshot first
        if is_past_month:
            monthly_snapshot_path = self.get_monthly_snapshot_path(year, month)
            if monthly_snapshot_path.exists():
                try:
                    with open(monthly_snapshot_path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading monthly snapshot {monthly_snapshot_path}: {e}")
        
        logger.info(f"Calculating monthly summary for {year}-{month:02d}")
        
        # Calculate date range for the month
        start_date = date(year, month, 1)
        
        # Get last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Collect daily summaries
        daily_summaries = []
        missing_snapshots = []
        
        current_date = start_date
        while current_date <= end_date:
            # Don't try to load future dates
            if current_date > today:
                break
            
            # For today, process live data
            if current_date == today:
                snapshot = self._get_today_summary()
                if snapshot:
                    daily_summaries.append(snapshot)
            else:
                # Try to load existing snapshot
                snapshot = self.load_snapshot(current_date)
                
                if snapshot:
                    daily_summaries.append(snapshot)
                else:
                    # Snapshot doesn't exist, try to create it
                    missing_snapshots.append(current_date)
                    snapshot = self.create_daily_snapshot(current_date)
                    if snapshot:
                        daily_summaries.append(snapshot)
            
            current_date += timedelta(days=1)
        
        if missing_snapshots:
            logger.info(f"Created {len(missing_snapshots)} missing snapshots")
        
        # Aggregate monthly totals
        summary = self._aggregate_summaries(daily_summaries, year, month)
        
        # If it's a past month and we have data, save the monthly snapshot
        if is_past_month and summary['total_decisions'] > 0:
            try:
                monthly_snapshot_path = self.get_monthly_snapshot_path(year, month)
                with open(monthly_snapshot_path, 'w') as f:
                    json.dump(summary, f, indent=2)
                logger.info(f"Saved monthly snapshot to {monthly_snapshot_path}")
            except Exception as e:
                logger.error(f"Error saving monthly snapshot: {e}")
                
        return summary
    
    def _get_today_summary(self) -> Optional[Dict[str, Any]]:
        """Get summary for today (live calculation, not from snapshot)"""
        today = date.today()
        date_str = today.strftime('%Y%m%d')
        
        # Find all decision files for today
        decision_files = list(self.energy_data_dir.glob(f"charging_decision_{date_str}_*.json"))
        
        if not decision_files:
            return None
        
        # Process today's decisions
        decisions = []
        for file_path in sorted(decision_files):
            try:
                with open(file_path, 'r') as f:
                    decision_data = json.load(f)
                    decisions.append(decision_data)
            except Exception as e:
                logger.warning(f"Error reading decision file {file_path}: {e}")
                continue
        
        if not decisions:
            return None
        
        return self._calculate_daily_summary(decisions, today)
    
    def _aggregate_summaries(self, daily_summaries: List[Dict[str, Any]], year: int, month: int) -> Dict[str, Any]:
        """Aggregate daily summaries into monthly totals"""
        
        if not daily_summaries:
            return {
                'year': year,
                'month': month,
                'month_name': date(year, month, 1).strftime('%B'),
                'total_decisions': 0,
                'charging_count': 0,
                'wait_count': 0,
                'total_energy_kwh': 0,
                'total_cost_pln': 0,
                'total_savings_pln': 0,
                'avg_cost_per_kwh': 0,
                'savings_percentage': 0,
                'avg_confidence': 0,
                'days_with_data': 0,
                'source_breakdown': {},
                'daily_summaries': []
            }
        
        # Sum up all metrics
        total_decisions = sum(s['total_decisions'] for s in daily_summaries)
        charging_count = sum(s['charging_count'] for s in daily_summaries)
        wait_count = sum(s['wait_count'] for s in daily_summaries)
        selling_count = sum(s.get('selling_count', 0) for s in daily_summaries)
        total_energy = sum(s['total_energy_kwh'] for s in daily_summaries)
        total_energy_sold = sum(s.get('total_energy_sold_kwh', 0) for s in daily_summaries)
        total_cost = sum(s['total_cost_pln'] for s in daily_summaries)
        total_savings = sum(s['total_savings_pln'] for s in daily_summaries)
        selling_revenue = sum(s.get('selling_revenue_pln', 0) for s in daily_summaries)
        
        # Calculate weighted average confidence
        confidence_sum = sum(s['avg_confidence'] * s['total_decisions'] for s in daily_summaries)
        avg_confidence = confidence_sum / total_decisions if total_decisions > 0 else 0
        
        # Aggregate source breakdown
        source_breakdown = {}
        for summary in daily_summaries:
            for source, count in summary.get('source_breakdown', {}).items():
                source_breakdown[source] = source_breakdown.get(source, 0) + count
        
        # Calculate monthly metrics
        avg_cost_per_kwh = total_cost / total_energy if total_energy > 0 else 0
        savings_percentage = (total_savings / (total_cost + total_savings)) * 100 if (total_cost + total_savings) > 0 else 0
        
        return {
            'year': year,
            'month': month,
            'month_name': date(year, month, 1).strftime('%B'),
            'total_decisions': total_decisions,
            'charging_count': charging_count,
            'wait_count': wait_count,
            'selling_count': selling_count,
            'total_energy_kwh': round(total_energy, 2),
            'total_energy_sold_kwh': round(total_energy_sold, 2),
            'total_cost_pln': round(total_cost, 2),
            'total_savings_pln': round(total_savings, 2),
            'selling_revenue_pln': round(selling_revenue, 2),
            'avg_cost_per_kwh': round(avg_cost_per_kwh, 4),
            'savings_percentage': round(savings_percentage, 1),
            'avg_confidence': round(avg_confidence, 4),
            'days_with_data': len(daily_summaries),
            'source_breakdown': source_breakdown,
            'daily_summaries': daily_summaries
        }
    
    def create_missing_snapshots(self, days_back: int = 30) -> int:
        """Create snapshots for any missing days in the last N days
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            Number of snapshots created
        """
        today = date.today()
        created_count = 0
        
        for i in range(days_back, 0, -1):
            target_date = today - timedelta(days=i)
            
            # Skip if snapshot already exists
            if self.snapshot_exists(target_date):
                continue
            
            # Try to create snapshot
            snapshot = self.create_daily_snapshot(target_date)
            if snapshot:
                created_count += 1
        
        logger.info(f"Created {created_count} missing snapshots for the last {days_back} days")
        return created_count


if __name__ == '__main__':
    # CLI tool for creating snapshots
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    manager = DailySnapshotManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'create-missing':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            count = manager.create_missing_snapshots(days_back=days)
            print(f"✅ Created {count} missing snapshots")
        
        elif command == 'monthly':
            year = int(sys.argv[2]) if len(sys.argv) > 2 else datetime.now().year
            month = int(sys.argv[3]) if len(sys.argv) > 3 else datetime.now().month
            summary = manager.get_monthly_summary(year, month)
            print(json.dumps(summary, indent=2))
        
        elif command == 'create':
            if len(sys.argv) > 2:
                target_date = datetime.strptime(sys.argv[2], '%Y-%m-%d').date()
            else:
                target_date = date.today() - timedelta(days=1)
            
            snapshot = manager.create_daily_snapshot(target_date)
            if snapshot:
                print(f"✅ Created snapshot for {target_date}")
                print(json.dumps(snapshot, indent=2))
            else:
                print(f"❌ No data found for {target_date}")
    else:
        print("Usage:")
        print("  python daily_snapshot_manager.py create-missing [days]")
        print("  python daily_snapshot_manager.py monthly [year] [month]")
        print("  python daily_snapshot_manager.py create [YYYY-MM-DD]")

