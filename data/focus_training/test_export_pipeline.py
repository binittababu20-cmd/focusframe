"""
Unit tests for FocusFrame export pipeline session span calculations.
Verifies safeguard 1: correct session-span calculation using event end timestamps
and event start times (end timestamp - duration) for single-event and multi-event sessions.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add data/focus_training to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from export_pipeline import calculate_session_span, norm_category, parse_timestamp


def test_calculate_session_span_empty():
    """Empty record list returns empty strings and 0.0 span."""
    start_iso, end_iso, span = calculate_session_span([])
    assert start_iso == ""
    assert end_iso == ""
    assert span == 0.0


def test_calculate_session_span_single_event():
    """
    Single-event session:
    Event ends at 2026-10-15T10:05:00Z (ts = 1792058700) with duration = 300 seconds.
    Earliest start is 1792058700 - 300 = 1792058400 (2026-10-15T10:00:00Z).
    Span must be 300.0 seconds (not 0.0 seconds).
    """
    recs = [
        {
            "_sec_ts": 1792058700.0,
            "duration_seconds": 300.0,
            "timestamp_iso": "2026-10-15T10:05:00Z"
        }
    ]
    start_iso, end_iso, span = calculate_session_span(recs)
    assert span == 300.0
    assert start_iso == "2026-10-15T10:00:00Z"
    assert end_iso == "2026-10-15T10:05:00Z"


def test_calculate_session_span_multiple_events_contiguous():
    """
    Multiple events back-to-back:
    Event 1: ends at 1792058700 (10:05:00Z), duration 300s (starts at 10:00:00Z)
    Event 2: ends at 1792059300 (10:15:00Z), duration 600s (starts at 10:05:00Z)
    Total span: 900.0 seconds (from 10:00:00Z to 10:15:00Z).
    """
    recs = [
        {
            "_sec_ts": 1792058700.0,
            "duration_seconds": 300.0,
            "timestamp_iso": "2026-10-15T10:05:00Z"
        },
        {
            "_sec_ts": 1792059300.0,
            "duration_seconds": 600.0,
            "timestamp_iso": "2026-10-15T10:15:00Z"
        }
    ]
    start_iso, end_iso, span = calculate_session_span(recs)
    assert span == 900.0
    assert start_iso == "2026-10-15T10:00:00Z"
    assert end_iso == "2026-10-15T10:15:00Z"


def test_calculate_session_span_multiple_events_with_idle_gap():
    """
    Multiple events with idle gap between them:
    Event 1: ends at 10:05:00Z, duration 300s (starts at 10:00:00Z).
    Idle gap: 10:05:00Z to 10:10:00Z (300s idle).
    Event 2: ends at 10:20:00Z, duration 600s (starts at 10:10:00Z).
    Session span from earliest start (10:00:00Z) to latest end (10:20:00Z) is 1200.0s.
    Total active usage is 900.0s. Active ratio is 900/1200 = 0.75.
    """
    recs = [
        {
            "_sec_ts": 1792058700.0,  # 10:05:00
            "duration_seconds": 300.0,
        },
        {
            "_sec_ts": 1792059600.0,  # 10:20:00
            "duration_seconds": 600.0,
        }
    ]
    start_iso, end_iso, span = calculate_session_span(recs)
    assert span == 1200.0
    assert start_iso == "2026-10-15T10:00:00Z"
    assert end_iso == "2026-10-15T10:20:00Z"


def test_calculate_session_span_negative_or_zero_duration_guard():
    """Defensive handling for records with zero duration."""
    recs = [
        {
            "_sec_ts": 1792058700.0,
            "duration_seconds": 0.0,
        }
    ]
    start_iso, end_iso, span = calculate_session_span(recs)
    assert span == 0.0
    assert start_iso == "2026-10-15T10:05:00Z"
    assert end_iso == "2026-10-15T10:05:00Z"
