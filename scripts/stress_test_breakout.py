import json,sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.backtesting.engine import BacktestSettings
from app.backtesting.strategies import build_strategy_frame
from app.backtesting.stress import add_breakout_stress_variants, stress_result


if __name__=="__main__":
    frame=add_breakout_stress_variants(build_strategy_frame(pd.read_csv("data/candles_60min.csv"))); times=sorted(frame.timestamp.unique()); boundaries=[times[0],times[len(times)//4],times[len(times)//2],times[3*len(times)//4],times[-1]]
    strategies=["breakout_base","breakout_morning","breakout_afternoon","breakout_lookback15","breakout_lookback30","breakout_volume10","breakout_volume14","breakout_adx15","breakout_adx25"]
    report={"time_definition":"morning entry before 12:00 America/New_York; afternoon entry at or after 12:00; all entries restricted to hours 09-15","selection_warning":"All results are research sensitivity checks on seen history and cannot promote a strategy.","variants":{}}
    for strategy in strategies: report["variants"][strategy]=stress_result(frame,strategy,BacktestSettings(),boundaries)
    report["higher_slippage"]={"10_bps_each_side":stress_result(frame,"breakout_base",BacktestSettings(slippage_bps_each_side=10),boundaries),"15_bps_each_side":stress_result(frame,"breakout_base",BacktestSettings(slippage_bps_each_side=15),boundaries)}
    output=Path("model_artifacts/breakout_stress_test.json"); output.write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps({"time_comparison":{k:{m:report["variants"][k][m] for m in ("total_return","maximum_drawdown","closed_trades","profit_factor")} for k in ("breakout_morning","breakout_afternoon")},"parameter_returns":{k:v["total_return"] for k,v in report["variants"].items()},"higher_slippage_returns":{k:v["total_return"] for k,v in report["higher_slippage"].items()}},indent=2))
