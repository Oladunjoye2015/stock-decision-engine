import argparse,json,os,sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.backtesting.breakout_shadow import evaluate_breakout_shadow,load_breakout_shadow_config,save_breakout_shadow_state
from app.backtesting.strategies import build_strategy_frame
from app.models.forward_shadow import evaluate_forward_shadow,load_shadow_config,save_shadow_state
from app.models.breakout_ml_shadow import evaluate_ml_shadow,load_ml_shadow,save_ml_shadow
from app.models.label_study import build_study_frame
from scripts.refresh_alpaca_candles import SYMBOLS,refresh


def integrity(d):
    d=d.copy(); d["timestamp"]=pd.to_datetime(d.timestamp,utc=True,errors="coerce"); bad=((d.high<d[["open","close","low"]].max(axis=1))|(d.low>d[["open","close","high"]].min(axis=1))).sum()
    return {"rows":len(d),"symbols":int(d.symbol.nunique()),"first":str(d.timestamp.min()),"last":str(d.timestamp.max()),"duplicates":int(d.duplicated(["symbol","timestamp"]).sum()),"bad_timestamps":int(d.timestamp.isna().sum()),"bad_ohlc":int(bad)}


def evaluate_all(storage="files"):
    if storage=="database":
        from app.database.runtime_store import load_candles,save_runtime_state
        hourly,m15,daily=(load_candles(name) for name in ("1Hour","15Min","1Day"))
    else: hourly=pd.read_csv("data/candles_60min.csv"); m15=pd.read_csv("data/candles_15min.csv"); daily=pd.read_csv("data/candles_1day.csv")
    breakout_config,breakout_hash=load_breakout_shadow_config(Path("model_artifacts/breakout_shadow_config.json")); breakout=evaluate_breakout_shadow(build_strategy_frame(hourly),breakout_config,breakout_hash); save_breakout_shadow_state(breakout,Path("data/breakout_shadow_state.json"))
    study_frame=build_study_frame(hourly,m15,daily); trend_config,trend_hash=load_shadow_config(Path("model_artifacts/forward_shadow_config.json")); trend=evaluate_forward_shadow(study_frame,trend_config,trend_hash); save_shadow_state(trend,Path("data/forward_shadow_state.json"))
    ml_config,ml_meta,ml_model=load_ml_shadow(Path("model_artifacts/breakout_ml_shadow_config.json"),Path("model_artifacts/registry.json"),Path("model_artifacts/artifacts")); ml=evaluate_ml_shadow(build_strategy_frame(hourly),breakout_config["atr_pct_low_volatility_cutoff_by_symbol"],ml_config,ml_meta,ml_model); save_ml_shadow(ml,Path("data/breakout_ml_shadow_state.json"))
    quality={"15Min":integrity(m15),"1Hour":integrity(hourly),"1Day":integrity(daily)}; quality_passed=all(not q["duplicates"] and not q["bad_timestamps"] and not q["bad_ohlc"] and q["symbols"]==12 for q in quality.values())
    report={"generated_at_utc":pd.Timestamp.now(tz="UTC").isoformat(),"storage":storage,"quality_passed":quality_passed,"data_quality":quality,"breakout":{"completed":breakout["completed_trades"],"pending":breakout["pending_trades"],"minimum_sample_reached":breakout["minimum_sample_reached"],"profit_factor":breakout["metrics"].get("profit_factor"),"by_entry_session":breakout["completed_by_entry_session"]},"breakout_ml_filter":{"research_only":True,"scored":ml["scored_candidates"],"allowed":ml["allowed_candidates"],"rejected":ml["rejected_candidates"],"threshold":ml["threshold"]},"long_trend":{"completed":trend["completed_trades"],"pending":trend["pending_signals"],"minimum_sample_reached":trend["minimum_sample_reached"],"metrics":trend["metrics"]},"execution_enabled":False,"automatic_promotion_enabled":False}
    if storage=="database":
        for key,value in {"breakout_shadow_state":breakout,"breakout_ml_shadow_state":ml,"forward_shadow_state":trend,"shadow_status":report}.items(): save_runtime_state(key,value)
    else: Path("data/shadow_status.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description="Refresh Alpaca market data, validate it, and recompute both execution-disabled shadow states."); p.add_argument("--skip-refresh",action="store_true"); p.add_argument("--storage",choices=("files","database"),default=os.getenv("RUNTIME_STORAGE","files")); a=p.parse_args()
    if not a.skip_refresh: refresh(list(("15Min","1Hour","1Day")),list(SYMBOLS),pd.Timestamp.now(tz="UTC"),storage=a.storage)
    print(json.dumps(evaluate_all(a.storage),indent=2))
