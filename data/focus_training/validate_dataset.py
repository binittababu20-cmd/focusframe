"""
FocusFrame - Dataset Validation Script
Usage: python validate_dataset.py [labeled_csv_path]
If no path is provided, it searches for the latest *_labeled.csv in this directory.
"""

import sys
import csv
import json
from pathlib import Path
from collections import Counter

OUTPUT_DIR = Path(__file__).resolve().parent
VALID_LABELS = {"focused", "potentially_distracted", "uncertain"}
VALID_REVIEW_STATUS = {"pending", "reviewed", "disputed"}

REQUIRED_USAGE_FIELDS = [
    "record_id", "session_id", "session_id_hash", "student_id_hash",
    "app_name", "package_name", "category", "duration_seconds",
]

REQUIRED_SESSION_FIELDS = [
    "session_id", "session_id_hash", "student_id_hash",
    "educational_ratio", "non_educational_ratio", "unknown_ratio",
    "app_switch_count", "focus_label", "review_status",
]

TRAINING_MINIMUM_SESSIONS = 50
MAX_CLASS_RATIO = 3.0  # maximum allowed ratio between majority and minority class

errors = []
warnings = []


def check(condition, error_msg, is_warning=False):
    if not condition:
        if is_warning:
            warnings.append(f"  [WARN] {error_msg}")
        else:
            errors.append(f"  [FAIL] {error_msg}")


def find_latest_file(pattern):
    matches = sorted(OUTPUT_DIR.glob(pattern))
    return matches[-1] if matches else None


def validate_usage_csv(path):
    print(f"\n--- Validating usage records: {path.name} ---")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for field in REQUIRED_USAGE_FIELDS:
            check(field in fieldnames, f"Missing required column: {field}")
        for i, row in enumerate(reader, start=2):
            rows.append(row)
            # Basic type checks
            try:
                float(row.get("duration_seconds", ""))
            except ValueError:
                errors.append(f"  [FAIL] Row {i}: duration_seconds is not numeric: {row.get('duration_seconds')!r}")
            cat = row.get("category", "")
            check(cat in ("educational", "non_educational", "unknown"),
                  f"Row {i}: unexpected category value: {cat!r}", is_warning=True)
            # No raw PII expected - check for suspicious fields
            stu_raw = row.get("student_id", "")
            if stu_raw and "@" in stu_raw:
                errors.append(f"  [FAIL] Row {i}: possible email in student_id column (PII risk)")

    print(f"  Records: {len(rows)}")
    durations = []
    for r in rows:
        try:
            durations.append(float(r["duration_seconds"]))
        except Exception:
            pass
    if durations:
        print(f"  Duration - min: {min(durations):.1f}s  max: {max(durations):.1f}s  mean: {sum(durations)/len(durations):.1f}s")
    cats = Counter(r.get("category", "") for r in rows)
    print(f"  Category distribution: {dict(cats)}")
    total = len(rows)
    check(total > 0, "Usage CSV has zero records")
    return rows


