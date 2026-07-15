from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalStackWebhookPayload(BaseModel):
    """Exact payload displayed by the user's Trade The Pool demo connection."""

    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=24)
    quantity: int = Field(ge=1)
    action: Literal["buy", "sell"]

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol.replace(".", "").replace("-", "").isalnum():
            raise ValueError("symbol contains unsupported characters")
        return symbol


def format_signalstack_payload(symbol: str, quantity: int, action: str) -> dict:
    return SignalStackWebhookPayload(symbol=symbol, quantity=quantity, action=action).model_dump()


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
