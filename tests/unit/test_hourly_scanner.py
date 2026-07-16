from types import SimpleNamespace

import pandas as pd

from app.scanning.hourly_breakout import _daily_regime,_is_candidate,_signal,_trend


def candidate_row(**overrides):
    values={"timestamp":pd.Timestamp("2026-07-15T14:00:00Z"),"symbol":"AAPL","open":100,"high":104,"low":99,"close":103,"volume":1_000_000,
            "prior_high20":102,"vol_ratio":1.5,"adx":25,"atr":2,"atr_pct":.01,"rsi":60,"ema20":101,"ema50":100,"ema200":95,"macd_hist":.5}
    values.update(overrides); return SimpleNamespace(**values)


def test_hourly_scanner_builds_deterministic_confirmed_signal():
    row=candidate_row(); assert _is_candidate(row)
    signal=_signal(row,{"daily_regime":"bullish","4hour_trend":"bullish","15min_confirmation":"bullish"})
    assert signal.signal_id=="railway-hourly-breakout-AAPL-1784124000"
    assert signal.signal_time_utc==pd.Timestamp("2026-07-15T15:00:00Z")
    assert signal.external_metadata["bar_confirmed"] is True and signal.external_metadata["source"]=="railway_hourly_scanner"


def test_hourly_scanner_rejects_weak_breakout_and_uses_closed_context():
    assert not _is_candidate(candidate_row(vol_ratio=1.1))
    rising=pd.DataFrame({"close":range(1,61)})
    falling=pd.DataFrame({"close":range(60,0,-1)})
    assert _trend(rising,20,50)=="bullish" and _daily_regime(rising)=="bullish"
    assert _trend(falling,20,50)=="bearish" and _daily_regime(falling)=="bearish"


def test_scanner_submits_only_fresh_latest_candidate(monkeypatch):
    import app.scanning.hourly_breakout as scanner
    timestamp=pd.Timestamp("2026-07-15T14:00:00Z")
    raw=pd.DataFrame({"timestamp":[timestamp],"symbol":["AAPL"],"data_provider":["alpaca_market_data_api"],"open":[100],"high":[104],"low":[99],"close":[103],"volume":[1_000_000]})
    strategy=pd.DataFrame([vars(candidate_row(timestamp=timestamp))])
    class Client:
        def recent_hourly(self,symbol,now): return raw.copy()
    saved=[]; submitted=[]
    monkeypatch.setattr(scanner,"ATR_CUTOFFS",{"AAPL":.006})
    monkeypatch.setattr(scanner,"load_runtime_state",lambda key:None)
    monkeypatch.setattr(scanner,"save_runtime_state",lambda key,value:saved.append(value))
    monkeypatch.setattr(scanner,"upsert_candles",lambda frame,timeframe:len(frame))
    monkeypatch.setattr(scanner,"build_strategy_frame",lambda frame:strategy)
    monkeypatch.setattr(scanner,"_context",lambda client,symbol,end:{"daily_regime":"bullish","4hour_trend":"bullish","15min_confirmation":"bullish"})
    def processor(signal,db,settings):
        submitted.append(signal); return {"signal_id":signal.signal_id,"final_decision":"blocked"}
    settings=SimpleNamespace(hourly_scanner_enabled=True,runtime_storage="database",hourly_scanner_max_age_seconds=900)
    result=scanner.scan(settings,pd.Timestamp("2026-07-15T15:05:00Z"),Client(),processor)
    assert result["submitted"]==1 and len(submitted)==1 and saved[0]["last_candidate"]["AAPL"]==timestamp.isoformat()

    submitted.clear(); saved.clear()
    stale=scanner.scan(settings,pd.Timestamp("2026-07-15T16:00:01Z"),Client(),processor)
    assert stale["submitted"]==0 and not submitted
