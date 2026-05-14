"""Central configuration: all file paths and model hyperparameters."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
ATTACK_CLASSIFIER_PATH = MODELS_DIR / "attack_classifier.pkl"

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

RF_TRAIN_SAMPLE = 150_000  # total rows for RF (stratified across all labels)

RF_PARAMS = {
    "n_estimators": 100,
    "class_weight": "balanced",
    "max_features": "sqrt",
    "random_state": 42,
    "n_jobs": -1,
}

RF_PATH = MODELS_DIR / "random_forest.pkl"

# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------
ENSEMBLE_THRESHOLD = 2   # votes needed (out of N models) to flag as intrusion

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
API_HOST = "0.0.0.0"
API_PORT = 8000

# ---------------------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFY_CONFIDENCE_THRESHOLD = 0.75

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "nids-secret-key-change-in-production")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ACCESS_TOKEN_EXPIRE_HOURS = 24
