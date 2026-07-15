import pandas as pd

from app.backtesting.engine import BacktestSettings, chronological_slice_metrics, run_strategy_backtest


def add_breakout_stress_variants(frame: pd.DataFrame) -> pd.DataFrame:
    x=frame.copy(); grouped=x.groupby("symbol",group_keys=False)
    for lookback in (15,20,30): x[f"prior_high_{lookback}"]=grouped.high.transform(lambda s,n=lookback:s.shift(1).rolling(n).max())
    local=x.timestamp.dt.tz_convert("America/New_York"); next_local=grouped.timestamp.shift(-1).dt.tz_convert("America/New_York"); regular_entry=next_local.dt.hour.between(9,15)
    definitions={
        "breakout_base":(20,1.2,20),"breakout_lookback15":(15,1.2,20),"breakout_lookback30":(30,1.2,20),
        "breakout_volume10":(20,1.0,20),"breakout_volume14":(20,1.4,20),"breakout_adx15":(20,1.2,15),"breakout_adx25":(20,1.2,25),
    }
    for name,(lookback,volume,adx) in definitions.items(): x[name]=(x.close>x[f"prior_high_{lookback}"])&(x.vol_ratio>=volume)&(x.adx>=adx)&regular_entry
    base=x.breakout_base; x["breakout_morning"]=base&(next_local.dt.hour<12); x["breakout_afternoon"]=base&(next_local.dt.hour>=12)
    return x


def grouped_trade_metrics(trades: pd.DataFrame, column: str):
    result={}
    for key,g in trades.groupby(column,observed=True):
        wins=g.pnl[g.pnl>0]; losses=g.pnl[g.pnl<0]
        result[str(key)]={"trades":len(g),"win_rate":float((g.pnl>0).mean()),"mean_trade_return":float(g.return_pct.mean()),"net_pnl":float(g.pnl.sum()),"profit_factor":float(wins.sum()/-losses.sum()) if len(losses) else None}
    return result


def stress_result(frame, strategy, settings, boundaries):
    run=run_strategy_backtest(frame,strategy,settings); trades=run["trades"]; trades["volatility_regime"]=pd.qcut(trades.entry_atr_pct,3,labels=["low","medium","high"],duplicates="drop") if len(trades) else None
    return {**run["metrics"],"chronological_slices":chronological_slice_metrics(run["equity"],trades,boundaries),"by_symbol":grouped_trade_metrics(trades,"symbol"),"by_year":grouped_trade_metrics(trades,"entry_year"),"by_session":grouped_trade_metrics(trades,"entry_session"),"by_volatility_regime":grouped_trade_metrics(trades,"volatility_regime")}
