from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from app.models.training import FEATURE_NAMES, build_training_frame, chronological_split
from app.models.backfill_training import add_multitimeframe_context, build_backfill_dataset, evaluate_setup_gates
from scripts.download_candles import month_windows, validate_frame
from scripts.import_candles import normalize_export
from app.models.label_study import label_configuration, summarize
from app.models.trigger_study import trigger_masks
from app.models.forward_shadow import evaluate_forward_shadow


def candles(count=500):
    times = pd.date_range("2025-01-01", periods=count, freq="h", tz="UTC"); rng = np.random.default_rng(42); returns = rng.normal(.0002, .005, count); close = 100*np.cumprod(1+returns); open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"timestamp": times, "symbol": "AAPL", "open": open_, "high": np.maximum(open_, close)*1.002, "low": np.minimum(open_, close)*.998, "close": close, "volume": rng.integers(1000, 10000, count)})


def test_training_features_and_splits_are_chronological():
    frame = build_training_frame(candles())
    assert not frame[FEATURE_NAMES].isna().any().any()
    train, validation, test = chronological_split(frame)
    assert train.timestamp.max() < validation.timestamp.min() < test.timestamp.min()


def test_downloader_month_windows_and_validation():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc); end = start+timedelta(days=75)
    assert len(list(month_windows(start, end))) == 3
    raw = pd.DataFrame([{"timestamp": 1, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}, {"timestamp": 1, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}, {"timestamp": 2, "open": 10, "high": 8, "low": 9, "close": 11, "volume": 100}])
    validated = validate_frame(raw, "AAPL")
    assert len(validated) == 1 and validated.iloc[0].symbol == "AAPL" and validated.iloc[0].data_provider == "finnhub"


def test_user_supplied_alpaca_export_is_normalized_without_api(tmp_path):
    source = tmp_path/"alpaca.csv"; output = tmp_path/"normalized.csv"
    pd.DataFrame({"timestamp": ["2026-01-01T15:00:00Z"], "symbol": ["AAPL"], "open": [100], "high": [102], "low": [99], "close": [101], "volume": [1000]}).to_csv(source, index=False)
    imported = normalize_export(source, output)
    assert output.is_file() and imported.iloc[0].data_provider == "user_supplied_alpaca_export"


def test_backfill_method_builds_full_side_aware_barrier_rows():
    rng=np.random.default_rng(3); n=350; times=pd.date_range("2024-01-01",periods=n,freq="h",tz="UTC"); returns=rng.normal(0,.012,n); close=100*np.cumprod(1+returns); open_=np.r_[close[0],close[:-1]]
    raw=pd.DataFrame({"timestamp":times,"symbol":"AAPL","open":open_,"high":np.maximum(open_,close)*(1+rng.uniform(.001,.01,n)),"low":np.minimum(open_,close)*(1-rng.uniform(.001,.01,n)),"close":close,"volume":rng.integers(1000,10000,n)})
    result=build_backfill_dataset(raw)
    assert not result.empty and set(result.outcome).issubset({-1,1})
    assert {"ema200","adx","bb_width","vwap","fib618","supply_top","side_hint","stop_hint","take_profit_hint"}.issubset(result.columns)
    buys=result[result.side_hint=="buy"]; assert (buys.stop_hint<buys.close).all() and (buys.take_profit_hint>buys.close).all()


def test_multitimeframe_join_uses_only_completed_context():
    hourly=candles(250); m15=candles(1000); m15["timestamp"]=pd.date_range("2024-12-22",periods=1000,freq="15min",tz="UTC")
    daily=candles(250); daily["timestamp"]=pd.date_range("2024-05-01",periods=250,freq="D",tz="UTC")
    base=pd.concat([__import__("app.models.backfill_training",fromlist=["_features"])._features(g) for _,g in hourly.groupby("symbol")])
    joined=add_multitimeframe_context(base,m15,daily)
    assert set(["m15_rsi","m15_age_minutes","d1_rsi","d1_age_days"]).issubset(joined.columns)
    assert (joined.m15_age_minutes.dropna()>=0).all() and (joined.d1_age_days.dropna()>=0).all()


