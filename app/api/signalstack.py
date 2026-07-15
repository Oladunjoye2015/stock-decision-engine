from fastapi import APIRouter, Body, Depends, HTTPException
from uuid import uuid4
from sqlalchemy.orm import Session

from app.compliance.approval_state import validate_live_approval
from app.config import get_settings
from app.core.exceptions import SignalStackNotConfiguredError
from app.core.security import authenticate_webhook
from app.database.engine import get_db
from app.database.models import SignalStackRequest, SignalStackResponse
from app.execution.signalstack_queue import SignalStackRequestQueue
from app.execution.signalstack_schemas import SignalStackWebhookPayload
from app.execution.signalstack_transport import SignalStackTestTransport
from app.core.time_utils import utc_now

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
    try: result=transport.send(payload)
    except SignalStackNotConfiguredError as exc: raise HTTPException(409,str(exc))
    request_id=str(uuid4())
    db.add(SignalStackRequest(request_id=request_id,idempotency_key=f"test:{request_id}",ticket_id="test-webhook",request_type="test",priority=0,status="test_sent",attempts=1,payload=payload.model_dump(),sent_at_utc=utc_now(),completed_at_utc=utc_now()))
    db.add(SignalStackResponse(request_id=request_id,status_code=result["status_code"],response_data={"test_only":True,"response_received":True})); db.commit()
    return {"approval":validate_live_approval(settings),"rate_limit":rate,"test_transport":state,"outbound_request_made":True,"result":result}
