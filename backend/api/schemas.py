"""Pydantic request / response schemas.

Every API response is wrapped in the envelope:
    { "status": "ok" | "error", "data": <payload>, "error": <message | null> }
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

class APIResponse(BaseModel):
    """Standard JSON envelope returned by every endpoint."""

    status: str = Field(..., examples=["ok", "error"])
    data: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, data: Any = None) -> "APIResponse":
        """Construct a successful response."""
        return cls(status="ok", data=data, error=None)

    @classmethod
    def err(cls, message: str) -> "APIResponse":
        """Construct an error response."""
        return cls(status="error", data=None, error=message)


# ---------------------------------------------------------------------------
# Predict endpoint
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """Raw (unscaled) network-flow feature vector plus optional metadata.

    The features dict must contain all 77 numeric feature columns that the
    scaler was trained on.  Metadata fields are optional and stored with the
    alert if an intrusion is detected.
    """

    features: dict[str, float] = Field(
        ...,
        description="Map of feature_name -> raw numeric value (77 features).",
    )
    source_ip: str = Field(default="unknown", description="Source IP address.")
    destination_ip: str = Field(default="unknown", description="Destination IP address.")
    protocol: str = Field(default="unknown", description="Transport protocol (TCP/UDP).")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Observation time (UTC). Defaults to now.",
    )


class ModelVotes(BaseModel):
    """Per-model anomaly vote (0 = normal, 1 = anomaly)."""

    isolation_forest: int
    lof: int
    svm: int
    random_forest: int = 0

    model_config = {"extra": "allow"}


class PredictResponse(BaseModel):
    """Result of running the ensemble on a single feature vector."""

    prediction: str = Field(..., description="'INTRUSION' or 'NORMAL'.")
    model_votes: ModelVotes
    attack_confidence: float = Field(
        ..., description="Fraction of models that voted anomaly (0.0–1.0)."
    )
    vote_sum: int = Field(..., description="Number of models that voted anomaly (0–4).")
    alert_id: int | None = Field(
        None, description="DB row id if the prediction was saved as an alert."
    )
    attack_type: str = Field(
        default="Unknown",
        description="Predicted attack category (e.g. DDoS, PortScan). 'BENIGN' if normal.",
    )


# ---------------------------------------------------------------------------
# Simulate endpoint
# ---------------------------------------------------------------------------

class SimulateRow(BaseModel):
    """Per-row prediction result returned inside POST /api/simulate."""

    index: int
    label: str
    prediction: str
    model_votes: dict[str, int]
    attack_confidence: float
    attack_type: str = "BENIGN"


class SimulateSummary(BaseModel):
    """Aggregate statistics returned by POST /api/simulate."""

    rows_evaluated: int
    intrusions_detected: int
    normal_count: int
    detection_rate: float = Field(..., description="Intrusions / total rows.")
    alerts_saved: int
    model_agreement: dict[str, int] = Field(
        ...,
        description="How many rows each model flagged as anomaly.",
    )
    rows: list[SimulateRow] = Field(..., description="Per-row predictions for the frontend table.")


# ---------------------------------------------------------------------------
# Alert (DB read-back)
# ---------------------------------------------------------------------------

class AlertOut(BaseModel):
    """Alert record returned from GET /api/alerts."""

    id: int
    timestamp: datetime
    source_ip: str
    destination_ip: str
    protocol: str
    prediction: str
    model_votes: dict[str, int]
    attack_confidence: float
    attack_type: str = "Unknown"
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    """Dashboard statistics returned by GET /api/stats."""

    total_alerts: int
    intrusion_count: int
    normal_count: int
    detection_rate: float
    model_vote_totals: dict[str, int] = Field(
        ...,
        description="Total anomaly votes cast by each model across all stored alerts.",
    )
    attack_type_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Count of intrusion alerts per attack type.",
    )
