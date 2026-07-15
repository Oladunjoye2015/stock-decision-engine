from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.signals import create_ticket
from app.compliance.audit import record
from app.config import get_settings
from app.core.exceptions import DecisionEngineError, TicketStateError
from app.core.time_utils import ensure_utc, utc_now
from app.database.engine import get_db
from app.database.models import DecisionRecord, TradeTicket
from app.database.repositories import get_by, list_recent
from app.execution.factory import get_adapter
from app.execution.manual import DISCLAIMER, ManualExecutionAdapter
from app.notifications.service import NotificationService
from app.schemas.tickets import FillIn, TicketAction

router = APIRouter(prefix="/tickets", tags=["tickets"])


def serialize(t):
    return {"ticket_id": t.ticket_id, "decision_id": t.decision_id, "signal_id": t.signal_id, "created_at_utc": t.created_at_utc, "expires_at_utc": t.expires_at_utc, "symbol": t.symbol, "side": t.side, "order_type": "market", "proposed_entry_price": t.proposed_entry_price, "proposed_stop_price": t.proposed_stop_price, "proposed_target_price": t.proposed_target_price, "proposed_quantity": t.proposed_quantity, "estimated_risk_usd": t.estimated_risk_usd, "estimated_reward_usd": t.estimated_reward_usd, "reward_risk_ratio": t.estimated_reward_usd / t.estimated_risk_usd if t.estimated_risk_usd else 0, "expected_movement_per_share": t.expected_movement_per_share, "reference_one_minute_volume": t.reference_one_minute_volume, "maximum_quantity_by_volume_rule": t.maximum_quantity_by_volume_rule, "signalstack_request_id": t.signalstack_request_id, "signalstack_idempotency_key": t.signalstack_idempotency_key, "signalstack_response_status": t.signalstack_response_status, "execution_mode": t.execution_mode, "status": t.status, "actual_entry_price": t.actual_entry_price, "actual_entry_quantity": t.actual_entry_quantity, "actual_entry_time": t.actual_entry_time, "actual_exit_price": t.actual_exit_price, "actual_exit_quantity": t.actual_exit_quantity, "actual_exit_time": t.actual_exit_time, "fees": t.fees, "realized_pnl": t.realized_pnl, "notes": t.notes, "details": t.details, "manual_notice": DISCLAIMER if t.execution_mode == "manual" else None}


def require(db, ticket_id):
    ticket = get_by(db, TradeTicket, ticket_id=ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    return ticket


def expire_if_needed(db, ticket):
    if ticket.status in {"proposed", "accepted"} and ensure_utc(ticket.expires_at_utc) <= utc_now():
        ticket.status = "expired"; db.commit(); NotificationService(get_settings()).send("ticket_expiration", {"ticket_id": ticket.ticket_id})
    return ticket


@router.post("/from-decision/{decision_id}")
def from_decision(decision_id: str, db: Session = Depends(get_db)):
    existing = get_by(db, TradeTicket, decision_id=decision_id)
    if existing: return serialize(existing)
    decision = get_by(db, DecisionRecord, decision_id=decision_id)
    if not decision: raise HTTPException(404, "Decision not found")
    if decision.final_decision not in {"proposed", "manual_ticket_created", "paper_submitted"} or not decision.details.get("risk", {}).get("passed"): raise HTTPException(409, "Decision is not eligible for a ticket")
    try: return serialize(create_ticket(db, decision, get_settings()))
    except IntegrityError: db.rollback(); return serialize(get_by(db, TradeTicket, decision_id=decision_id))


@router.get("")
def tickets(limit: int = 100, db: Session = Depends(get_db)): return [serialize(expire_if_needed(db, x)) for x in list_recent(db, TradeTicket, limit)]


@router.get("/{ticket_id}")
def ticket(ticket_id: str, db: Session = Depends(get_db)): return serialize(expire_if_needed(db, require(db, ticket_id)))


@router.post("/{ticket_id}/accept")
def accept(ticket_id: str, body: TicketAction, db: Session = Depends(get_db)):
    t = expire_if_needed(db, require(db, ticket_id))
    if t.status == "expired": raise HTTPException(409, "Expired tickets cannot be accepted")
    try: t = get_adapter(get_settings()).accept(db, t)
    except DecisionEngineError as exc: record(db, "execution_refused", ticket_id, {"reason": str(exc)}, True); raise HTTPException(409, str(exc))
    record(db, "ticket_accepted", ticket_id, {"mode": t.execution_mode, "external_order_transmitted": False}); return serialize(t)


@router.post("/{ticket_id}/reject")
def reject(ticket_id: str, body: TicketAction, db: Session = Depends(get_db)):
    t = expire_if_needed(db, require(db, ticket_id))
    if t.status not in {"proposed", "accepted"}: raise HTTPException(409, "Ticket cannot be rejected")
    t.status = "rejected"; t.notes = body.notes; db.commit(); record(db, "ticket_rejected", ticket_id, {"notes": body.notes}); return serialize(t)


@router.post("/{ticket_id}/record-entry")
def record_entry(ticket_id: str, fill: FillIn, db: Session = Depends(get_db)):
    t = expire_if_needed(db, require(db, ticket_id))
    if t.execution_mode != "manual": raise HTTPException(409, "Entry fills can only be user-recorded in manual mode")
    try: t = ManualExecutionAdapter().record_entry(db, t, fill)
    except TicketStateError as exc: raise HTTPException(409, str(exc))
    record(db, "manual_entry_recorded", ticket_id, fill.model_dump(mode="json")); return serialize(t)


@router.post("/{ticket_id}/record-exit")
def record_exit(ticket_id: str, fill: FillIn, db: Session = Depends(get_db)):
    t = require(db, ticket_id)
    try: t = get_adapter(get_settings()).record_exit(db, t, fill)
    except DecisionEngineError as exc: raise HTTPException(409, str(exc))
    record(db, "exit_recorded", ticket_id, {**fill.model_dump(mode="json"), "realized_pnl": t.realized_pnl}); return serialize(t)


@router.post("/{ticket_id}/cancel")
def cancel(ticket_id: str, body: TicketAction, db: Session = Depends(get_db)):
    t = require(db, ticket_id)
    if t.status not in {"proposed", "accepted"}: raise HTTPException(409, "Only pending tickets can be cancelled")
    t.status = "cancelled"; t.notes = body.notes; db.commit(); record(db, "ticket_cancelled", ticket_id, {"notes": body.notes}); return serialize(t)
