import json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.breakout_ml_shadow import evaluate_ml_shadow,load_ml_shadow,save_ml_shadow
from app.backtesting.strategies import build_strategy_frame

if __name__=="__main__":
    config,meta,model=load_ml_shadow(Path("model_artifacts/breakout_ml_shadow_config.json"),Path("model_artifacts/registry.json"),Path("model_artifacts/artifacts")); breakout=json.loads(Path("model_artifacts/breakout_shadow_config.json").read_text()); frame=build_strategy_frame(pd.read_csv("data/candles_60min.csv")); state=evaluate_ml_shadow(frame,breakout["atr_pct_low_volatility_cutoff_by_symbol"],config,meta,model); save_ml_shadow(state,Path("data/breakout_ml_shadow_state.json")); print(json.dumps(state,indent=2))
