from uuid import uuid4

from sqlalchemy import select

from app.core.exceptions import SignalStackNotConfiguredError
from app.core.rate_limit import RollingRateLimiter
from app.database.models import SignalStackQueue, SignalStackRequest


class SignalStackRequestQueue:
    def __init__(self, settings): self.settings = settings

    def rate_state(self, db):
        sent = list(db.scalars(select(SignalStackRequest.sent_at_utc).where(SignalStackRequest.sent_at_utc.is_not(None))))
        return RollingRateLimiter(self.settings.signalstack_max_requests_per_minute, self.settings.signalstack_min_request_interval_seconds).evaluate(sent).as_dict()

    def enqueue(self, db, ticket_id: str, payload: dict, idempotency_key: str, request_type: str = "entry"):
        existing = db.scalar(select(SignalStackRequest).where(SignalStackRequest.idempotency_key == idempotency_key))
        if existing: return existing
        queued = db.query(SignalStackRequest).filter(SignalStackRequest.status.in_(["queued", "delayed", "retrying"])).count()
        if not self.settings.signalstack_queue_enabled or queued >= self.settings.signalstack_max_queue_size: raise SignalStackNotConfiguredError("SignalStack queue is disabled or unsafe")
        request_id = str(uuid4()); priority = 100 if request_type in {"exit", "cancel"} else 0
        request = SignalStackRequest(request_id=request_id, idempotency_key=idempotency_key, ticket_id=ticket_id, request_type=request_type, priority=priority, status="queued", payload=payload)
        db.add(request); db.add(SignalStackQueue(request_id=request_id, state="queued", reason="awaiting validated transport and rate-limit availability")); db.commit(); db.refresh(request); return request

    def list(self, db):
        return list(db.scalars(select(SignalStackRequest).order_by(SignalStackRequest.priority.desc(), SignalStackRequest.created_at_utc.asc())))

    def cancel(self, db, request_id: str):
        request = db.scalar(select(SignalStackRequest).where(SignalStackRequest.request_id == request_id))
        if request and request.status in {"queued", "delayed", "retrying"}: request.status = "cancelled"; db.commit(); db.refresh(request)
        return request
