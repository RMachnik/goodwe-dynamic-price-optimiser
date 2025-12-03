#!/usr/bin/env python3
"""
PSE Peak Hours (Kompas Energetyczny) collector using official OData endpoint `pdgsz`.

This module intentionally avoids any side-effects during initialization. It does
NOT perform network calls unless `fetch_peak_hours()` is called explicitly by
the orchestrator. This keeps the core decision engine deterministic for tests.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PeakHourStatus:
    """Represents Kompas status for a single hour."""
    time: datetime
    code: int
    label: str


USAGE_CODE_TO_LABEL: Dict[int, str] = {
    0: "ZALECANE UŻYTKOWANIE",
    1: "NORMALNE UŻYTKOWANIE",
    2: "ZALECANE OSZCZĘDZANIE",
    3: "WYMAGANE OGRANICZANIE",
}


class PSEPeakHoursCollector:
    """Collector for PSE Peak Hours (Kompas) via pdgsz endpoint."""

    def __init__(self, config: Dict[str, Any]):
        cfg = config.get("pse_peak_hours", {}) or {}
        self.enabled: bool = bool(cfg.get("enabled", False))
        self.api_url: str = cfg.get("api_url", "https://api.raporty.pse.pl/api/pdgsz")
        self.update_interval_minutes: int = int(cfg.get("update_interval_minutes", 60))

        fb = cfg.get("fallback", {}) or {}
        self.retry_attempts: int = int(fb.get("retry_attempts", 3))
        self.retry_delay_seconds: int = int(fb.get("retry_delay_seconds", 60))

        # runtime cache
        self._cache_day: Optional[str] = None
        self._cache_timestamp: Optional[float] = None
        self._statuses: List[PeakHourStatus] = []

        logger.info(
            "PSE Peak Hours Collector initialized (enabled: %s)", self.enabled
        )

    def has_data(self) -> bool:
        """Whether collector currently holds any statuses in cache."""
        return bool(self._statuses)

    def get_status_for_time(self, dt: datetime) -> Optional[PeakHourStatus]:
        """Return cached status for a specific hour (if available)."""
        if not self._statuses:
            return None
        hour_dt = dt.replace(minute=0, second=0, microsecond=0)
        for s in self._statuses:
            if s.time == hour_dt:
                return s
        return None

    async def fetch_peak_hours(self, business_day: Optional[date] = None) -> List[PeakHourStatus]:
        """Fetch peak-hour statuses for a given `business_day` (async).

        The function is resilient and will retry on transient network errors. It
        populates the in-memory cache and returns the parsed list.
        """
        if not self.enabled:
            logger.debug("Peak Hours collection disabled")
            return []

        target_day = (business_day or date.today()).isoformat()
        # reuse fresh cache
        if (
            self._cache_day == target_day
            and self._cache_timestamp
            and (time.time() - self._cache_timestamp) < self.update_interval_minutes * 60
        ):
            return self._statuses

        query = (
            f"{self.api_url}?$filter=business_date eq '{target_day}' and is_active eq true"
            f"&$orderby=dtime asc&$first=20000"
        )

        last_error: Optional[Exception] = None
        for attempt in range(self.retry_attempts):
            try:
                # Use aiohttp if available, otherwise fallback to requests
                if AIOHTTP_AVAILABLE:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(query, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            resp.raise_for_status()
                            payload = await resp.json()
                else:
                    import requests
                    resp = requests.get(query, timeout=15)
                    resp.raise_for_status()
                    payload = resp.json()
                
                values = payload.get("value", [])
                statuses: List[PeakHourStatus] = []
                for item in values:
                    dtime_str = item.get("dtime")
                    code = int(item.get("usage_fcst", 0))
                    if not dtime_str:
                        continue
                    # Accept both with and without seconds
                    try:
                        if dtime_str.count(":") == 2:
                            dt = datetime.strptime(dtime_str, "%Y-%m-%d %H:%M:%S")
                        else:
                            dt = datetime.strptime(dtime_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        logger.warning("Unparsable dtime in pdgsz: %s", dtime_str)
                        continue
                    statuses.append(
                        PeakHourStatus(time=dt, code=code, label=USAGE_CODE_TO_LABEL.get(code, "UNKNOWN"))
                    )

                # update cache
                self._statuses = statuses
                self._cache_day = target_day
                self._cache_timestamp = time.time()
                logger.info("Fetched %d peak-hour statuses for %s", len(statuses), target_day)
                return statuses
            except Exception as e:
                last_error = e
                logger.error(
                    "Peak Hours fetch failed (attempt %d/%d): %s",
                    attempt + 1,
                    self.retry_attempts,
                    e,
                )
                if attempt + 1 < self.retry_attempts:
                    await asyncio.sleep(self.retry_delay_seconds)

        if last_error:
            logger.warning("Peak Hours fetch ultimately failed: %s", last_error)
        # keep previous cache if present
        return self._statuses


