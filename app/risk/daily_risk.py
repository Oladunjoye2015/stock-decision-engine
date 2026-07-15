from datetime import date

from sqlalchemy.orm import Session

from app.database.models import DailyRiskState


def get_or_create(db: Session, settings) -> DailyRiskState:
    key = date.today().isoformat()
    state = db.query(DailyRiskState).filter_by(date_key=key).one_or_none()
    if state is None:
        state = DailyRiskState(date_key=key, reconciled=not settings.daily_reconciliation_required, kill_switch=settings.kill_switch_enabled)
        db.add(state); db.commit(); db.refresh(state)
    return state


def check(state: DailyRiskState, settings, projected_risk: float) -> dict:
    reasons = []
    if state.kill_switch: reasons.append("kill switch is active")
    if state.daily_pause: reasons.append("Daily Pause is active")
    if state.maximum_loss_buffer_reached: reasons.append("Maximum Loss buffer reached")
    if settings.daily_reconciliation_required and not state.reconciled: reasons.append("daily reconciliation is incomplete")
    if state.realized_pnl <= -settings.max_daily_loss_usd: reasons.append("daily loss limit reached")
    if state.trades_count >= settings.max_trades_per_day: reasons.append("daily trade limit reached")
    if state.open_risk + projected_risk > settings.max_aggregate_open_risk_usd: reasons.append("aggregate open-risk limit exceeded")
    return {"passed": not reasons, "reason": "passed" if not reasons else "; ".join(reasons)}
