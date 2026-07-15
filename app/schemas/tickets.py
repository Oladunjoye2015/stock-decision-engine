from datetime import datetime

from pydantic import BaseModel, Field


class FillIn(BaseModel):
    price: float = Field(gt=0)
    quantity: float = Field(gt=0)
    time_utc: datetime | None = None
    fees: float = Field(default=0, ge=0)
    notes: str = ""


class TicketAction(BaseModel):
    notes: str = ""

