
import httpx
import logging
from datetime import datetime, timedelta
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from ..models import MarketPrice

logger = logging.getLogger(__name__)

PSE_API_URL = "https://api.raporty.pse.pl/api/energy-prices"
WARSAW_TZ = pytz.timezone("Europe/Warsaw")

async def fetch_and_store_prices(db: AsyncSession):
    """
    Fetches prices from PSE API and stores them in the database.
    Focuses on CSDAC (Day-Ahead) prices.
    """
    today_warsaw = datetime.now(WARSAW_TZ).strftime('%Y-%m-%d')
    url = f"{PSE_API_URL}?$filter=business_date ge '{today_warsaw}'"
    
    logger.info(f"Fetching market prices from PSE: {url}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            
        points = data.get("value", [])
        if not points:
            logger.warning("No price data returned from PSE API")
            return 0
            
        count = 0
        new_prices = []
        
        for item in points:
            price_raw = item.get("csdac_pln")
            if price_raw is None:
                continue
                
            # Parse Warsaw time
            dtime_str = item.get("dtime")
            try:
                # PSE returns different formats: "2024-06-14 00:15:00" or "2024-06-14 00:15"
                dtime_str = dtime_str.strip()
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
                    try:
                        naive_dt = datetime.strptime(dtime_str[:19] if ':' in dtime_str[16:] else dtime_str[:16], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Could not parse: {dtime_str}")
                warsaw_dt = WARSAW_TZ.localize(naive_dt)
                utc_dt = warsaw_dt.astimezone(pytz.UTC).replace(tzinfo=None)
            except Exception as e:
                logger.error(f"Failed to parse timestamp {dtime_str}: {e}")
                continue
                
            # Prepare model
            new_prices.append(MarketPrice(
                timestamp=utc_dt,
                price_pln_mwh=float(price_raw),
                source="PSE"
            ))
            count += 1

        if new_prices:
            # Simple "Upsert" strategy: Delete existing for these timestamps and insert new
            # For a production app, we'd use ON CONFLICT but SQLAlchemy CORE/Async is cleaner here
            timestamps = [p.timestamp for p in new_prices]
            await db.execute(delete(MarketPrice).where(MarketPrice.timestamp.in_(timestamps)))
            db.add_all(new_prices)
            await db.commit()
            logger.info(f"Successfully stored {count} market price points")
            
        return count

    except Exception as e:
        logger.error(f"Error in fetch_and_store_prices: {e}")
        return 0
