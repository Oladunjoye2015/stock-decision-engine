from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import Position, TradeTicket


def check(db: Session, settings, symbol: str) -> dict:
    open_positions = db.query(Position).filter_by(status="open").all()
    active = db.query(TradeTicket).filter(TradeTicket.symbol == symbol, TradeTicket.status.in_(["proposed", "accepted", "paper_opened", "manually_opened"])).first()
    reasons = []
    if len(open_positions) >= settings.max_open_positions: reasons.append("maximum open positions reached")
    if any(p.symbol == symbol for p in open_positions): reasons.append("duplicate or conflicting position")
    if active: reasons.append("duplicate active ticket")
    return {"passed": not reasons, "reason": "passed" if not reasons else "; ".join(reasons)}

