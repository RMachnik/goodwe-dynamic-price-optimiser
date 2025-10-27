#!/usr/bin/env python3
import sys
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from master_coordinator import MultiFactorDecisionEngine


class DummyCollector:
    def __init__(self, code):
        from types import SimpleNamespace
        self._status = SimpleNamespace(
            time=datetime.now().replace(minute=0, second=0, microsecond=0),
            code=code,
            label="X",
        )

    def has_data(self):
        return True

    def get_status_for_time(self, dt):  # noqa: ARG002
        return self._status


def _mk_engine():
    cfg = {
        "coordinator": {},
    }
    # charging_controller not needed for policy function
    return MultiFactorDecisionEngine(cfg, None)


def test_required_reduction_blocks_start():
    eng = _mk_engine()
    eng.peak_hours_collector = DummyCollector(3)
    assert eng._apply_peak_hours_policy("start_charging") == "none"


def test_recommended_saving_defers_start():
    eng = _mk_engine()
    eng.peak_hours_collector = DummyCollector(2)
    assert eng._apply_peak_hours_policy("start_charging") == "none"


def test_normal_no_change():
    eng = _mk_engine()
    eng.peak_hours_collector = DummyCollector(0)
    assert eng._apply_peak_hours_policy("start_charging") == "start_charging"


