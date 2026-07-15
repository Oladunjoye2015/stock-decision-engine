import json,sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.backtesting.breakout_shadow import evaluate_breakout_shadow,load_breakout_shadow_config,save_breakout_shadow_state
from app.backtesting.strategies import build_strategy_frame


if __name__=="__main__":
    config,checksum=load_breakout_shadow_config(Path("model_artifacts/breakout_shadow_config.json")); frame=build_strategy_frame(pd.read_csv("data/candles_60min.csv")); state=evaluate_breakout_shadow(frame,config,checksum); save_breakout_shadow_state(state,Path("data/breakout_shadow_state.json")); print(json.dumps({k:state[k] for k in ("candidate_id","last_candle_timestamp","completed_trades","pending_trades","minimum_sample_reached","profit_factor_gate_reached","promotion_blocked","metrics","completed_by_entry_session")},indent=2))