def test_gate_selection_never_uses_test_outcomes():
    n=1200; data=pd.DataFrame({"timestamp":pd.date_range("2024-01-01",periods=n,freq="h",tz="UTC"),"side_hint":"buy","di_plus":30,"di_minus":10,"macd_hist":1,"m15_macd_hist":1,"m15_rsi":60,"d1_dist_ema50":.1,"d1_macd_hist":1,"hour_utc":15,"vol_ratio":1,"in_supply":False,"in_demand":False,"adx":25,"target":([1,0,1]*400)})
    train_end=data.timestamp.iloc[500]; validation_end=data.timestamp.iloc[900]; first,_=evaluate_setup_gates(data,train_end,validation_end,minimum_rows=100)
    data.loc[data.timestamp>=validation_end,"target"]=0; second,_=evaluate_setup_gates(data,train_end,validation_end,minimum_rows=100)
    assert first==second


def test_label_study_tracks_timeouts_and_values_horizon_exit():
    frame=pd.DataFrame({"timestamp":pd.date_range("2025-01-01",periods=5,freq="h",tz="UTC"),"symbol":"AAPL","side_hint":"buy","close":[100,101,101,101,101],"high":[100.1,101.1,101.1,101.1,101.1],"low":[99.9,100.9,100.9,100.9,100.9],"atr":2.0,"atr_pct":.02})
    labels=label_configuration(frame,2,2,hold_bars=2,cost_bps=0); stats=summarize(labels)
    assert stats["rows"]==3 and stats["timeout_rate"]==1
    assert labels.iloc[0].gross_r==.25


def test_direction_triggers_are_sparse_and_side_specific():
    frame=pd.DataFrame({"hour_utc":[15],"vol_ratio":[1.2],"trend_up":[True],"trend_down":[False],"d1_trend_up":[True],"d1_trend_down":[False],"close":[101],"vwap":[100],"m15_macd_hist":[1],"rsi":[55],"dist_recent_high":[.002],"dist_recent_low":[.2],"m15_vol_ratio":[1.2],"dist_ema20":[.005],"in_demand":[False],"in_supply":[False],"d1_dist_ema50":[.1]})
    masks=trigger_masks(frame)
    assert masks["long_trend_continuation"].iloc[0]
    assert not any(mask.iloc[0] for name,mask in masks.items() if name.startswith("short_"))


def test_forward_shadow_excludes_boundary_and_never_promotes():
    n=25; frame=pd.DataFrame({"timestamp":pd.date_range("2026-07-14 15:00",periods=n,freq="h",tz="UTC"),"symbol":"AAPL","side_hint":"buy","hour_utc":15,"vol_ratio":1.2,"trend_up":True,"trend_down":False,"d1_trend_up":True,"d1_trend_down":False,"close":100.0,"vwap":99.0,"m15_macd_hist":1.0,"rsi":55.0,"dist_recent_high":.002,"dist_recent_low":.2,"m15_vol_ratio":1.2,"dist_ema20":.005,"in_demand":False,"in_supply":False,"d1_dist_ema50":.1,"m15_age_minutes":0.0,"d1_age_days":1.0,"high":100.1,"low":99.9,"atr":2.0,"atr_pct":.02})
    config={"candidate_id":"x","accept_signals_after_utc":"2026-07-14T15:00:00Z","side":"buy","trigger_name":"long_trend_continuation","stop_atr":2.5,"reward_risk":2,"hold_bars":16,"cost_bps":10,"maximum_m15_age_minutes":15,"maximum_daily_age_days":4,"minimum_completed_trades":100}
    state=evaluate_forward_shadow(frame,config,"abc")
    assert all(t["timestamp"]!="2026-07-14T15:00:00+00:00" for t in state["trades"])
    assert state["promotion_blocked"] and not state["minimum_sample_reached"]
