import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.label_study import label_configuration, summarize


def trigger_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Predetermined sparse entry definitions; each explicitly chooses a side."""
    regular=frame.hour_utc.between(14,19); liquid=frame.vol_ratio>=.8
    long_trend=frame.trend_up&frame.d1_trend_up&(frame.close>frame.vwap)&(frame.m15_macd_hist>0)
    short_trend=frame.trend_down&frame.d1_trend_down&(frame.close<frame.vwap)&(frame.m15_macd_hist<0)
    return {
        "long_trend_continuation":regular&liquid&long_trend&frame.rsi.between(50,68),
        "long_breakout":regular&liquid&long_trend&(frame.dist_recent_high<=.006)&(frame.m15_vol_ratio>=1),
        "long_pullback":regular&long_trend&frame.rsi.between(42,58)&(frame.dist_ema20.abs()<=.01),
        "long_demand_reversal":regular&liquid&frame.in_demand&(frame.rsi<=40)&(frame.m15_macd_hist>0)&(frame.d1_dist_ema50>0),
        "short_trend_continuation":regular&liquid&short_trend&frame.rsi.between(32,50),
        "short_breakdown":regular&liquid&short_trend&(frame.dist_recent_low<=.006)&(frame.m15_vol_ratio>=1),
        "short_pullback":regular&short_trend&frame.rsi.between(42,58)&(frame.dist_ema20.abs()<=.01),
        "short_supply_reversal":regular&liquid&frame.in_supply&(frame.rsi>=60)&(frame.m15_macd_hist<0)&(frame.d1_dist_ema50<0),
    }


def run_trigger_study(frame, stop_atr=2.5, reward_risk=2, hold_bars=16, cost_bps=10, minimum_rows=200):
    labels=label_configuration(frame,stop_atr,reward_risk,hold_bars,cost_bps).set_index("source_index"); masks=trigger_masks(frame); times=np.array(sorted(frame.timestamp.unique())); train_end=times[int(len(times)*.70)]; validation_end=times[int(len(times)*.85)]; reports={}
    for name,mask in masks.items():
        side="buy" if name.startswith("long_") else "sell"; indices=frame.index[mask&frame.side_hint.eq(side)]; chosen=labels.loc[labels.index.intersection(indices)]
        train=chosen[chosen.timestamp<train_end]; valid=chosen[(chosen.timestamp>=train_end)&(chosen.timestamp<validation_end)]; later=chosen[chosen.timestamp>=validation_end]
        tr,va=summarize(train),summarize(valid); eligible=tr["rows"]>=minimum_rows and va["rows"]>=minimum_rows and tr["mean_net_r"]>0 and va["mean_net_r"]>0
        reports[name]={"side":side,"train":tr,"validation":va,"selection_eligible":eligible,"later_seen_period_exploratory":summarize(later)}
    selected={}
    for side,prefix in (("buy","long_"),("sell","short_")):
        eligible=[(name,value) for name,value in reports.items() if name.startswith(prefix) and value["selection_eligible"]]
        selected[side]=max(eligible,key=lambda item:item[1]["validation"]["mean_net_r"])[0] if eligible else None
    selected_indices=pd.Index([])
    for side,name in selected.items():
        if name: selected_indices=selected_indices.union(frame.index[masks[name]&frame.side_hint.eq(side)])
    combined=labels.loc[labels.index.intersection(selected_indices)]; later=combined[combined.timestamp>=validation_end]
    return {"protocol":"separate predeclared long/short trigger selection on train and validation; later period is exploratory because it was inspected by prior studies","label_configuration":{"stop_atr":stop_atr,"reward_risk":reward_risk,"hold_bars":hold_bars,"cost_bps":cost_bps},"train_end":str(pd.Timestamp(train_end)),"validation_end":str(pd.Timestamp(validation_end)),"selected_triggers":selected,"combined_later_seen_period_exploratory":summarize(later),"triggers":reports}


def save_trigger_study(result, output: Path):
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2)+"\n")
