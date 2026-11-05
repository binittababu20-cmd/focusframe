"""
FocusFrame - Real Supervised Training Pipeline
Usage:
  python data/focus_training/train_real_model.py
  python data/focus_training/train_real_model.py --labeled-csv path/to/labeled.csv
  python data/focus_training/train_real_model.py --dry-run

Output (if training proceeds):
  focus_model_real.joblib       - real model (never overwrites focus_model_demo.joblib)
  focus_model_real_report.json  - evaluation metrics + limitations

Safety guarantees:
  - NEVER overwrites focus_model_demo.joblib.
  - Halts with a clear explanation if data gates are not met.
  - All printed accuracy figures are from held-out split or CV.

Training gates (all must pass):
  1. At least MIN_LABELED_SESSIONS reviewed sessions with binary label.
  2. At least MIN_CLASSES distinct binary labels.
  3. Class imbalance ratio <= MAX_CLASS_RATIO.
  4. At least MIN_STUDENTS distinct students.

Features (session-level):
  - non_educational_ratio, educational_ratio, unknown_ratio
  - app_switch_count, unique_apps_count, session_span_minutes
"""

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split, StratifiedKFold
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        classification_report, confusion_matrix,
    )
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
except ImportError as e:
    print(f"[ERROR] Missing ML dependency: {e}")
    print("Install with: pip install scikit-learn joblib pandas numpy")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TRAINING_DIR = Path(__file__).resolve().parent
MODEL_OUT    = PROJECT_ROOT / "focus_model_real.joblib"
REPORT_OUT   = PROJECT_ROOT / "focus_model_real_report.json"
DEMO_MODEL   = PROJECT_ROOT / "focus_model_demo.joblib"

MIN_LABELED_SESSIONS = 10
MIN_CLASSES          = 2
MAX_CLASS_RATIO      = 9.0
MIN_STUDENTS         = 1
RECOMMENDED_SESSIONS = 50
RECOMMENDED_STUDENTS = 5

VALID_BINARY_LABELS = {"focused", "potentially_distracted"}
LABEL_TO_INT = {"focused": 0, "potentially_distracted": 1}

FEATURE_COLS = [
    "non_educational_ratio",
    "educational_ratio",
    "unknown_ratio",
    "app_switch_count",
    "unique_apps_count",
    "session_span_minutes",
]

SEP = "=" * 65


def _sep(title=""):
    print(f"\n{SEP}")
    if title:
        print(f"  {title}")
    print(SEP)


def find_latest_labeled_csv():
    matches = sorted(TRAINING_DIR.glob("*_labeled.csv"))
    return matches[-1] if matches else None


