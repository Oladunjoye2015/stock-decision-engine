import argparse, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.label_study import build_study_frame
from app.models.trigger_study import run_trigger_study, save_trigger_study


if __name__ == "__main__":
    p=argparse.ArgumentParser(description="Study sparse long and short entry triggers separately."); p.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); p.add_argument("--input-15min",type=Path,default=Path("data/candles_15min.csv")); p.add_argument("--input-daily",type=Path,default=Path("data/candles_1day.csv")); p.add_argument("--output",type=Path,default=Path("model_artifacts/direction_trigger_study.json")); a=p.parse_args()
    frame=build_study_frame(pd.read_csv(a.input),pd.read_csv(a.input_15min),pd.read_csv(a.input_daily)); result=run_trigger_study(frame); save_trigger_study(result,a.output); print(json.dumps({"selected_triggers":result["selected_triggers"],"combined_later_seen_period_exploratory":result["combined_later_seen_period_exploratory"]},indent=2))
