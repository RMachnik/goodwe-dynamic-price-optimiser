#!/usr/bin/env python3
import sys
from pathlib import Path
import json
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pse_peak_hours_collector import PSEPeakHoursCollector, USAGE_CODE_TO_LABEL


def test_usage_code_mapping_complete():
    assert 0 in USAGE_CODE_TO_LABEL
    assert 1 in USAGE_CODE_TO_LABEL
    assert 2 in USAGE_CODE_TO_LABEL
    assert 3 in USAGE_CODE_TO_LABEL


def test_parse_and_cache(monkeypatch):
    # Prepare fake payload for a single active day
    payload = {
        "value": [
            {"dtime": "2025-09-20 19:00", "usage_fcst": 3, "is_active": True},
            {"dtime": "2025-09-20 11:00", "usage_fcst": 1, "is_active": True},
        ]
    }

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    def fake_get(url, timeout=15):  # noqa: ARG001
        return FakeResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    cfg = {
        "pse_peak_hours": {
            "enabled": True,
            "update_interval_minutes": 60,
        }
    }
    c = PSEPeakHoursCollector(cfg)
    out = c.fetch_peak_hours()
    assert len(out) == 2

    # Check mapping
    reduction = [o for o in out if o.code == 3]
    assert reduction and reduction[0].label == "REQUIRED REDUCTION"

    # Cache hit should avoid second fetch
    called = {"count": 0}

    def fake_get_count(url, timeout=15):  # noqa: ARG001
        called["count"] += 1
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get_count)
    out2 = c.fetch_peak_hours()
    assert len(out2) == 2
    assert called["count"] == 0  # no network due to cache