def load_and_validate(csv_path):
    _sep("STEP 1 - Loading labeled CSV")
    print(f"  File : {csv_path}")
    if not csv_path.exists():
        print(f"\n[FATAL] File not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path, encoding="utf-8")
    print(f"  Total rows in CSV : {len(df)}")

    required_cols = [
        "focus_label", "review_status", "non_educational_ratio",
        "educational_ratio", "unknown_ratio", "app_switch_count",
        "unique_apps_count", "session_span_seconds", "student_id_hash",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"\n[FATAL] CSV missing required columns: {missing}")
        sys.exit(1)

    reviewed_df = df[df["review_status"].str.strip() == "reviewed"].copy()
    labeled_df  = reviewed_df[
        reviewed_df["focus_label"].str.strip().isin(VALID_BINARY_LABELS)
    ].copy()

    n_reviewed  = len(reviewed_df)
    n_labeled   = len(labeled_df)
    n_uncertain = n_reviewed - n_labeled
    label_dist  = Counter(labeled_df["focus_label"].str.strip())
    student_dist = Counter(labeled_df["student_id_hash"].str.strip())

    print(f"  Reviewed rows       : {n_reviewed}")
    print(f"  Binary labeled      : {n_labeled}  (uncertain excluded: {n_uncertain})")
    print(f"  Label distribution  : {dict(label_dist)}")
    print(f"  Distinct students   : {len(student_dist)}")

    # HARD GATE 1
    if n_labeled < MIN_LABELED_SESSIONS:
        _sep("TRAINING CANNOT PROCEED")
        print(f"""
  REASON: Insufficient labeled sessions.
  Found   : {n_labeled} reviewed sessions with a binary label
  Required: {MIN_LABELED_SESSIONS} (hard minimum)
  Recommended: {RECOMMENDED_SESSIONS} for reliable generalisation

  LABELING CHECKLIST:
    [ ] Open: data/focus_training/session_label_template_*.csv
    [ ] Read: data/focus_training/labeling_guide.md
    [ ] Set focus_label = focused / potentially_distracted / uncertain
    [ ] Set review_status = reviewed for each verified row
    [ ] Add reviewer_id (e.g., reviewer_A)
    [ ] Save as: session_label_template_YYYYMMDD_HHMMSS_labeled.csv
    [ ] Need >= {MIN_LABELED_SESSIONS} binary-labeled rows to proceed
    [ ] Need both 'focused' AND 'potentially_distracted' labels

  No model file has been written. The demo model is unaffected.
""")
        sys.exit(2)

    # HARD GATE 2
    if len(label_dist) < MIN_CLASSES:
        _sep("TRAINING CANNOT PROCEED")
        missing_cls = list(VALID_BINARY_LABELS - set(label_dist.keys()))
        print(f"""
  REASON: Only one class present: {list(label_dist.keys())}
  Missing class: {missing_cls}
  Label sessions as '{missing_cls[0] if missing_cls else "the other class"}' and re-run.
  No model file has been written.
""")
        sys.exit(2)

    # HARD GATE 3
    majority = max(label_dist.values())
    minority = min(label_dist.values())
    ratio = majority / minority if minority > 0 else float("inf")
    if ratio > MAX_CLASS_RATIO:
        _sep("TRAINING CANNOT PROCEED")
        print(f"""
  REASON: Extreme class imbalance {dict(label_dist)}, ratio={ratio:.1f} (max={MAX_CLASS_RATIO:.1f})
  Label more minority-class sessions and re-run.
  No model file has been written.
""")
        sys.exit(2)

    # HARD GATE 4
    n_students = len(student_dist)
    if n_students < MIN_STUDENTS:
        _sep("TRAINING CANNOT PROCEED")
        print(f"  REASON: Insufficient students ({n_students} < {MIN_STUDENTS})")
        sys.exit(2)

    # Soft warnings
    print()
    if n_labeled < RECOMMENDED_SESSIONS:
        print(f"  [WARN] Only {n_labeled} sessions (recommended: {RECOMMENDED_SESSIONS}).")
        print("         Metrics are INDICATIVE ONLY - not statistically reliable.")
    if n_students < RECOMMENDED_STUDENTS:
        print(f"  [WARN] Only {n_students} student(s). Model may not generalise.")

    # Feature engineering
    _sep("STEP 2 - Feature Engineering")
    labeled_df = labeled_df.copy()
    labeled_df["session_span_minutes"] = (
        pd.to_numeric(labeled_df["session_span_seconds"], errors="coerce").fillna(0) / 60.0
    )
    for col in ["non_educational_ratio", "educational_ratio", "unknown_ratio",
                "app_switch_count", "unique_apps_count"]:
        labeled_df[col] = pd.to_numeric(labeled_df[col], errors="coerce").fillna(0)
    labeled_df["label_int"] = labeled_df["focus_label"].str.strip().map(LABEL_TO_INT)

    X = labeled_df[FEATURE_COLS].copy()
    y = labeled_df["label_int"].copy()
    student_ids = labeled_df["student_id_hash"].str.strip()

    for col in FEATURE_COLS:
        print(f"  {col:<30}  NaN={X[col].isna().sum()}  "
              f"min={X[col].min():.3f}  max={X[col].max():.3f}  mean={X[col].mean():.3f}")

    return X, y, student_ids, labeled_df, n_students, label_dist


def run_cross_validation(X, y, n_splits=5):
    _sep("STEP 3 - Cross-Validation")
    n = len(y)
    actual_splits = min(n_splits, n, int(y.value_counts().min()))
    actual_splits = max(2, actual_splits)
    if actual_splits < n_splits:
        print(f"  [WARN] Reduced to {actual_splits}-fold CV "
              f"(n={n}, minority={int(y.value_counts().min())})")
    print(f"  CV strategy: Stratified {actual_splits}-fold")

    cv = StratifiedKFold(n_splits=actual_splits, shuffle=True, random_state=42)
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(
            n_estimators=100, random_state=42,
            class_weight="balanced", max_features="sqrt"
        ))
    ])

    metrics = {"accuracy": [], "precision": [], "recall": [], "f1": []}
    for fold_i, (tr_idx, te_idx) in enumerate(cv.split(X, y), start=1):
        X_tr, X_te = X.iloc[tr_idx], X.iloc[te_idx]
        y_tr, y_te = y.iloc[tr_idx], y.iloc[te_idx]
        clf.fit(X_tr, y_tr)
        y_pred = clf.predict(X_te)
        acc = accuracy_score(y_te, y_pred)
        p, r, f, _ = precision_recall_fscore_support(y_te, y_pred, average="macro", zero_division=0)
        metrics["accuracy"].append(acc)
        metrics["precision"].append(p)
        metrics["recall"].append(r)
        metrics["f1"].append(f)
        print(f"  Fold {fold_i}: acc={acc:.3f} prec={p:.3f} rec={r:.3f} f1={f:.3f} "
              f"dist={dict(Counter(y_te.tolist()))}")

    results = {k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
               for k, v in metrics.items()}
    print(f"\n  CV summary ({actual_splits} folds):")
    for m, s in results.items():
        print(f"    {m:<12}  mean={s['mean']:.3f}  std={s['std']:.3f}")
    return results, actual_splits


