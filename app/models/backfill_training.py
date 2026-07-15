import hashlib, importlib.metadata, json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import balanced_accuracy_score, log_loss, precision_score, roc_auc_score

CATEGORICAL = ["symbol", "timeframe", "side_hint", "trigger_mode"]
EXCLUDED = {"timestamp", "target", "outcome", "hit_type", "future_return"}
MTF_COLUMNS = [
    "m15_rsi", "m15_macd_hist", "m15_ret1", "m15_ret4", "m15_vol_ratio",
    "m15_atr_pct", "m15_trend_up", "m15_trend_down", "m15_age_minutes",
    "d1_rsi", "d1_macd_hist", "d1_ret1", "d1_ret5", "d1_atr_pct",
    "d1_trend_up", "d1_trend_down", "d1_dist_ema50", "d1_age_days",
]


def setup_gate_masks(data: pd.DataFrame) -> dict[str, pd.Series]:
    """Predetermined, interpretable setup gates; no outcome-dependent thresholds."""
    buy=data.side_hint.eq("buy"); sell=~buy
    h1_direction=(buy&(data.di_plus>data.di_minus)&(data.macd_hist>0))|(sell&(data.di_minus>data.di_plus)&(data.macd_hist<0))
    m15_direction=(buy&(data.m15_macd_hist>0)&(data.m15_rsi>=50))|(sell&(data.m15_macd_hist<0)&(data.m15_rsi<50))
    daily_direction=(buy&(data.d1_dist_ema50>0)&(data.d1_macd_hist>0))|(sell&(data.d1_dist_ema50<0)&(data.d1_macd_hist<0))
    regular_session=data.hour_utc.between(14,19)
    liquid=data.vol_ratio>=.75
    not_opposing_zone=(buy&~data.in_supply)|(sell&~data.in_demand)
    return {
        "regular_session":regular_session,
        "h1_direction":h1_direction,
        "m15_direction":m15_direction,
        "daily_direction":daily_direction,
        "h1_m15_direction":h1_direction&m15_direction,
        "h1_daily_direction":h1_direction&daily_direction,
        "all_timeframes_direction":h1_direction&m15_direction&daily_direction,
        "direction_liquidity":h1_direction&m15_direction&liquid,
        "direction_no_opposing_zone":h1_direction&m15_direction&not_opposing_zone,
        "regular_direction":regular_session&h1_direction&m15_direction,
        "moderate_trend_direction":regular_session&h1_direction&m15_direction&data.adx.between(18,35),
    }


def evaluate_setup_gates(data: pd.DataFrame, train_end, validation_end, minimum_rows=300):
    """Select using training and validation only, then report test once."""
    periods={"train":data.timestamp<train_end,"validation":data.timestamp.between(train_end,validation_end,inclusive="left"),"test":data.timestamp>=validation_end}
    report={}
    for name,mask in setup_gate_masks(data).items():
        stats={}
        for period,period_mask in periods.items():
            chosen=data[mask&period_mask]; precision=float(chosen.target.mean()) if len(chosen) else 0.0
            stats[period]={"rows":len(chosen),"precision":precision,"expected_r_multiple_before_costs":3*precision-1 if len(chosen) else None}
        stats["selection_eligible"]=all(stats[p]["rows"]>=minimum_rows and stats[p]["expected_r_multiple_before_costs"]>0 for p in ("train","validation"))
        report[name]=stats
    eligible=[(name,stats) for name,stats in report.items() if stats["selection_eligible"]]
    selected=max(eligible,key=lambda item:item[1]["validation"]["expected_r_multiple_before_costs"])[0] if eligible else None
    return selected,report


def _rsi(x, n=14):
    d=x.diff(); gain=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); loss=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean(); return 100-100/(1+gain/loss.replace(0,np.nan))


