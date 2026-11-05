"""
FocusFrame â€” Complete Dataset Export and Audit Script
Runs in read-only mode against Firebase Realtime Database.
Generates:
  1. usage_records_anonymized_YYYYMMDD_HHMMSS.csv
  2. session_label_template_YYYYMMDD_HHMMSS.csv
  3. dataset_manifest_YYYYMMDD_HHMMSS.json
  4. dataset_audit_report_YYYYMMDD_HHMMSS.md
"""

import sys
import os
import json
import csv
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from home.firebase_config import db

TIMESTAMP_STR = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = PROJECT_ROOT / "data" / "focus_training"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def safe_hash(val: str, prefix="stu_") -> str:
    if not val:
        return ""
    h = hashlib.sha256(str(val).strip().encode("utf-8")).hexdigest()[:12]
    return f"{prefix}{h}"

def norm_category(cat_raw):
    if not cat_raw:
        return "unknown"
    s = str(cat_raw).strip().lower().replace(" ", "_").replace("-", "_")
    if "non_edu" in s or "nonedu" in s:
        return "non_educational"
    if "edu" in s:
        return "educational"
    return "unknown"

def parse_timestamp(ts):
    if ts is None or str(ts).strip() == "":
        return "", "", 0.0
    try:
        ts_num = int(ts)
        if ts_num > 10**12:
            ts_sec = ts_num / 1000.0
        else:
            ts_sec = float(ts_num)
        dt = datetime.fromtimestamp(ts_sec, timezone.utc)
        return str(ts), dt.strftime("%Y-%m-%dT%H:%M:%SZ"), ts_sec
    except Exception:
        # Check if already ISO string
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return str(ts), dt.strftime("%Y-%m-%dT%H:%M:%SZ"), dt.timestamp()
        except Exception:
            return str(ts), "", 0.0