def train_and_evaluate(X, y):
    _sep("STEP 4 - Final Model Training")
    n = len(y)
    minority_count = int(y.value_counts().min())
    can_split = (n >= 20) and (minority_count >= 4)

    if can_split:
        test_size = max(0.2, min(0.3, 6 / n))
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        print(f"  Train: {len(X_train)} rows   Test (held-out): {len(X_test)} rows")
    else:
        print(f"  [WARN] Too small for held-out split (n={n}, minority={minority_count}).")
        print("  Training on all data. Rely on CV metrics above.")
        X_train, y_train = X, y
        X_test, y_test = None, None

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(
            n_estimators=200, max_depth=None, min_samples_leaf=1,
            random_state=42, class_weight="balanced", max_features="sqrt",
        ))
    ])
    pipeline.fit(X_train, y_train)
    print("  Model trained successfully.")

    rf = pipeline.named_steps["rf"]
    importances = dict(zip(FEATURE_COLS, rf.feature_importances_.tolist()))
    print("\n  Feature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        print(f"    {feat:<30}  {imp:.4f}  {'#' * int(imp * 30)}")

    eval_metrics = {"feature_importances": importances}

    if X_test is not None:
        _sep("STEP 5 - Held-Out Evaluation")
        y_pred = pipeline.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        p, r, f, _ = precision_recall_fscore_support(y_test, y_pred, average="macro", zero_division=0)
        cm = confusion_matrix(y_test, y_pred).tolist()
        report_str = classification_report(
            y_test, y_pred,
            target_names=["Focused(0)", "Distracted(1)"],
            zero_division=0
        )
        print(f"\n  Held-out ({len(y_test)} rows):")
        print(f"    Accuracy  : {acc*100:.1f}%")
        print(f"    Precision : {p:.3f} (macro)")
        print(f"    Recall    : {r:.3f} (macro)")
        print(f"    F1        : {f:.3f} (macro)")
        print(f"  Confusion matrix:  {cm}")
        print("  Per-class report:")
        for line in report_str.strip().split("\n"):
            print("    " + line)

        eval_metrics.update({
            "held_out_n": len(y_test),
            "held_out_accuracy": round(acc, 4),
            "held_out_precision_macro": round(float(p), 4),
            "held_out_recall_macro": round(float(r), 4),
            "held_out_f1_macro": round(float(f), 4),
            "confusion_matrix": cm,
            "class_distribution_test": dict(Counter(y_test.tolist())),
        })
    else:
        eval_metrics["held_out_n"] = 0

    return pipeline, eval_metrics


def save_artifacts(pipeline, eval_metrics, cv_results, n_labeled,
                   n_students, label_dist, csv_path, n_cv_splits, dry_run):
    _sep("STEP 6 - Saving")
    assert MODEL_OUT.resolve() != DEMO_MODEL.resolve(), \
        "BUG: real model path equals demo path!"

    limitations = [
        f"Trained on {n_labeled} sessions from {n_students} student(s).",
        "Labels based on app-usage telemetry only — no direct classroom observation.",
        "Session-level features cannot capture within-session burst distractions.",
        "~50% of events are 'unknown' category — reduces signal quality.",
        "Do not quote these accuracy figures as production-system performance.",
    ]
    if n_labeled < RECOMMENDED_SESSIONS:
        limitations.insert(0,
            f"CRITICAL: Only {n_labeled}/{RECOMMENDED_SESSIONS} recommended sessions. "
            "Metrics are INDICATIVE ONLY."
        )

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(csv_path),
        "model_file": str(MODEL_OUT),
        "demo_model_overwritten": False,
        "is_demo_model": False,
        "features": FEATURE_COLS,
        "label_map": LABEL_TO_INT,
        "gates": {
            "MIN_LABELED_SESSIONS": MIN_LABELED_SESSIONS,
            "MIN_CLASSES": MIN_CLASSES,
            "MAX_CLASS_RATIO": MAX_CLASS_RATIO,
            "MIN_STUDENTS": MIN_STUDENTS,
        },
        "dataset": {
            "n_labeled": n_labeled,
            "n_students": n_students,
            "label_distribution": dict(label_dist),
        },
        "cross_validation": {"n_splits": n_cv_splits, "results": cv_results},
        "evaluation": eval_metrics,
        "limitations": limitations,
    }

    if dry_run:
        print("  [DRY RUN] Validation passed. No files written.")
        print(json.dumps(report, indent=2, default=str))
        return

    joblib.dump(pipeline, MODEL_OUT)
    print(f"  Saved model  : {MODEL_OUT}")
    with open(REPORT_OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"  Saved report : {REPORT_OUT}")
    print("\n  NEXT: If evaluation is satisfactory, update home/ai_model.py")
    print("  to prefer focus_model_real.joblib and run Django tests.")


