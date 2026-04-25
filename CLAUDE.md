# Network Intrusion Detection System — Diploma Project

## Project Goal
Working web dashboard that detects network intrusions using an ensemble of 
3 outlier detection algorithms: Isolation Forest, Local Outlier Factor, One-Class SVM.
Ensemble uses majority voting. Dataset: CICIDS2017.

## Stack
- Backend: Python 3.11, FastAPI, scikit-learn, pandas, numpy, joblib
- Frontend: React 18, Recharts, TailwindCSS
- DB: SQLite via SQLAlchemy
- Dataset: CICIDS2017 (CSV files in /data/raw/)

## Project Structure
project/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── models/              # ML model files (.pkl)
│   ├── pipeline/
│   │   ├── preprocess.py    # Data cleaning & feature engineering
│   │   ├── train.py         # Train all 3 models + ensemble
│   │   └── predict.py       # Inference logic
│   ├── api/
│   │   ├── routes.py        # All API endpoints
│   │   └── schemas.py       # Pydantic models
│   └── db/
│       └── database.py      # SQLite setup, alerts table
├── frontend/
│   ├── src/
│   │   ├── components/      # Dashboard, AlertTable, Charts
│   │   └── App.jsx
├── data/
│   └── raw/                 # Put CICIDS2017 CSV files here
├── notebooks/               # Exploration only, not production
└── CLAUDE.md

## Key Business Logic
1. Input: network traffic features (44 columns from CICIDS2017)
2. Each model votes: 1 = anomaly, 0 = normal
3. Ensemble: if 2 or 3 models vote anomaly → flag as intrusion
4. Alert saved to SQLite with timestamp, severity, attack type
5. Dashboard shows: live alerts, detection rate, model agreement chart

## Conventions
- All ML code in backend/pipeline/
- Never hardcode file paths — use config.py
- Every function must have a docstring
- API responses always return JSON with {status, data, error}
- Keep frontend components small, max 150 lines per file

## Current Status — Updated 20.04.2026

### Completed ✅
- [x] Project structure created (backend/ frontend/ data/)
- [x] Dataset: CICIDS2017 from Kaggle (~170MB, single CSV, 2.2M rows)
- [x] backend/pipeline/preprocess.py — cleans data, saves cleaned.csv + scaler.pkl
- [x] backend/pipeline/train.py — trains IF (200k rows), LOF (50k), SVM (30k), saves .pkl files
- [x] backend/pipeline/evaluate.py — ensemble majority vote, F1=0.534
- [x] backend/pipeline/predict.py — inference logic with lru_cache
- [x] backend/db/database.py — SQLite, alerts table
- [x] backend/api/schemas.py — Pydantic models
- [x] backend/api/routes.py — /predict /simulate /alerts /stats /health
- [x] backend/main.py — FastAPI + CORS
- [x] frontend — React + Vite + Recharts + Tailwind
- [x] All 4 tabs working: Overview, Live Detection, Alerts, Models
- [x] UI redesigned: professional dark theme, no emojis, Grafana-style

### How to Run
Terminal 1 (backend):
uvicorn backend.main:app --reload --port 8000

Terminal 2 (frontend):
cd frontend && npm run dev

Dashboard: http://localhost:5173
API docs: http://localhost:8000/docs

### Remaining
- [ ] README.md for thesis
- [ ] docs/ folder with thesis documentation in Russian