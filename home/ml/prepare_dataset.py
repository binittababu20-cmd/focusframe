import csv
import hashlib
import os
from pathlib import Path
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# PROJECT SETUP
# ---------------------------------------------------------------------------
# Explicitly add the Django project root to the module search path.
# Adjust this path if the project location changes.
PROJECT_ROOT = Path(r"D:\\Binitta\\mobile_monitoring")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the already‑initialised Firebase DB reference.
# The firebase_config module creates the app only once, so re‑importing is safe.
try:
    from home.firebase_config import db
except Exception as e:
    print(f"❌ Failed to import Firebase configuration: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CONSTANTS & HELPERS
# ---------------------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "phone_usage_prepared.csv"

# Normalise category values – any unknown or empty string becomes "unknown"
CATEGORY_MAP = {
    "educational": "educational",
    "non-educational": "non_educational",
    "noneducational": "non_educational",
    "unknown": "unknown",
}

def normalise_category(raw: str) -> str:
    if not isinstance(raw, str):
        return "unknown"
    lowered = raw.strip().lower().replace(" ", "-")
    return CATEGORY_MAP.get(lowered, "unknown")

def safe_hash(value: str) -> str:
    """Return a deterministic short hash for anonymising identifiers.
    The same input always yields the same 8‑character hex string.
    """
    h = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return h[:8]

# ---------------------------------------------------------------------------
# DATA FETCHING
# ---------------------------------------------------------------------------
def fetch_phone_usage():
    """Read the full ``phone_usage`` node from Firebase.
    Returns a nested dict ``{session_id: {record_key: record_dict, ...}, ...}``.
    """
    try:
        ref = db.reference("phone_usage")
        data = ref.get()
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as exc:
        print(f"❌ Error while reading from Firebase: {exc}")
        return {}

# ---------------------------------------------------------------------------
# DATA PREPARATION
# ---------------------------------------------------------------------------
def prepare_dataset(raw_data: dict):
    """Transform raw Firebase usage records into a sanitized tabular dataset.

    Parameters
    ----------
    raw_data: dict
        Nested mapping from session_id -> record_key -> record dict.

    Returns
    -------
    rows: list[dict]
        List of processed rows ready for CSV export.
    summary: dict
        Statistics used for the final report.
    """
    rows = []
    sessions_seen = set()
    category_counts = {}
    missing_counts = {}
    processed = 0
    skipped = 0

    for session_id, records in raw_data.items():
        sessions_seen.add(session_id)
        if not isinstance(records, dict):
            continue
        for rec_key, rec in records.items():
            if not isinstance(rec, dict):
                continue
            # Required fields (presence check only – values may be None)
            required = ["app_name", "category", "duration", "timestamp", "student_id"]
            missing = [field for field in required if field not in rec]
            if missing:
                skipped += 1
                for f in missing:
                    missing_counts[f] = missing_counts.get(f, 0) + 1
                continue

            # Extract and sanitize fields
            app_name = rec.get("app_name") or ""
            category_raw = rec.get("category")
            category = normalise_category(str(category_raw))
            category_counts[category] = category_counts.get(category, 0) + 1

            # Duration – keep raw numeric value if possible
            duration = rec.get("duration")
            try:
                duration_seconds = float(duration)
            except Exception:
                missing_counts["duration"] = missing_counts.get("duration", 0) + 1
                skipped += 1
                continue

            # Timestamp – store as ISO‑8601 if it looks like a Unix epoch (ms or s)
            ts_raw = rec.get("timestamp")
            try:
                ts_int = int(ts_raw)
                if ts_int > 10**12:
                    ts_int //= 1000
                timestamp_iso = datetime.fromtimestamp(ts_int, datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
            except Exception:
                timestamp_iso = ""
                missing_counts["timestamp"] = missing_counts.get("timestamp", 0) + 1

            # Optional fields – keep empty string when missing
            confidence = rec.get("confidence", "")
            package_name = rec.get("package_name", "")
            student_id_raw = rec.get("student_id", "")
            student_hash = safe_hash(str(student_id_raw)) if student_id_raw else ""

            row = {
                "session_hash": safe_hash(str(session_id)),
                "student_hash": student_hash,
                "app_name": app_name,
                "category": category,
                "confidence": confidence,
                "duration_seconds": duration_seconds,
                "package_name": package_name,
                "timestamp": timestamp_iso,
            }
            rows.append(row)
            processed += 1

    summary = {
        "total_sessions": len(sessions_seen),
        "total_records": sum(len(r) for r in raw_data.values() if isinstance(r, dict)),
        "processed": processed,
        "skipped": skipped,
        "category_counts": category_counts,
        "missing_counts": missing_counts,
    }
    return rows, summary

# ---------------------------------------------------------------------------
# FILE OUTPUT
# ---------------------------------------------------------------------------
def write_csv(rows: list[dict]):
    if not rows:
        print("⚠️ No rows to write – dataset is empty.")
        return
    os.makedirs(DATA_DIR, exist_ok=True)
    if OUTPUT_FILE.exists():
        backup_name = DATA_DIR / f"phone_usage_prepared_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        print(f"⚠️ Output file exists – writing to a timestamped backup: {backup_name}")
        target = backup_name
    else:
        target = OUTPUT_FILE
    fieldnames = [
        "session_hash",
        "student_hash",
        "app_name",
        "category",
        "confidence",
        "duration_seconds",
        "package_name",
        "timestamp",
    ]
    try:
        with open(target, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Dataset written to {target}")
    except Exception as exc:
        print(f"❌ Failed to write CSV: {exc}")

# ---------------------------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------------------------
def main():
    print("🔎 Fetching phone_usage data from Firebase…")
    raw = fetch_phone_usage()
    if not raw:
        print("⚠️ No phone_usage data found – exiting.")
        return
    rows, summary = prepare_dataset(raw)
    print("\n--- Summary ---")
    print(f"Sessions represented: {summary['total_sessions']}")
    print(f"Total raw records   : {summary['total_records']}")
    print(f"Processed records   : {summary['processed']}")
    print(f"Skipped records     : {summary['skipped']}")
    print("Category distribution:")
    for cat, cnt in summary["category_counts"].items():
        print(f"  {cat}: {cnt}")
    if summary["missing_counts"]:
        print("Missing field counts (records skipped for this reason):")
        for field, cnt in summary["missing_counts"].items():
            print(f"  {field}: {cnt}")
    write_csv(rows)
    print("\n✅ Preparation complete. Remember: human‑reviewed labels are required for supervised model training.")

if __name__ == "__main__":
    main()
