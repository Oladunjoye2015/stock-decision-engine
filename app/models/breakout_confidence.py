import hashlib,importlib.metadata,json
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss,log_loss,roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

FEATURES=["breakout_pct","breakout_atr","vol_ratio","volume_acceleration","adx","adx_change3","atr_pct","atr_percentile","rsi","macd_hist_pct","di_spread","ret1","ret3","ret5","ret20","gap_pct","body_pct","range_pct","close_location","dist_ema20","dist_ema50","dist_ema200","dist_vwap","bb_width","hour_sin","hour_cos","dow","spy_ret20","qqq_ret20","relative_strength20","market_breadth","market_trend_breadth","m15_rsi","m15_macd_hist_pct","m15_ret4","m15_vol_ratio","m15_atr_pct","m15_trend_up","d1_rsi","d1_macd_hist_pct","d1_ret5","d1_atr_pct","d1_trend_up","d1_dist_ema50"]
HOURLY_FEATURES=[name for name in FEATURES if not name.startswith(("m15_","d1_"))]


def prepare_breakout_feature_frame(frame,cutoffs):
    x=frame.sort_values(["symbol","timestamp"]).copy(); grouped=x.groupby("symbol"); x["prior_high20"]=grouped.high.transform(lambda s:s.shift(1).rolling(20).max()); x["ret20"]=grouped.close.pct_change(20); x["next_timestamp"]=grouped.timestamp.shift(-1); next_local=x.next_timestamp.dt.tz_convert("America/New_York"); cutoff=x.symbol.map(cutoffs); x["candidate"]=(x.close>x.prior_high20)&(x.vol_ratio>=1.2)&(x.adx>=20)&(x.atr_pct>=cutoff)&next_local.dt.hour.between(9,15)
    spy=x[x.symbol=="SPY"].set_index("timestamp").ret20; qqq=x[x.symbol=="QQQ"].set_index("timestamp").ret20; x["spy_ret20"]=x.timestamp.map(spy); x["qqq_ret20"]=x.timestamp.map(qqq); x["relative_strength20"]=x.ret20-x.spy_ret20
    x["market_breadth"]=(x.close>x.ema50).groupby(x.timestamp).transform("mean"); x["market_trend_breadth"]=x.trend_up.groupby(x.timestamp).transform("mean"); x["breakout_pct"]=x.close/x.prior_high20-1; x["breakout_atr"]=(x.close-x.prior_high20)/x.atr; x["macd_hist_pct"]=x.macd_hist/x.close; x["di_spread"]=(x.di_plus-x.di_minus)/100; x["volume_acceleration"]=x.vol_ratio/grouped.vol_ratio.shift(1); x["adx_change3"]=x.adx-grouped.adx.shift(3); x["atr_percentile"]=grouped.atr_pct.transform(lambda s:s.rolling(252,min_periods=50).rank(pct=True)); x["gap_pct"]=x.open/grouped.close.shift(1)-1; x["body_pct"]=(x.close-x.open)/x.open; x["range_pct"]=(x.high-x.low)/x.close; x["close_location"]=(x.close-x.low)/(x.high-x.low).replace(0,np.nan); x["hour_sin"]=np.sin(2*np.pi*next_local.dt.hour/24); x["hour_cos"]=np.cos(2*np.pi*next_local.dt.hour/24); x["dow"]=next_local.dt.dayofweek
    for prefix in ("m15","d1"):
        if f"{prefix}_macd_hist" in x: x[f"{prefix}_macd_hist_pct"]=x[f"{prefix}_macd_hist"]/x.close
    for name in FEATURES:
        if name not in x: x[name]=0.0
    return x


def build_breakout_candidates(frame,cutoffs,hold_bars=16,stop_atr=2,reward_risk=2,slippage_bps_each_side=5):
    x=prepare_breakout_feature_frame(frame,cutoffs)
    records=[]; slip=slippage_bps_each_side/10000
    for _,group in x.groupby("symbol",sort=False):
        rows=group.reset_index()
        for i,row in rows[rows.candidate].iterrows():
            future=rows.iloc[i+1:i+1+hold_bars]
            if len(future)<hold_bars: continue
            entry=float(future.iloc[0].open)*(1+slip); risk=stop_atr*float(row.atr); stop=entry-risk; target=entry+risk*reward_risk; raw_exit=float(future.iloc[-1].close); outcome="timeout"
            for _,bar in future.iterrows():
                if bar.low<=stop: raw_exit,outcome=stop,"stop"; break
                if bar.high>=target: raw_exit,outcome=target,"target"; break
            exit_price=raw_exit*(1-slip); net_return=exit_price/entry-1; record={"timestamp":row.timestamp,"symbol":row.symbol,"entry_timestamp":future.iloc[0].timestamp,"outcome":outcome,"net_return":net_return,"target":int(net_return>0)}
            record.update({name:float(row[name]) if pd.notna(row[name]) else 0.0 for name in FEATURES}); records.append(record)
    return pd.DataFrame(records).sort_values(["timestamp","symbol"]).reset_index(drop=True)


