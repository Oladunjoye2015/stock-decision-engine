from uuid import uuid4

from app.core.exceptions import TicketStateError
from app.core.time_utils import utc_now
from app.database.models import ManualExecution, Position

DISCLAIMER = "Manual execution only. No order has been transmitted."


class ManualExecutionAdapter:
    def accept(self, db, ticket):
        ticket.status = "accepted"; ticket.notes = f"{ticket.notes}\n{DISCLAIMER}".strip(); db.commit(); return ticket

    def record_entry(self, db, ticket, fill):
        if ticket.status not in {"accepted", "proposed"}: raise TicketStateError("Ticket cannot record an entry in its current state")
        when = fill.time_utc or utc_now()
        ticket.status = "manually_opened"; ticket.actual_entry_price = fill.price; ticket.actual_entry_quantity = fill.quantity; ticket.actual_entry_time = when; ticket.fees += fill.fees
        db.add(ManualExecution(execution_id=str(uuid4()), ticket_id=ticket.ticket_id, action="entry", price=fill.price, quantity=fill.quantity, fees=fill.fees))
        db.add(Position(symbol=ticket.symbol, side=ticket.side, quantity=fill.quantity, entry_price=fill.price, stop_price=ticket.proposed_stop_price, execution_mode="manual"))
        db.commit(); db.refresh(ticket); return ticket

    def record_exit(self, db, ticket, fill):
        if ticket.status != "manually_opened": raise TicketStateError("Manual ticket is not open")
        direction = 1 if ticket.side == "long" else -1
        quantity = min(fill.quantity, ticket.actual_entry_quantity or 0)
        ticket.status = "manually_closed"; ticket.actual_exit_price = fill.price; ticket.actual_exit_quantity = quantity; ticket.actual_exit_time = fill.time_utc or utc_now(); ticket.fees += fill.fees
        ticket.realized_pnl = (fill.price - ticket.actual_entry_price) * quantity * direction - ticket.fees
        db.add(ManualExecution(execution_id=str(uuid4()), ticket_id=ticket.ticket_id, action="exit", price=fill.price, quantity=quantity, fees=fill.fees))
        position = db.query(Position).filter_by(symbol=ticket.symbol, status="open", execution_mode="manual").first()
        if position: position.status = "closed"
        db.commit(); db.refresh(ticket); return ticket

