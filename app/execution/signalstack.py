from app.core.exceptions import SignalStackNotConfiguredError
from app.execution.signalstack_queue import SignalStackRequestQueue


class SignalStackAdapter:
    """Validated intent/queue adapter. Outbound transport remains deliberately absent."""
    def __init__(self, settings): self.settings = settings
    def validate_authentication(self):
        missing = [key for key, enabled in self.settings.signalstack_safety_flags.items() if not enabled]
        if missing: raise SignalStackNotConfiguredError("SignalStack execution is disabled; missing prerequisites: " + ", ".join(missing))
        return {"valid": True, "transport_enabled": False}
    def submit_signal(self, *_args, **_kwargs): self._disabled()
    def format_order_intent(self, *_args, **_kwargs): self._disabled()
    def stop_loss(self, *_args, **_kwargs): self._disabled()
    def take_profit(self, *_args, **_kwargs): self._disabled()
    def close_position(self, *_args, **_kwargs): self._disabled()
    def short_sale(self, *_args, **_kwargs): self._disabled()
    def reconcile_status(self, *_args, **_kwargs): self._disabled()
    def accept(self, db, ticket):
        self.validate_authentication()
        payload = {"intent_type": "entry", "ticket_id": ticket.ticket_id, "symbol": ticket.symbol, "side": ticket.side, "quantity": ticket.proposed_quantity, "order_type": "market", "entry_price": ticket.proposed_entry_price, "stop_price": ticket.proposed_stop_price, "target_price": ticket.proposed_target_price}
        request = SignalStackRequestQueue(self.settings).enqueue(db, ticket.ticket_id, payload, ticket.signalstack_idempotency_key or f"ticket:{ticket.ticket_id}")
        ticket.status = "signalstack_queued"; ticket.signalstack_request_id = request.request_id; ticket.signalstack_idempotency_key = request.idempotency_key; db.commit(); db.refresh(ticket); return ticket
    def record_exit(self, *_args, **_kwargs): self._disabled()
    def _disabled(self):
        missing = [key for key, enabled in self.settings.signalstack_safety_flags.items() if not enabled]
        suffix = ", ".join(missing) if missing else "outbound transport awaits account-specific official payload confirmation"
        raise SignalStackNotConfiguredError("SignalStack outbound transmission is disabled: " + suffix)
