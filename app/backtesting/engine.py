from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestSettings:
    initial_cash: float=100_000
    max_positions: int=3
    risk_per_trade: float=.01
    stop_atr: float=2
    reward_risk: float=2
    max_hold_bars: int=16
    slippage_bps_each_side: float=5
    force_close_end: bool=True


def _metrics(equity, trades, initial_cash):
    if equity.empty: return {}
    curve=equity.equity; returns=curve.pct_change().fillna(0); drawdown=curve/curve.cummax()-1; closed=trades[trades.status=="closed"] if not trades.empty else trades
    pnl=closed["pnl"] if len(closed) and "pnl" in closed else pd.Series(dtype=float); wins=pnl[pnl>0]; losses=pnl[pnl<0]
    return {"initial_equity":initial_cash,"final_equity":float(curve.iloc[-1]),"total_return":float(curve.iloc[-1]/initial_cash-1),"maximum_drawdown":float(drawdown.min()),"annualized_sharpe":float(np.sqrt(252*7)*returns.mean()/returns.std()) if returns.std()>0 else 0.0,"closed_trades":len(closed),"win_rate":float((pnl>0).mean()) if len(pnl) else None,"mean_trade_return":float(closed.return_pct.mean()) if len(closed) else None,"profit_factor":float(wins.sum()/-losses.sum()) if len(losses) and losses.sum()!=0 else None}


