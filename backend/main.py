"""FastAPI application entry point.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.api.auth_routes import router_auth
from backend.api.capture_routes import router_capture, set_main_loop, set_notifier
from backend.api.geo_routes import router_geo
from backend.api.routes import router
from backend.config import API_HOST, API_PORT
from backend.db.database import SessionLocal, init_db
from backend.notifications import TelegramNotifier

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
    allow_origins=["http://localhost:3000", "http://localhost:5173", "https://diplloma.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_auth)
app.include_router(router)
app.include_router(router_capture)
app.include_router(router_geo)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    """Initialise the SQLite database, event loop reference, and Telegram notifier."""
    import backend.api.capture_routes as cr
    init_db()
    cr._db_session_factory = SessionLocal
    set_main_loop(asyncio.get_event_loop())

    notifier = TelegramNotifier()
    app.state.notifier = notifier
    set_notifier(notifier)

    status = "configured" if notifier.is_configured() else "not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env)"
    print("Database initialised.")
    print(f"Telegram notifier: {status}")


# ---------------------------------------------------------------------------
# Dev convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=API_HOST, port=API_PORT, reload=True)
