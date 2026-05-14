"""Train a multiclass Random Forest classifier for attack type identification.

This is separate from the binary intrusion detector in train.py.
The classifier learns to distinguish BENIGN from specific attack categories
(DDoS, PortScan, BruteForce, etc.), enabling the NIDS to report *what type*
of attack was detected alongside the binary INTRUSION verdict.

Run:
    python -m backend.pipeline.train_classifier
"""

import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    ATTACK_CLASSIFIER_PATH,
    CLEANED_CSV,
    LABEL_COLUMN,
    MODELS_DIR,
)

CLASSIFIER_SAMPLE = 150_000
CLASSIFIER_PARAMS = {
    "n_estimators": 200,
    "class_weight": "balanced",
    "n_jobs": -1,
    "random_state": 42,
}


def load_stratified_sample(
    path: Path = CLEANED_CSV,
    n: int = CLASSIFIER_SAMPLE,
) -> tuple[pd.DataFrame, pd.Series]:
    """Load cleaned.csv and build a proportional stratified sample across all classes.

    Args:
        path: Path to cleaned.csv produced by preprocess.py.
        n: Target total rows; each class contributes proportionally.

    Returns:
        Tuple (X, y) where y contains original string labels (multiclass).

    Raises:
        FileNotFoundError: If cleaned.csv is missing.
    """
    print(f"[1/3] Loading data from: {path}")
    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at {path}. "
            "Run backend/pipeline/preprocess.py first."
        )

    df = pd.read_csv(path, low_memory=False)
    n = min(n, len(df))
    frac = n / len(df)

    print(f"      Total rows : {len(df):,}  |  Classes : {df[LABEL_COLUMN].nunique()}")
    print(f"      Sampling {frac:.1%} per class (target {n:,} rows total)")

    groups = []
    for label, group in df.groupby(LABEL_COLUMN):
        k = max(1, int(frac * len(group)))
        groups.append(group.sample(n=min(k, len(group)), random_state=42))

    sample = pd.concat(groups).sample(frac=1, random_state=42)
    y = sample[LABEL_COLUMN]
    X = sample.drop(columns=[LABEL_COLUMN])

    print(f"      Sample size : {len(sample):,}")
    print(f"      Class breakdown:\n{y.value_counts().to_string()}")
    return X, y


def train_classifier(X: pd.DataFrame, y: pd.Series) -> RandomForestClassifier:
    """Fit a multiclass RandomForestClassifier on the labeled sample.

    Args:
        X: Feature matrix (numeric, all CICIDS2017 flow features).
        y: String label series — BENIGN, DDoS, PortScan, BruteForce, etc.

    Returns:
        Fitted RandomForestClassifier instance.
    """
    print(f"\n[2/3] Training RandomForestClassifier  (n={len(X):,}) ...")
    print(f"      Params : {CLASSIFIER_PARAMS}")
    t0 = time.time()
    model = RandomForestClassifier(**CLASSIFIER_PARAMS)
    model.fit(X, y)
    print(f"      Done in {time.time() - t0:.1f}s")
    return model


def evaluate_and_save(
    model: RandomForestClassifier,
    X: pd.DataFrame,
    y: pd.Series,
) -> None:
    """Print a classification report on the training sample and save the model.

    Args:
        model: Fitted classifier.
        X: Feature matrix (same data used for training).
        y: True string labels.
    """
    print("\n[3/3] Evaluating on training sample ...")
    y_pred = model.predict(X)
    print(classification_report(y, y_pred, digits=3))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ATTACK_CLASSIFIER_PATH)
    size_mb = ATTACK_CLASSIFIER_PATH.stat().st_size / 1_048_576
    print(f"      Saved -> {ATTACK_CLASSIFIER_PATH.name}  ({size_mb:.1f} MB)")


def run_training() -> RandomForestClassifier:
    """Execute the full attack-type classifier training pipeline.

    Steps:
        1. Load cleaned.csv and build a 150k stratified sample.
        2. Train RandomForest(200 trees, balanced weights) on all classes.
        3. Print classification report and save attack_classifier.pkl.

    Returns:
        Fitted RandomForestClassifier instance.
    """
    print("=" * 60)
    print("  Attack Type Classifier — Training Pipeline")
    print("=" * 60)

    X, y = load_stratified_sample()
    model = train_classifier(X, y)
    evaluate_and_save(model, X, y)

    print("\n" + "=" * 60)
    print("  Training complete.  attack_classifier.pkl saved.")
    print("=" * 60)
    return model


if __name__ == "__main__":
    run_training()
