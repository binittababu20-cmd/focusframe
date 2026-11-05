import os
import sys
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# PROJECT SETUP
# ---------------------------------------------------------------------------
# Ensure the Django project root is on the Python path (adjust if moved)
PROJECT_ROOT = Path(r"D:\\Binitta\\mobile_monitoring")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
PREPARED_CSV = DATA_DIR / "phone_usage_prepared_20261023_210210.csv"
AGGREGATED_CSV = DATA_DIR / "phone_usage_aggregated_template_20261023_210210.csv"

def aggregate_sessions(input_path: Path) -> pd.DataFrame:
    """Read the prepared per‑app CSV and return a DataFrame where each row
    represents a unique (session_hash, student_hash) pair.

    The returned DataFrame contains the following columns:
        - session_hash, student_hash (anonymised identifiers)
        - total_duration_seconds
        - educational_duration_seconds
        - non_educational_duration_seconds
        - unknown_duration_seconds
        - educational_proportion (0‑1)
        - non_educational_proportion (0‑1)
        - unknown_proportion (0‑1)
        - interaction_count (number of app‑usage records)
        - avg_confidence (mean of the confidence column, NaN if all missing)
        - focus_label (blank, for human reviewers)
        - reviewer_notes (blank, free‑text for reviewer comments)
    """
    df = pd.read_csv(input_path)

    # Ensure required columns exist (defensive programming)
    required = ["session_hash", "student_hash", "category", "duration_seconds", "confidence"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {missing}")

    # Helper to sum durations per category
    def cat_duration(g, cat):
        return g.loc[g['category'] == cat, 'duration_seconds'].sum()

    # Group by session & student
    grouped = df.groupby(["session_hash", "student_hash"])
    rows = []
    for (sess, stud), g in grouped:
        total = g['duration_seconds'].sum()
        edu = cat_duration(g, "educational")
        non_edu = cat_duration(g, "non_educational")
        unk = cat_duration(g, "unknown")
        # Avoid division by zero – if total is 0 we keep proportions as 0
        if total > 0:
            edu_prop = edu / total
            non_edu_prop = non_edu / total
            unk_prop = unk / total
        else:
            edu_prop = non_edu_prop = unk_prop = 0.0
        avg_conf = g['confidence'].astype(float).mean() if not g['confidence'].empty else float('nan')
        rows.append({
            "session_hash": sess,
            "student_hash": stud,
            "total_duration_seconds": total,
            "educational_duration_seconds": edu,
            "non_educational_duration_seconds": non_edu,
            "unknown_duration_seconds": unk,
            "educational_proportion": edu_prop,
            "non_educational_proportion": non_edu_prop,
            "unknown_proportion": unk_prop,
            "interaction_count": int(g.shape[0]),
            "avg_confidence": avg_conf,
            "focus_label": "",
            "reviewer_notes": ""
        })
    agg_df = pd.DataFrame(rows)
    return agg_df

def main():
    if not PREPARED_CSV.exists():
        print(f"❌ Prepared CSV not found at {PREPARED_CSV}")
        sys.exit(1)
    agg_df = aggregate_sessions(PREPARED_CSV)
    # Save to CSV (index disabled for clean file)
    agg_df.to_csv(AGGREGATED_CSV, index=False)
    print(f"[OK] Aggregated labeling template written to {AGGREGATED_CSV}")
    print(f"Unique student-session groups: {len(agg_df)}")
    # Show a tiny preview for sanity
    print("\nSample rows:")
    print(agg_df.head())

if __name__ == "__main__":
    main()
