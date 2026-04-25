"""All API route handlers.

Endpoints:
    POST /api/predict   — score one raw feature vector with the ensemble
    POST /api/simulate  — run ensemble on 100 random rows from cleaned.csv
    GET  /api/alerts    — list recent alerts from the DB
    GET  /api/stats     — aggregate detection statistics
    GET  /api/health    — liveness check
"""

import random
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.schemas import (
    APIResponse,
    AlertOut,
    ModelVotes,
    PredictRequest,
    PredictResponse,
    SimulateRow,
    SimulateSummary,
    StatsResponse,
)
from backend.config import CLEANED_CSV, LABEL_COLUMN, SAMPLE_CSV
from backend.db.database import Alert, get_db
from backend.pipeline.predict import predict_batch_scaled, predict_single

router = APIRouter(prefix="/api")

SIMULATE_ROWS = 100


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> APIResponse:
    """Liveness probe — confirms the API is reachable."""
    return APIResponse.ok({"message": "NIDS API is running"})


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=APIResponse)
def predict(body: PredictRequest, db: Session = Depends(get_db)) -> APIResponse:
    """Score a single raw network-flow feature vector with the 3-model ensemble.

    Applies the saved StandardScaler to the raw features before inference.
    If the ensemble predicts INTRUSION the alert is persisted to SQLite.

    Args:
        body: PredictRequest containing feature dict and optional metadata.
        db:   Injected database session.

    Returns:
        APIResponse whose data is a PredictResponse.
    """
    try:
        result = predict_single(body.features)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    alert_id = None
    if result["prediction"] == "INTRUSION":
        alert = Alert(
            timestamp=body.timestamp,
            source_ip=body.source_ip,
            destination_ip=body.destination_ip,
            protocol=body.protocol,
            prediction=result["prediction"],
            model_votes=result["model_votes"],
            attack_confidence=result["attack_confidence"],
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

    payload = PredictResponse(
        prediction=result["prediction"],
        model_votes=ModelVotes(**result["model_votes"]),
        attack_confidence=result["attack_confidence"],
        vote_sum=result["vote_sum"],
        alert_id=alert_id,
    )
    return APIResponse.ok(payload.model_dump())


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------

@router.post("/simulate", response_model=APIResponse)
def simulate(db: Session = Depends(get_db)) -> APIResponse:
    """Run the ensemble on 100 random rows from cleaned.csv and save intrusions.

    Rows are drawn from the pre-scaled cleaned dataset so no re-scaling is
    applied.  Intrusion rows are persisted to the alerts table.

    Args:
        db: Injected database session.

    Returns:
        APIResponse whose data is a SimulateSummary.
    """
    # Prefer the full cleaned dataset locally; fall back to the committed sample on Render.
    csv_path = CLEANED_CSV if CLEANED_CSV.exists() else SAMPLE_CSV
    if not csv_path.exists():
        raise HTTPException(
            status_code=503,
            detail="No dataset available for simulation. "
                   "Expected data/processed/sample.csv to be present.",
        )

    df = pd.read_csv(csv_path, low_memory=False).sample(
        n=SIMULATE_ROWS, random_state=None  # different each call
    )
    labels = df[LABEL_COLUMN].tolist() if LABEL_COLUMN in df.columns else ["unknown"] * SIMULATE_ROWS
    X = df.drop(columns=[LABEL_COLUMN], errors="ignore")

    try:
        results = predict_batch_scaled(X)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    now = datetime.utcnow()
    alerts_saved = 0
    model_agreement: dict[str, int] = {"isolation_forest": 0, "lof": 0, "svm": 0}
    intrusion_count = 0
    row_results: list[SimulateRow] = []

    for i, res in enumerate(results):
        for model_name, vote in res["model_votes"].items():
            model_agreement[model_name] += vote

        src_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"8.8.{random.randint(1, 254)}.{random.randint(1, 254)}"

        if res["prediction"] == "INTRUSION":
            intrusion_count += 1
            alert = Alert(
                timestamp=now,
                source_ip=src_ip,
                destination_ip=dst_ip,
                protocol="TCP",
                prediction=res["prediction"],
                model_votes=res["model_votes"],
                attack_confidence=res["attack_confidence"],
                created_at=now,
            )
            db.add(alert)
            alerts_saved += 1
        row_results.append(SimulateRow(
            index=i,
            label=labels[i],
            prediction=res["prediction"],
            model_votes=res["model_votes"],
            attack_confidence=res["attack_confidence"],
        ))

    db.commit()

    summary = SimulateSummary(
        rows_evaluated=SIMULATE_ROWS,
        intrusions_detected=intrusion_count,
        normal_count=SIMULATE_ROWS - intrusion_count,
        detection_rate=round(intrusion_count / SIMULATE_ROWS, 4),
        alerts_saved=alerts_saved,
        model_agreement=model_agreement,
        rows=row_results,
    )
    return APIResponse.ok(summary.model_dump())


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=APIResponse)
def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    prediction: str | None = Query(default=None, description="Filter by 'INTRUSION' or 'NORMAL'."),
    db: Session = Depends(get_db),
) -> APIResponse:
    """Return recent alerts from the database, newest first.

    Args:
        limit:      Maximum number of rows to return (1–500, default 50).
        offset:     Number of rows to skip for pagination.
        prediction: Optional filter — 'INTRUSION' or 'NORMAL'.
        db:         Injected database session.

    Returns:
        APIResponse whose data contains a list of AlertOut dicts plus total count.
    """
    query = db.query(Alert)
    if prediction:
        query = query.filter(Alert.prediction == prediction.upper())

    total = query.count()
    alerts = (
        query.order_by(Alert.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return APIResponse.ok({
        "total": total,
        "offset": offset,
        "limit": limit,
        "alerts": [AlertOut.model_validate(a).model_dump() for a in alerts],
    })


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=APIResponse)
def get_stats(db: Session = Depends(get_db)) -> APIResponse:
    """Return aggregate detection statistics across all stored alerts.

    Args:
        db: Injected database session.

    Returns:
        APIResponse whose data is a StatsResponse.
    """
    all_alerts = db.query(Alert).all()
    total = len(all_alerts)
    intrusions = [a for a in all_alerts if a.prediction == "INTRUSION"]
    intrusion_count = len(intrusions)

    model_vote_totals: dict[str, int] = {"isolation_forest": 0, "lof": 0, "svm": 0}
    for alert in all_alerts:
        if isinstance(alert.model_votes, dict):
            for model_name, vote in alert.model_votes.items():
                if model_name in model_vote_totals:
                    model_vote_totals[model_name] += int(vote)

    stats = StatsResponse(
        total_alerts=total,
        intrusion_count=intrusion_count,
        normal_count=total - intrusion_count,
        detection_rate=round(intrusion_count / total, 4) if total else 0.0,
        model_vote_totals=model_vote_totals,
    )
    return APIResponse.ok(stats.model_dump())
