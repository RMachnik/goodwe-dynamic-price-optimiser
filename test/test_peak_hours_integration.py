#!/usr/bin/env python3
import sys
from pathlib import Path
import json
from datetime import datetime
import asyncio
from unittest.mock import AsyncMock, patch

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pse_peak_hours_collector import PSEPeakHoursCollector, USAGE_CODE_TO_LABEL


def test_usage_code_mapping_complete():
    assert 0 in USAGE_CODE_TO_LABEL
    assert 1 in USAGE_CODE_TO_LABEL
    assert 2 in USAGE_CODE_TO_LABEL
    assert 3 in USAGE_CODE_TO_LABEL


def test_parse_and_cache():
    """Test PSE peak hours parsing and caching with async support"""
    # Prepare fake payload for a single active day
    payload = {
        "value": [
            {"dtime": "2025-09-20 19:00", "usage_fcst": 3, "is_active": True},
            {"dtime": "2025-09-20 11:00", "usage_fcst": 1, "is_active": True},
        ]
    }

    cfg = {
        "pse_peak_hours": {
            "enabled": True,
            "update_interval_minutes": 60,
        }
    }
    
    # Mock the aiohttp response
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=payload)
        mock_response.raise_for_status = AsyncMock()
        mock_get.return_value.__aenter__.return_value = mock_response
        
        c = PSEPeakHoursCollector(cfg)
        
        # FIX: Use asyncio.run() to await the coroutine
        out = asyncio.run(c.fetch_peak_hours())
        assert len(out) == 2

        # Check mapping
        reduction = [o for o in out if o.code == 3]
        assert reduction and reduction[0].label == "WYMAGANE OGRANICZANIE"

        # Cache hit should avoid second fetch - reset the mock
        mock_get.reset_mock()
        
        # FIX: Use asyncio.run() to await the coroutine
        out2 = asyncio.run(c.fetch_peak_hours())
        assert len(out2) == 2
        # Cache should prevent network call
        mock_get.assert_not_called()