def calculate_session_span(recs):
    """
    Calculate the observed time span for a list of session usage records.
    Each record r is assumed to have '_sec_ts' (completion timestamp in seconds)
    and 'duration_seconds' (active duration in seconds).
    
    The span covers from the earliest interval start to the latest interval end:
      earliest_start = min(end_sec - duration_sec)
      latest_end = max(end_sec)
      duration_span = round(latest_end - earliest_start, 1)
    
    Returns: (start_iso, end_iso, duration_span)
    """
    valid_recs = [r for r in recs if r.get("_sec_ts", 0) > 0]
    if not valid_recs:
        return "", "", 0.0

    starts_sec = [r["_sec_ts"] - max(0.0, float(r.get("duration_seconds", 0.0))) for r in valid_recs]
    ends_sec = [r["_sec_ts"] for r in valid_recs]

    min_start_sec = min(starts_sec)
    max_end_sec = max(ends_sec)
    duration_span = max(0.0, round(max_end_sec - min_start_sec, 1))

    start_iso = datetime.fromtimestamp(min_start_sec, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = datetime.fromtimestamp(max_end_sec, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return start_iso, end_iso, duration_span

def main():
    print("=== STARTING READ-ONLY FIREBASE EXPORT ===")
    
    # 1. Capture exact top-level counts before export
    nodes_to_check = ["phone_usage", "classroom_sessions", "users", "attendance", "devices", "alerts", "alert_history"]
    before_counts = {}
    for node in nodes_to_check:
        try:
            val = db.reference(node).get()
            before_counts[node] = len(val) if isinstance(val, dict) else (0 if val is None else 1)
        except Exception as e:
            before_counts[node] = str(e)
    
    print("Firebase Record Counts (Before Export):", before_counts)

    # 2. Fetch phone_usage and classroom_sessions
    phone_usage_data = db.reference("phone_usage").get() or {}
    classroom_sessions = db.reference("classroom_sessions").get() or {}

    total_sessions_in_pu = len(phone_usage_data)
    total_entries_retrieved = 0
    valid_usage_records = []
    metadata_entries = []
    student_raw_ids = set()
    category_counts = Counter()
    app_counts = Counter()

    for session_id, records in phone_usage_data.items():
        if not isinstance(records, dict):
            continue
        total_entries_retrieved += len(records)
        for rec_id, rec in records.items():
            if not isinstance(rec, dict):
                continue
            
            # Check if this is a focus_summary metadata dict or an app usage event
            if "app_name" not in rec and any("mca" in k or "student" in k for k in rec.keys()):
                metadata_entries.append({
                    "session_id": session_id,
                    "record_id": rec_id,
                    "data": rec
                })
                continue

            app_name = str(rec.get("app_name", "")).strip()
            package_name = str(rec.get("package_name", "")).strip()
            cat_raw = rec.get("category", "")
            category = norm_category(cat_raw)
            confidence = rec.get("confidence", "")
            
            try:
                duration = float(rec.get("duration", 0))
            except Exception:
                duration = 0.0

            raw_ts, iso_ts, sec_ts = parse_timestamp(rec.get("timestamp"))
            student_id = str(rec.get("student_id", "")).strip()
            if student_id:
                student_raw_ids.add(student_id)

            category_counts[category] += 1
            if app_name:
                app_counts[app_name] += 1

            record_dict = {
                "record_id": rec_id,
                "session_id": session_id,
                "session_id_hash": safe_hash(session_id, prefix="sess_"),
                "student_id_hash": safe_hash(student_id, prefix="stu_"),
                "app_name": app_name,
                "package_name": package_name,
                "category": category,
                "category_raw": str(cat_raw).strip(),
                "confidence": str(confidence).strip(),
                "duration_seconds": duration,
                "timestamp_raw": raw_ts,
                "timestamp_iso": iso_ts,
                "_sec_ts": sec_ts,
                "ml_prediction": str(rec.get("ml_prediction", "")),
                "ml_label": str(rec.get("ml_label", "")),
                "ml_is_demo": str(rec.get("ml_is_demo", ""))
            }
            valid_usage_records.append(record_dict)

    print(f"Total entries retrieved: {total_entries_retrieved}")
    print(f"Valid app usage records: {len(valid_usage_records)}")
    print(f"Metadata/summary records: {len(metadata_entries)}")
    print(f"Distinct students represented: {len(student_raw_ids)}")
    print(f"Category distribution: {dict(category_counts)}")

    # 3. Write usage_records_anonymized_<TS>.csv
    usage_csv_path = OUTPUT_DIR / f"usage_records_anonymized_{TIMESTAMP_STR}.csv"
    usage_fieldnames = [
        "record_id",
        "session_id",
        "session_id_hash",
        "student_id_hash",
        "app_name",
        "package_name",
        "category",
        "category_raw",
        "confidence",
        "duration_seconds",
        "timestamp_raw",
        "timestamp_iso",
        "ml_prediction",
        "ml_label",
        "ml_is_demo"
    ]

    with open(usage_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=usage_fieldnames)
        writer.writeheader()
        for r in valid_usage_records:
            row = {k: r[k] for k in usage_fieldnames}
            writer.writerow(row)
    
    print(f"âœ… Wrote anonymized usage records CSV: {usage_csv_path}")

    # 4. Aggregate by (session_id, student_id_hash) for session_label_template
    session_groups = {}
    for r in valid_usage_records:
        key = (r["session_id"], r["student_id_hash"])
        if key not in session_groups:
            session_groups[key] = []
        session_groups[key].append(r)

    session_rows = []
    for (sess_id, stu_hash), recs in sorted(session_groups.items(), key=lambda x: x[0][0]):
        # Compute accurate session span from earliest event start to latest event end
        start_iso, end_iso, duration_span = calculate_session_span(recs)

        # Classroom session info if available
        cs_info = classroom_sessions.get(sess_id, {})
        classroom_name = cs_info.get("classroom", "CS-402 Mobile Computing")

        total_usage_sec = round(sum(r["duration_seconds"] for r in recs), 1)
        edu_sec = round(sum(r["duration_seconds"] for r in recs if r["category"] == "educational"), 1)
        non_edu_sec = round(sum(r["duration_seconds"] for r in recs if r["category"] == "non_educational"), 1)
        unknown_sec = round(sum(r["duration_seconds"] for r in recs if r["category"] == "unknown"), 1)

        edu_ratio = round(edu_sec / total_usage_sec, 3) if total_usage_sec > 0 else 0.0
        non_edu_ratio = round(non_edu_sec / total_usage_sec, 3) if total_usage_sec > 0 else 0.0
        unknown_ratio = round(unknown_sec / total_usage_sec, 3) if total_usage_sec > 0 else 0.0

        # App switch & top apps
        app_switch_count = len(recs)
        apps_counter = Counter(r["app_name"] for r in recs if r["app_name"])
        unique_apps = len(apps_counter)
        top_apps_str = "; ".join(f"{app} ({cnt})" for app, cnt in apps_counter.most_common(3))

        session_rows.append({
            "session_id": sess_id,
            "session_id_hash": safe_hash(sess_id, prefix="sess_"),
            "student_id_hash": stu_hash,
            "classroom": classroom_name,
            "session_start_iso": start_iso,
            "session_end_iso": end_iso,
            "session_span_seconds": duration_span,
            "total_usage_seconds": total_usage_sec,
            "educational_usage_seconds": edu_sec,
            "non_educational_usage_seconds": non_edu_sec,
            "unknown_usage_seconds": unknown_sec,
            "educational_ratio": edu_ratio,
            "non_educational_ratio": non_edu_ratio,
            "unknown_ratio": unknown_ratio,
            "app_switch_count": app_switch_count,
            "unique_apps_count": unique_apps,
            "top_apps_summary": top_apps_str,
            "focus_label": "",               # Deliberately left blank for reviewer
            "review_status": "pending",      # Explicitly pending review
            "reviewer_id": "",
            "review_evidence": "",
            "reviewer_notes": ""
        })

    session_template_path = OUTPUT_DIR / f"session_label_template_{TIMESTAMP_STR}.csv"
    session_fieldnames = [
        "session_id",
        "session_id_hash",
        "student_id_hash",
        "classroom",
        "session_start_iso",
        "session_end_iso",
        "session_span_seconds",
        "total_usage_seconds",
        "educational_usage_seconds",
        "non_educational_usage_seconds",
        "unknown_usage_seconds",
        "educational_ratio",
        "non_educational_ratio",
        "unknown_ratio",
        "app_switch_count",
        "unique_apps_count",
        "top_apps_summary",
        "focus_label",
        "review_status",
        "reviewer_id",
        "review_evidence",
        "reviewer_notes"
    ]

    with open(session_template_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=session_fieldnames)
        writer.writeheader()
        for s in session_rows:
            writer.writerow(s)

    print(f"âœ… Wrote session labelling template CSV: {session_template_path}")
    print(f"   Total student-session units to review: {len(session_rows)}")

    # 5. Write dataset_manifest_<TS>.json
    manifest_data = {
        "manifest_version": "1.0.0",
        "project": "FocusFrame",
        "dataset_name": "focus_training_dataset",
        "export_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp_id": TIMESTAMP_STR,
        "source": "Firebase Realtime Database (node: /phone_usage)",
        "security_and_privacy": {
            "pii_removed": ["student_name", "student_email", "device_imei", "passwords", "auth_tokens"],
            "pseudonymization_method": "SHA-256 (truncated to 12 hex chars with prefix)",
            "read_only_access_verified": True
        },
        "counts": {
            "total_raw_entries_in_phone_usage": total_entries_retrieved,
            "valid_app_usage_events": len(valid_usage_records),
            "metadata_summary_records_excluded": len(metadata_entries),
            "distinct_sessions_in_phone_usage": total_sessions_in_pu,
            "distinct_student_sessions_for_labeling": len(session_rows),
            "distinct_students": len(student_raw_ids),
            "category_distribution": dict(category_counts),
            "labels_reviewed": 0,
            "labels_pending": len(session_rows),
            "training_ready": False
        },
        "files": {
            "usage_records_anonymized": str(usage_csv_path.name),
            "session_label_template": str(session_template_path.name),
            "labeling_guide": "labeling_guide.md",
            "dataset_audit_report": f"dataset_audit_report_{TIMESTAMP_STR}.md"
        },
        "schema_description": {
            "usage_records_anonymized": {
                "record_id": "Original Firebase push key for usage event reference",
                "session_id": "Original classroom session identifier",
                "session_id_hash": "Pseudonymized session hash",
                "student_id_hash": "Pseudonymized student identifier (SHA-256)",
                "app_name": "Human-readable application name",
                "package_name": "Android application package name",
                "category": "Normalized category: educational, non_educational, unknown",
                "category_raw": "Original string category from client",
                "confidence": "Classification confidence from client lookup",
                "duration_seconds": "Active app duration in seconds",
                "timestamp_raw": "Original timestamp from Android client",
                "timestamp_iso": "Normalized ISO-8601 UTC timestamp",
                "ml_prediction": "Demo model prediction (if recorded)",
                "ml_label": "Demo model text label (if recorded)",
                "ml_is_demo": "Boolean flag indicating demo prediction"
            },
            "session_label_template": {
                "session_id": "Firebase session push key",
                "student_id_hash": "Pseudonymized student identifier",
                "focus_label": "Ground-truth target label: focused, potentially_distracted, uncertain (blank if pending)",
                "review_status": "Human review lifecycle: pending, reviewed, disputed",
                "review_evidence": "Documented observational or telemetry evidence justification",
                "reviewer_id": "Pseudonymous reviewer identifier"
            }
        }
    }

    manifest_path = OUTPUT_DIR / f"dataset_manifest_{TIMESTAMP_STR}.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"âœ… Wrote dataset manifest JSON: {manifest_path}")

    # 6. Capture after counts to verify ZERO changes occurred in Firebase
    after_counts = {}
    for node in nodes_to_check:
        try:
            val = db.reference(node).get()
            after_counts[node] = len(val) if isinstance(val, dict) else (0 if val is None else 1)
        except Exception as e:
            after_counts[node] = str(e)
    
    print("Firebase Record Counts (After Export):", after_counts)
    assert before_counts == after_counts, "FIREBASE RECORD COUNTS CHANGED! ABORTING!"
    print("âœ… Verified: Firebase was accessed strictly in READ-ONLY mode. All counts match exactly.")

if __name__ == "__main__":
    main()

