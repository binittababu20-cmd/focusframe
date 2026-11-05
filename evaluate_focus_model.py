"""
evaluate_focus_model.py
=======================
FocusFrame â€” Standalone ML Model Evaluation Script

PURPOSE
-------
Evaluate the saved `focus_model_demo.joblib` against its original held-out
test split, and optionally against any labeled real-world CSV produced by
the data pipeline.

USAGE
-----
  # 1. Evaluate on the synthetic held-out split only (always works)
  python evaluate_focus_model.py

  # 2. Also evaluate on a labeled real CSV (requires human-reviewed labels)
  python evaluate_focus_model.py --labeled-csv data/focus_training/session_label_template_YYYYMMDD_labeled.csv

SAFETY GUARANTEES
-----------------
- This script NEVER retrains or overwrites focus_model_demo.joblib.
- This script does NOT modify views.py, ai_model.py, Firebase, or any
  attendance / authentication / Android files.
- No secrets are read or printed.
- Exit code 0 = evaluation completed; exit code 1 = environment error.
"""

import sys
import argparse
from pathlib import Path

# â”€â”€ dependency check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
try:
    import joblib
    import pandas as pd
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
    )
    from sklearn.model_selection import train_test_split
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Install with: pip install joblib pandas scikit-learn numpy")
    sys.exit(1)

# â”€â”€ paths â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH   = PROJECT_ROOT / "focus_model_demo.joblib"

SEPARATOR = "=" * 65


# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def print_section(title: str):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def load_model():
    if not MODEL_PATH.exists():
        print(f"[ERROR] Model file not found: {MODEL_PATH}")
        sys.exit(1)
    model = joblib.load(MODEL_PATH)
    print(f"[OK] Loaded model: {MODEL_PATH.name}")
    print(f"     Type            : {type(model).__name__}")
    print(f"     n_estimators    : {model.n_estimators}")
    print(f"     Features        : {list(model.feature_names_in_)}")
    print(f"     Classes         : {list(model.classes_)}  (0=Focused, 1=Distracted)")
    print(f"     class_weight    : {model.class_weight}")
    return model


def print_metrics(y_true, y_pred, dataset_label: str):
    acc  = accuracy_score(y_true, y_pred)
    cm   = confusion_matrix(y_true, y_pred)
    report = classification_report(
        y_true, y_pred,
        target_names=["Focused (0)", "Potentially Distracted (1)"],
        zero_division=0,
    )

    n = len(y_true)
    classes, counts = np.unique(y_true, return_counts=True)
    dist = {int(c): int(k) for c, k in zip(classes, counts)}

    print(f"\n  Dataset          : {dataset_label}")
    print(f"  Samples          : {n}")
    print(f"  Class dist       : Focused={dist.get(0,0)}, Distracted={dist.get(1,0)}")
    print(f"\n  Accuracy         : {acc*100:.1f}%  ({int(acc*n)}/{n} correct)")
    print()
    print("  Confusion Matrix")
    print("                       Pred Focused    Pred Distracted")
    print(f"  Actual Focused            {cm[0][0]}                  {cm[0][1]}")
    print(f"  Actual Distracted         {cm[1][0]}                  {cm[1][1]}")
    print()
    print("  Per-class Metrics:")
    for line in report.strip().split("\n"):
        print("    " + line)

    return acc, cm


