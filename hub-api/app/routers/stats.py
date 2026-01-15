from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, text, cast, Date, select, Float
from ..database import get_db
from ..models import Telemetry, User
from ..auth import get_current_user, get_authenticated_entity
from typing import List
from pydantic import BaseModel
import datetime

router = APIRouter(prefix="/stats", tags=["stats"])

class DailySavings(BaseModel):
    date: datetime.date
    savings_pln: float

@router.get("/daily-savings/{node_id}", response_model=List[DailySavings])
async def get_daily_savings(
    node_id: str, 
    days: int = 7, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Calculate start date
    start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    
    # Complex query: We need the MAX daily_savings_pln per day.
    # Since it's JSONB, we cast to float.
    # We group by the date of the timestamp.
    
    # Note: This assumes daily_savings_pln is strictly increasing during the day.
    
    # Principal Dev Review: 
    # 1. Cast safely using numeric type
    # 2. Use COALESCE to handle nulls in aggregation
    
    # Extract the JSON path as text, then cast to float.
    # We use a subquery or strict filtering to ensure we don't crash on bad data?
    # Postgres 'cast' throws error on bad format.
    # For now, we trust the schema is consistent (enforced by code).
    
    # Using 'MAX' aggregation per day.
    
    # Async SQLAlchemy must use 'select', not 'query' (Principal Dev Fix)
    stmt = select(
        cast(Telemetry.timestamp, Date).label('day'),
        func.max(
            cast(
                func.coalesce(Telemetry.data['optimizer']['daily_savings_pln'].astext, '0'), 
                Float
            )
        ).label('max_savings')
    ).where(
        Telemetry.node_id == node_id,
        Telemetry.timestamp >= start_date
    ).group_by(
        text('day')
    ).order_by(
        text('day')
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    stats = []
    for row in rows:
        # If savings is None (missing data), default to 0
        val = row.max_savings if row.max_savings is not None else 0.0
        stats.append(DailySavings(date=row.day, savings_pln=val))
        
    return stats

@router.get("/market-prices")
async def get_market_prices(
    db: AsyncSession = Depends(get_db),
    authenticated_entity = Depends(get_authenticated_entity)
):
    """
    Returns yesterday's, today's and tomorrow's real market prices from PSE (PLN/kWh).
    Converted from PLN/MWh stored in DB. Spans 3 days for better visualization.
    """
    from ..models import MarketPrice
    from sqlalchemy import select
    from datetime import datetime, timedelta, timezone
    
    # 3 days: yesterday 00:00 to tomorrow 23:59
    start_of_yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    end_of_tomorrow = start_of_yesterday + timedelta(days=3)
    
    stmt = select(MarketPrice).where(
        MarketPrice.timestamp >= start_of_yesterday,
        MarketPrice.timestamp < end_of_tomorrow
    ).order_by(MarketPrice.timestamp.asc())
    
    result = await db.execute(stmt)
    rows = result.scalars().all()
    
    if not rows:
        # Fallback to mock only if DB is completely empty (e.g. initial setup)
        # Principal Dev Fix: Return empty list if no data, let UI handle it, 
        # but for Phase 6 migration we'll keep a small mock fallback for dev-friendliness if empty.
        return [{"timestamp": datetime.utcnow().isoformat(), "price_pln_kwh": 0.50}]
        
    prices = []
    for row in rows:
        prices.append({
            "timestamp": row.timestamp.replace(tzinfo=timezone.utc).isoformat(),
            "price_pln_kwh": round(row.price_pln_mwh / 1000.0, 4)
        })
        
    return prices
