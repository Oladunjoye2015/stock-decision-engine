from sqlalchemy import select
from sqlalchemy.orm import Session


def get_by(db: Session, model, **criteria):
    return db.scalar(select(model).filter_by(**criteria))


def list_recent(db: Session, model, limit: int = 100):
    return list(db.scalars(select(model).order_by(model.id.desc()).limit(min(limit, 500))))


def save(db: Session, value):
    db.add(value)
    db.commit()
    db.refresh(value)
    return value

