import argparse, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.backtesting.engine import BacktestSettings, chronological_slice_metrics, equal_weight_buy_hold, run_strategy_backtest
from app.backtesting.strategies import STRATEGIES, build_strategy_frame


if __name__=="__main__":
    p=argparse.ArgumentParser(description="Backtest deterministic strategies against an explicit local candle dataset."); p.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); p.add_argument("--strategies",default=",".join(STRATEGIES)); p.add_argument("--initial-cash",type=float,default=100000); p.add_argument("--output",type=Path,default=Path("model_artifacts/backtest_deterministic_baselines.json")); a=p.parse_args()
    frame=build_strategy_frame(pd.read_csv(a.input)); settings=BacktestSettings(initial_cash=a.initial_cash); times=sorted(frame.timestamp.unique()); boundaries=[times[0],times[len(times)//4],times[len(times)//2],times[(3*len(times))//4],times[-1]]; report={"methodology":{"entry":"next hourly bar open","same_bar_tie":"stop first","position_sizing":"1% equity risk capped at one-third equity and 3 concurrent positions","exit":"2 ATR stop, 2R target, or 16 bars","slippage_bps_each_side":settings.slippage_bps_each_side,"chronological_slices":"four fixed equal-timestamp periods; strategy rules are unchanged"},"dataset":{"rows":len(frame),"symbols":sorted(frame.symbol.unique().tolist()),"start":str(frame.timestamp.min()),"end":str(frame.timestamp.max())},"equal_weight_buy_hold_return":equal_weight_buy_hold(frame,a.initial_cash),"strategies":{}}
    output_dir=Path("data/backtests"); output_dir.mkdir(parents=True,exist_ok=True)
    for strategy in [s.strip() for s in a.strategies.split(",") if s.strip()]:
        if strategy not in STRATEGIES: raise ValueError(f"Unknown strategy: {strategy}")
        result=run_strategy_backtest(frame,strategy,settings); report["strategies"][strategy]={**result["metrics"],"chronological_slices":chronological_slice_metrics(result["equity"],result["trades"],boundaries)}; result["trades"].to_csv(output_dir/f"{strategy}_trades.csv",index=False); result["equity"].to_csv(output_dir/f"{strategy}_equity.csv",index=False)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps(report,indent=2))
