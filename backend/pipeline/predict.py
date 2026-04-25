"""Inference logic: load models once, expose predict helpers for routes.

Two entry points:
  predict_single(raw_features)  — accepts a dict of raw (unscaled) feature
                                   values, applies the saved scaler, returns
                                   the ensemble result.
  predict_batch_scaled(df)      — accepts an already-scaled DataFrame (e.g.
                                   rows straight from cleaned.csv) and returns
                                   a list of result dicts.
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    ENSEMBLE_THRESHOLD,
    ISO_FOREST_PATH,
    LOF_PATH,
    OCSVM_PATH,
    SCALER_PATH,
)

# ---------------------------------------------------------------------------
# Model registry — loaded once per process
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_models() -> dict:
    """Load scaler and all three outlier models from disk (cached).

    Returns:
        Dict with keys: 'scaler', 'isolation_forest', 'lof', 'svm'.

    Raises:
        FileNotFoundError: If any artefact is missing.
    """
    required = {
        "scaler": SCALER_PATH,
        "isolation_forest": ISO_FOREST_PATH,
        "lof": LOF_PATH,
        "svm": OCSVM_PATH,
    }
    loaded = {}
    for name, path in required.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Required artefact missing: {path}. "
                "Run train.py (and preprocess.py for the scaler) first."
            )
        loaded[name] = joblib.load(path)
    return loaded


def get_feature_names() -> list[str]:
    """Return the feature names the scaler was fitted on.

    The StandardScaler stores feature_names_in_ when fitted with a DataFrame.

    Returns:
        List of feature column names (in the order the scaler expects).
    """
    models = _load_models()
    scaler = models["scaler"]
    if hasattr(scaler, "feature_names_in_"):
        return list(scaler.feature_names_in_)
    raise RuntimeError(
        "Scaler was not fitted with a named DataFrame — cannot retrieve feature names."
    )


# ---------------------------------------------------------------------------
# Core prediction helpers
# ---------------------------------------------------------------------------

def _sklearn_to_vote(raw: np.ndarray) -> np.ndarray:
    """Convert sklearn +1/-1 output to binary anomaly votes (0/1).

    Args:
        raw: Array of +1 (inlier) / -1 (outlier) values.

    Returns:
        Integer array: 1 = anomaly, 0 = normal.
    """
    return (raw == -1).astype(int)


def _run_ensemble(X_scaled: pd.DataFrame) -> list[dict[str, Any]]:
    """Run all three models on a scaled feature matrix and apply majority vote.

    Args:
        X_scaled: DataFrame whose column order matches the scaler's feature set.

    Returns:
        List of result dicts, one per row:
            prediction      : "INTRUSION" or "NORMAL"
            model_votes     : dict {model_name: 0 or 1}
            attack_confidence: float — fraction of models that voted anomaly
            vote_sum        : int (0-3)
    """
    models = _load_models()

    votes = {
        "isolation_forest": _sklearn_to_vote(
            models["isolation_forest"].predict(X_scaled)
        ),
        "lof": _sklearn_to_vote(models["lof"].predict(X_scaled)),
        "svm": _sklearn_to_vote(models["svm"].predict(X_scaled)),
    }

    vote_matrix = np.stack(list(votes.values()), axis=1)  # (n, 3)
    vote_sums = vote_matrix.sum(axis=1)

    results = []
    for i in range(len(X_scaled)):
        vote_sum = int(vote_sums[i])
        results.append({
            "prediction": "INTRUSION" if vote_sum >= ENSEMBLE_THRESHOLD else "NORMAL",
            "model_votes": {name: int(arr[i]) for name, arr in votes.items()},
            "attack_confidence": round(vote_sum / 3, 4),
            "vote_sum": vote_sum,
        })
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict_single(raw_features: dict[str, float]) -> dict[str, Any]:
    """Scale a single raw feature dict and return the ensemble prediction.

    Args:
        raw_features: Mapping of feature_name -> raw (unscaled) numeric value.
                      Must contain all features the scaler was trained on.

    Returns:
        Result dict with keys: prediction, model_votes, attack_confidence, vote_sum.

    Raises:
        ValueError: If any required feature is missing from raw_features.
    """
    feature_names = get_feature_names()
    missing = [f for f in feature_names if f not in raw_features]
    if missing:
        raise ValueError(f"Missing {len(missing)} required features: {missing[:10]}...")

    models = _load_models()
    row = pd.DataFrame([[raw_features[f] for f in feature_names]], columns=feature_names)
    row_scaled = pd.DataFrame(
        models["scaler"].transform(row), columns=feature_names
    )
    return _run_ensemble(row_scaled)[0]


def predict_batch_scaled(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Run ensemble on a batch of already-scaled rows (e.g. from cleaned.csv).

    Args:
        df: DataFrame with the same 77 feature columns as cleaned.csv
            (Label column must be removed before calling).

    Returns:
        List of result dicts, one per row.
    """
    feature_names = get_feature_names()
    # Align columns to scaler order; fill any gaps with 0
    df_aligned = df.reindex(columns=feature_names, fill_value=0.0)
    return _run_ensemble(df_aligned)
