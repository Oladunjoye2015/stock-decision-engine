from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignalIn(BaseModel):
    signal_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=24)
    timeframe: str
    side_hint: Literal["long", "short", "buy", "sell"] | None = None
    strategy: str = "default"
    signal_time_utc: datetime
    current_price: float = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    stop_hint: float | None = None
    take_profit_hint: float | None = None
    indicators: dict[str, Any] = Field(default_factory=dict)
    higher_timeframe_context: dict[str, Any] = Field(default_factory=dict)
    external_metadata: dict[str, Any] = Field(default_factory=dict)
    recent_ohlcv: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.replace(".", "").replace("-", "").isalnum():
            raise ValueError("Invalid stock symbol")
        return value

    @field_validator("high")
    @classmethod
    def valid_high(cls, value: float, info):
        return value


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    signal_id: str
    symbol: str
    timeframe: str
    status: str
    created_at_utc: datetime

