import hashlib
import json
from pathlib import Path

import pandas as pd

from app.models.label_study import label_configuration, summarize
from app.models.trigger_study import trigger_masks


def load_shadow_config(path: Path):
    raw=path.read_bytes(); config=json.loads(raw)
    if config.get("execution_enabled") is not False: raise ValueError("Shadow evaluator requires execution_enabled=false")
    if config.get("promotion_requires_new_review") is not True: raise ValueError("Shadow promotion must require a new review")
    return config,hashlib.sha256(raw).hexdigest()


def evaluate_forward_shadow(frame: pd.DataFrame, config: dict, config_sha256: str):
    boundary=pd.Timestamp(config["accept_signals_after_utc"]); mask=trigger_masks(frame)[config["trigger_name"]]
    eligible=frame[mask&frame.side_hint.eq(config["side"])&(frame.timestamp>boundary)&(frame.m15_age_minutes<=config["maximum_m15_age_minutes"])&(frame.d1_age_days<=config["maximum_daily_age_days"])].copy()
    labels=label_configuration(frame,config["stop_atr"],config["reward_risk"],config["hold_bars"],config["cost_bps"]).set_index("source_index")
    completed_indices=eligible.index.intersection(labels.index); completed=labels.loc[completed_indices].sort_values(["timestamp","symbol"]); pending=eligible.loc[eligible.index.difference(completed_indices)].sort_values(["timestamp","symbol"])
    trades=[{"signal_id":f"{config['candidate_id']}:{row.symbol}:{pd.Timestamp(row.timestamp).isoformat()}","timestamp":pd.Timestamp(row.timestamp).isoformat(),"symbol":row.symbol,"outcome":row.outcome,"gross_r":float(row.gross_r),"net_r":float(row.net_r)} for _,row in completed.iterrows()]
    return {"schema_version":1,"candidate_id":config["candidate_id"],"config_sha256":config_sha256,"accept_signals_after_utc":config["accept_signals_after_utc"],"last_candle_timestamp":pd.Timestamp(frame.timestamp.max()).isoformat(),"completed_trades":len(completed),"pending_signals":len(pending),"minimum_completed_trades":config["minimum_completed_trades"],"minimum_sample_reached":len(completed)>=config["minimum_completed_trades"],"promotion_blocked":True,"promotion_block_reason":"A new human review is required after the fresh-trade minimum; shadow results never auto-enable execution.","metrics":summarize(completed),"trades":trades,"pending":[{"signal_id":f"{config['candidate_id']}:{row.symbol}:{pd.Timestamp(row.timestamp).isoformat()}","timestamp":pd.Timestamp(row.timestamp).isoformat(),"symbol":row.symbol} for _,row in pending.iterrows()]}


def save_shadow_state(state, path: Path):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(state,indent=2)+"\n")
