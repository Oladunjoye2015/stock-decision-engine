import json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.breakout_confidence import build_breakout_candidates,train_confidence_gate
from app.models.label_study import build_study_frame

if __name__=="__main__":
    config=json.loads(Path("model_artifacts/breakout_shadow_config.json").read_text()); frame=build_study_frame(pd.read_csv("data/candles_60min.csv"),pd.read_csv("data/candles_15min.csv"),pd.read_csv("data/candles_1day.csv")); candidates=build_breakout_candidates(frame,config["atr_pct_low_volatility_cutoff_by_symbol"]); meta=train_confidence_gate(candidates,Path("model_artifacts/artifacts"),Path("model_artifacts/registry.json")); print(json.dumps(meta["training_metadata"],indent=2))
