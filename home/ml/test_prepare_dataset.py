# Tests for the data‑preparation script

import pytest
from pathlib import Path
import sys

# Ensure the project root is on the import path for the module under test
PROJECT_ROOT = Path(r"d:/project/mobile_monitoring/")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from home.ml.prepare_dataset import prepare_dataset

def test_prepare_dataset_empty():
    """Empty input should return no rows and a summary with zeros."""
    rows, summary = prepare_dataset({})
    assert rows == []
    assert summary["total_sessions"] == 0
    assert summary["total_records"] == 0
    assert summary["processed"] == 0
    assert summary["skipped"] == 0

def test_prepare_dataset_malformed_records():
    """Records missing required fields are skipped and counted as missing."""
    raw = {
        "session1": {
            "rec1": {
                "app_name": "YouTube",
                "category": "Non-Educational",
                "duration": 120,
                "timestamp": 1729657200000,
                "student_id": "stu123"
            },
            "rec2": {
                "app_name": "Google Docs",
                # Missing category
                "duration": 60,
                "timestamp": 1729657300000,
                "student_id": "stu124"
            },
            "rec3": {
                "app_name": "Chrome",
                "category": "Educational",
                # Missing duration
                "timestamp": 1729657400000,
                "student_id": "stu125"
            }
        }
    }
    rows, summary = prepare_dataset(raw)
    # Only the fully valid record should be processed
    assert len(rows) == 1
    assert summary["processed"] == 1
    # Two records should be skipped, counted in missing_counts
    assert summary["skipped"] == 2
    assert summary["missing_counts"].get("category", 0) == 1
    assert summary["missing_counts"].get("duration", 0) == 1


def test_prepare_dataset_missing_student_id():
    """Records missing student_id are skipped and counted."""
    raw = {
        "session1": {
            "rec1": {
                "app_name": "YouTube",
                "category": "Non-Educational",
                "duration": 120,
                "timestamp": 1729657200000
                # student_id missing
            }
        }
    }
    rows, summary = prepare_dataset(raw)
    assert len(rows) == 0
    assert summary["skipped"] == 1
    assert summary["missing_counts"].get("student_id", 0) == 1

def test_prepare_dataset_future_timestamp():
    """Records with future timestamps are still processed."""
    future_ts = 9999999999999
    raw = {
        "session1": {
            "rec1": {
                "app_name": "YouTube",
                "category": "Non-Educational",
                "duration": 120,
                "timestamp": future_ts,
                "student_id": "stu999"
            }
        }
    }
    rows, summary = prepare_dataset(raw)
    assert len(rows) == 1
    assert summary["processed"] == 1