def performance(returns,selected):
    values=np.asarray(returns)[np.asarray(selected)]; wins=values[values>0]; losses=values[values<0]
    return {"signals":int(len(values)),"mean_net_return":float(values.mean()) if len(values) else None,"win_rate":float((values>0).mean()) if len(values) else None,"profit_factor":float(wins.sum()/-losses.sum()) if len(losses) else None}


def train_confidence_gate(candidates,artifact_dir:Path,registry_path:Path,model_id="breakout-confidence-v2",raw_features=None,model_names=None):
    data=candidates.copy(); raw_features=raw_features or FEATURES; encoded=pd.get_dummies(data[["symbol"]+raw_features],columns=["symbol"],dtype=float); feature_names=list(encoded.columns); times=np.array(sorted(data.timestamp.unique())); a,b=times[int(len(times)*.70)],times[int(len(times)*.85)]; train=data.timestamp<a; valid=(data.timestamp>=a)&(data.timestamp<b); test=data.timestamp>=b; Xtr,Xv,Xt=encoded[train],encoded[valid],encoded[test]; ytr,yv,yt=data.target[train],data.target[valid],data.target[test]
    estimators={"logistic":make_pipeline(StandardScaler(),LogisticRegression(max_iter=2000,class_weight="balanced",random_state=42)),"random_forest":RandomForestClassifier(n_estimators=400,min_samples_leaf=8,class_weight="balanced",random_state=42,n_jobs=-1),"catboost":CatBoostClassifier(iterations=400,depth=5,learning_rate=.03,loss_function="Logloss",verbose=False,allow_writing_files=False,random_seed=42,auto_class_weights="Balanced"),"xgboost":XGBClassifier(n_estimators=400,max_depth=4,learning_rate=.03,subsample=.8,colsample_bytree=.8,eval_metric="logloss",random_state=42,n_jobs=4)}
    if model_names: estimators={name:estimators[name] for name in model_names}
    fitted={}; validation={}
    for name,base in estimators.items():
        model=CalibratedClassifierCV(base,method="sigmoid",cv=TimeSeriesSplit(3)); model.fit(Xtr,ytr); p=model.predict_proba(Xv)[:,1]; fitted[name]=model; validation[name]={"log_loss":log_loss(yv,p,labels=[0,1]),"brier":brier_score_loss(yv,p),"roc_auc":roc_auc_score(yv,p)}
    selected_name=min(validation,key=lambda name:validation[name]["brier"]); model=fitted[selected_name]; pv=model.predict_proba(Xv)[:,1]; threshold_table={}
    for threshold in (.50,.55,.60,.65,.70): threshold_table[f"{threshold:.2f}"]=performance(data.loc[valid,"net_return"],pv>=threshold)
    eligible=[(float(k),v) for k,v in threshold_table.items() if v["signals"]>=40 and v["mean_net_return"] is not None and v["mean_net_return"]>0]; threshold=max(eligible,key=lambda z:z[1]["mean_net_return"])[0] if eligible else .60
    pt=model.predict_proba(Xt)[:,1]; final={"probability":{"log_loss":log_loss(yt,pt,labels=[0,1]),"brier":brier_score_loss(yt,pt),"roc_auc":roc_auc_score(yt,pt)},"all_breakouts":performance(data.loc[test,"net_return"],np.ones(test.sum(),dtype=bool)),"confidence_gated":performance(data.loc[test,"net_return"],pt>=threshold),"threshold":threshold}
    eligible_final=final["confidence_gated"]["signals"]>=40 and final["confidence_gated"]["mean_net_return"] and final["confidence_gated"]["mean_net_return"]>final["all_breakouts"]["mean_net_return"] and final["confidence_gated"]["profit_factor"] and final["confidence_gated"]["profit_factor"]>=1.2
    artifact_dir.mkdir(parents=True,exist_ok=True); import joblib; path=artifact_dir/f"{model_id}.joblib"; joblib.dump(model,path); checksum=hashlib.sha256(path.read_bytes()).hexdigest(); meta={"model_id":model_id,"model_type":"calibrated_breakout_confidence_classifier","model_version":datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),"artifact":path.name,"sha256":checksum,"timeframe":"60Min","supported_symbols":sorted(data.symbol.unique()),"feature_names":feature_names,"probability_method":"predict_proba","class_labels":[0,1],"dependency_versions":{n:importlib.metadata.version(n) for n in ("scikit-learn","catboost","xgboost","pandas","numpy")},"training_metadata":{"purpose":"confidence gate for deterministic breakout candidates only","raw_feature_names":raw_features,"rows":len(data),"train_rows":int(train.sum()),"validation_rows":int(valid.sum()),"test_rows":int(test.sum()),"candidate_features_from_signal_bar_only":True,"entry_at_next_bar_open":True,"validation_models":validation,"selected_model":selected_name,"validation_threshold_table":threshold_table,"final_test":final,"production_eligible":bool(eligible_final),"test_period_previously_seen_for_strategy_research":True},"enabled":False}
    registry=json.loads(registry_path.read_text()); registry["models"]=[m for m in registry["models"] if m.get("model_id")!=model_id]+[meta]; registry_path.write_text(json.dumps(registry,indent=2)+"\n"); (artifact_dir/f"{model_id}.metadata.json").write_text(json.dumps(meta,indent=2)+"\n"); return meta
