"""Data cleaning and feature engineering for CICIDS2017.

Run directly to execute the full preprocessing pipeline:
    python -m backend.pipeline.preprocess
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.preprocessing import StandardScaler

# Allow running as a script from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import (
    CLEANED_CSV,
    LABEL_COLUMN,
    MODELS_DIR,
    NULL_DROP_THRESHOLD,
    PROCESSED_DIR,
    RAW_CSV,
    SCALER_PATH,
)


# ---------------------------------------------------------------------------
# Individual pipeline steps
# ---------------------------------------------------------------------------

def load_raw(path: Path = RAW_CSV) -> pd.DataFrame:
    """Load the raw CICIDS2017 CSV and print basic info."""
    print(f"[1/6] Loading raw data from: {path}")
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. "
            "Place CICIDS2017.csv in data/raw/ and retry."
        )

    df = pd.read_csv(path, low_memory=False)
    print(f"      Shape      : {df.shape}")
    print(f"      Columns    : {df.columns.tolist()}")
    return df


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading/trailing whitespace from every column name."""
    print("[2/6] Stripping whitespace from column names …")
    before = set(df.columns)
    df.columns = df.columns.str.strip()
    after = set(df.columns)
    renamed = {b for b in before if b.strip() != b}
    if renamed:
        print(f"      Fixed {len(renamed)} column name(s): {renamed}")
    else:
        print("      All column names already clean.")
    return df


def drop_high_null_columns(
    df: pd.DataFrame, threshold: float = NULL_DROP_THRESHOLD
) -> pd.DataFrame:
    """Drop columns whose null fraction exceeds *threshold*.

    Args:
        df: Input DataFrame.
        threshold: Maximum allowed null fraction (0–1).

    Returns:
        DataFrame with offending columns removed.
    """
    print(f"[3/6] Dropping columns with >{threshold*100:.0f}% null values …")
    null_frac = df.isnull().mean()
    bad_cols = null_frac[null_frac > threshold].index.tolist()
    if bad_cols:
        print(f"      Removing {len(bad_cols)} column(s): {bad_cols}")
        df = df.drop(columns=bad_cols)
    else:
        print("      No columns exceed the null threshold.")
    return df


def handle_infinite_values(df: pd.DataFrame) -> pd.DataFrame:
    """Replace ±inf with NaN, then drop rows that contain any NaN.

    Args:
        df: Input DataFrame (numeric columns only affected).

    Returns:
        Clean DataFrame with no infinite or NaN values.
    """
    print("[4/6] Replacing infinite values with NaN and dropping those rows …")
    rows_before = len(df)

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)

    df = df.dropna()
    dropped = rows_before - len(df)
    print(f"      Dropped {dropped:,} rows  |  Remaining: {len(df):,}")
    return df


def separate_label(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split DataFrame into feature matrix X and label series y.

    Args:
        df: DataFrame that must contain a column named by LABEL_COLUMN.

    Returns:
        Tuple (X, y) where X has the label column removed.
    """
    print(f"[5/6] Separating label column '{LABEL_COLUMN}' from features …")
    if LABEL_COLUMN not in df.columns:
        raise KeyError(
            f"Column '{LABEL_COLUMN}' not found. "
            f"Available columns: {df.columns.tolist()}"
        )
    y = df[LABEL_COLUMN].copy()
    X = df.drop(columns=[LABEL_COLUMN])

    # Drop any remaining non-numeric columns (e.g. IP addresses)
    non_numeric = X.select_dtypes(exclude=[np.number]).columns.tolist()
    if non_numeric:
        print(f"      Dropping non-numeric feature columns: {non_numeric}")
        X = X.drop(columns=non_numeric)

    print(f"      Feature shape : {X.shape}")
    print(f"      Label counts  :\n{y.value_counts()}")
    return X, y


def scale_features(X: pd.DataFrame) -> tuple[pd.DataFrame, StandardScaler]:
    """Fit a StandardScaler on X and return the scaled DataFrame and scaler.

    Args:
        X: Numeric feature matrix.

    Returns:
        Tuple (X_scaled, fitted_scaler).
    """
    print("[6/6] Fitting StandardScaler …")
    scaler = StandardScaler()
    X_scaled_arr = scaler.fit_transform(X)
    X_scaled = pd.DataFrame(X_scaled_arr, columns=X.columns, index=X.index)
    print(f"      Scaler fitted on {X_scaled.shape[1]} features.")
    return X_scaled, scaler


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_cleaned_data(X_scaled: pd.DataFrame, y: pd.Series) -> None:
    """Persist the scaled feature matrix with its label column to CSV.

    Args:
        X_scaled: Scaled feature DataFrame.
        y: Label Series aligned with X_scaled.
    """
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = X_scaled.copy()
    out[LABEL_COLUMN] = y.values
    out.to_csv(CLEANED_CSV, index=False)
    print(f"   Cleaned data saved -> {CLEANED_CSV}  ({out.shape})")


def save_scaler(scaler: StandardScaler) -> None:
    """Serialise the fitted scaler with joblib.

    Args:
        scaler: Fitted StandardScaler instance.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, SCALER_PATH)
    print(f"   Scaler saved     -> {SCALER_PATH}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_preprocessing() -> tuple[pd.DataFrame, pd.Series]:
    """Execute the full preprocessing pipeline end-to-end.

    Steps:
        1. Load raw CSV.
        2. Strip column-name whitespace.
        3. Drop high-null columns.
        4. Replace ±inf → NaN, drop NaN rows.
        5. Separate label from features.
        6. Scale features with StandardScaler.
        7. Save cleaned CSV and scaler artefact.

    Returns:
        Tuple (X_scaled, y) — scaled features and label series.
    """
    print("=" * 60)
    print("  CICIDS2017 Preprocessing Pipeline")
    print("=" * 60)

    df = load_raw()
    df = clean_column_names(df)
    df = drop_high_null_columns(df)
    df = handle_infinite_values(df)
    X, y = separate_label(df)
    X_scaled, scaler = scale_features(X)

    print("\n[Saving artefacts]")
    save_cleaned_data(X_scaled, y)
    save_scaler(scaler)

    print("\n" + "=" * 60)
    print("  Preprocessing complete.")
    print("=" * 60)
    return X_scaled, y


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    X_scaled, y = run_preprocessing()

    print("\n[Final summary]")
    print(f"  Feature matrix shape : {X_scaled.shape}")
    print(f"  Label value_counts   :\n{y.value_counts()}")
