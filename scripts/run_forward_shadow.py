import argparse, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.forward_shadow import evaluate_forward_shadow, load_shadow_config, save_shadow_state
from app.models.label_study import build_study_frame


if __name__ == "__main__":
    p=argparse.ArgumentParser(description="Evaluate the frozen candidate on candles strictly newer than its freeze boundary; never sends orders."); p.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); p.add_argument("--input-15min",type=Path,default=Path("data/candles_15min.csv")); p.add_argument("--input-daily",type=Path,default=Path("data/candles_1day.csv")); p.add_argument("--config",type=Path,default=Path("model_artifacts/forward_shadow_config.json")); p.add_argument("--state",type=Path,default=Path("data/forward_shadow_state.json")); a=p.parse_args()
    config,checksum=load_shadow_config(a.config); frame=build_study_frame(pd.read_csv(a.input),pd.read_csv(a.input_15min),pd.read_csv(a.input_daily)); state=evaluate_forward_shadow(frame,config,checksum); save_shadow_state(state,a.state); print(json.dumps({k:state[k] for k in ("candidate_id","last_candle_timestamp","completed_trades","pending_signals","minimum_sample_reached","promotion_blocked","metrics")},indent=2))
