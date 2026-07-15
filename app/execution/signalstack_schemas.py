from typing import Literal

from pydantic import BaseModel


class SignalStackOrderIntent(BaseModel):
    ticket_id: str
    symbol: str
    side: Literal["long", "short"]
    quantity: int
    order_type: str
    entry_price: float
    stop_price: float
    target_price: float
    intent_type: Literal["entry", "exit", "cancel", "modify"] = "entry"

