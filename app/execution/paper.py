from uuid import uuid4
from datetime import timedelta

from app.core.exceptions import TicketStateError
from app.core.time_utils import utc_now
from app.database.models import PaperExecution, Position


class PaperExecutionAdapter:
    def __init__(self, settings): self.settings = settings
    def accept(self, db, ticket):
        if ticket.status != "proposed": raise TicketStateError("Paper ticket is not proposed")
        if self.settings.paper_simulate_rejection:
            ticket.status = "rejected"; ticket.notes = "Simulated paper rejection; no external order transmitted."; db.commit(); db.refresh(ticket); return ticket
        slip = self.settings.paper_slippage_bps / 10_000 * (1 if ticket.side == "long" else -1)
        price = ticket.proposed_entry_price * (1 + slip); qty = max(1, ticket.proposed_quantity * min(100, max(0, self.settings.paper_partial_fill_pct)) / 100); fees = qty * self.settings.paper_commission_per_share
        ticket.status = "paper_opened"; ticket.actual_entry_price = price; ticket.actual_entry_quantity = qty; ticket.actual_entry_time = utc_now() + timedelta(seconds=max(0, self.settings.paper_fill_delay_seconds)); ticket.fees = fees
        if qty < ticket.proposed_quantity: ticket.notes = f"Simulated partial fill: {qty} of {ticket.proposed_quantity} shares."
        db.add(PaperExecution(execution_id=str(uuid4()), ticket_id=ticket.ticket_id, action="entry", price=price, quantity=qty, fees=fees))
        db.add(Position(symbol=ticket.symbol, side=ticket.side, quantity=qty, entry_price=price, stop_price=ticket.proposed_stop_price, execution_mode="paper"))
        db.commit(); db.refresh(ticket); return ticket
    def record_exit(self, db, ticket, fill):
        if ticket.status != "paper_opened": raise TicketStateError("Paper ticket is not open")
        slip = self.settings.paper_slippage_bps / 10_000 * (-1 if ticket.side == "long" else 1)
        price = fill.price * (1 + slip); qty = min(fill.quantity, ticket.actual_entry_quantity or 0); exit_fee = qty * self.settings.paper_commission_per_share; direction = 1 if ticket.side == "long" else -1
        ticket.status = "paper_closed"; ticket.actual_exit_price = price; ticket.actual_exit_quantity = qty; ticket.actual_exit_time = fill.time_utc or utc_now(); ticket.fees += exit_fee; ticket.realized_pnl = (price - ticket.actual_entry_price) * qty * direction - ticket.fees
        db.add(PaperExecution(execution_id=str(uuid4()), ticket_id=ticket.ticket_id, action="exit", price=price, quantity=qty, fees=exit_fee))
        position = db.query(Position).filter_by(symbol=ticket.symbol, status="open", execution_mode="paper").first()
        if position: position.status = "closed"
        db.commit(); db.refresh(ticket); return ticket