def main():
    parser = argparse.ArgumentParser(description="FocusFrame real training pipeline.")
    parser.add_argument("--labeled-csv", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _sep("FocusFrame - Real Model Training Pipeline")
    print("""
  Safety:
    WILL NOT overwrite focus_model_demo.joblib
    WILL NOT modify views.py, Firebase, or Android files
    WILL STOP if data gates are not met
    All accuracy figures come from held-out data or CV
""")

    csv_path = args.labeled_csv or find_latest_labeled_csv()

    if csv_path is None:
        _sep("TRAINING CANNOT PROCEED")
        print(f"""
  REASON: No labeled CSV found.
  Pattern: data/focus_training/*_labeled.csv
  Dir    : {TRAINING_DIR}

  LABELING CHECKLIST:
    [ ] Open session_label_template_*.csv
    [ ] Read labeling_guide.md
    [ ] Fill focus_label + set review_status=reviewed for each row
    [ ] Save as session_label_template_YYYYMMDD_HHMMSS_labeled.csv
    [ ] Need >= {MIN_LABELED_SESSIONS} binary-labeled rows
    [ ] Need both focused AND potentially_distracted labels

  No model file has been written. Demo model is unaffected.
""")
        sys.exit(2)

    X, y, student_ids, labeled_df, n_students, label_dist = load_and_validate(csv_path)
    n_labeled = len(y)

    if args.dry_run:
        print(f"\n  [DRY RUN] Validation passed. n={n_labeled}, students={n_students}")
        sys.exit(0)

    cv_results, n_cv_splits = run_cross_validation(X, y)
    pipeline, eval_metrics = train_and_evaluate(X, y)
    save_artifacts(pipeline, eval_metrics, cv_results, n_labeled,
                   n_students, label_dist, csv_path, n_cv_splits, args.dry_run)

    _sep("COMPLETE")
    print(f"  Model : {MODEL_OUT}")
    print(f"  Report: {REPORT_OUT}")
    print(f"  Demo  : {DEMO_MODEL}  <- UNTOUCHED")
    if n_labeled < RECOMMENDED_SESSIONS:
        print(f"\n  WARN: {n_labeled}/{RECOMMENDED_SESSIONS} sessions — accuracy indicative only.")
    print(f"  WARN: {n_students} student(s) — limited generalisation.")
    print()


if __name__ == "__main__":
    main()
