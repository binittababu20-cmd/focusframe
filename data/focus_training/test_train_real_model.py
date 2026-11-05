"""
Unit tests for data/focus_training/train_real_model.py

Tests:
  - Data gates (insufficient labels, single class, imbalance, no file)
  - Feature engineering (span_minutes, numeric coercion)
  - Cross-validation runs without error on minimal data
  - Full pipeline train+evaluate on synthetic labeled data
  - ai_model.py: falls back to demo when real model absent
  - ai_model.py: prefers real model when present
  - ai_model.py: returns correct is_demo_model flag for each model
  - Model file safety: real model path != demo model path
"""

import sys
import csv
import json
import os
import tempfile
import importlib
from pathlib import Path
from unittest import mock
from io import StringIO

import pytest

# Make sure the training module is importable
TRAINING_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TRAINING_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---- helpers -----------------------------------------------------------------

def make_labeled_csv(rows, path):
    """Write rows (list of dicts) to a labeled-style session CSV."""
    fieldnames = [
        "session_id", "session_id_hash", "student_id_hash", "classroom",
        "session_start_iso", "session_end_iso", "session_span_seconds",
        "total_usage_seconds", "educational_usage_seconds",
        "non_educational_usage_seconds", "unknown_usage_seconds",
        "educational_ratio", "non_educational_ratio", "unknown_ratio",
        "app_switch_count", "unique_apps_count", "top_apps_summary",
        "focus_label", "review_status", "reviewer_id",
        "review_evidence", "reviewer_notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            full_row = {k: "" for k in fieldnames}
            full_row.update(row)
            writer.writerow(full_row)


def _base_row(i, label, status="reviewed", student="stu_aaa"):
    return {
        "session_id": f"sess_{i}",
        "session_id_hash": f"hash_{i}",
        "student_id_hash": student,
        "session_span_seconds": 3600,
        "non_educational_ratio": 0.7 if label == "potentially_distracted" else 0.1,
        "educational_ratio":    0.1 if label == "potentially_distracted" else 0.8,
        "unknown_ratio":        0.2,
        "app_switch_count":     10 if label == "potentially_distracted" else 3,
        "unique_apps_count":    5,
        "focus_label": label,
        "review_status": status,
        "reviewer_id": "reviewer_A",
    }


def make_sufficient_rows(n_distracted=7, n_focused=7, student="stu_aaa"):
    rows = []
    for i in range(n_distracted):
        rows.append(_base_row(i, "potentially_distracted", student=student))
    for i in range(n_focused):
        rows.append(_base_row(100 + i, "focused", student=student))
    return rows


# ---- fixtures ----------------------------------------------------------------

@pytest.fixture()
def tmp_csv(tmp_path):
    """Return a factory: call it with rows to get a labeled CSV path."""
    def factory(rows):
        p = tmp_path / "test_labeled.csv"
        make_labeled_csv(rows, p)
        return p
    return factory


@pytest.fixture()
def mod(monkeypatch):
    """Import train_real_model with PROJECT_ROOT and TRAINING_DIR patched."""
    import importlib
    import data.focus_training.train_real_model as m
    importlib.reload(m)
    return m


# ===========================================================================
# Gate 1 — insufficient labeled sessions
# ===========================================================================

def test_gate_insufficient_labels(tmp_csv, mod, monkeypatch):
    """Pipeline exits 2 when fewer than MIN_LABELED_SESSIONS reviewed rows."""
    rows = [_base_row(i, "potentially_distracted") for i in range(3)]
    rows += [_base_row(10 + i, "focused") for i in range(3)]
    csv_path = tmp_csv(rows)

    with pytest.raises(SystemExit) as exc:
        mod.load_and_validate(csv_path)
    assert exc.value.code == 2


# ===========================================================================
# Gate 2 — single class only
# ===========================================================================

def test_gate_single_class(tmp_csv, mod):
    """Pipeline exits 2 when only one binary class is present."""
    rows = [_base_row(i, "potentially_distracted") for i in range(12)]
    csv_path = tmp_csv(rows)
    with pytest.raises(SystemExit) as exc:
        mod.load_and_validate(csv_path)
    assert exc.value.code == 2


# ===========================================================================
# Gate 3 — extreme imbalance
# ===========================================================================

def test_gate_extreme_imbalance(tmp_csv, mod):
    """Pipeline exits 2 when imbalance ratio exceeds MAX_CLASS_RATIO."""
    rows = [_base_row(i, "potentially_distracted") for i in range(20)]
    rows += [_base_row(100, "focused")]   # 20:1 ratio
    csv_path = tmp_csv(rows)
    with pytest.raises(SystemExit) as exc:
        mod.load_and_validate(csv_path)
    assert exc.value.code == 2


# ===========================================================================
# Gate — no file found
# ===========================================================================

def test_gate_no_file(mod, tmp_path):
    """Pipeline exits 1 if the labeled CSV path does not exist."""
    missing = tmp_path / "does_not_exist.csv"
    with pytest.raises(SystemExit) as exc:
        mod.load_and_validate(missing)
    assert exc.value.code == 1


# ===========================================================================
# Feature engineering
# ===========================================================================

def test_feature_engineering_session_span_minutes(tmp_csv, mod):
    """session_span_minutes = session_span_seconds / 60."""
    rows = make_sufficient_rows()
    for r in rows:
        r["session_span_seconds"] = 3600   # 60 minutes
    csv_path = tmp_csv(rows)
    X, y, _, labeled_df, _, _ = mod.load_and_validate(csv_path)
    assert "session_span_minutes" in X.columns
    assert abs(X["session_span_minutes"].iloc[0] - 60.0) < 0.01


def test_feature_engineering_coerces_nan(tmp_csv, mod):
    """Non-numeric values in ratio columns are coerced to 0.0, not NaN."""
    rows = make_sufficient_rows()
    rows[0]["non_educational_ratio"] = "MISSING"
    csv_path = tmp_csv(rows)
    X, y, _, labeled_df, _, _ = mod.load_and_validate(csv_path)
    assert X["non_educational_ratio"].isna().sum() == 0


def test_uncertain_labels_excluded(tmp_csv, mod):
    """Rows with focus_label='uncertain' are excluded from training data."""
    rows = make_sufficient_rows()
    uncertain_row = _base_row(999, "uncertain")
    uncertain_row["review_status"] = "reviewed"
    rows.append(uncertain_row)
    n_total = len(rows)
    csv_path = tmp_csv(rows)
    X, y, _, labeled_df, _, _ = mod.load_and_validate(csv_path)
    # uncertain row excluded
    assert len(X) == n_total - 1


def test_pending_rows_excluded(tmp_csv, mod):
    """Rows with review_status='pending' are excluded regardless of label."""
    rows = make_sufficient_rows()
    pending_row = _base_row(998, "focused", status="pending")
    rows.append(pending_row)
    n_total = len(rows)
    csv_path = tmp_csv(rows)
    X, y, _, labeled_df, _, _ = mod.load_and_validate(csv_path)
    assert len(X) == n_total - 1


# ===========================================================================
# Cross-validation
# ===========================================================================

def test_cross_validation_returns_metrics(tmp_csv, mod):
    """run_cross_validation returns a dict with accuracy, precision, recall, f1."""
    rows = make_sufficient_rows(n_distracted=7, n_focused=7)
    csv_path = tmp_csv(rows)
    X, y, _, _, _, _ = mod.load_and_validate(csv_path)
    results, n_splits = mod.run_cross_validation(X, y)
    for metric in ["accuracy", "precision", "recall", "f1"]:
        assert metric in results
        assert "mean" in results[metric]
        assert "std" in results[metric]
        assert 0.0 <= results[metric]["mean"] <= 1.0


# ===========================================================================
# Full pipeline on sufficient synthetic data
# ===========================================================================

def test_full_pipeline_trains_and_saves(tmp_csv, mod, tmp_path, monkeypatch):
    """Full pipeline: validate -> CV -> train -> saves model and report."""
    rows = make_sufficient_rows(n_distracted=10, n_focused=10)
    csv_path = tmp_csv(rows)

    fake_model_out = tmp_path / "focus_model_real.joblib"
    fake_report_out = tmp_path / "focus_model_real_report.json"
    fake_demo = tmp_path / "focus_model_demo.joblib"
    # Write a placeholder so the paths differ
    fake_demo.write_text("demo")

    monkeypatch.setattr(mod, "MODEL_OUT", fake_model_out)
    monkeypatch.setattr(mod, "REPORT_OUT", fake_report_out)
    monkeypatch.setattr(mod, "DEMO_MODEL", fake_demo)

    X, y, student_ids, labeled_df, n_students, label_dist = mod.load_and_validate(csv_path)
    cv_results, n_splits = mod.run_cross_validation(X, y)
    pipeline, eval_metrics = mod.train_and_evaluate(X, y)
    mod.save_artifacts(
        pipeline, eval_metrics, cv_results,
        len(y), n_students, label_dist,
        csv_path, n_splits, dry_run=False
    )

    assert fake_model_out.exists(), "Model file should be written"
    assert fake_report_out.exists(), "Report file should be written"

    with open(fake_report_out) as f:
        report = json.load(f)
    assert report["is_demo_model"] is False
    assert report["demo_model_overwritten"] is False
    assert report["features"] == mod.FEATURE_COLS


def test_dry_run_does_not_write_model(tmp_csv, mod, tmp_path, monkeypatch):
    """With dry_run=True, save_artifacts must not write any files."""
    rows = make_sufficient_rows(n_distracted=10, n_focused=10)
    csv_path = tmp_csv(rows)

    fake_model_out = tmp_path / "focus_model_real.joblib"
    fake_report_out = tmp_path / "focus_model_real_report.json"
    fake_demo = tmp_path / "focus_model_demo.joblib"
    fake_demo.write_text("demo")

    monkeypatch.setattr(mod, "MODEL_OUT", fake_model_out)
    monkeypatch.setattr(mod, "REPORT_OUT", fake_report_out)
    monkeypatch.setattr(mod, "DEMO_MODEL", fake_demo)

    X, y, _, labeled_df, n_students, label_dist = mod.load_and_validate(csv_path)
    cv_results, n_splits = mod.run_cross_validation(X, y)
    pipeline, eval_metrics = mod.train_and_evaluate(X, y)
    mod.save_artifacts(
        pipeline, eval_metrics, cv_results,
        len(y), n_students, label_dist,
        csv_path, n_splits, dry_run=True
    )

    assert not fake_model_out.exists(), "Dry run must not write model"
    assert not fake_report_out.exists(), "Dry run must not write report"


# ===========================================================================
# ai_model.py: model selection and fallback
# ===========================================================================

@pytest.fixture()
def ai_mod(tmp_path, monkeypatch):
    """Import ai_model with MODEL paths patched."""
    import home.ai_model as ai
    importlib.reload(ai)
    return ai


def test_demo_model_path_ne_real_model_path(mod):
    """Safety: real model output path must never equal demo model path."""
    assert mod.MODEL_OUT.resolve() != mod.DEMO_MODEL.resolve()


def test_ai_model_imports_without_crash():
    """ai_model.py must be importable without crashing."""
    import importlib
    import home.ai_model as ai
    importlib.reload(ai)


def test_ai_model_predict_focus_returns_dict():
    """predict_focus returns a dict with prediction, label, is_demo_model."""
    import home.ai_model as ai
    if not ai._DEPS_AVAILABLE:
        pytest.skip("ML deps not installed")
    result = ai.predict_focus(120.0, True)
    assert isinstance(result, dict)
    assert "prediction" in result
    assert "label" in result
    assert "is_demo_model" in result
    assert result["prediction"] in (0, 1)


def test_ai_model_predict_focus_without_deps_raises():
    """Without ML deps, predict_focus must raise RuntimeError."""
    import home.ai_model as ai
    if ai._DEPS_AVAILABLE:
        pytest.skip("sklearn is installed - skipping missing-deps test")
    with pytest.raises(RuntimeError):
        ai.predict_focus(120.0, True)


def test_ai_model_prefers_real_model_when_present(tmp_path, monkeypatch):
    """ai_model.py must load focus_model_real.joblib when it exists."""
    import home.ai_model as ai
    if not ai._DEPS_AVAILABLE:
        pytest.skip("ML deps not installed")

    # Train a minimal real model and save it
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    import joblib

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(n_estimators=10, random_state=42))
    ])
    import data.focus_training.train_real_model as trm
    rows = make_sufficient_rows(n_distracted=8, n_focused=8)
    import io
    csv_content = io.StringIO()
    fieldnames = [
        "session_id", "session_id_hash", "student_id_hash", "classroom",
        "session_start_iso", "session_end_iso", "session_span_seconds",
        "total_usage_seconds", "educational_usage_seconds",
        "non_educational_usage_seconds", "unknown_usage_seconds",
        "educational_ratio", "non_educational_ratio", "unknown_ratio",
        "app_switch_count", "unique_apps_count", "top_apps_summary",
        "focus_label", "review_status", "reviewer_id",
        "review_evidence", "reviewer_notes",
    ]
    csv_path = tmp_path / "labeled.csv"
    make_labeled_csv(rows, csv_path)
    X, y, _, _, n_stu, ld = trm.load_and_validate(csv_path)
    pipe.fit(X, y)
    real_model_path = tmp_path / "focus_model_real.joblib"
    joblib.dump(pipe, real_model_path)

    monkeypatch.setattr(ai, "REAL_MODEL_PATH", real_model_path)
    monkeypatch.setattr(ai, "_real_model", None)   # clear real-model cache

    # Must pass all 6 session-level features to trigger real-model path
    result = ai.predict_focus_with_best_model(
        duration_seconds=120.0,
        non_educational=True,
        non_educational_ratio=0.7,
        educational_ratio=0.1,
        unknown_ratio=0.2,
        app_switch_count=10,
        unique_apps_count=5,
        session_span_minutes=60.0,
    )
    assert result["is_demo_model"] is False


def test_ai_model_falls_back_to_demo_when_real_absent(tmp_path, monkeypatch):
    """ai_model.py must fall back to demo when real model does not exist."""
    import home.ai_model as ai
    if not ai._DEPS_AVAILABLE:
        pytest.skip("ML deps not installed")

    absent_path = tmp_path / "nonexistent_real.joblib"
    monkeypatch.setattr(ai, "REAL_MODEL_PATH", absent_path)
    monkeypatch.setattr(ai, "_model", None)

    result = ai.predict_focus_with_best_model(120.0, True)
    assert result["is_demo_model"] is True
