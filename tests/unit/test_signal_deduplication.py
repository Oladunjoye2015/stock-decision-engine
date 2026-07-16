from datetime import datetime,timezone
from types import SimpleNamespace

from app.core.signal_deduplication import canonical_claim


def signal(at: str, source: str):
    return SimpleNamespace(strategy="breakout-medium-high-vol-shadow-v1",timeframe="60Min",symbol="AAPL",
                           signal_time_utc=datetime.fromisoformat(at).replace(tzinfo=timezone.utc),external_metadata={"source":source})


def test_session_and_clock_aligned_hourly_closes_share_claim():
    tradingview=canonical_claim(signal("2026-07-16T14:30:00","tradingview"))
    scanner=canonical_claim(signal("2026-07-16T15:00:00","railway_hourly_scanner"))
    assert tradingview["canonical_key"]==scanner["canonical_key"]
    assert tradingview["source"]=="tradingview" and scanner["source"]=="railway_hourly_scanner"


def test_non_breakout_signal_has_no_cross_source_claim():
    value=signal("2026-07-16T15:00:00","api"); value.strategy="other"
    assert canonical_claim(value) is None
