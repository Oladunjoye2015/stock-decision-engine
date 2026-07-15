from typing import Any
import math

from app.schemas.signals import SignalIn


BASE_FEATURES = [
    "open", "high", "low", "close", "volume", "ema20", "ema50", "ema200",
    "rsi", "macd_hist", "adx", "atr", "atr_pct", "vwap", "vol_ratio",
]


def build_features(signal: SignalIn, expected_order: list[str] | None = None) -> dict[str, Any]:
    i = signal.indicators; ema20, ema50 = i.get("ema20"), i.get("ema50"); atr = i.get("atr"); timestamp = signal.signal_time_utc
    closes = [float(row["close"]) for row in signal.recent_ohlcv if row.get("close") is not None]
    ret1 = i.get("ret1", (signal.close/closes[-1]-1) if closes else None); ret3 = i.get("ret3", (signal.close/closes[-3]-1) if len(closes) >= 3 else None)
    hour = timestamp.hour + timestamp.minute/60
    derived = {"body_pct": (signal.close-signal.open)/signal.open, "range_pct": (signal.high-signal.low)/signal.close, "close_vs_ema20": (signal.close-ema20)/ema20 if ema20 else None, "ema20_vs_ema50": (ema20-ema50)/ema50 if ema20 and ema50 else None, "rsi": i.get("rsi"), "atr_pct": atr/signal.close if atr else i.get("atr_pct"), "vol_ratio": i.get("vol_ratio"), "ret1": ret1, "ret3": ret3, "hour_sin": math.sin(2*math.pi*hour/24), "hour_cos": math.cos(2*math.pi*hour/24)}
    raw: dict[str, Any] = {
        "open": signal.open, "high": signal.high, "low": signal.low,
        "close": signal.close, "volume": signal.volume,
        **signal.indicators, **derived,
    }
    order = expected_order or BASE_FEATURES
    return {name: raw.get(name) for name in order}
