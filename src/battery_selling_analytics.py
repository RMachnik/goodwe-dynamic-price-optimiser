#!/usr/bin/env python3
"""
Battery Selling Analytics and Revenue Tracking

This module provides comprehensive analytics and revenue tracking for battery energy selling
with performance metrics, cost analysis, and financial reporting.

Usage:
    from battery_selling_analytics import BatterySellingAnalytics
    
    analytics = BatterySellingAnalytics(config)
    revenue_data = analytics.get_revenue_summary()
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import statistics


@dataclass
class SellingSessionRecord:
    """Record of a completed battery selling session"""
    session_id: str
    start_time: datetime
    end_time: datetime
    start_soc: float
    end_soc: float
    energy_sold_kwh: float
    average_price_pln: float
    revenue_pln: float
    selling_power_w: int
    duration_hours: float
    safety_checks_passed: bool
    risk_level: str


@dataclass
class DailyRevenueSummary:
    """Daily revenue and performance summary"""
    date: str
    total_sessions: int
    total_energy_sold_kwh: float
    total_revenue_pln: float
    average_price_pln: float
    peak_revenue_hour: int
    battery_cycles: int
    efficiency_percent: float
    safety_incidents: int


@dataclass
class MonthlyRevenueReport:
    """Monthly revenue and performance report"""
    month: str
    total_sessions: int
    total_energy_sold_kwh: float
    total_revenue_pln: float
    average_daily_revenue_pln: float
    best_day_revenue_pln: float
    worst_day_revenue_pln: float
    battery_cycles: int
    average_efficiency_percent: float
    safety_incidents: int
    roi_percent: float


class BatterySellingAnalytics:
    """Comprehensive analytics and revenue tracking for battery energy selling"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the analytics system"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Data storage
        self.data_dir = Path("out/battery_selling_analytics")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.battery_capacity_kwh = config.get('battery_management', {}).get('capacity_kwh', 10.0)
        self.discharge_efficiency = 0.95  # 95% efficiency
        self.expected_annual_revenue = config.get('battery_selling', {}).get('expected_annual_revenue_pln', 260.0)
        
        # Performance tracking
        self.session_records: List[SellingSessionRecord] = []
        self.daily_summaries: List[DailyRevenueSummary] = []
        self.monthly_reports: List[MonthlyRevenueReport] = []
        
        # Load existing data
        self._load_historical_data()
        
        self.logger.info("Battery Selling Analytics initialized")
        self.logger.info(f"  - Data directory: {self.data_dir}")
        self.logger.info(f"  - Expected annual revenue: {self.expected_annual_revenue} PLN")
    
    def _load_historical_data(self):
        """Load historical session records and summaries"""
        try:
            # Load session records
            sessions_file = self.data_dir / "session_records.json"
            if sessions_file.exists():
                with open(sessions_file, 'r') as f:
                    data = json.load(f)
                    self.session_records = [
                        SellingSessionRecord(
                            session_id=record['session_id'],
                            start_time=datetime.fromisoformat(record['start_time']),
                            end_time=datetime.fromisoformat(record['end_time']),
                            start_soc=record['start_soc'],
                            end_soc=record['end_soc'],
                            energy_sold_kwh=record['energy_sold_kwh'],
                            average_price_pln=record['average_price_pln'],
                            revenue_pln=record['revenue_pln'],
                            selling_power_w=record['selling_power_w'],
                            duration_hours=record['duration_hours'],
                            safety_checks_passed=record['safety_checks_passed'],
                            risk_level=record['risk_level']
                        )
                        for record in data
                    ]
                self.logger.info(f"Loaded {len(self.session_records)} historical session records")
            
            # Load daily summaries
            daily_file = self.data_dir / "daily_summaries.json"
            if daily_file.exists():
                with open(daily_file, 'r') as f:
                    data = json.load(f)
                    self.daily_summaries = [
                        DailyRevenueSummary(**summary) for summary in data
                    ]
                self.logger.info(f"Loaded {len(self.daily_summaries)} daily summaries")
            
            # Load monthly reports
            monthly_file = self.data_dir / "monthly_reports.json"
            if monthly_file.exists():
                with open(monthly_file, 'r') as f:
                    data = json.load(f)
                    self.monthly_reports = [
                        MonthlyRevenueReport(**report) for report in data
                    ]
                self.logger.info(f"Loaded {len(self.monthly_reports)} monthly reports")
                
        except Exception as e:
            self.logger.error(f"Failed to load historical data: {e}")
    
    def _save_data(self):
        """Save all data to files"""
        try:
            # Save session records
            sessions_file = self.data_dir / "session_records.json"
            with open(sessions_file, 'w') as f:
                json.dump([asdict(record) for record in self.session_records], f, indent=2, default=str)
            
            # Save daily summaries
            daily_file = self.data_dir / "daily_summaries.json"
            with open(daily_file, 'w') as f:
                json.dump([asdict(summary) for summary in self.daily_summaries], f, indent=2)
            
            # Save monthly reports
            monthly_file = self.data_dir / "monthly_reports.json"
            with open(monthly_file, 'w') as f:
                json.dump([asdict(report) for report in self.monthly_reports], f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save data: {e}")
    
    def record_session(self, session_data: Dict[str, Any]):
        """Record a completed selling session"""
        try:
            # Calculate energy sold
            energy_sold_kwh = (session_data['start_soc'] - session_data['end_soc']) / 100 * self.battery_capacity_kwh * self.discharge_efficiency
            
            # Create session record
            record = SellingSessionRecord(
                session_id=session_data['session_id'],
                start_time=session_data['start_time'],
                end_time=session_data['end_time'],
                start_soc=session_data['start_soc'],
                end_soc=session_data['end_soc'],
                energy_sold_kwh=energy_sold_kwh,
                average_price_pln=session_data['average_price_pln'],
                revenue_pln=energy_sold_kwh * session_data['average_price_pln'],
                selling_power_w=session_data['selling_power_w'],
                duration_hours=session_data['duration_hours'],
                safety_checks_passed=session_data['safety_checks_passed'],
                risk_level=session_data['risk_level']
            )
            
            # Add to records
            self.session_records.append(record)
            
            # Update daily summary
            self._update_daily_summary(record)
            
            # Save data
            self._save_data()
            
            self.logger.info(f"Recorded selling session {record.session_id}: {record.revenue_pln:.2f} PLN revenue")
            
        except Exception as e:
            self.logger.error(f"Failed to record session: {e}")
    
    def _update_daily_summary(self, record: SellingSessionRecord):
        """Update daily summary with new session record"""
        try:
            date_str = record.start_time.date().isoformat()
            
            # Find existing daily summary
            daily_summary = next(
                (summary for summary in self.daily_summaries if summary.date == date_str),
                None
            )
            
            if daily_summary:
                # Update existing summary
                daily_summary.total_sessions += 1
                daily_summary.total_energy_sold_kwh += record.energy_sold_kwh
                daily_summary.total_revenue_pln += record.revenue_pln
                daily_summary.battery_cycles += 1
                daily_summary.average_price_pln = daily_summary.total_revenue_pln / daily_summary.total_energy_sold_kwh if daily_summary.total_energy_sold_kwh > 0 else 0
                daily_summary.efficiency_percent = (daily_summary.total_energy_sold_kwh / (daily_summary.battery_cycles * self.battery_capacity_kwh * 0.3)) * 100  # 30% usable capacity
            else:
                # Create new daily summary
                daily_summary = DailyRevenueSummary(
                    date=date_str,
                    total_sessions=1,
                    total_energy_sold_kwh=record.energy_sold_kwh,
                    total_revenue_pln=record.revenue_pln,
                    average_price_pln=record.average_price_pln,
                    peak_revenue_hour=record.start_time.hour,
                    battery_cycles=1,
                    efficiency_percent=(record.energy_sold_kwh / (self.battery_capacity_kwh * 0.3)) * 100,
                    safety_incidents=0 if record.safety_checks_passed else 1
                )
                self.daily_summaries.append(daily_summary)
            
            # Update monthly report
            self._update_monthly_report(daily_summary)
            
        except Exception as e:
            self.logger.error(f"Failed to update daily summary: {e}")
    
    def _update_monthly_report(self, daily_summary: DailyRevenueSummary):
        """Update monthly report with daily summary"""
        try:
            month_str = daily_summary.date[:7]  # YYYY-MM format
            
            # Find existing monthly report
            monthly_report = next(
                (report for report in self.monthly_reports if report.month == month_str),
                None
            )
            
            if monthly_report:
                # Update existing report
                monthly_report.total_sessions += daily_summary.total_sessions
                monthly_report.total_energy_sold_kwh += daily_summary.total_energy_sold_kwh
                monthly_report.total_revenue_pln += daily_summary.total_revenue_pln
                monthly_report.battery_cycles += daily_summary.battery_cycles
                monthly_report.safety_incidents += daily_summary.safety_incidents
                
                # Recalculate averages
                days_in_month = len([s for s in self.daily_summaries if s.date.startswith(month_str)])
                monthly_report.average_daily_revenue_pln = monthly_report.total_revenue_pln / days_in_month if days_in_month > 0 else 0
                
                # Update best/worst day
                if daily_summary.total_revenue_pln > monthly_report.best_day_revenue_pln:
                    monthly_report.best_day_revenue_pln = daily_summary.total_revenue_pln
                if daily_summary.total_revenue_pln < monthly_report.worst_day_revenue_pln or monthly_report.worst_day_revenue_pln == 0:
                    monthly_report.worst_day_revenue_pln = daily_summary.total_revenue_pln
                
                # Calculate ROI (simplified)
                monthly_report.roi_percent = (monthly_report.total_revenue_pln / self.expected_annual_revenue * 12) * 100
            else:
                # Create new monthly report
                monthly_report = MonthlyRevenueReport(
                    month=month_str,
                    total_sessions=daily_summary.total_sessions,
                    total_energy_sold_kwh=daily_summary.total_energy_sold_kwh,
                    total_revenue_pln=daily_summary.total_revenue_pln,
                    average_daily_revenue_pln=daily_summary.total_revenue_pln,
                    best_day_revenue_pln=daily_summary.total_revenue_pln,
                    worst_day_revenue_pln=daily_summary.total_revenue_pln,
                    battery_cycles=daily_summary.battery_cycles,
                    average_efficiency_percent=daily_summary.efficiency_percent,
                    safety_incidents=daily_summary.safety_incidents,
                    roi_percent=(daily_summary.total_revenue_pln / self.expected_annual_revenue * 12) * 100
                )
                self.monthly_reports.append(monthly_report)
            
        except Exception as e:
            self.logger.error(f"Failed to update monthly report: {e}")
    
    def get_revenue_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get revenue summary for specified number of days"""
        try:
            cutoff_date = datetime.now().date() - timedelta(days=days)
            
            # Filter recent data
            recent_sessions = [
                record for record in self.session_records
                if record.start_time.date() >= cutoff_date
            ]
            
            recent_daily = [
                summary for summary in self.daily_summaries
                if datetime.fromisoformat(summary.date).date() >= cutoff_date
            ]
            
            # Calculate totals
            total_sessions = len(recent_sessions)
            total_energy_sold = sum(record.energy_sold_kwh for record in recent_sessions)
            total_revenue = sum(record.revenue_pln for record in recent_sessions)
            total_cycles = sum(record.energy_sold_kwh / (self.battery_capacity_kwh * 0.3) for record in recent_sessions)
            
            # Calculate averages
            average_price = total_revenue / total_energy_sold if total_energy_sold > 0 else 0
            average_daily_revenue = total_revenue / days if days > 0 else 0
            average_session_revenue = total_revenue / total_sessions if total_sessions > 0 else 0
            
            # Calculate efficiency
            theoretical_max_energy = total_cycles * self.battery_capacity_kwh * 0.3  # 30% usable capacity
            efficiency_percent = (total_energy_sold / theoretical_max_energy * 100) if theoretical_max_energy > 0 else 0
            
            # Project annual revenue
            projected_annual_revenue = average_daily_revenue * 365
            
            # Compare to expected
            revenue_vs_expected = (projected_annual_revenue / self.expected_annual_revenue * 100) if self.expected_annual_revenue > 0 else 0
            
            return {
                "period_days": days,
                "total_sessions": total_sessions,
                "total_energy_sold_kwh": round(total_energy_sold, 2),
                "total_revenue_pln": round(total_revenue, 2),
                "average_price_pln": round(average_price, 3),
                "average_daily_revenue_pln": round(average_daily_revenue, 2),
                "average_session_revenue_pln": round(average_session_revenue, 2),
                "total_cycles": round(total_cycles, 1),
                "efficiency_percent": round(efficiency_percent, 1),
                "projected_annual_revenue_pln": round(projected_annual_revenue, 2),
                "expected_annual_revenue_pln": self.expected_annual_revenue,
                "revenue_vs_expected_percent": round(revenue_vs_expected, 1),
                "best_day_revenue_pln": round(max([s.total_revenue_pln for s in recent_daily], default=0), 2),
                "worst_day_revenue_pln": round(min([s.total_revenue_pln for s in recent_daily], default=0), 2)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get revenue summary: {e}")
            return {}
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        try:
            if not self.session_records:
                return {"message": "No session data available"}
            
            # Calculate various metrics
            total_sessions = len(self.session_records)
            total_revenue = sum(record.revenue_pln for record in self.session_records)
            total_energy = sum(record.energy_sold_kwh for record in self.session_records)
            
            # Revenue trends
            recent_30_days = [r for r in self.session_records if r.start_time >= datetime.now() - timedelta(days=30)]
            recent_7_days = [r for r in self.session_records if r.start_time >= datetime.now() - timedelta(days=7)]
            
            # Safety metrics
            safety_incidents = len([r for r in self.session_records if not r.safety_checks_passed])
            safety_rate = ((total_sessions - safety_incidents) / total_sessions * 100) if total_sessions > 0 else 100
            
            # Efficiency metrics
            theoretical_max = total_sessions * self.battery_capacity_kwh * 0.3
            actual_efficiency = (total_energy / theoretical_max * 100) if theoretical_max > 0 else 0
            
            # Price analysis
            prices = [record.average_price_pln for record in self.session_records]
            avg_price = statistics.mean(prices) if prices else 0
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            
            # Time analysis
            peak_hours = {}
            for record in self.session_records:
                hour = record.start_time.hour
                peak_hours[hour] = peak_hours.get(hour, 0) + record.revenue_pln
            
            best_hour = max(peak_hours.items(), key=lambda x: x[1])[0] if peak_hours else 0
            
            return {
                "overall": {
                    "total_sessions": total_sessions,
                    "total_revenue_pln": round(total_revenue, 2),
                    "total_energy_sold_kwh": round(total_energy, 2),
                    "average_session_revenue_pln": round(total_revenue / total_sessions, 2) if total_sessions > 0 else 0
                },
                "recent_performance": {
                    "last_30_days_sessions": len(recent_30_days),
                    "last_30_days_revenue_pln": round(sum(r.revenue_pln for r in recent_30_days), 2),
                    "last_7_days_sessions": len(recent_7_days),
                    "last_7_days_revenue_pln": round(sum(r.revenue_pln for r in recent_7_days), 2)
                },
                "safety": {
                    "safety_incidents": safety_incidents,
                    "safety_rate_percent": round(safety_rate, 1),
                    "risk_level_distribution": {
                        "low": len([r for r in self.session_records if r.risk_level == "low"]),
                        "medium": len([r for r in self.session_records if r.risk_level == "medium"]),
                        "high": len([r for r in self.session_records if r.risk_level == "high"])
                    }
                },
                "efficiency": {
                    "actual_efficiency_percent": round(actual_efficiency, 1),
                    "theoretical_max_energy_kwh": round(theoretical_max, 2),
                    "average_energy_per_session_kwh": round(total_energy / total_sessions, 2) if total_sessions > 0 else 0
                },
                "pricing": {
                    "average_price_pln": round(avg_price, 3),
                    "min_price_pln": round(min_price, 3),
                    "max_price_pln": round(max_price, 3),
                    "best_selling_hour": best_hour
                },
                "projections": {
                    "projected_annual_revenue_pln": round(total_revenue / len(self.session_records) * 365, 2) if self.session_records else 0,
                    "expected_annual_revenue_pln": self.expected_annual_revenue,
                    "roi_percent": round((total_revenue / self.expected_annual_revenue * 100), 1) if self.expected_annual_revenue > 0 else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}
    
    def get_daily_breakdown(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily revenue breakdown for specified days"""
        try:
            cutoff_date = datetime.now().date() - timedelta(days=days)
            
            # Get daily summaries
            recent_daily = [
                summary for summary in self.daily_summaries
                if datetime.fromisoformat(summary.date).date() >= cutoff_date
            ]
            
            # Sort by date
            recent_daily.sort(key=lambda x: x.date)
            
            return [
                {
                    "date": summary.date,
                    "sessions": summary.total_sessions,
                    "energy_sold_kwh": round(summary.total_energy_sold_kwh, 2),
                    "revenue_pln": round(summary.total_revenue_pln, 2),
                    "average_price_pln": round(summary.average_price_pln, 3),
                    "efficiency_percent": round(summary.efficiency_percent, 1),
                    "cycles": summary.battery_cycles,
                    "safety_incidents": summary.safety_incidents
                }
                for summary in recent_daily
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to get daily breakdown: {e}")
            return []
    
    def export_data(self, format: str = "json") -> str:
        """Export all data in specified format"""
        try:
            if format.lower() == "json":
                export_data = {
                    "session_records": [asdict(record) for record in self.session_records],
                    "daily_summaries": [asdict(summary) for summary in self.daily_summaries],
                    "monthly_reports": [asdict(report) for report in self.monthly_reports],
                    "export_timestamp": datetime.now().isoformat()
                }
                
                export_file = self.data_dir / f"battery_selling_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(export_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                return str(export_file)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
        except Exception as e:
            self.logger.error(f"Failed to export data: {e}")
            return ""