def validate_session_template(path, is_labeled=True):
    print(f"\n--- Validating session template: {path.name} ---")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for field in REQUIRED_SESSION_FIELDS:
            check(field in fieldnames, f"Missing required column: {field}")
        for i, row in enumerate(reader, start=2):
            rows.append(row)

    total_sessions = len(rows)
    print(f"  Total student-session rows: {total_sessions}")

    if not is_labeled:
        print("  [INFO] Template has not been labeled yet. Skipping label checks.")
        return rows

    # Label coverage
    label_counts = Counter(r.get("focus_label", "").strip() for r in rows)
    reviewed = sum(1 for r in rows if r.get("review_status", "").strip() == "reviewed")
    pending = sum(1 for r in rows if r.get("review_status", "").strip() == "pending")
    disputed = sum(1 for r in rows if r.get("review_status", "").strip() == "disputed")

    print(f"  Label distribution: {dict(label_counts)}")
    print(f"  Review status: reviewed={reviewed}, pending={pending}, disputed={disputed}")

    # Validate label values
    for i, row in enumerate(rows, start=2):
        label = row.get("focus_label", "").strip()
        status = row.get("review_status", "").strip()
        if label and label not in VALID_LABELS:
            errors.append(f"  [FAIL] Row {i}: invalid focus_label: {label!r}")
        if status and status not in VALID_REVIEW_STATUS:
            errors.append(f"  [FAIL] Row {i}: invalid review_status: {status!r}")
        if status == "reviewed" and not label:
            errors.append(f"  [FAIL] Row {i}: review_status=reviewed but focus_label is empty")
        if status == "reviewed" and not row.get("reviewer_id", "").strip():
            warnings.append(f"  [WARN] Row {i}: review_status=reviewed but reviewer_id is empty")

    # Training readiness checks
    labeled_sessions = [r for r in rows if r.get("focus_label", "").strip() in VALID_LABELS - {"uncertain"}]
    n_labeled = len(labeled_sessions)

    print(f"\n  --- Training Readiness Gate ---")
    check(n_labeled >= TRAINING_MINIMUM_SESSIONS,
          f"Only {n_labeled} labeled sessions (need >= {TRAINING_MINIMUM_SESSIONS} to train)")

    binary_counts = Counter(r.get("focus_label", "").strip() for r in labeled_sessions)
    if binary_counts:
        majority = max(binary_counts.values())
        minority = min(binary_counts.values())
        ratio = majority / minority if minority > 0 else float("inf")
        check(ratio <= MAX_CLASS_RATIO,
              f"Class imbalance too high: {dict(binary_counts)}, ratio={ratio:.2f} (max {MAX_CLASS_RATIO})",
              is_warning=True)

    return rows


def validate_manifest(path):
    print(f"\n--- Validating manifest: {path.name} ---")
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)

    required_keys = ["manifest_version", "project", "export_timestamp_utc", "counts", "files", "schema_description"]
    for k in required_keys:
        check(k in manifest, f"Missing key in manifest: {k}")

    counts = manifest.get("counts", {})
    print(f"  Manifest counts: {counts}")
    check(counts.get("valid_app_usage_events", 0) > 0, "Manifest reports zero valid usage events")
    training_ready = counts.get("training_ready", None)
    print(f"  training_ready flag: {training_ready}")
    if training_ready:
        warnings.append("  [WARN] Manifest training_ready=True but labels have not been validated by this script yet")


def main():
    print("=" * 60)
    print("  FocusFrame Dataset Validation")
    print("=" * 60)

    # Locate files
    if len(sys.argv) > 1:
        labeled_path = Path(sys.argv[1])
        if not labeled_path.is_absolute():
            labeled_path = OUTPUT_DIR / labeled_path
    else:
        labeled_path = find_latest_file("*_labeled.csv")

    usage_path = find_latest_file("usage_records_anonymized_*.csv")
    template_path = find_latest_file("session_label_template_*.csv")
    manifest_path = find_latest_file("dataset_manifest_*.json")

    if usage_path:
        validate_usage_csv(usage_path)
    else:
        errors.append("  [FAIL] No usage_records_anonymized_*.csv found in output directory")

    if labeled_path and labeled_path.exists():
        validate_session_template(labeled_path, is_labeled=True)
    elif template_path:
        print(f"\n[INFO] No labeled CSV found (pattern: *_labeled.csv). Validating base template without label checks.")
        validate_session_template(template_path, is_labeled=False)
    else:
        errors.append("  [FAIL] No session_label_template_*.csv found in output directory")

    if manifest_path:
        validate_manifest(manifest_path)
    else:
        warnings.append("  [WARN] No dataset_manifest_*.json found in output directory")

    # Summary
    print("\n" + "=" * 60)
    print("  VALIDATION SUMMARY")
    print("=" * 60)
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(e)
    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(w)
    if not errors and not warnings:
        print("  All checks passed. Dataset is ready for review.")
    elif not errors:
        print(f"\n  No errors. {len(warnings)} warning(s) noted.")
    else:
        print(f"\n  {len(errors)} error(s) must be resolved before training.")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