def _features(group: pd.DataFrame) -> pd.DataFrame:
    x=group.sort_values("timestamp").copy(); close=x.close; prev=close.shift(); tr=pd.concat([x.high-x.low,(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
    for n in (20,50,200): x[f"ema{n}"]=close.ewm(span=n,adjust=False).mean()
    x["ema_fast"],x["ema_slow"]=x.ema20,x.ema50; x["rsi"]=_rsi(close); macd=close.ewm(span=12,adjust=False).mean()-close.ewm(span=26,adjust=False).mean(); x["macd_hist"]=macd-macd.ewm(span=9,adjust=False).mean()
    up=x.high.diff(); down=-x.low.diff(); plus=pd.Series(np.where((up>down)&(up>0),up,0),index=x.index); minus=pd.Series(np.where((down>up)&(down>0),down,0),index=x.index); atr=tr.ewm(alpha=1/14,adjust=False).mean(); x["di_plus"]=100*plus.ewm(alpha=1/14,adjust=False).mean()/atr; x["di_minus"]=100*minus.ewm(alpha=1/14,adjust=False).mean()/atr; dx=100*(x.di_plus-x.di_minus).abs()/(x.di_plus+x.di_minus); x["adx"]=dx.ewm(alpha=1/14,adjust=False).mean(); x["atr"],x["atr_pct"]=atr,atr/close
    basis=close.rolling(20).mean(); dev=close.rolling(20).std(ddof=0)*2; x["bb_width"]=(4*dev)/basis
    local=x.timestamp.dt.tz_convert("America/New_York"); session=local.dt.date; x["vwap"]=(close*x.volume).groupby(session).cumsum()/x.volume.groupby(session).cumsum(); x["dist_vwap"]=(close-x.vwap)/close
    for n in (1,3,5): x[f"ret{n}"]=close.pct_change(n)
    for n in (20,50,200): x[f"dist_ema{n}"]=(close-x[f"ema{n}"])/close
    x["dist_ema_fast"],x["dist_ema_slow"]=x.dist_ema20,x.dist_ema50; x["vol_ratio"]=x.volume/x.volume.rolling(20).mean(); x["recent_high"],x["recent_low"]=x.high.rolling(20).max(),x.low.rolling(20).min(); x["dist_recent_high"]=(x.recent_high-close)/close; x["dist_recent_low"]=(close-x.recent_low)/close
    span=x.recent_high-x.recent_low
    for label,ratio in (("382",.382),("500",.5),("618",.618)): x[f"fib{label}"]=x.recent_high-span*ratio; x[f"dist_fib{label}"]=(close-x[f"fib{label}"])/close
    zone=atr*.5; x["supply_top"]=x.high.rolling(20).max(); x["supply_bot"]=x.supply_top-zone; x["demand_bot"]=x.low.rolling(20).min(); x["demand_top"]=x.demand_bot+zone; x["dist_supply"]=(x.supply_bot-close)/close; x["dist_demand"]=(close-x.demand_top)/close; x["in_supply"]=(close<=x.supply_top)&(close>=x.supply_bot); x["in_demand"]=(close>=x.demand_bot)&(close<=x.demand_top)
    x["trend_up"]=(x.ema20>x.ema50)&(x.ema50>x.ema200); x["trend_down"]=(x.ema20<x.ema50)&(x.ema50<x.ema200); x["side_hint"]=np.where(x.trend_down&(x.rsi<50)&(x.macd_hist<0),"sell","buy"); x["stop_hint"]=np.where(x.side_hint=="buy",close-atr*2,close+atr*2); x["take_profit_hint"]=np.where(x.side_hint=="buy",close+atr*4,close-atr*4); x["timeframe"]="60Min"; x["trigger_mode"]="H1_COLLECTION"; x["hour_utc"]=x.timestamp.dt.hour; x["dow_utc"]=x.timestamp.dt.dayofweek; x["month_utc"]=x.timestamp.dt.month
    return x


def _context_features(candles: pd.DataFrame, prefix: str, duration: pd.Timedelta) -> pd.DataFrame:
    """Build context known only after the source candle has completed."""
    parts=[]
    for symbol, group in candles.groupby("symbol"):
        x=group.sort_values("timestamp").copy(); close=x.close; prev=close.shift()
        tr=pd.concat([x.high-x.low,(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
        ema20=close.ewm(span=20,adjust=False).mean(); ema50=close.ewm(span=50,adjust=False).mean(); ema200=close.ewm(span=200,adjust=False).mean()
        macd=close.ewm(span=12,adjust=False).mean()-close.ewm(span=26,adjust=False).mean()
        out=pd.DataFrame({
            "symbol":symbol, "available_at":x.timestamp+duration, "context_timestamp":x.timestamp,
            f"{prefix}_rsi":_rsi(close), f"{prefix}_macd_hist":macd-macd.ewm(span=9,adjust=False).mean(),
            f"{prefix}_ret1":close.pct_change(), f"{prefix}_atr_pct":tr.ewm(alpha=1/14,adjust=False).mean()/close,
            f"{prefix}_trend_up":(ema20>ema50)&(ema50>ema200), f"{prefix}_trend_down":(ema20<ema50)&(ema50<ema200),
        })
        if prefix=="m15":
            out[f"{prefix}_ret4"]=close.pct_change(4); out[f"{prefix}_vol_ratio"]=x.volume/x.volume.rolling(20).mean()
        else:
            out[f"{prefix}_ret5"]=close.pct_change(5); out[f"{prefix}_dist_ema50"]=(close-ema50)/close
        parts.append(out)
    return pd.concat(parts,ignore_index=True)


def add_multitimeframe_context(hourly: pd.DataFrame, candles_15min: pd.DataFrame, candles_daily: pd.DataFrame) -> pd.DataFrame:
    """Join the latest fully completed 15-minute and prior-day context per symbol."""
    base=hourly.copy(); base["timestamp"]=pd.to_datetime(base.timestamp,utc=True); base["signal_available_at"]=base.timestamp+pd.to_timedelta(1,unit="h"); joined=[]
    m15=_context_features(candles_15min,"m15",pd.to_timedelta(15,unit="min")); daily=_context_features(candles_daily,"d1",pd.to_timedelta(1,unit="D"))
    for symbol, group in base.groupby("symbol"):
        left=group.sort_values("signal_available_at")
        a=pd.merge_asof(left,m15[m15.symbol==symbol].drop(columns="symbol").sort_values("available_at"),left_on="signal_available_at",right_on="available_at",direction="backward")
        a=a.rename(columns={"context_timestamp":"m15_context_timestamp"}).drop(columns="available_at")
        a=pd.merge_asof(a.sort_values("signal_available_at"),daily[daily.symbol==symbol].drop(columns="symbol").sort_values("available_at"),left_on="signal_available_at",right_on="available_at",direction="backward")
        a=a.rename(columns={"context_timestamp":"d1_context_timestamp"}).drop(columns="available_at")
        a["m15_age_minutes"]=(a.signal_available_at-a.m15_context_timestamp-pd.to_timedelta(15,unit="min")).dt.total_seconds()/60
        a["d1_age_days"]=(a.signal_available_at-a.d1_context_timestamp-pd.to_timedelta(1,unit="D")).dt.total_seconds()/86400
        joined.append(a)
    result=pd.concat(joined,ignore_index=True).drop(columns=["signal_available_at","m15_context_timestamp","d1_context_timestamp"])
    return result.sort_values(["timestamp","symbol"])


def _walk_forward(data, feature_names, times, threshold=.55):
    """Expanding past-only fits followed by non-overlapping forward tests."""
    reports=[]
    for train_fraction,test_fraction in ((.55,.15),(.70,.15),(.85,.15)):
        train_end=times[int(len(times)*train_fraction)]; test_end=times[min(int(len(times)*(train_fraction+test_fraction)),len(times)-1)]
        tr=data[data.timestamp<train_end]; te=data[(data.timestamp>=train_end)&(data.timestamp<=test_end)]
        def prepared(frame):
            X=frame[feature_names].copy()
            for c in CATEGORICAL: X[c]=X[c].astype(str)
            for c in set(feature_names)-set(CATEGORICAL): X[c]=pd.to_numeric(X[c],errors="coerce").fillna(0)
            return X,frame.target
        Xtr,ytr=prepared(tr); Xte,yte=prepared(te)
        fold=CatBoostClassifier(iterations=400,depth=6,learning_rate=.03,loss_function="Logloss",eval_metric="AUC",auto_class_weights="Balanced",random_seed=42,verbose=False,allow_writing_files=False)
        fold.fit(Xtr,ytr,cat_features=CATEGORICAL); probabilities=fold.predict_proba(Xte)[:,1]; selected=probabilities>=threshold; precision=precision_score(yte,selected,zero_division=0)
        reports.append({"train_end":str(pd.Timestamp(train_end)),"test_end":str(pd.Timestamp(test_end)),"train_rows":len(tr),"test_rows":len(te),"roc_auc":roc_auc_score(yte,probabilities),"signals":int(selected.sum()),"precision":precision,"expected_r_multiple_before_costs":3*precision-1})
    return reports


def build_backfill_dataset(candles: pd.DataFrame, max_hold_bars=8, minimum_future_bars=2, candles_15min: pd.DataFrame | None=None, candles_daily: pd.DataFrame | None=None) -> pd.DataFrame:
    df=candles.copy(); df["timestamp"]=pd.to_datetime(df.timestamp,utc=True); enriched=pd.concat([_features(g) for _,g in df.groupby("symbol")]).sort_values(["timestamp","symbol"])
    if (candles_15min is None) != (candles_daily is None): raise ValueError("Both 15-minute and daily candles are required for multi-timeframe training")
    if candles_15min is not None:
        m15=candles_15min.copy(); daily=candles_daily.copy(); m15["timestamp"]=pd.to_datetime(m15.timestamp,utc=True); daily["timestamp"]=pd.to_datetime(daily.timestamp,utc=True)
        enriched=add_multitimeframe_context(enriched,m15,daily)
    outcomes=[]
    for _,g in enriched.groupby("symbol"):
        rows=g.reset_index(drop=True)
        for i,row in rows.iterrows():
            future=rows.iloc[i+1:i+1+max_hold_bars]; outcome=0; hit="timeout"
            if len(future)>=minimum_future_bars and pd.notna(row.stop_hint):
                for _,bar in future.iterrows():
                    stop=(bar.low<=row.stop_hint) if row.side_hint=="buy" else (bar.high>=row.stop_hint); target=(bar.high>=row.take_profit_hint) if row.side_hint=="buy" else (bar.low<=row.take_profit_hint)
                    if stop: outcome,hit=-1,"sl"; break
                    if target: outcome,hit=1,"tp"; break
            outcomes.append((row.name,g.index[i],outcome,hit))
    mapping={index:(outcome,hit) for _,index,outcome,hit in outcomes}; enriched["outcome"]=[mapping[i][0] for i in enriched.index]; enriched["hit_type"]=[mapping[i][1] for i in enriched.index]; enriched=enriched[enriched.outcome.isin([-1,1])].copy(); enriched["target"]=(enriched.outcome==1).astype(int)
    needed=[c for c in enriched.columns if c not in {"data_provider","trade_count","vwap_source"}]; return enriched.dropna(subset=[c for c in needed if c not in CATEGORICAL]).reset_index(drop=True)


def train_backfill_catboost(candles, artifact_dir: Path, registry_path: Path, model_id="catboost-h1-backfill-v1", candles_15min=None, candles_daily=None):
    data=build_backfill_dataset(candles,candles_15min=candles_15min,candles_daily=candles_daily); feature_names=[c for c in data.columns if c not in EXCLUDED and c not in {"data_provider"}]; times=np.array(sorted(data.timestamp.unique())); a,b=times[int(len(times)*.70)],times[int(len(times)*.85)]; train=data[data.timestamp<a]; valid=data[(data.timestamp>=a)&(data.timestamp<b)]; test=data[data.timestamp>=b]
    def xy(d):
        X=d[feature_names].copy()
        for c in CATEGORICAL: X[c]=X[c].astype(str)
        for c in set(feature_names)-set(CATEGORICAL): X[c]=pd.to_numeric(X[c],errors="coerce").fillna(0)
        return X,d.target
    Xtr,ytr=xy(train); Xv,yv=xy(valid); Xt,yt=xy(test); model=CatBoostClassifier(iterations=700,depth=6,learning_rate=.03,loss_function="Logloss",eval_metric="AUC",auto_class_weights="Balanced",random_seed=42,verbose=100,allow_writing_files=False); model.fit(Xtr,ytr,cat_features=CATEGORICAL,eval_set=(Xv,yv),use_best_model=True,early_stopping_rounds=75)
    pv=model.predict_proba(Xv)[:,1]; threshold_table={}
    for threshold in np.arange(.50,.81,.05):
        selected=pv>=threshold; precision=precision_score(yv,selected,zero_division=0); threshold_table[f"{threshold:.2f}"]={"signals":int(selected.sum()),"precision":precision,"expected_r_multiple":3*precision-1}
    eligible_thresholds=[(float(k),v) for k,v in threshold_table.items() if v["signals"]>=100]; selected_threshold=max(eligible_thresholds,key=lambda item:item[1]["expected_r_multiple"])[0] if eligible_thresholds else .60
    p=model.predict_proba(Xt)[:,1]; pred=p>=selected_threshold; precision=precision_score(yt,pred,zero_division=0); result={"log_loss":log_loss(yt,p,labels=[0,1]),"roc_auc":roc_auc_score(yt,p),"balanced_accuracy":balanced_accuracy_score(yt,pred),"selected_probability_threshold":selected_threshold,"precision":precision,"signals":int(pred.sum()),"expected_r_multiple_before_costs":3*precision-1,"wins":int(yt.sum()),"losses":int((yt==0).sum())}
    scored=test[["timestamp","symbol","side_hint","adx","atr_pct"]].copy(); scored["target"]=yt.to_numpy(); scored["selected"]=pred
    scored["year"]=scored.timestamp.dt.year; scored["regime"]=np.select([scored.adx>=25,scored.atr_pct>=scored.atr_pct.median()],["trend","high_vol"],default="range")
    diagnostics={}
    for dimension in ("symbol","side_hint","year","regime"):
        rows={}
        for key,g in scored.groupby(dimension):
            chosen=g[g.selected]; pr=float(chosen.target.mean()) if len(chosen) else 0.0; rows[str(key)]={"rows":len(g),"signals":len(chosen),"precision":pr,"expected_r_multiple_before_costs":3*pr-1 if len(chosen) else None}
        diagnostics[dimension]=rows
    result["diagnostics"]=diagnostics; walk_forward=_walk_forward(data,feature_names,times); stable_walk_forward=all(f["roc_auc"]>=.52 and f["expected_r_multiple_before_costs"]>0 and f["signals"]>=100 for f in walk_forward); eligible=result["roc_auc"]>=.55 and result["expected_r_multiple_before_costs"]>0 and result["signals"]>=100 and stable_walk_forward
    artifact_dir.mkdir(parents=True,exist_ok=True); path=artifact_dir/f"{model_id}.cbm"; model.save_model(path); checksum=hashlib.sha256(path.read_bytes()).hexdigest(); meta={"model_id":model_id,"model_type":"catboost_classifier","model_version":datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),"artifact":path.name,"sha256":checksum,"timeframe":"60Min","supported_symbols":sorted(data.symbol.unique().tolist()),"feature_names":feature_names,"preprocessing":{"categorical":CATEGORICAL,"numeric_missing":0},"probability_method":"predict_proba","class_labels":[0,1],"dependency_versions":{"catboost":importlib.metadata.version("catboost"),"pandas":importlib.metadata.version("pandas"),"numpy":importlib.metadata.version("numpy")},"training_metadata":{"method":"independent multi-timeframe adaptation of backfill features with conservative next-bar barrier labeling","context_timeframes":["15Min","1Day"] if candles_15min is not None else [],"context_availability":{"15Min":"bar timestamp + 15 minutes","1Day":"bar timestamp + 1 calendar day"},"max_hold_bars":8,"stop_atr_multiple":2,"reward_risk":2,"rows":len(data),"train_rows":len(train),"validation_rows":len(valid),"test_rows":len(test),"validation_threshold_table":threshold_table,"walk_forward_fixed_threshold":.55,"walk_forward_metrics":walk_forward,"stable_walk_forward":stable_walk_forward,"final_test_metrics":result,"production_eligible":eligible,"current_bar_excluded_from_label":True},"enabled":eligible}
    registry=json.loads(registry_path.read_text()); [x.update(enabled=False) for x in registry["models"] if x.get("timeframe")=="60Min"]; registry["models"]=[x for x in registry["models"] if x.get("model_id")!=model_id]+[meta]; registry_path.write_text(json.dumps(registry,indent=2)+"\n"); (artifact_dir/f"{model_id}.metadata.json").write_text(json.dumps(meta,indent=2)+"\n"); return meta
