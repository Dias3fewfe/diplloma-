"""Train Isolation Forest, Local Outlier Factor, and One-Class SVM.

All three models are unsupervised outlier detectors trained exclusively on
BENIGN traffic rows.  They learn what 'normal' looks like; anything that
deviates is scored as an anomaly at inference time.

To keep runtime practical, each model trains on a capped random sample of
BENIGN rows (nested subsets, all seeded with random_state=42):
    Isolation Forest : 200,000 rows
    LOF              :  50,000 rows  (first 50k of the ISO sample)
    One-Class SVM    :  30,000 rows  (first 30k of the LOF sample)

Run:
    python -m backend.pipeline.train
"""

import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    CLEANED_CSV,
    ISO_FOREST_PATH,
    ISO_TRAIN_SAMPLE,
    ISOLATION_FOREST_PARAMS,
    LABEL_COLUMN,
    LOF_PARAMS,
    LOF_PATH,
    LOF_TRAIN_SAMPLE,
    MODELS_DIR,
    OCSVM_PARAMS,
    OCSVM_PATH,
    SVM_TRAIN_SAMPLE,
)

BENIGN_LABEL = "BENIGN"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_benign_sample(path: Path = CLEANED_CSV) -> pd.DataFrame:
    """Load cleaned data, filter BENIGN rows, and draw a 200k random sample.

    The returned DataFrame is the master sample from which all three models
    draw their nested subsets, ensuring consistency across models.

    Args:
        path: Path to cleaned.csv produced by preprocess.py.

    Returns:
        DataFrame of up to ISO_TRAIN_SAMPLE BENIGN rows (label column removed).

    Raises:
        FileNotFoundError: If cleaned.csv is missing.
    """
    print(f"[1/4] Loading cleaned data from: {path}")
    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at {path}. "
            "Run backend/pipeline/preprocess.py first."
        )

    df = pd.read_csv(path, low_memory=False)
    print(f"      Total rows loaded : {len(df):,}")

    benign_all = df[df[LABEL_COLUMN] == BENIGN_LABEL].drop(columns=[LABEL_COLUMN])
    print(f"      BENIGN rows total : {len(benign_all):,}  "
          f"({len(benign_all) / len(df) * 100:.1f}% of dataset)")

    n = min(ISO_TRAIN_SAMPLE, len(benign_all))
    benign_sample = benign_all.sample(n=n, random_state=42)
    print(f"      Master sample     : {len(benign_sample):,} rows  (random_state=42)")
    return benign_sample


# ---------------------------------------------------------------------------
# Training functions
# ---------------------------------------------------------------------------

def train_isolation_forest(X: pd.DataFrame) -> IsolationForest:
    """Fit Isolation Forest on up to ISO_TRAIN_SAMPLE BENIGN rows.

    Args:
        X: Master BENIGN sample (already capped at 200k rows).

    Returns:
        Fitted IsolationForest instance.
    """
    print(f"\n[2/4] Training Isolation Forest  (n={len(X):,}) ...")
    print(f"      Params : {ISOLATION_FOREST_PARAMS}")
    t0 = time.time()

    model = IsolationForest(**ISOLATION_FOREST_PARAMS)
    model.fit(X)

    print(f"      Done in {time.time() - t0:.1f}s")
    return model


def train_lof(X: pd.DataFrame) -> LocalOutlierFactor:
    """Fit Local Outlier Factor on up to LOF_TRAIN_SAMPLE BENIGN rows.

    Uses the first LOF_TRAIN_SAMPLE rows of the master sample so the
    subset is nested inside the Isolation Forest training set.

    novelty=True enables predict() on new data after fitting.

    Args:
        X: Master BENIGN sample.

    Returns:
        Fitted LocalOutlierFactor instance.
    """
    n = min(LOF_TRAIN_SAMPLE, len(X))
    X_lof = X.iloc[:n]
    print(f"\n[3/4] Training Local Outlier Factor  (n={len(X_lof):,}) ...")
    print(f"      Params : {LOF_PARAMS}")
    t0 = time.time()

    model = LocalOutlierFactor(**LOF_PARAMS)
    model.fit(X_lof)

    print(f"      Done in {time.time() - t0:.1f}s")
    return model


def train_ocsvm(X: pd.DataFrame) -> OneClassSVM:
    """Fit One-Class SVM on up to SVM_TRAIN_SAMPLE BENIGN rows.

    OneClassSVM has O(n^2) training complexity. A 30k subsample keeps
    runtime under a minute while still capturing the normal-traffic manifold.
    Uses the first SVM_TRAIN_SAMPLE rows of the master sample.

    Args:
        X: Master BENIGN sample.

    Returns:
        Fitted OneClassSVM instance.
    """
    n = min(SVM_TRAIN_SAMPLE, len(X))
    X_svm = X.iloc[:n]
    print(f"\n[4/4] Training One-Class SVM  (n={len(X_svm):,}) ...")
    print(f"      Params : {OCSVM_PARAMS}")
    t0 = time.time()

    model = OneClassSVM(**OCSVM_PARAMS)
    model.fit(X_svm)

    print(f"      Done in {time.time() - t0:.1f}s")
    return model


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_model(model: object, path: Path, name: str) -> None:
    """Serialise a fitted model to disk with joblib.

    Args:
        model: Fitted scikit-learn estimator.
        path: Destination .pkl path (parent dir created if needed).
        name: Human-readable label for log output.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    size_mb = path.stat().st_size / 1_048_576
    print(f"   {name:25s} saved -> {path.name}  ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_training() -> dict:
    """Execute the full training pipeline and save all three models.

    Steps:
        1. Load & sample BENIGN rows (master sample, 200k rows).
        2. Train Isolation Forest on the full master sample (200k).
        3. Train LOF on first 50k rows of master sample.
        4. Train One-Class SVM on first 30k rows of master sample.
        5. Save each model as a .pkl file in backend/models/.

    Returns:
        Dict mapping model names to fitted instances.
    """
    print("=" * 60)
    print("  Model Training Pipeline")
    print("=" * 60)

    X_master = load_benign_sample()

    iso = train_isolation_forest(X_master)
    lof = train_lof(X_master)
    svm = train_ocsvm(X_master)

    print("\n[Saving models]")
    save_model(iso, ISO_FOREST_PATH, "Isolation Forest")
    save_model(lof, LOF_PATH, "Local Outlier Factor")
    save_model(svm, OCSVM_PATH, "One-Class SVM")

    print("\n" + "=" * 60)
    print("  Training complete.  All 3 models saved.")
    print("=" * 60)

    return {"isolation_forest": iso, "lof": lof, "svm": svm}


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    models = run_training()
    print(f"\nModels available: {list(models.keys())}")
