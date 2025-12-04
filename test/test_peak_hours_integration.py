#!/usr/bin/env python3
"""
Tests for PSE Peak Hours Integration

This module tests the integration with Polish Power System (PSE) peak hours data,
including async data fetching, caching behavior, and usage code mappings.

The PSE system provides forecasts for grid load and usage patterns, which are used
to optimize battery charging and discharging decisions.
"""
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
    """
    Verify that all PSE usage codes are properly mapped to labels.
    
    Tests that the USAGE_CODE_TO_LABEL dictionary contains mappings for
    all expected usage codes (0-3) used by the PSE system for grid load classification.
    
    Expected codes:
    - 0: Normal usage
    - 1: Increased usage
    - 2: High usage warning
    - 3: Critical usage reduction required
    """
    assert 0 in USAGE_CODE_TO_LABEL
    assert 1 in USAGE_CODE_TO_LABEL
    assert 2 in USAGE_CODE_TO_LABEL
    assert 3 in USAGE_CODE_TO_LABEL


def test_parse_and_cache():
    """
    Test PSE peak hours parsing and caching with async support.
    
    This test verifies:
    1. Async fetching of peak hours data from PSE API
    2. Correct parsing of usage forecast codes and labels
    3. Caching behavior to avoid redundant API calls
    
    Scenario:
    - Mock PSE API response with 2 forecast entries
    - Fetch data and verify correct parsing
    - Second fetch should use cache (no API call)
    
    Expected behavior:
    - First call: Makes API request, returns 2 peak hour records
    - Usage code 3 maps to "WYMAGANE OGRANICZANIE" label
    - Second call: Uses cache, no API request made
    """
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


