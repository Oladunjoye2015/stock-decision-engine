from datetime import timedelta

from app.core.time_utils import ensure_utc


BREAKOUT_STRATEGY = "breakout-medium-high-vol-shadow-v1"


def canonical_claim(signal):
    if signal.strategy != BREAKOUT_STRATEGY or signal.timeframe != "60Min":
        return None
    signal_time=ensure_utc(signal.signal_time_utc)
    # TradingView session-aligned hourly bars can close on the half-hour while
    # Alpaca hourly bars are clock-aligned. Both belong to the same nearest
    # hourly decision window.
    canonical_close=(signal_time+timedelta(minutes=30)).replace(minute=0,second=0,microsecond=0)
    key=f"{signal.symbol}|{signal.strategy}|{signal.timeframe}|{canonical_close.isoformat()}"
    return {"canonical_key":key,"canonical_bar_close_utc":canonical_close,
            "source":str(signal.external_metadata.get("source") or "api")}
