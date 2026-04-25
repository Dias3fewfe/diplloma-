"""Central configuration: all file paths and model hyperparameters."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Root paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT_DIR / "backend" / "models"
DB_DIR = ROOT_DIR / "backend" / "db"

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
RAW_CSV = RAW_DIR / "CICIDS2017.csv"
CLEANED_CSV = PROCESSED_DIR / "cleaned.csv"
SAMPLE_CSV = PROCESSED_DIR / "sample.csv"   # 5k-row subset committed to git

# ---------------------------------------------------------------------------
# Serialised artefacts
# ---------------------------------------------------------------------------
SCALER_PATH = MODELS_DIR / "scaler.pkl"
ISO_FOREST_PATH = MODELS_DIR / "isolation_forest.pkl"
LOF_PATH = MODELS_DIR / "lof.pkl"
OCSVM_PATH = MODELS_DIR / "svm.pkl"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DB_PATH = DB_DIR / "alerts.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------
LABEL_COLUMN = "Label"
NULL_DROP_THRESHOLD = 0.40   # drop columns with > 40 % nulls

# ---------------------------------------------------------------------------
# Model hyperparameters
# ---------------------------------------------------------------------------
ISOLATION_FOREST_PARAMS = {
    "n_estimators": 100,
    "max_samples": "auto",
    "contamination": 0.05,
    "random_state": 42,
    "n_jobs": -1,
}

# Per-model row caps (BENIGN only) — subsets are nested for consistency
ISO_TRAIN_SAMPLE = 200_000
LOF_TRAIN_SAMPLE = 50_000
SVM_TRAIN_SAMPLE = 30_000
TEST_SAMPLE_SIZE = 10_000

LOF_PARAMS = {
    "n_neighbors": 20,
    "contamination": 0.05,
    "novelty": True,        # enables predict() on unseen data
    "n_jobs": -1,
}

OCSVM_PARAMS = {
    "kernel": "rbf",
    "nu": 0.05,
    "gamma": "scale",
}

# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------
ENSEMBLE_THRESHOLD = 2   # votes needed (out of 3) to flag as intrusion

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
API_HOST = "0.0.0.0"
API_PORT = 8000
