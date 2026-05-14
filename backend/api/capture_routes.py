"""Live-capture API endpoints.

Routes:
    POST /api/capture/start       — start packet sniffing
    POST /api/capture/stop        — stop sniffing
    GET  /api/capture/status      — capture state + counters
    GET  /api/capture/interfaces  — list available NICs
    WS   /api/ws/live             — stream flow results in real time
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.config import NOTIFY_CONFIDENCE_THRESHOLD
from backend.db.database import Alert, get_db
from backend.pipeline.capture import SCAPY_AVAILABLE, FlowCapture

router_capture = APIRouter(prefix="/api")

# Singleton capture state
_capture: Optional[FlowCapture] = None
_subscribers: list[WebSocket] = []
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_db_session_factory = None   # set at startup so background thread can persist alerts
_notifier = None              # set at startup by main.py


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the running event loop so background threads can schedule coroutines."""
    global _main_loop
    _main_loop = loop


def set_notifier(notifier) -> None:
    """Store the TelegramNotifier instance for use in the capture callback thread.

    Args:
        notifier: Configured TelegramNotifier instance (or None to disable).
    """
    global _notifier
    _notifier = notifier


# ---------------------------------------------------------------------------
# WebSocket broadcast helpers
# ---------------------------------------------------------------------------

async def _broadcast(payload: dict) -> None:
    dead = []
    for ws in list(_subscribers):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _subscribers:
            _subscribers.remove(ws)


def _on_flow_complete(meta: dict, result: dict) -> None:
    """Callback invoked from the capture background thread."""
    payload = {**meta, **result, "timestamp": datetime.utcnow().isoformat()}

    if _main_loop and not _main_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_broadcast(payload), _main_loop)

    # Persist intrusions to SQLite via a dedicated DB session
    if result["prediction"] == "INTRUSION" and _db_session_factory:
        try:
            db = _db_session_factory()
            alert = Alert(
                timestamp=datetime.utcnow(),
                source_ip=meta.get("src_ip"),
                destination_ip=meta.get("dst_ip"),
                protocol=meta.get("protocol"),
                prediction="INTRUSION",
                model_votes=result["model_votes"],
                attack_confidence=result["attack_confidence"],
                created_at=datetime.utcnow(),
            )
            db.add(alert)
            db.commit()
            db.close()
        except Exception:
            pass

        # Send Telegram notification if confidence exceeds threshold
        confidence = result.get("attack_confidence", 0.0)
        if _notifier and _main_loop and not _main_loop.is_closed() and confidence >= NOTIFY_CONFIDENCE_THRESHOLD:
            asyncio.run_coroutine_threadsafe(
                _notifier.send_alert({
                    "attack_type": "Live Capture",
                    "attack_confidence": confidence,
                    "source_ip": meta.get("src_ip", "unknown"),
                    "protocol": meta.get("protocol", "unknown"),
                    "model_votes": result["model_votes"],
                    "timestamp": datetime.utcnow(),
                }),
                _main_loop,
            )


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router_capture.post("/capture/start")
async def start_capture(body: dict = None) -> dict:
    """Start live packet capture on the specified interface."""
    global _capture

    if not SCAPY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=(
                "scapy is not installed. Run: pip install scapy\n"
                "On Windows, also install Npcap from https://npcap.com/ "
                "and restart with Administrator privileges."
            ),
        )

    if _capture and _capture._running:
        return {"status": "ok", "data": {"message": "Capture already running"}}

    interface = (body or {}).get("interface") or None
    _capture = FlowCapture(on_flow_complete=_on_flow_complete, interface=interface)

    try:
        _capture.start()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "data": {
        "message": "Capture started",
        "interface": interface or "default",
    }}


@router_capture.post("/capture/stop")
async def stop_capture() -> dict:
    """Stop the active packet capture."""
    global _capture
    if not _capture or not _capture._running:
        return {"status": "ok", "data": {"message": "No active capture"}}

    _capture.stop()
    stats = dict(_capture.stats)
    return {"status": "ok", "data": {"message": "Capture stopped", "stats": stats}}


@router_capture.get("/capture/status")
async def capture_status() -> dict:
    """Return whether capture is running and live counters."""
    if not _capture:
        return {"status": "ok", "data": {"running": False, "stats": {}, "active_flows": 0}}

    return {"status": "ok", "data": {
        "running": _capture._running,
        "interface": _capture._interface,
        "stats": dict(_capture.stats),
        "active_flows": len(_capture._flows),
    }}


@router_capture.get("/capture/interfaces")
async def list_interfaces() -> dict:
    """List available network interfaces detected by scapy."""
    if not SCAPY_AVAILABLE:
        raise HTTPException(status_code=503, detail="scapy is not installed")

    try:
        from scapy.all import get_if_list
        ifaces = get_if_list()
        return {"status": "ok", "data": {"interfaces": ifaces}}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router_capture.websocket("/ws/live")
async def websocket_live(ws: WebSocket) -> None:
    """Stream finalised-flow detection results to the client in real time."""
    global _main_loop
    _main_loop = asyncio.get_event_loop()

    await ws.accept()
    _subscribers.append(ws)
    try:
        while True:
            await asyncio.sleep(20)
            await ws.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ws in _subscribers:
            _subscribers.remove(ws)
