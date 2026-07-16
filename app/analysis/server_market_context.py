from __future__ import annotations

import pandas as pd

from app.database.runtime_store import load_recent_candles
from app.database.runtime_store import upsert_candles
from app.market_data.alpaca_candles import AlpacaCandleClient
from app.models.backfill_training import _features


def _number(value):
    return float(value) if pd.notna(value) else None


def _frame_with_signal(signal, symbol: str, settings) -> pd.DataFrame:
    try:
        fresh=AlpacaCandleClient(settings).recent_hourly(symbol,signal.signal_time_utc)
        if not fresh.empty: upsert_candles(fresh,"1Hour")
        frame=fresh
    except Exception:
        frame=load_recent_candles("1Hour", symbol, 250)
    if symbol == signal.symbol:
        bar_start=signal.external_metadata.get("bar_start_utc")
        bar_start=pd.Timestamp(bar_start) if bar_start else pd.Timestamp(signal.signal_time_utc)-pd.Timedelta(hours=1)
        current = pd.DataFrame([{"timestamp": bar_start, "symbol": signal.symbol,
            "data_provider": f"{signal.external_metadata.get('source','external')}_confirmed_bar", "open": signal.open, "high": signal.high,
            "low": signal.low, "close": signal.close, "volume": signal.volume}])
        frame = pd.concat([frame, current], ignore_index=True).drop_duplicates(["symbol", "timestamp"], keep="last")
    if frame.empty:
        return frame
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    return frame.sort_values("timestamp")


def build_server_context(signal, settings) -> dict:
    frames = {symbol: _frame_with_signal(signal, symbol, settings) for symbol in {signal.symbol, "SPY", "QQQ"}}
    evidence = {}
    for symbol, frame in frames.items():
        if len(frame) < 50:
            evidence[symbol] = {"available": False, "bars": len(frame)}
            continue
        features = _features(frame)
        enriched = features.iloc[-1]
        prior_high20 = frame.high.shift(1).rolling(20).max().iloc[-1]
        evidence[symbol] = {"available": True, "bars": len(frame), "last_timestamp": pd.Timestamp(enriched.timestamp).isoformat(),
            "close": _number(enriched.close), "ema20": _number(enriched.ema20), "ema50": _number(enriched.ema50),
            "ema200": _number(enriched.ema200), "rsi": _number(enriched.rsi), "macd_hist": _number(enriched.macd_hist),
            "adx": _number(enriched.adx), "atr": _number(enriched.atr), "atr_pct": _number(enriched.atr_pct),
            "vol_ratio": _number(enriched.vol_ratio), "prior_high20": _number(prior_high20),
            "trend_up": bool(enriched.trend_up), "trend_down": bool(enriched.trend_down), "dist_vwap": _number(enriched.dist_vwap)}
    primary = evidence.get(signal.symbol, {})
    required = ("ema20", "ema50", "ema200", "rsi", "macd_hist", "adx", "atr", "atr_pct", "vol_ratio")
    complete = primary.get("available", False) and all(pd.notna(primary.get(key)) for key in required)
    benchmarks_available = all(evidence.get(symbol, {}).get("available") for symbol in ("SPY", "QQQ"))
    if benchmarks_available:
        benchmark_freshness_hours=max((pd.Timestamp(signal.signal_time_utc)-pd.Timestamp(evidence[symbol]["last_timestamp"])).total_seconds()/3600 for symbol in ("SPY","QQQ"))
        benchmarks_available=benchmark_freshness_hours<=2.5
    else: benchmark_freshness_hours=None
    benchmark_support = benchmarks_available and not (evidence["SPY"]["trend_down"] and evidence["QQQ"]["trend_down"])
    return {"complete": complete, "benchmarks_available": benchmarks_available,"benchmark_freshness_hours":benchmark_freshness_hours,
            "benchmark_support": benchmark_support, "symbols": evidence,
            "source": "postgres_market_candles_plus_confirmed_tradingview_bar"}
