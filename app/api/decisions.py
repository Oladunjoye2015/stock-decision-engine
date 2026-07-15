from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.engine import get_db
from app.database.models import DecisionRecord
from app.database.repositories import get_by, list_recent

router = APIRouter(prefix="/decisions", tags=["decisions"])


def serialize(x): return {"decision_id": x.decision_id, "signal_id": x.signal_id, "symbol": x.symbol, "side": x.side, "strategy": x.strategy, "primary_timeframe": x.primary_timeframe, "final_decision": x.final_decision, "execution_mode": x.execution_mode, "reason": x.reason, "details": x.details, "created_at_utc": x.created_at_utc}


@router.get("")
def list_decisions(limit: int = 100, db: Session = Depends(get_db)): return [serialize(x) for x in list_recent(db, DecisionRecord, limit)]


@router.get("/{decision_id}")
def get_decision(decision_id: str, db: Session = Depends(get_db)):
    value = get_by(db, DecisionRecord, decision_id=decision_id)
    if not value: raise HTTPException(404, "Decision not found")
    return serialize(value)

