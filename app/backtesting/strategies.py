import numpy as np
import pandas as pd

from app.models.backfill_training import _features


STRATEGIES=("sma_trend","momentum","breakout","pullback")


def build_strategy_frame(candles: pd.DataFrame) -> pd.DataFrame:
    data=candles.copy(); data["timestamp"]=pd.to_datetime(data.timestamp,utc=True); parts=[]
    for _,group in data.groupby("symbol"):
        x=_features(group).sort_values("timestamp"); x["prior_high20"]=x.high.shift(1).rolling(20).max(); x["ret20"]=x.close.pct_change(20)
        x["sma20"]=x.close.rolling(20).mean(); x["sma50"]=x.close.rolling(50).mean(); x["sma200"]=x.close.rolling(200).mean()
        x["sma_trend"]=(x.sma20>x.sma50)&(x.sma20.shift(1)<=x.sma50.shift(1))&(x.close>x.sma200)
        x["momentum"]=(x.ret20>.04)&x.rsi.between(50,70)&(x.macd_hist>0)&(x.vol_ratio>=1)
        x["breakout"]=(x.close>x.prior_high20)&(x.vol_ratio>=1.2)&(x.adx>=20)
        x["pullback"]=(x.ema20>x.ema50)&(x.ema50>x.ema200)&(x.low<=x.ema20)&(x.close>x.ema20)&x.rsi.between(45,65)
        x["signal_strength"]=np.maximum.reduce([x.ret20.fillna(0).to_numpy(),(x.vol_ratio.fillna(0)-1).to_numpy(),(x.adx.fillna(0)/100).to_numpy()])
        parts.append(x)
    return pd.concat(parts,ignore_index=True).sort_values(["timestamp","symbol"])
