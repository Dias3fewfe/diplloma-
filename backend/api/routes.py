"""All API route handlers.

Endpoints:
    POST /api/predict              — score one raw feature vector with the ensemble
    POST /api/simulate             — run ensemble on 100 random rows from cleaned.csv
    GET  /api/alerts               — list recent alerts from the DB
    GET  /api/alerts/export/csv    — download all alerts as CSV
    GET  /api/alerts/export/pdf    — download all alerts as PDF
    GET  /api/stats                — aggregate detection statistics
    GET  /api/health               — liveness check
    GET  /api/notification-status  — Telegram notifier configuration status
"""

import csv
import io
import random
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
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
from backend.pipeline.predict import (
    classify_attack_type,
    classify_attack_type_batch,
    predict_batch_scaled,
    predict_single,
)

router = APIRouter(prefix="/api")

SIMULATE_ROWS = 100


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health")
def health() -> APIResponse:
    """Liveness probe — confirms the API is reachable."""
    return APIResponse.ok({"message": "NIDS API is running"})


@router.get("/notification-status")
def notification_status(request: Request) -> APIResponse:
    """Return whether the Telegram notifier is configured and active.

    Args:
        request: FastAPI request (provides access to app.state.notifier).

    Returns:
        APIResponse whose data contains telegram_configured (bool).
    """
    notifier = getattr(request.app.state, "notifier", None)
    configured = notifier.is_configured() if notifier else False
    return APIResponse.ok({"telegram_configured": configured})


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=APIResponse)
def predict(
    body: PredictRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    """Score a single raw network-flow feature vector with the ensemble.

    Applies the saved StandardScaler to the raw features before inference.
    If the ensemble predicts INTRUSION the alert is persisted to SQLite and,
    if confidence >= threshold, a Telegram notification is sent in background.

    Args:
        body:             PredictRequest with feature dict and optional metadata.
        background_tasks: FastAPI background task queue.
        request:          FastAPI request (provides access to app.state.notifier).
        db:               Injected database session.

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
    attack_type = "BENIGN"
    if result["prediction"] == "INTRUSION":
        cls = classify_attack_type(body.features)
        attack_type = cls["label"]
        alert = Alert(
            timestamp=body.timestamp,
            source_ip=body.source_ip,
            destination_ip=body.destination_ip,
            protocol=body.protocol,
            prediction=result["prediction"],
            model_votes=result["model_votes"],
            attack_confidence=result["attack_confidence"],
            attack_type=attack_type,
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        notifier = getattr(request.app.state, "notifier", None)
        if notifier:
            background_tasks.add_task(notifier.send_alert, {
                "attack_type": attack_type,
                "attack_confidence": result["attack_confidence"],
                "source_ip": body.source_ip,
                "protocol": body.protocol,
                "model_votes": result["model_votes"],
                "timestamp": body.timestamp,
            })

    votes = result["model_votes"]
    payload = PredictResponse(
        prediction=result["prediction"],
        model_votes=ModelVotes(
            isolation_forest=votes.get("isolation_forest", 0),
            lof=votes.get("lof", 0),
            svm=votes.get("svm", 0),
            random_forest=votes.get("random_forest", 0),
        ),
        attack_confidence=result["attack_confidence"],
        vote_sum=result["vote_sum"],
        alert_id=alert_id,
        attack_type=attack_type,
    )
    return APIResponse.ok(payload.model_dump())


# ---------------------------------------------------------------------------
# Simulate
# ---------------------------------------------------------------------------

@router.post("/simulate", response_model=APIResponse)
def simulate(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
) -> APIResponse:
    """Run the ensemble on 100 random rows from cleaned.csv and save intrusions.

    Rows are drawn from the pre-scaled cleaned dataset so no re-scaling is
    applied.  Intrusion rows are persisted to the alerts table.  A Telegram
    notification is sent (in background) for each intrusion above the threshold.

    Args:
        background_tasks: FastAPI background task queue.
        request:          FastAPI request (provides access to app.state.notifier).
        db:               Injected database session.

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
    model_agreement: dict[str, int] = {}
    intrusion_count = 0
    row_results: list[SimulateRow] = []

    attack_types = classify_attack_type_batch(X)

    for i, res in enumerate(results):
        for model_name, vote in res["model_votes"].items():
            model_agreement[model_name] = model_agreement.get(model_name, 0) + vote

        src_ip = f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"8.8.{random.randint(1, 254)}.{random.randint(1, 254)}"

        attack_type = attack_types[i]["label"] if res["prediction"] == "INTRUSION" else "BENIGN"

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
                attack_type=attack_type,
                created_at=now,
            )
            db.add(alert)
            alerts_saved += 1

            notifier = getattr(request.app.state, "notifier", None)
            if notifier:
                background_tasks.add_task(notifier.send_alert, {
                    "attack_type": attack_type,
                    "attack_confidence": res["attack_confidence"],
                    "source_ip": src_ip,
                    "protocol": "TCP",
                    "model_votes": res["model_votes"],
                    "timestamp": now,
                })
        row_results.append(SimulateRow(
            index=i,
            label=labels[i],
            prediction=res["prediction"],
            model_votes=res["model_votes"],
            attack_confidence=res["attack_confidence"],
            attack_type=attack_type,
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
# Export
# ---------------------------------------------------------------------------

@router.get("/alerts/export/csv")
def export_alerts_csv(db: Session = Depends(get_db)) -> StreamingResponse:
    """Stream all alerts as a CSV file download.

    Args:
        db: Injected database session.

    Returns:
        StreamingResponse with text/csv content and attachment header.
    """
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "timestamp", "source_ip", "destination_ip", "protocol",
        "prediction", "attack_type", "confidence",
        "vote_IF", "vote_LOF", "vote_SVM", "vote_RF",
    ])
    for a in alerts:
        votes = a.model_votes or {}
        writer.writerow([
            a.id,
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
            a.source_ip or "",
            a.destination_ip or "",
            a.protocol or "",
            a.prediction or "",
            a.attack_type or "",
            f"{a.attack_confidence:.3f}" if a.attack_confidence is not None else "",
            votes.get("isolation_forest", 0),
            votes.get("lof", 0),
            votes.get("svm", 0),
            votes.get("random_forest", 0),
        ])

    buf.seek(0)
    filename = f"nids_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/alerts/export/pdf")
