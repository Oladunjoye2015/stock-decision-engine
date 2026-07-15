import hashlib,json
from pathlib import Path

import pandas as pd

from app.backtesting.engine import BacktestSettings, run_strategy_backtest
from app.backtesting.stress import grouped_trade_metrics


def load_breakout_shadow_config(path: Path):
    raw=path.read_bytes(); config=json.loads(raw)
    if config.get("execution_enabled") is not False or config.get("promotion_requires_new_review") is not True: raise ValueError("Breakout shadow must be execution-disabled and require review")
    return config,hashlib.sha256(raw).hexdigest()


def evaluate_breakout_shadow(frame: pd.DataFrame, config: dict, checksum: str):
    x=frame.copy(); boundary=pd.Timestamp(config["accept_signals_after_utc"]); lookback=int(config["lookback_bars"])
    x["shadow_prior_high"]=x.groupby("symbol").high.transform(lambda s:s.shift(1).rolling(lookback).max()); cutoff=x.symbol.map(config["atr_pct_low_volatility_cutoff_by_symbol"])
    x["breakout_shadow"]=(x.timestamp>boundary)&(x.close>x.shadow_prior_high)&(x.vol_ratio>=config["relative_volume_minimum"])&(x.adx>=config["adx_minimum"])&(x.atr_pct>=cutoff)
    settings=BacktestSettings(max_positions=config["maximum_positions"],risk_per_trade=config["risk_per_trade"],stop_atr=config["stop_atr"],reward_risk=config["reward_risk"],max_hold_bars=config["maximum_hold_bars"],slippage_bps_each_side=config["assumed_slippage_bps_each_side"],force_close_end=False)
    result=run_strategy_backtest(x,"breakout_shadow",settings); trades=result["trades"]; completed=trades[trades.status=="closed"].copy() if len(trades) else trades; pending=trades[trades.status=="open"].copy() if len(trades) else trades; pf=result["metrics"].get("profit_factor"); minimum=len(completed)>=config["minimum_completed_trades"]
    return {"schema_version":1,"candidate_id":config["candidate_id"],"config_sha256":checksum,"last_candle_timestamp":pd.Timestamp(x.timestamp.max()).isoformat(),"completed_trades":len(completed),"pending_trades":len(pending),"minimum_sample_reached":minimum,"profit_factor_gate_reached":minimum and pf is not None and pf>=config["minimum_profit_factor"],"promotion_blocked":True,"promotion_block_reason":"Shadow results require a new human review and never auto-enable execution.","assumed_slippage_bps_each_side":config["assumed_slippage_bps_each_side"],"maximum_acceptable_slippage_bps_each_side":config["maximum_acceptable_slippage_bps_each_side"],"metrics":result["metrics"],"completed_by_entry_session":grouped_trade_metrics(completed,"entry_session") if len(completed) else {},"trades":json.loads(trades.to_json(orient="records",date_format="iso")) if len(trades) else []}


def save_breakout_shadow_state(state,path:Path):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(state,indent=2)+"\n")
