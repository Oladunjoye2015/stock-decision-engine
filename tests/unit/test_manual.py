from datetime import timedelta

from app.core.time_utils import utc_now
from app.database.models import TradeTicket
from app.execution.manual import DISCLAIMER, ManualExecutionAdapter
from app.schemas.tickets import FillIn


def test_manual_acceptance_and_pnl_do_not_execute_network():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database.engine import Base
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    with Session(engine) as db:
        t = TradeTicket(ticket_id="t", decision_id="d", signal_id="s", symbol="AAPL", side="long", execution_mode="manual", status="proposed", expires_at_utc=utc_now()+timedelta(minutes=5), proposed_entry_price=100, proposed_stop_price=99, proposed_target_price=103, proposed_quantity=10, estimated_risk_usd=10, estimated_reward_usd=30)
        db.add(t); db.commit()
        adapter = ManualExecutionAdapter(); adapter.accept(db, t)
        assert t.status == "accepted" and DISCLAIMER in t.notes
        adapter.record_entry(db, t, FillIn(price=100, quantity=10, fees=1))
        adapter.record_exit(db, t, FillIn(price=105, quantity=10, fees=1))
        assert t.realized_pnl == 48

