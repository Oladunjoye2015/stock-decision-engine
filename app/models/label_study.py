import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.backfill_training import CATEGORICAL, _features, add_multitimeframe_context


def build_study_frame(hourly, candles_15min=None, candles_daily=None):
    data=hourly.copy(); data["timestamp"]=pd.to_datetime(data.timestamp,utc=True)
    enriched=pd.concat([_features(g) for _,g in data.groupby("symbol")]).sort_values(["timestamp","symbol"])
    if candles_15min is not None and candles_daily is not None:
        m15=candles_15min.copy(); daily=candles_daily.copy(); m15["timestamp"]=pd.to_datetime(m15.timestamp,utc=True); daily["timestamp"]=pd.to_datetime(daily.timestamp,utc=True)
        enriched=add_multitimeframe_context(enriched,m15,daily)
    required=["close","high","low","atr","atr_pct","side_hint"]
    return enriched.dropna(subset=required).sort_values(["symbol","timestamp"]).reset_index(drop=True)


def label_configuration(frame, stop_atr, reward_risk, hold_bars, cost_bps=10.0):
    """Barrier outcome with stop-first ties and marked-to-market horizon timeouts."""
    parts=[]
    for _,group in frame.groupby("symbol",sort=False):
        n=len(group); usable=n-hold_bars
        if usable<=0: continue
        close=group.close.to_numpy(float); high=group.high.to_numpy(float); low=group.low.to_numpy(float); atr=group.atr.to_numpy(float); atr_pct=group.atr_pct.to_numpy(float); buy=group.side_hint.to_numpy()=="buy"
        entry=close[:usable]; risk=stop_atr*atr[:usable]; is_buy=buy[:usable]; stop=np.where(is_buy,entry-risk,entry+risk); target=np.where(is_buy,entry+risk*reward_risk,entry-risk*reward_risk)
        future_high=np.lib.stride_tricks.sliding_window_view(high[1:],hold_bars); future_low=np.lib.stride_tricks.sliding_window_view(low[1:],hold_bars)
        stop_hits=np.where(is_buy[:,None],future_low<=stop[:,None],future_high>=stop[:,None]); target_hits=np.where(is_buy[:,None],future_high>=target[:,None],future_low<=target[:,None])
        outcome=np.full(usable,"timeout",dtype="U7"); terminal=close[hold_bars:]; gross=np.clip(np.where(is_buy,terminal-entry,entry-terminal)/risk,-1,reward_risk); active=np.ones(usable,dtype=bool)
        for offset in range(hold_bars):
            stopped=active&stop_hits[:,offset]; outcome[stopped]="sl"; gross[stopped]=-1; active[stopped]=False
            targeted=active&target_hits[:,offset]; outcome[targeted]="tp"; gross[targeted]=reward_risk; active[targeted]=False
        cost_r=(cost_bps/10000)/np.maximum(stop_atr*atr_pct[:usable],1e-9)
        parts.append(pd.DataFrame({"source_index":group.index[:usable],"timestamp":group.timestamp.iloc[:usable].to_numpy(),"symbol":group.symbol.iloc[:usable].to_numpy(),"side_hint":group.side_hint.iloc[:usable].to_numpy(),"outcome":outcome,"gross_r":gross,"net_r":gross-cost_r}))
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=["source_index","timestamp","symbol","side_hint","outcome","gross_r","net_r"])


def summarize(labels):
    if labels.empty: return {"rows":0,"resolved_rows":0,"timeout_rate":None,"win_rate_resolved":None,"mean_gross_r":None,"mean_net_r":None}
    resolved=labels[labels.outcome!="timeout"]
    return {"rows":len(labels),"resolved_rows":len(resolved),"timeout_rate":float((labels.outcome=="timeout").mean()),"win_rate_resolved":float((resolved.outcome=="tp").mean()) if len(resolved) else None,"mean_gross_r":float(labels.gross_r.mean()),"mean_net_r":float(labels.net_r.mean())}


def run_label_study(frame, stop_values=(1,1.5,2,2.5), reward_values=(1,1.5,2), hold_values=(4,8,12,16), cost_bps=10.0, minimum_rows=1000):
    times=np.array(sorted(frame.timestamp.unique())); train_end=times[int(len(times)*.70)]; validation_end=times[int(len(times)*.85)]; candidates=[]; cache={}
    for stop,reward,hold in product(stop_values,reward_values,hold_values):
        key=f"stop_{stop:g}_reward_{reward:g}_hold_{hold}"; labels=label_configuration(frame,stop,reward,hold,cost_bps); cache[key]=labels
        train=labels[labels.timestamp<train_end]; valid=labels[(labels.timestamp>=train_end)&(labels.timestamp<validation_end)]
        train_stats=summarize(train); valid_stats=summarize(valid)
        eligible=train_stats["rows"]>=minimum_rows and valid_stats["rows"]>=minimum_rows and train_stats["mean_net_r"]>0 and valid_stats["mean_net_r"]>0 and abs(train_stats["mean_net_r"]-valid_stats["mean_net_r"])<=.15
        candidates.append({"configuration":key,"stop_atr":stop,"reward_risk":reward,"hold_bars":hold,"train":train_stats,"validation":valid_stats,"selection_eligible":eligible})
    eligible=[x for x in candidates if x["selection_eligible"]]; selected=max(eligible,key=lambda x:x["validation"]["mean_net_r"]) if eligible else None
    final=None
    if selected:
        labels=cache[selected["configuration"]]; test=labels[labels.timestamp>=validation_end]; final={"overall":summarize(test),"by_symbol":{str(k):summarize(g) for k,g in test.groupby("symbol")},"by_side":{str(k):summarize(g) for k,g in test.groupby("side_hint")}}
    return {"selection_protocol":"48 predeclared configurations; positive mean net R in train and validation, >=1000 rows each, train-validation difference <=0.15R; final read only for selected configuration","cost_bps":cost_bps,"train_end":str(pd.Timestamp(train_end)),"validation_end":str(pd.Timestamp(validation_end)),"selected_configuration":selected,"selected_final_test":final,"candidates":candidates}


def save_study(result, output: Path):
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2)+"\n")