def export_alerts_pdf(db: Session = Depends(get_db)) -> StreamingResponse:
    """Stream all alerts as a PDF file download.

    Args:
        db: Injected database session.

    Returns:
        StreamingResponse with application/pdf content and attachment header.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=503, detail="fpdf2 not installed. Run: pip install fpdf2")

    alerts = db.query(Alert).order_by(Alert.created_at.desc()).all()

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "NIDS — Alert Export", ln=True, align="C")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC   |   Total: {len(alerts)} alerts", ln=True, align="C")
    pdf.ln(3)

    cols    = ["ID", "Timestamp", "Src IP", "Dst IP", "Proto", "Prediction", "Attack Type", "Conf", "IF", "LOF", "SVM", "RF"]
    widths  = [10,   38,          28,       28,       14,      22,           28,            12,     8,    8,    8,    8]

    pdf.set_fill_color(30, 30, 50)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica", "B", 7)
    for col, w in zip(cols, widths):
        pdf.cell(w, 6, col, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for i, a in enumerate(alerts):
        votes = a.model_votes or {}
        fill = i % 2 == 0
        pdf.set_fill_color(26, 29, 39) if fill else pdf.set_fill_color(22, 25, 35)
        pdf.set_text_color(200, 200, 210) if a.prediction == "INTRUSION" else pdf.set_text_color(150, 160, 170)

        ts = a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else ""
        conf = f"{a.attack_confidence*100:.0f}%" if a.attack_confidence is not None else ""
        row = [
            str(a.id),
            ts,
            a.source_ip or "",
            a.destination_ip or "",
            a.protocol or "",
            a.prediction or "",
            a.attack_type or "",
            conf,
            str(votes.get("isolation_forest", 0)),
            str(votes.get("lof", 0)),
            str(votes.get("svm", 0)),
            str(votes.get("random_forest", 0)),
        ]
        for val, w in zip(row, widths):
            pdf.cell(w, 5, val[:18], border="LR", fill=True)
        pdf.ln()

    pdf.set_fill_color(30, 30, 50)
    pdf.set_text_color(100, 116, 139)
    for w in widths:
        pdf.cell(w, 1, "", border="T", fill=True)

    buf = io.BytesIO(pdf.output())
    filename = f"nids_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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

    model_vote_totals: dict[str, int] = {}
    for alert in all_alerts:
        if isinstance(alert.model_votes, dict):
            for model_name, vote in alert.model_votes.items():
                model_vote_totals[model_name] = model_vote_totals.get(model_name, 0) + int(vote)

    breakdown_rows = (
        db.query(Alert.attack_type, func.count(Alert.id))
        .filter(Alert.prediction == "INTRUSION")
        .filter(Alert.attack_type.isnot(None))
        .group_by(Alert.attack_type)
        .all()
    )
    attack_type_breakdown = {row[0]: row[1] for row in breakdown_rows if row[0]}

    stats = StatsResponse(
        total_alerts=total,
        intrusion_count=intrusion_count,
        normal_count=total - intrusion_count,
        detection_rate=round(intrusion_count / total, 4) if total else 0.0,
        model_vote_totals=model_vote_totals,
        attack_type_breakdown=attack_type_breakdown,
    )
    return APIResponse.ok(stats.model_dump())
