from __future__ import annotations

from datetime import timedelta
from typing import Callable

import httpx
import pandas as pd

from app.analysis.breakout_demo_gate import ATR_CUTOFFS
from app.api.signals import process_signal
from app.backtesting.strategies import build_strategy_frame
from app.database.engine import SessionLocal
from app.database.runtime_store import load_runtime_state, save_runtime_state, upsert_candles
from app.market_data.alpaca_candles import AlpacaCandleClient
from app.schemas.signals import SignalIn

STATE_KEY = "hourly_breakout_scanner_state"
STATE_SCHEMA_VERSION = 2
STRATEGY = "breakout-medium-high-vol-shadow-v1"


def _trend(frame: pd.DataFrame, fast: int, slow: int) -> str:
    if len(frame) < slow:
        return "neutral"
    close = pd.to_numeric(frame["close"], errors="coerce")
    fast_value = close.ewm(span=fast, adjust=False).mean().iloc[-1]
    slow_value = close.ewm(span=slow, adjust=False).mean().iloc[-1]
    return "bullish" if fast_value > slow_value else "bearish"


def _daily_regime(frame: pd.DataFrame) -> str:
    if len(frame) < 50:
        return "neutral"
    close=pd.to_numeric(frame["close"],errors="coerce")
    return "bullish" if close.iloc[-1]>close.ewm(span=50,adjust=False).mean().iloc[-1] else "bearish"


def _completed(frame: pd.DataFrame, duration: timedelta, end) -> pd.DataFrame:
    if frame.empty:
        return frame
    timestamps=pd.to_datetime(frame["timestamp"],utc=True)
    return frame[timestamps+duration<=pd.Timestamp(end)].copy()


def _context(client: AlpacaCandleClient, symbol: str, end) -> dict:
    m15 = _completed(client.recent(symbol,end,"15Min",10,250,True),timedelta(minutes=15),end)
    h4 = _completed(client.recent(symbol,end,"4Hour",180,250,True),timedelta(hours=4),end)
    daily = _completed(client.recent(symbol,end,"1Day",500,250,False),timedelta(days=1),end)
    for timeframe, frame in (("15Min",m15),("4Hour",h4),("1Day",daily)):
        upsert_candles(frame,timeframe)
    return {"daily_regime":_daily_regime(daily),
            "4hour_trend":_trend(h4,20,50),"15min_confirmation":_trend(m15,20,50)}


def _is_candidate(row) -> bool:
    cutoff=ATR_CUTOFFS.get(str(row.symbol))
    required=(row.prior_high20,row.vol_ratio,row.adx,row.atr_pct,cutoff)
    return all(pd.notna(value) for value in required) and row.close>row.prior_high20 and row.vol_ratio>=1.2 and row.adx>=20 and row.atr_pct>=cutoff


def _signal(row, context: dict) -> SignalIn:
    bar_start=pd.Timestamp(row.timestamp); bar_close=bar_start+timedelta(hours=1); atr=float(row.atr)
    indicators={key:float(getattr(row,key)) for key in ("prior_high20","vol_ratio","adx","atr","atr_pct","rsi","ema20","ema50","ema200","macd_hist")}
    return SignalIn(signal_id=f"railway-hourly-breakout-{row.symbol}-{int(bar_start.timestamp())}",symbol=str(row.symbol),timeframe="60Min",side_hint="long",strategy=STRATEGY,
        signal_time_utc=bar_close.to_pydatetime(),current_price=float(row.close),open=float(row.open),high=float(row.high),low=float(row.low),close=float(row.close),volume=float(row.volume),
        stop_hint=float(row.close)-2*atr,take_profit_hint=float(row.close)+4*atr,indicators=indicators,higher_timeframe_context=context,
        external_metadata={"bar_confirmed":True,"source":"railway_hourly_scanner","bar_start_utc":bar_start.isoformat()},recent_ohlcv=[])


def scan(settings, now=None, client: AlpacaCandleClient | None = None, processor: Callable = process_signal) -> dict:
    if not settings.hourly_scanner_enabled:
        return {"enabled":False,"submitted":0,"reason":"HOURLY_SCANNER_ENABLED is false"}
    if settings.runtime_storage != "database":
        raise RuntimeError("Hourly scanner requires RUNTIME_STORAGE=database")
    now=pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if now.tzinfo is None: now=now.tz_localize("UTC")
    state=load_runtime_state(STATE_KEY) or {"last_scanned":{},"last_candidate":{}}
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        state={**state,"schema_version":STATE_SCHEMA_VERSION,"last_candidate":{}}
    owns=client is None; transport=httpx.Client(timeout=30) if owns else None; client=client or AlpacaCandleClient(settings,transport)
    allowed=set(getattr(settings,"allowed_symbol_set",set()) or set())
    scan_symbols=sorted(set(ATR_CUTOFFS)&allowed) if allowed else sorted(ATR_CUTOFFS)
    frames=[]; results=[]
    try:
        for symbol in scan_symbols:
            frame=client.recent_hourly(symbol,now); upsert_candles(frame,"1Hour"); frames.append(frame)
            print(f"[hourly-scanner] refreshed {symbol}: {len(frame)} hourly rows",flush=True)
        strategy=build_strategy_frame(pd.concat(frames,ignore_index=True)) if frames else pd.DataFrame()
        for symbol, group in strategy.groupby("symbol"):
            completed=group[group.timestamp+timedelta(hours=1)<=now].sort_values("timestamp")
            if completed.empty: continue
            row=completed.iloc[-1]; bar_start=pd.Timestamp(row.timestamp); bar_close=bar_start+timedelta(hours=1)
            state["last_scanned"][symbol]=bar_start.isoformat()
            age=(now-bar_close).total_seconds()
            if age<0 or age>settings.hourly_scanner_max_age_seconds or not _is_candidate(row): continue
            previous=state["last_candidate"].get(symbol)
            if previous and int((completed.timestamp>pd.Timestamp(previous)).sum())<16: continue
            context=_context(client,symbol,bar_close)
            signal=_signal(row,context)
            with SessionLocal() as db: result=processor(signal,db,settings)
            state["last_candidate"][symbol]=bar_start.isoformat(); results.append({**result,"symbol":signal.symbol,"signal_time_utc":signal.signal_time_utc.isoformat()})
            print(f"[hourly-scanner] submitted {signal.signal_id}: {result.get('final_decision')}",flush=True)
    finally:
        if transport is not None: transport.close()
    state.update({"schema_version":STATE_SCHEMA_VERSION,"generated_at_utc":now.isoformat(),"enabled":True,"scan_symbols":scan_symbols,"submitted":len(results),"results":results})
    save_runtime_state(STATE_KEY,state)
    return state
