from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.compliance.audit import record
from app.config import get_settings
from app.database.engine import get_db
from app.risk.daily_risk import get_or_create
from app.risk.kill_switch import set_state
from app.risk.reconciliation import reconcile
from app.schemas.risk import KillSwitchRequest, ReconcileRequest

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status")
def risk_status(db: Session = Depends(get_db)):
    s = get_or_create(db, get_settings())
    return {"date": s.date_key, "realized_pnl": s.realized_pnl, "open_risk": s.open_risk, "trades_count": s.trades_count, "reconciled": s.reconciled, "kill_switch": s.kill_switch, "daily_pause": s.daily_pause, "maximum_loss_buffer_reached": s.maximum_loss_buffer_reached}


@router.post("/kill-switch")
def activate(body: KillSwitchRequest, db: Session = Depends(get_db)):
    s = set_state(db, get_settings(), True); record(db, "kill_switch_activated", s.date_key, {"reason": body.reason}, True); return {"active": s.kill_switch}


@router.post("/kill-switch/reset")
def reset(body: KillSwitchRequest, db: Session = Depends(get_db)):
    s = set_state(db, get_settings(), False); record(db, "kill_switch_reset", s.date_key, {"reason": body.reason}, True); return {"active": s.kill_switch}


@router.post("/reconcile")
def reconcile_risk(body: ReconcileRequest, db: Session = Depends(get_db)):
    s = reconcile(db, get_settings(), body.realized_pnl, body.open_risk, body.trades_count); record(db, "daily_reconciled", s.date_key, body.model_dump(), True); return {"reconciled": True, "date": s.date_key}
