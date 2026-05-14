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
    ATTACK_CLASSIFIER_PATH,
    ENSEMBLE_THRESHOLD,
    ISO_FOREST_PATH,
    LOF_PATH,
    OCSVM_PATH,
    RF_PATH,
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
    # Random Forest is optional — loaded automatically once trained
    if RF_PATH.exists():
        loaded["random_forest"] = joblib.load(RF_PATH)
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

    votes = {}
    for name, model in models.items():
        if name == "scaler":
            continue
        raw = model.predict(X_scaled)
        # Supervised classifiers (e.g. RandomForest) output 0/1 directly;
        # outlier detectors output +1/-1 which need conversion.
        if hasattr(model, "classes_"):
            votes[name] = raw.astype(int)
        else:
            votes[name] = _sklearn_to_vote(raw)

    vote_matrix = np.stack(list(votes.values()), axis=1)  # (n, n_models)
    n_models = vote_matrix.shape[1]
    vote_sums = vote_matrix.sum(axis=1)

    results = []
    for i in range(len(X_scaled)):
        vote_sum = int(vote_sums[i])
        results.append({
            "prediction": "INTRUSION" if vote_sum >= ENSEMBLE_THRESHOLD else "NORMAL",
            "model_votes": {name: int(arr[i]) for name, arr in votes.items()},
            "attack_confidence": round(vote_sum / n_models, 4),
            "vote_sum": vote_sum,
        })
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_attack_classifier():
    """Load the multiclass attack-type classifier from disk (cached).

    Returns:
        Fitted RandomForestClassifier, or None if not yet trained.
    """
    if not ATTACK_CLASSIFIER_PATH.exists():
        return None
    return joblib.load(ATTACK_CLASSIFIER_PATH)


def classify_attack_type(raw_features: dict[str, float]) -> dict[str, Any]:
    """Classify the specific attack type for a raw feature vector.

    Uses the multiclass RandomForest trained by train_classifier.py.
    Returns "Unknown" gracefully if the classifier has not been trained yet.

    Args:
        raw_features: Raw (unscaled) feature dict — same format as predict_single().

    Returns:
        Dict with keys:
            label      : str  — predicted class name (e.g. "DDoS", "PortScan", "BENIGN").
            confidence : float — probability of the predicted class (0.0–1.0).
    """
    model = _load_attack_classifier()
    if model is None:
        return {"label": "Unknown", "confidence": 0.0}

    feature_names = get_feature_names()
    if any(f not in raw_features for f in feature_names):
        return {"label": "Unknown", "confidence": 0.0}

    row = pd.DataFrame([[raw_features[f] for f in feature_names]], columns=feature_names)
    label = str(model.predict(row)[0])
    confidence = float(model.predict_proba(row)[0].max())
    return {"label": label, "confidence": round(confidence, 4)}


def classify_attack_type_batch(X: pd.DataFrame) -> list[dict[str, Any]]:
    """Classify attack types for a batch of rows from cleaned.csv.

    Args:
        X: DataFrame whose columns match those the classifier was trained on.
           Label column must already be removed.

    Returns:
        List of dicts with keys: label (str), confidence (float).
        Each entry corresponds to one row of X.
    """
    model = _load_attack_classifier()
    if model is None:
        return [{"label": "Unknown", "confidence": 0.0}] * len(X)

    feature_names = list(model.feature_names_in_)
    X_aligned = X.reindex(columns=feature_names, fill_value=0.0)
    labels = model.predict(X_aligned)
    probas = model.predict_proba(X_aligned)
    return [
        {"label": str(labels[i]), "confidence": round(float(probas[i].max()), 4)}
        for i in range(len(X_aligned))
    ]


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
