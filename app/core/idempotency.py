from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import SignalRecord


def signal_exists(db: Session, signal_id: str) -> bool:
    return db.scalar(select(SignalRecord.id).where(SignalRecord.signal_id == signal_id)) is not None

