"""SQLite database setup and Alert ORM model.

Exposes:
    engine      — SQLAlchemy engine (SQLite)
    SessionLocal — session factory for dependency injection
    Base        — declarative base for ORM models
    Alert       — ORM model for the alerts table
    init_db()   — create tables if they don't exist
"""

import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import DATABASE_URL, DB_DIR

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

DB_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# ORM base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Alert model
# ---------------------------------------------------------------------------

class Alert(Base):
    """Persisted record of a network intrusion alert.

    Columns:
        id               : Auto-increment primary key.
        timestamp        : When the traffic flow was observed (from caller).
        source_ip        : Source IP address string (may be 'unknown').
        destination_ip   : Destination IP address string (may be 'unknown').
        protocol         : Transport protocol (TCP / UDP / 'unknown').
        prediction       : Ensemble verdict — 'INTRUSION' or 'NORMAL'.
        model_votes      : JSON dict mapping model name to 0/1 vote.
        attack_confidence: Fraction of models that voted anomaly (0.0–1.0).
        created_at       : UTC time the row was inserted into the DB.
    """

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    source_ip = Column(String(45), nullable=False, default="unknown")
    destination_ip = Column(String(45), nullable=False, default="unknown")
    protocol = Column(String(16), nullable=False, default="unknown")
    prediction = Column(String(16), nullable=False)
    model_votes = Column(JSON, nullable=False)
    attack_confidence = Column(Float, nullable=False)
    attack_type = Column(String(64), nullable=True, default="Unknown")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables in the SQLite database if they do not already exist.

    Also runs an idempotent migration to add attack_type column to existing DBs.
    """
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE alerts ADD COLUMN attack_type VARCHAR(64) DEFAULT 'Unknown'"
            ))
            conn.commit()
        except Exception:
            pass  # Column already exists — safe to ignore


def get_db():
    """FastAPI dependency that yields a database session and closes it after use."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
