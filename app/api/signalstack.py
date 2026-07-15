from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.compliance.approval_state import validate_live_approval
from app.config import get_settings
from app.core.exceptions import SignalStackNotConfiguredError
from app.core.security import authenticate_webhook
from app.database.engine import get_db
from app.execution.signalstack_queue import SignalStackRequestQueue
from app.execution.signalstack_schemas import SignalStackWebhookPayload
from app.execution.signalstack_transport import SignalStackTestTransport, send_and_record_test

router = APIRouter(prefix="/signalstack", tags=["signalstack"])


def serialize(x): return {"request_id": x.request_id, "ticket_id": x.ticket_id, "request_type": x.request_type, "priority": x.priority, "status": x.status, "attempts": x.attempts, "created_at_utc": x.created_at_utc, "next_attempt_at": x.next_attempt_at, "last_error": x.last_error}


@router.get("/status")
def signalstack_status(db: Session = Depends(get_db)):
    settings = get_settings(); queue = SignalStackRequestQueue(settings)
    test_state=SignalStackTestTransport(settings).readiness()
    return {"approval": validate_live_approval(settings), "rate_limit": queue.rate_state(db), "queue_size": len([x for x in queue.list(db) if x.status in {"queued", "delayed", "retrying"}]), "outbound_transport_enabled": False, "test_transport":test_state}


@router.get("/queue")
def queue(db: Session = Depends(get_db)): return [serialize(x) for x in SignalStackRequestQueue(get_settings()).list(db)]


@router.post("/queue/{request_id}/cancel")
def cancel(request_id: str, db: Session = Depends(get_db)):
    value = SignalStackRequestQueue(get_settings()).cancel(db, request_id)
    if not value: raise HTTPException(404, "SignalStack request not found")
    return serialize(value)


@router.post("/test-configuration", dependencies=[Depends(authenticate_webhook)])
def test_configuration(payload: SignalStackWebhookPayload | None = Body(default=None), db: Session = Depends(get_db)):
    settings = get_settings()
    transport=SignalStackTestTransport(settings); state=transport.readiness()
    if payload is None or not state["ready"]:
        return {"approval": validate_live_approval(settings), "rate_limit": SignalStackRequestQueue(settings).rate_state(db), "test_transport":state, "outbound_request_made":False}
    rate=SignalStackRequestQueue(settings).rate_state(db)
    if not rate["allowed"]: raise HTTPException(429,"SignalStack rate limit blocks this test request")
    try: result=send_and_record_test(db,settings,payload)
    except SignalStackNotConfiguredError as exc: raise HTTPException(409,str(exc))
    return {"approval":validate_live_approval(settings),"rate_limit":rate,"test_transport":state,"outbound_request_made":True,"result":result}
