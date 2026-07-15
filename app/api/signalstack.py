from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.compliance.approval_state import validate_live_approval
from app.config import get_settings
from app.database.engine import get_db
from app.execution.signalstack_queue import SignalStackRequestQueue

router = APIRouter(prefix="/signalstack", tags=["signalstack"])


def serialize(x): return {"request_id": x.request_id, "ticket_id": x.ticket_id, "request_type": x.request_type, "priority": x.priority, "status": x.status, "attempts": x.attempts, "created_at_utc": x.created_at_utc, "next_attempt_at": x.next_attempt_at, "last_error": x.last_error}


@router.get("/status")
def signalstack_status(db: Session = Depends(get_db)):
    settings = get_settings(); queue = SignalStackRequestQueue(settings)
    return {"approval": validate_live_approval(settings), "rate_limit": queue.rate_state(db), "queue_size": len([x for x in queue.list(db) if x.status in {"queued", "delayed", "retrying"}]), "outbound_transport_enabled": False}


@router.get("/queue")
def queue(db: Session = Depends(get_db)): return [serialize(x) for x in SignalStackRequestQueue(get_settings()).list(db)]


@router.post("/queue/{request_id}/cancel")
def cancel(request_id: str, db: Session = Depends(get_db)):
    value = SignalStackRequestQueue(get_settings()).cancel(db, request_id)
    if not value: raise HTTPException(404, "SignalStack request not found")
    return serialize(value)


@router.post("/test-configuration")
def test_configuration(db: Session = Depends(get_db)):
    settings = get_settings()
    return {"approval": validate_live_approval(settings), "rate_limit": SignalStackRequestQueue(settings).rate_state(db), "outbound_request_made": False}