def run_strategy_backtest(frame: pd.DataFrame, strategy: str, settings=BacktestSettings()):
    x=frame.sort_values(["timestamp","symbol"]).copy(); grouped=x.groupby("symbol"); x["entry_signal"]=grouped[strategy].shift(1,fill_value=False).astype(bool); x["signal_atr"]=grouped.atr.shift(1); x["entry_signal_strength"]=grouped.signal_strength.shift(1)
    for column in ("adx","atr_pct","vol_ratio","rsi","macd_hist","ret20","dist_vwap"):
        if column in x: x[f"signal_{column}"]=grouped[column].shift(1)
    cash=settings.initial_cash; positions={}; trades=[]; equity_rows=[]; bars_held={}; slip=settings.slippage_bps_each_side/10000
    for timestamp,bars in x.groupby("timestamp",sort=True):
        by_symbol={row.symbol:row for _,row in bars.iterrows()}
        for symbol in list(positions):
            if symbol not in by_symbol: continue
            row=by_symbol[symbol]; position=positions[symbol]; bars_held[symbol]+=1; raw_exit=None; reason=None
            if row.low<=position["stop"]: raw_exit,reason=position["stop"],"stop"
            elif row.high>=position["target"]: raw_exit,reason=position["target"],"target"
            elif bars_held[symbol]>=settings.max_hold_bars: raw_exit,reason=row.close,"timeout"
            if raw_exit is not None:
                exit_price=raw_exit*(1-slip); cash+=position["quantity"]*exit_price; pnl=position["quantity"]*(exit_price-position["entry_price"]); trades[position["trade_index"]].update(status="closed",exit_time=timestamp,exit_price=exit_price,exit_reason=reason,pnl=pnl,return_pct=exit_price/position["entry_price"]-1,bars_held=bars_held[symbol]); del positions[symbol]; del bars_held[symbol]
        candidates=bars[bars.entry_signal&~bars.symbol.isin(positions)].sort_values("entry_signal_strength",ascending=False)
        for _,row in candidates.iterrows():
            if len(positions)>=settings.max_positions: break
            entry=row.open*(1+slip); risk_per_share=settings.stop_atr*row.signal_atr
            if not np.isfinite(risk_per_share) or risk_per_share<=0: continue
            marked_equity=cash+sum(p["quantity"]*by_symbol[s].close for s,p in positions.items() if s in by_symbol); quantity=min(marked_equity*settings.risk_per_trade/risk_per_share,marked_equity/settings.max_positions/entry,cash/entry)
            if quantity<=0: continue
            local_time=pd.Timestamp(timestamp).tz_convert("America/New_York"); trade={"strategy":strategy,"symbol":row.symbol,"entry_time":timestamp,"entry_year":local_time.year,"entry_hour_ny":local_time.hour,"entry_session":"morning" if local_time.hour<12 else "afternoon","entry_adx":float(row.signal_adx) if "signal_adx" in row else None,"entry_atr_pct":float(row.signal_atr_pct) if "signal_atr_pct" in row else None,"entry_price":entry,"quantity":quantity,"stop":entry-risk_per_share,"target":entry+risk_per_share*settings.reward_risk,"status":"open","signal_timestamp":row.timestamp-pd.to_timedelta(1,unit="h")}; cash-=quantity*entry; trades.append(trade); positions[row.symbol]={**trade,"trade_index":len(trades)-1}; bars_held[row.symbol]=0
        # Next-open entries may hit a bracket in their entry bar. If OHLC shows
        # both barriers, intrabar order is unknowable and the stop wins.
        for symbol in [s for s in positions if bars_held[s]==0 and s in by_symbol]:
            row=by_symbol[symbol]; position=positions[symbol]; raw_exit=None; reason=None
            if row.low<=position["stop"]: raw_exit,reason=position["stop"],"stop"
            elif row.high>=position["target"]: raw_exit,reason=position["target"],"target"
            if raw_exit is not None:
                exit_price=raw_exit*(1-slip); cash+=position["quantity"]*exit_price; pnl=position["quantity"]*(exit_price-position["entry_price"]); trades[position["trade_index"]].update(status="closed",exit_time=timestamp,exit_price=exit_price,exit_reason=reason,pnl=pnl,return_pct=exit_price/position["entry_price"]-1,bars_held=0); del positions[symbol]; del bars_held[symbol]
        marked=cash+sum(p["quantity"]*(by_symbol[s].close if s in by_symbol else p["entry_price"]) for s,p in positions.items()); equity_rows.append({"timestamp":timestamp,"equity":marked,"cash":cash,"open_positions":len(positions)})
    if len(equity_rows) and settings.force_close_end:
        timestamp=equity_rows[-1]["timestamp"]
        last=x.groupby("symbol").tail(1).set_index("symbol")
        for symbol,position in list(positions.items()):
            raw=float(last.loc[symbol].close); exit_price=raw*(1-slip); cash+=position["quantity"]*exit_price; pnl=position["quantity"]*(exit_price-position["entry_price"]); trades[position["trade_index"]].update(status="closed",exit_time=timestamp,exit_price=exit_price,exit_reason="end_of_data",pnl=pnl,return_pct=exit_price/position["entry_price"]-1,bars_held=bars_held[symbol])
        equity_rows[-1]["equity"]=cash; equity_rows[-1]["cash"]=cash; equity_rows[-1]["open_positions"]=0
    equity=pd.DataFrame(equity_rows); trade_frame=pd.DataFrame(trades); return {"metrics":_metrics(equity,trade_frame,settings.initial_cash),"equity":equity,"trades":trade_frame}


def equal_weight_buy_hold(frame, initial_cash):
    returns=[]
    for _,g in frame.groupby("symbol"):
        g=g.sort_values("timestamp"); returns.append(g.close.iloc[-1]/g.open.iloc[0]-1)
    return float(np.mean(returns)) if returns else 0.0


def chronological_slice_metrics(equity: pd.DataFrame, trades: pd.DataFrame, boundaries):
    reports=[]
    for start,end in zip(boundaries[:-1],boundaries[1:]):
        curve=equity[(equity.timestamp>=start)&(equity.timestamp<=end)].copy(); closed=trades[(trades.exit_time>=start)&(trades.exit_time<=end)] if len(trades) else trades
        if curve.empty: continue
        normalized=curve.equity/curve.equity.iloc[0]; drawdown=normalized/normalized.cummax()-1; pnl=closed.pnl if len(closed) else pd.Series(dtype=float)
        reports.append({"start":str(pd.Timestamp(start)),"end":str(pd.Timestamp(end)),"return":float(normalized.iloc[-1]-1),"maximum_drawdown":float(drawdown.min()),"closed_trades":len(closed),"win_rate":float((pnl>0).mean()) if len(pnl) else None,"profit_factor":float(pnl[pnl>0].sum()/-pnl[pnl<0].sum()) if (pnl<0).any() else None})
    return reports
