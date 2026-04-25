"""Evaluate the 3-model ensemble on a stratified test sample.

Loads all three trained models, runs predictions on a mixed BENIGN + attack
sample, applies majority-vote ensemble logic, and prints:
  - Per-model detection summary
  - Ensemble classification report (precision / recall / F1 per attack type)

Sklearn outlier detectors use the convention:
    +1  -> inlier  (normal traffic)
    -1  -> outlier (anomaly / potential intrusion)

We convert to binary votes: -1 -> 1 (anomaly vote), +1 -> 0 (normal vote).
Ensemble fires when vote_sum >= ENSEMBLE_THRESHOLD (default 2 out of 3).

Run:
    python -m backend.pipeline.evaluate
"""

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    CLEANED_CSV,
    ENSEMBLE_THRESHOLD,
    ISO_FOREST_PATH,
    LABEL_COLUMN,
    LOF_PATH,
    MODELS_DIR,
    OCSVM_PATH,
    TEST_SAMPLE_SIZE,
)

BENIGN_LABEL = "BENIGN"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_models() -> dict:
    """Load all three trained outlier-detection models from disk.

    Returns:
        Dict with keys 'isolation_forest', 'lof', 'svm'.

    Raises:
        FileNotFoundError: If any model file is missing.
    """
    paths = {
        "isolation_forest": ISO_FOREST_PATH,
        "lof": LOF_PATH,
        "svm": OCSVM_PATH,
    }
    models = {}
    print("[1/3] Loading trained models ...")
    for name, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Model not found: {path}. Run backend/pipeline/train.py first."
            )
        models[name] = joblib.load(path)
        print(f"      Loaded {name:25s} <- {path.name}")
    return models


