from app.risk.daily_risk import get_or_create
from app.risk.daily_pause import update_daily_pause
from app.risk.maximum_loss import update_maximum_loss


def reconcile(db, settings, realized_pnl: float, open_risk: float, trades_count: int):
    state = get_or_create(db, settings)
    state.realized_pnl, state.open_risk, state.trades_count, state.reconciled = realized_pnl, open_risk, trades_count, True
    update_daily_pause(state, settings); update_maximum_loss(state, settings)
    db.commit(); db.refresh(state); return state
