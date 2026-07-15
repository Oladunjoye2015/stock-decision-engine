from pydantic import BaseModel


class OHLCV(BaseModel):
    open: float; high: float; low: float; close: float; volume: float

