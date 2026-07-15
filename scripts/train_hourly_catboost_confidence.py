import json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.backtesting.strategies import build_strategy_frame
from app.models.breakout_confidence import HOURLY_FEATURES,build_breakout_candidates,train_confidence_gate

if __name__=="__main__":
    config=json.loads(Path("model_artifacts/breakout_shadow_config.json").read_text()); frame=build_strategy_frame(pd.read_csv("data/candles_60min.csv")); candidates=build_breakout_candidates(frame,config["atr_pct_low_volatility_cutoff_by_symbol"]); meta=train_confidence_gate(candidates,Path("model_artifacts/artifacts"),Path("model_artifacts/registry.json"),model_id="breakout-hourly-catboost-v1",raw_features=HOURLY_FEATURES,model_names=["catboost"]); print(json.dumps(meta["training_metadata"],indent=2))
