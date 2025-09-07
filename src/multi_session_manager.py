#!/usr/bin/env python3
"""
GoodWe Dynamic Price Optimiser - Multi-Session Charging Manager
Manages multiple charging sessions per day with intelligent scheduling
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from polish_electricity_analyzer import PolishElectricityAnalyzer, ChargingWindow

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class ChargingSession:
    """Represents a single charging session"""
    session_id: str
    start_time: datetime
    end_time: datetime
    duration_hours: float
    target_energy_kwh: float
    status: str  # 'planned', 'active', 'completed', 'cancelled', 'failed'
    priority: int  # 1=highest, 3=lowest
    estimated_cost_pln: float
    estimated_savings_pln: float
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_energy_kwh: Optional[float] = None
    actual_cost_pln: Optional[float] = None

@dataclass
class DailyChargingPlan:
    """Represents a complete daily charging plan"""
    date: datetime
    total_sessions: int
    total_duration_hours: float
    total_estimated_energy_kwh: float
    total_estimated_cost_pln: float
    total_estimated_savings_pln: float
    sessions: List[ChargingSession]
    created_at: datetime
    status: str  # 'planned', 'active', 'completed', 'cancelled'

class MultiSessionManager:
    """Manages multiple charging sessions per day"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the multi-session manager"""
        self.config = config
        self.multi_session_config = config.get('coordinator', {}).get('multi_session_charging', {})
        
        # Configuration parameters
        self.enabled = self.multi_session_config.get('enabled', True)
        self.max_sessions_per_day = self.multi_session_config.get('max_sessions_per_day', 3)
        self.min_session_duration_hours = self.multi_session_config.get('min_session_duration_hours', 1.0)
        self.max_session_duration_hours = self.multi_session_config.get('max_session_duration_hours', 4.0)
        self.min_savings_percent = self.multi_session_config.get('min_savings_percent', 15.0)
        self.session_gap_minutes = self.multi_session_config.get('session_gap_minutes', 30)
        self.daily_planning_time = self.multi_session_config.get('daily_planning_time', '06:00')
        
        # State management
        self.current_plan: Optional[DailyChargingPlan] = None
        self.active_session: Optional[ChargingSession] = None
        self.session_history: List[ChargingSession] = []
        
        # Data directory for persistence
        self.data_dir = Path("out/multi_session_data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize price analyzer
        self.price_analyzer = PolishElectricityAnalyzer()
        
        logger.info(f"Multi-session manager initialized: enabled={self.enabled}, max_sessions={self.max_sessions_per_day}")
    
    async def create_daily_plan(self, date: datetime = None) -> Optional[DailyChargingPlan]:
        """Create a daily charging plan for the specified date"""
        if not self.enabled:
            logger.info("Multi-session charging is disabled")
            return None
            
        if date is None:
            date = datetime.now().date()
        
        logger.info(f"Creating daily charging plan for {date}")
        
        try:
            # Fetch price data for the date
            price_data = await self._fetch_price_data_for_date(date)
            if not price_data:
                logger.warning(f"No price data available for {date}")
                return None
            
            # Find optimal charging windows
            charging_windows = self.price_analyzer.get_daily_charging_schedule(
                target_charge_hours=self.max_session_duration_hours,
                max_windows=self.max_sessions_per_day
            )
            
            if not charging_windows:
                logger.info(f"No optimal charging windows found for {date}")
                return None
            
            # Convert windows to charging sessions
            sessions = []
            for i, window in enumerate(charging_windows):
                session = ChargingSession(
                    session_id=f"{date.strftime('%Y%m%d')}_{i+1}",
                    start_time=window.start_time,
                    end_time=window.end_time,
                    duration_hours=window.duration_minutes / 60.0,
                    target_energy_kwh=self._estimate_energy_for_session(window.duration_minutes / 60.0),
                    status='planned',
                    priority=i + 1,
                    estimated_cost_pln=self._calculate_session_cost(window),
                    estimated_savings_pln=self._calculate_session_savings(window),
                    created_at=datetime.now()
                )
                sessions.append(session)
            
            # Create daily plan
            plan = DailyChargingPlan(
                date=date,
                total_sessions=len(sessions),
                total_duration_hours=sum(s.duration_hours for s in sessions),
                total_estimated_energy_kwh=sum(s.target_energy_kwh for s in sessions),
                total_estimated_cost_pln=sum(s.estimated_cost_pln for s in sessions),
                total_estimated_savings_pln=sum(s.estimated_savings_pln for s in sessions),
                sessions=sessions,
                created_at=datetime.now(),
                status='planned'
            )
            
            # Save plan to file
            await self._save_daily_plan(plan)
            
            self.current_plan = plan
            logger.info(f"Created daily plan with {len(sessions)} sessions, total savings: {plan.total_estimated_savings_pln:.2f} PLN")
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to create daily plan for {date}: {e}")
            return None
    
    async def get_next_session(self) -> Optional[ChargingSession]:
        """Get the next scheduled charging session"""
        if not self.current_plan or not self.current_plan.sessions:
            return None
        
        now = datetime.now()
        
        # Find the next planned session
        for session in self.current_plan.sessions:
            if session.status == 'planned' and session.start_time > now:
                return session
        
        # Check if there's a session that should start now
        for session in self.current_plan.sessions:
            if (session.status == 'planned' and 
                session.start_time <= now <= session.end_time):
                return session
        
        return None
    
    async def start_session(self, session: ChargingSession) -> bool:
        """Start a charging session"""
        try:
            logger.info(f"Starting charging session {session.session_id}")
            
            session.status = 'active'
            session.started_at = datetime.now()
            self.active_session = session
            
            # Update plan status
            if self.current_plan:
                self.current_plan.status = 'active'
            
            # Save updated plan
            await self._save_daily_plan(self.current_plan)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start session {session.session_id}: {e}")
            session.status = 'failed'
            return False
    
    async def complete_session(self, session: ChargingSession, actual_energy_kwh: float = None, actual_cost_pln: float = None) -> bool:
        """Complete a charging session"""
        try:
            logger.info(f"Completing charging session {session.session_id}")
            
            session.status = 'completed'
            session.completed_at = datetime.now()
            session.actual_energy_kwh = actual_energy_kwh
            session.actual_cost_pln = actual_cost_pln
            
            # Add to history
            self.session_history.append(session)
            
            # Clear active session
            if self.active_session and self.active_session.session_id == session.session_id:
                self.active_session = None
            
            # Check if all sessions are completed
            if self.current_plan:
                remaining_sessions = [s for s in self.current_plan.sessions if s.status == 'planned']
                if not remaining_sessions:
                    self.current_plan.status = 'completed'
                    logger.info("All daily charging sessions completed")
            
            # Save updated plan
            await self._save_daily_plan(self.current_plan)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete session {session.session_id}: {e}")
            return False
    
    async def cancel_session(self, session: ChargingSession, reason: str = "User cancelled") -> bool:
        """Cancel a charging session"""
        try:
            logger.info(f"Cancelling charging session {session.session_id}: {reason}")
            
            session.status = 'cancelled'
            session.completed_at = datetime.now()
            
            # Clear active session if this was the active one
            if self.active_session and self.active_session.session_id == session.session_id:
                self.active_session = None
            
            # Save updated plan
            await self._save_daily_plan(self.current_plan)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel session {session.session_id}: {e}")
            return False
    
    def get_current_plan_status(self) -> Dict[str, Any]:
        """Get current plan status"""
        if not self.current_plan:
            return {
                'has_plan': False,
                'status': 'no_plan',
                'message': 'No daily charging plan available'
            }
        
        now = datetime.now()
        active_sessions = [s for s in self.current_plan.sessions if s.status == 'active']
        completed_sessions = [s for s in self.current_plan.sessions if s.status == 'completed']
        planned_sessions = [s for s in self.current_plan.sessions if s.status == 'planned']
        
        return {
            'has_plan': True,
            'date': self.current_plan.date.strftime('%Y-%m-%d'),
            'status': self.current_plan.status,
            'total_sessions': self.current_plan.total_sessions,
            'completed_sessions': len(completed_sessions),
            'active_sessions': len(active_sessions),
            'planned_sessions': len(planned_sessions),
            'total_estimated_savings_pln': self.current_plan.total_estimated_savings_pln,
            'active_session': {
                'session_id': self.active_session.session_id,
                'start_time': self.active_session.start_time.isoformat(),
                'end_time': self.active_session.end_time.isoformat()
            } if self.active_session else None,
            'next_session': {
                'session_id': planned_sessions[0].session_id,
                'start_time': planned_sessions[0].start_time.isoformat(),
                'end_time': planned_sessions[0].end_time.isoformat()
            } if planned_sessions else None
        }
    
    async def _fetch_price_data_for_date(self, date: datetime) -> Optional[Dict]:
        """Fetch price data for a specific date"""
        try:
            # This would integrate with the existing price fetching logic
            # For now, we'll use the price analyzer's existing method
            price_data = await self.price_analyzer.fetch_price_data()
            return price_data
        except Exception as e:
            logger.error(f"Failed to fetch price data for {date}: {e}")
            return None
    
    def _estimate_energy_for_session(self, duration_hours: float) -> float:
        """Estimate energy that can be charged in a session"""
        # Assume average charging power of 3kW (configurable)
        charging_power_kw = 3.0
        return duration_hours * charging_power_kw
    
    def _calculate_session_cost(self, window: ChargingWindow) -> float:
        """Calculate estimated cost for a charging session"""
        energy_kwh = self._estimate_energy_for_session(window.duration_minutes / 60.0)
        return energy_kwh * (window.avg_price / 1000.0)  # Convert from PLN/MWh to PLN/kWh
    
    def _calculate_session_savings(self, window: ChargingWindow) -> float:
        """Calculate estimated savings for a charging session"""
        # This would compare against average daily price
        # For now, use the savings_per_mwh from the window
        energy_kwh = self._estimate_energy_for_session(window.duration_minutes / 60.0)
        return energy_kwh * (window.savings_per_mwh / 1000.0)
    
    async def _save_daily_plan(self, plan: DailyChargingPlan):
        """Save daily plan to file"""
        try:
            filename = f"daily_plan_{plan.date.strftime('%Y%m%d')}.json"
            filepath = self.data_dir / filename
            
            # Convert to serializable format
            plan_data = {
                'date': plan.date.isoformat(),
                'total_sessions': plan.total_sessions,
                'total_duration_hours': plan.total_duration_hours,
                'total_estimated_energy_kwh': plan.total_estimated_energy_kwh,
                'total_estimated_cost_pln': plan.total_estimated_cost_pln,
                'total_estimated_savings_pln': plan.total_estimated_savings_pln,
                'sessions': [asdict(session) for session in plan.sessions],
                'created_at': plan.created_at.isoformat(),
                'status': plan.status
            }
            
            with open(filepath, 'w') as f:
                json.dump(plan_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save daily plan: {e}")
    
    async def _load_daily_plan(self, date: datetime) -> Optional[DailyChargingPlan]:
        """Load daily plan from file"""
        try:
            filename = f"daily_plan_{date.strftime('%Y%m%d')}.json"
            filepath = self.data_dir / filename
            
            if not filepath.exists():
                return None
            
            with open(filepath, 'r') as f:
                plan_data = json.load(f)
            
            # Reconstruct sessions
            sessions = []
            for session_data in plan_data['sessions']:
                session = ChargingSession(
                    session_id=session_data['session_id'],
                    start_time=datetime.fromisoformat(session_data['start_time']),
                    end_time=datetime.fromisoformat(session_data['end_time']),
                    duration_hours=session_data['duration_hours'],
                    target_energy_kwh=session_data['target_energy_kwh'],
                    status=session_data['status'],
                    priority=session_data['priority'],
                    estimated_cost_pln=session_data['estimated_cost_pln'],
                    estimated_savings_pln=session_data['estimated_savings_pln'],
                    created_at=datetime.fromisoformat(session_data['created_at']),
                    started_at=datetime.fromisoformat(session_data['started_at']) if session_data.get('started_at') else None,
                    completed_at=datetime.fromisoformat(session_data['completed_at']) if session_data.get('completed_at') else None,
                    actual_energy_kwh=session_data.get('actual_energy_kwh'),
                    actual_cost_pln=session_data.get('actual_cost_pln')
                )
                sessions.append(session)
            
            # Reconstruct plan
            plan = DailyChargingPlan(
                date=datetime.fromisoformat(plan_data['date']).date(),
                total_sessions=plan_data['total_sessions'],
                total_duration_hours=plan_data['total_duration_hours'],
                total_estimated_energy_kwh=plan_data['total_estimated_energy_kwh'],
                total_estimated_cost_pln=plan_data['total_estimated_cost_pln'],
                total_estimated_savings_pln=plan_data['total_estimated_savings_pln'],
                sessions=sessions,
                created_at=datetime.fromisoformat(plan_data['created_at']),
                status=plan_data['status']
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to load daily plan for {date}: {e}")
            return None
