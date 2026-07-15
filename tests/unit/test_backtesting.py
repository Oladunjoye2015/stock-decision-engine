import pandas as pd

from app.backtesting.engine import BacktestSettings, chronological_slice_metrics, run_strategy_backtest


def test_backtest_enters_next_bar_and_respects_position_cap():
    rows=[]
    for timestamp in pd.date_range("2025-01-01",periods=5,freq="h",tz="UTC"):
        for symbol in ("AAPL","MSFT"):
            rows.append({"timestamp":timestamp,"symbol":symbol,"open":100,"high":101,"low":99,"close":100,"atr":1,"signal_strength":1,"test_strategy":timestamp.hour==0})
    frame=pd.DataFrame(rows); result=run_strategy_backtest(frame,"test_strategy",BacktestSettings(max_positions=1,max_hold_bars=2,slippage_bps_each_side=0))
    trades=result["trades"]
    assert len(trades)==1 and trades.iloc[0].entry_time==pd.Timestamp("2025-01-01 01:00:00+00:00")
    assert result["equity"].open_positions.max()<=1


def test_stop_wins_when_stop_and_target_hit_same_bar():
    frame=pd.DataFrame({"timestamp":pd.date_range("2025-01-01",periods=3,freq="h",tz="UTC"),"symbol":"AAPL","open":100,"high":[100,105,100],"low":[100,95,100],"close":100,"atr":1,"signal_strength":1,"test_strategy":[True,False,False]})
    result=run_strategy_backtest(frame,"test_strategy",BacktestSettings(stop_atr=2,reward_risk=2,slippage_bps_each_side=0))
    assert result["trades"].iloc[0].exit_reason=="stop"


def test_sparse_symbol_timestamp_does_not_break_open_position():
    frame=pd.DataFrame([{"timestamp":"2025-01-01T00:00:00Z","symbol":"AAPL","open":100,"high":100,"low":100,"close":100,"atr":1,"signal_strength":1,"test_strategy":True},{"timestamp":"2025-01-01T01:00:00Z","symbol":"AAPL","open":100,"high":100,"low":100,"close":100,"atr":1,"signal_strength":1,"test_strategy":False},{"timestamp":"2025-01-01T02:00:00Z","symbol":"MSFT","open":100,"high":100,"low":100,"close":100,"atr":1,"signal_strength":1,"test_strategy":False}]); frame["timestamp"]=pd.to_datetime(frame.timestamp,utc=True)
    result=run_strategy_backtest(frame,"test_strategy",BacktestSettings(slippage_bps_each_side=0))
    assert len(result["trades"])==1


def test_chronological_slices_are_reported_separately():
    equity=pd.DataFrame({"timestamp":pd.date_range("2025-01-01",periods=4,freq="D",tz="UTC"),"equity":[100,110,105,120]}); trades=pd.DataFrame(columns=["exit_time","pnl"])
    result=chronological_slice_metrics(equity,trades,[equity.timestamp.iloc[0],equity.timestamp.iloc[2],equity.timestamp.iloc[3]])
    assert len(result)==2 and abs(result[0]["return"]-.05)<1e-9


def test_open_positions_can_remain_pending_at_shadow_data_end():
    frame=pd.DataFrame({"timestamp":pd.date_range("2025-01-01",periods=3,freq="h",tz="UTC"),"symbol":"AAPL","open":100,"high":100,"low":100,"close":100,"atr":1,"atr_pct":.01,"adx":25,"signal_strength":1,"test_strategy":[True,False,False]})
    result=run_strategy_backtest(frame,"test_strategy",BacktestSettings(force_close_end=False,slippage_bps_each_side=0))
    assert result["trades"].iloc[0].status=="open"


def test_entry_bracket_uses_signal_bar_atr_not_entry_bar_atr():
    frame=pd.DataFrame({"timestamp":pd.date_range("2025-01-01",periods=3,freq="h",tz="UTC"),"symbol":"AAPL","open":100,"high":100,"low":100,"close":100,"atr":[1,50,50],"atr_pct":.01,"adx":25,"signal_strength":1,"test_strategy":[True,False,False]})
    trade=run_strategy_backtest(frame,"test_strategy",BacktestSettings(force_close_end=False,stop_atr=2,slippage_bps_each_side=0))["trades"].iloc[0]
    assert trade.stop==98