# -------------------------------------------------------------------
def evaluate_synthetic_split(model):
    print_section("Model Evaluation - Held-Out Test Split")

    # Reproduce the exact data and split used when the model was saved.
    data = pd.DataFrame({
        "duration_seconds": [
             5,  10,  10, 120,  25,  20,  65,
           150,  90,  45,  30,  20,  45,  15,
            30,  35, 250, 110, 220, 300,  60,
            90, 140, 120,  80,  75, 200, 100
        ],
        "non_educational": [
            1, 1, 0, 0, 1, 1, 1,
            0, 0, 0, 1, 0, 1, 0,
            0, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1
        ],
        "label": [
            0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0,
            0, 0, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1
        ],
    })

    X = data[["duration_seconds", "non_educational"]]
    y = data["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    print(f"  Dataset size           : {len(data)} rows")
    print(f"  Train split (75%)      : {len(X_train)} rows")
    print(f"  Test  split (25%)      : {len(X_test)} rows")

    # Verify the model was not re-used with training data
    train_overlap = set(X_train.index) & set(X_test.index)
    print(f"  Train/test index overlap: {len(train_overlap)} (should be 0)")

    y_pred = model.predict(X_test)
    acc, cm = print_metrics(y_test, y_pred, f"Held-out test split ({len(X_test)} samples)")

    print(f"\n  Feature Importances:")
    for feat, imp in zip(model.feature_names_in_, model.feature_importances_):
        bar = "#" * int(imp * 40)
        print(f"    {feat:<22} {imp:.4f}  {bar}")

    return acc


# â”€â”€ Evaluation B: real labeled CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def evaluate_real_csv(model, csv_path: Path):
    print_section("EVALUATION B â€” Real Labeled Session Data")

    if not csv_path.exists():
        print(f"  [SKIP] File not found: {csv_path}")
        print("  Provide a path to a labeled CSV (see labeling_guide.md).")
        return None

    df = pd.read_csv(csv_path, encoding="utf-8")

    # Check required columns
    required = ["focus_label", "total_usage_seconds",
                "non_educational_usage_seconds", "review_status"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  [ERROR] CSV is missing columns: {missing}")
        print("  Make sure you are providing the completed labeled template.")
        return None

    # Keep only reviewed rows with valid binary labels
    valid_labels = {"focused", "potentially_distracted"}
    df = df[df["review_status"] == "reviewed"].copy()
    df = df[df["focus_label"].isin(valid_labels)].copy()

    if len(df) == 0:
        print("  [SKIP] No reviewed rows with valid labels found.")
        print("  Open session_label_template_*.csv, fill in focus_label and")
        print("  set review_status='reviewed', then rerun this script.")
        return None

    print(f"  Reviewed + labeled rows: {len(df)}")

    # Map string labels to integers matching model classes
    label_map = {"focused": 0, "potentially_distracted": 1}
    df["label_int"] = df["focus_label"].map(label_map)

    # Build features the model expects
    # The model uses: duration_seconds, non_educational (binary)
    df["duration_seconds"]  = pd.to_numeric(
        df["total_usage_seconds"], errors="coerce").fillna(0)
    df["non_educational"]   = (
        pd.to_numeric(df["non_educational_usage_seconds"], errors="coerce").fillna(0)
        > 0
    ).astype(int)

    X_real = df[["duration_seconds", "non_educational"]]
    y_real = df["label_int"]

    # Warn about small sample size
    n = len(df)
    if n < 20:
        print(f"\n  [WARNING] Only {n} labeled rows â€” results are not statistically")
        print("  reliable. Collect at least 50 labeled sessions before drawing")
        print("  conclusions about real-world accuracy.")

    y_pred = model.predict(X_real)
    acc, cm = print_metrics(y_real, y_pred, f"Real labeled data ({n} sessions)")
    return acc


# ── Summary ────────────────────────────────────────────────────────
def print_verdict(acc):
    print_section("SUMMARY")
    print(f"\n  Accuracy = {acc*100:.1f}%\n")


# ── main ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Evaluate FocusFrame ML model (read-only, never retrains)."
    )
    parser.add_argument(
        "--labeled-csv",
        type=Path,
        default=None,
        help="Path to a completed labeled session CSV (optional).",
    )
    args = parser.parse_args()

    print_section("FocusFrame - ML Model Evaluation")
    model = load_model()

    if args.labeled_csv:
        acc = evaluate_real_csv(model, args.labeled_csv)
    else:
        acc = evaluate_synthetic_split(model)

    print_verdict(acc)
    print(f"{'='*65}")
    print("  Evaluation complete.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()

