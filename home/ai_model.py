
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional heavy dependencies — wrapped so the module can be imported even
# when scikit-learn / joblib / pandas are not installed in this environment.
# ---------------------------------------------------------------------------
try:
    import joblib
    import pandas as pd
    import sklearn
    _DEPS_AVAILABLE = True
except ImportError:
    _DEPS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Model paths
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent.parent   # mobile_monitoring/

MODEL_PATH = _MODULE_DIR / "focus_model_demo.joblib"   # original demo model
REAL_MODEL_PATH = _MODULE_DIR / "focus_model_real.joblib"  # real model (may not exist)

# ---------------------------------------------------------------------------
# Model cache — separate caches so both can co-exist in a long-running server
# ---------------------------------------------------------------------------
_model = None        # demo model cache
_real_model = None   # real model cache


# ---------------------------------------------------------------------------
# FEATURES used by the real model (session-level)
# ---------------------------------------------------------------------------
REAL_FEATURE_COLS = [
    "non_educational_ratio",
    "educational_ratio",
    "unknown_ratio",
    "app_switch_count",
    "unique_apps_count",
    "session_span_minutes",
]

# FEATURES used by the demo model (per-event)
DEMO_FEATURE_COLS = ["duration_seconds", "non_educational"]


def predict_focus(duration_seconds, non_educational):
    """
    Predict student focus from a single usage record (per-event level).

    This function is intentionally UNCHANGED from the original implementation
    so that all existing callers (views.py, tests) continue to work.

    Returns a dict with keys: prediction (0/1), label (str), is_demo_model (True).
    Raises RuntimeError if ML dependencies are not installed.
    NOTE: This uses the demo model trained on synthetic data.
    """
    global _model

    if not _DEPS_AVAILABLE:
        raise RuntimeError(
            "ML dependencies (joblib, pandas, scikit-learn) are not installed. "
            "Install them with: pip install joblib pandas scikit-learn"
        )

    if _model is None:
        _model = joblib.load(MODEL_PATH)

    features = pd.DataFrame([{
        "duration_seconds": max(0, float(duration_seconds)),
        "non_educational": int(bool(non_educational)),
    }])

    prediction = int(_model.predict(features)[0])

    return {
        "prediction": prediction,
        "label": (
            "Potentially Distracted"
            if prediction == 1
            else "Focused"
        ),
        "is_demo_model": True,   # clearly labeled — synthetic training data
    }


def predict_focus_with_best_model(duration_seconds, non_educational,
                                  non_educational_ratio=None,
                                  educational_ratio=None,
                                  unknown_ratio=None,
                                  app_switch_count=None,
                                  unique_apps_count=None,
                                  session_span_minutes=None):
    """
    Predict student focus using the best available model:

      1. If focus_model_real.joblib exists (trained on human-reviewed labels),
         use the real model with session-level features.
         Returns is_demo_model=False.

      2. Otherwise fall back to focus_model_demo.joblib (synthetic data).
         Returns is_demo_model=True.

    The real model uses 6 session-level features:
      non_educational_ratio, educational_ratio, unknown_ratio,
      app_switch_count, unique_apps_count, session_span_minutes.

    When session-level features are not provided (e.g., called from the
    per-event receive_phone_usage endpoint), we fall back to the demo model
    regardless of whether the real model exists.

    Parameters
    ----------
    duration_seconds    : float  — per-event app usage duration (for demo fallback)
    non_educational     : bool   — whether app is non-educational (for demo fallback)
    non_educational_ratio : float — fraction of session in non-educational apps
    educational_ratio   : float  — fraction of session in educational apps
    unknown_ratio       : float  — fraction of session in unknown apps
    app_switch_count    : int    — number of app switches in the session
    unique_apps_count   : int    — number of distinct apps used in the session
    session_span_minutes : float — total observed session duration in minutes

    Returns
    -------
    dict with keys:
      prediction   (int)  — 0=Focused, 1=Potentially Distracted
      label        (str)  — human-readable label
      is_demo_model (bool) — True if using synthetic-data model
    """
    global _real_model

    if not _DEPS_AVAILABLE:
        raise RuntimeError(
            "ML dependencies (joblib, pandas, scikit-learn) are not installed. "
            "Install them with: pip install joblib pandas scikit-learn"
        )

    # Check if session-level features were provided and real model exists
    session_features_provided = all(v is not None for v in [
        non_educational_ratio, educational_ratio, unknown_ratio,
        app_switch_count, unique_apps_count, session_span_minutes
    ])

    if session_features_provided and REAL_MODEL_PATH.exists():
        # Load real model (cached after first call)
        if _real_model is None:
            _real_model = joblib.load(REAL_MODEL_PATH)

        features = pd.DataFrame([{
            "non_educational_ratio": float(non_educational_ratio),
            "educational_ratio":     float(educational_ratio),
            "unknown_ratio":         float(unknown_ratio),
            "app_switch_count":      float(app_switch_count),
            "unique_apps_count":     float(unique_apps_count),
            "session_span_minutes":  float(session_span_minutes),
        }])

        prediction = int(_real_model.predict(features)[0])
        return {
            "prediction": prediction,
            "label": (
                "Potentially Distracted"
                if prediction == 1
                else "Focused"
            ),
            "is_demo_model": False,
        }

    # Fall back to demo model (per-event)
    return predict_focus(duration_seconds, non_educational)