def load_test_sample(
    path: Path = CLEANED_CSV,
    n: int = TEST_SAMPLE_SIZE,
    random_state: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a stratified test sample with BENIGN and attack rows.

    Samples proportionally from each label class so that rare attack types
    (Infiltration, Heartbleed) are still represented.

    Args:
        path: Path to cleaned.csv.
        n: Total number of rows to include in the sample.
        random_state: RNG seed for reproducibility.

    Returns:
        Tuple (X, y) — feature matrix and label series.
    """
    print(f"\n[2/3] Building stratified test sample (n={n:,}) ...")
    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found at {path}. "
            "Run backend/pipeline/preprocess.py first."
        )

    df = pd.read_csv(path, low_memory=False)
    label_counts = df[LABEL_COLUMN].value_counts()
    print(f"      Full dataset size : {len(df):,} rows  |  "
          f"{label_counts.shape[0]} classes")

    # Stratified sample: each class contributes proportionally, but every
    # class gets at least 1 row so rare attacks appear in evaluation.
    fractions = (label_counts / len(df)).clip(lower=1 / n)
    sampled_parts = []
    for label, frac in fractions.items():
        class_rows = df[df[LABEL_COLUMN] == label]
        k = max(1, int(frac * n))
        k = min(k, len(class_rows))
        sampled_parts.append(class_rows.sample(n=k, random_state=random_state))

    sample = pd.concat(sampled_parts).sample(frac=1, random_state=random_state)

    y = sample[LABEL_COLUMN].copy()
    X = sample.drop(columns=[LABEL_COLUMN])

    print(f"      Sample size       : {len(sample):,} rows")
    print(f"      Class breakdown   :\n{y.value_counts().to_string()}")
    return X, y


# ---------------------------------------------------------------------------
# Prediction helpers
# ---------------------------------------------------------------------------

def sklearn_to_anomaly_vote(raw_preds: np.ndarray) -> np.ndarray:
    """Convert sklearn outlier predictions to binary anomaly votes.

    sklearn uses +1 (inlier) / -1 (outlier).  We map to 0 (normal) / 1 (anomaly).

    Args:
        raw_preds: Array of +1/-1 values from model.predict().

    Returns:
        Integer array of 0s and 1s.
    """
    return ((raw_preds == -1).astype(int))


def predict_all(
    models: dict, X: pd.DataFrame
) -> dict[str, np.ndarray]:
    """Run each model's predict() and return anomaly votes (0/1).

    Args:
        models: Dict of fitted models from load_models().
        X: Feature matrix to score.

    Returns:
        Dict mapping model name -> 1-D array of anomaly votes (0 or 1).
    """
    votes = {}
    for name, model in models.items():
        raw = model.predict(X)
        votes[name] = sklearn_to_anomaly_vote(raw)
        anomaly_count = votes[name].sum()
        print(f"      {name:25s}: {anomaly_count:,} anomalies flagged "
              f"({anomaly_count/len(X)*100:.1f}%)")
    return votes


def ensemble_predict(
    votes: dict[str, np.ndarray], threshold: int = ENSEMBLE_THRESHOLD
) -> np.ndarray:
    """Apply majority-vote ensemble: flag row as intrusion if >= threshold models agree.

    Args:
        votes: Dict of per-model anomaly vote arrays (values 0 or 1).
        threshold: Minimum vote count to classify as intrusion.

    Returns:
        Binary array: 1 = INTRUSION, 0 = NORMAL.
    """
    vote_matrix = np.stack(list(votes.values()), axis=1)  # (n_rows, 3)
    vote_sum = vote_matrix.sum(axis=1)
    return (vote_sum >= threshold).astype(int)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_per_model_summary(
    votes: dict[str, np.ndarray], y_true_binary: np.ndarray, y_labels: pd.Series
) -> None:
    """Print a table showing how many attacks each model caught.

    Args:
        votes: Per-model anomaly vote arrays.
        y_true_binary: Ground truth: 1 = attack, 0 = BENIGN.
        y_labels: Original string Label series (for attack-type breakdown).
    """
    print("\n" + "-" * 60)
    print("  Per-Model Detection Summary")
    print("-" * 60)

    attack_mask = y_true_binary == 1
    n_attacks = attack_mask.sum()
    n_benign = (y_true_binary == 0).sum()

    print(f"  Total samples : {len(y_true_binary):,}  "
          f"(BENIGN={n_benign:,}, Attack={n_attacks:,})\n")

    header = f"  {'Model':<25} {'TP':>8} {'FP':>8} {'Recall':>8} {'FPR':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for name, vote in votes.items():
        tp = int((vote[attack_mask] == 1).sum())
        fp = int((vote[~attack_mask] == 1).sum())
        recall = tp / n_attacks if n_attacks else 0.0
        fpr = fp / n_benign if n_benign else 0.0
        print(f"  {name:<25} {tp:>8,} {fp:>8,} {recall:>7.1%} {fpr:>7.1%}")


def print_ensemble_report(
    y_pred: np.ndarray, y_true_binary: np.ndarray, y_labels: pd.Series
) -> None:
    """Print ensemble classification report at both binary and per-attack-type level.

    Args:
        y_pred: Ensemble predictions (0/1).
        y_true_binary: Binary ground truth (0=BENIGN, 1=attack).
        y_labels: Original string Label series.
    """
    print("\n" + "-" * 60)
    print("  Ensemble Classification Report  (binary: BENIGN vs INTRUSION)")
    print("-" * 60)
    print(classification_report(
        y_true_binary, y_pred,
        target_names=["BENIGN", "INTRUSION"],
        digits=3,
    ))

    # Per-attack-type breakdown for rows the ensemble flagged
    print("-" * 60)
    print("  Ensemble Detection Rate by Attack Type")
    print("-" * 60)
    attack_types = y_labels[y_true_binary == 1].unique()
    rows = []
    for atype in sorted(attack_types):
        mask = (y_labels == atype).values
        total = mask.sum()
        caught = int(y_pred[mask].sum())
        rows.append({
            "Attack Type": atype,
            "Total Samples": total,
            "Caught": caught,
            "Detection Rate": f"{caught/total:.1%}" if total else "N/A",
        })

    report_df = pd.DataFrame(rows).set_index("Attack Type")
    print(report_df.to_string())
    print()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_evaluation() -> None:
    """Execute the full evaluation pipeline end-to-end.

    Steps:
        1. Load trained models.
        2. Build a stratified 10,000-row test sample.
        3. Collect anomaly votes from each model.
        4. Apply ensemble majority-vote logic.
        5. Print per-model summary and ensemble classification report.
    """
    print("=" * 60)
    print("  Ensemble Evaluation Pipeline")
    print("=" * 60)

    models = load_models()
    X_test, y_labels = load_test_sample()

    # Ground truth: anything that isn't BENIGN is an attack
    y_true_binary = (y_labels != BENIGN_LABEL).astype(int).values

    print("\n[3/3] Running predictions ...")
    votes = predict_all(models, X_test)
    y_pred = ensemble_predict(votes)

    print_per_model_summary(votes, y_true_binary, y_labels)
    print_ensemble_report(y_pred, y_true_binary, y_labels)

    print("=" * 60)
    print("  Evaluation complete.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_evaluation()
