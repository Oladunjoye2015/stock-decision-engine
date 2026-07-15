import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.database.engine import SessionLocal, init_database
from app.risk.reconciliation import reconcile


if __name__ == "__main__":
    init_database()
    with SessionLocal() as db: print(reconcile(db, get_settings(), 0, 0, 0).date_key)
