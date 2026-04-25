"""FastAPI application entry point.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.routes import router
from backend.config import API_HOST, API_PORT
from backend.db.database import init_db

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Network Intrusion Detection System",
    description=(
        "Ensemble of Isolation Forest, Local Outlier Factor, and One-Class SVM "
        "trained on CICIDS2017 to detect anomalous network traffic in real time."
    ),
    version="1.0.0",
)

# Allow the React dev server (port 3000/5173) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup() -> None:
    """Initialise the SQLite database on first start."""
    init_db()
    print("Database initialised.")


# ---------------------------------------------------------------------------
# Dev convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=True)
