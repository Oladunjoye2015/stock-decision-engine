import argparse, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.label_study import build_study_frame, run_label_study, save_study


if __name__ == "__main__":
    p=argparse.ArgumentParser(description="Study backfill stop, reward and holding configurations before model training."); p.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); p.add_argument("--input-15min",type=Path,default=Path("data/candles_15min.csv")); p.add_argument("--input-daily",type=Path,default=Path("data/candles_1day.csv")); p.add_argument("--cost-bps",type=float,default=10); p.add_argument("--output",type=Path,default=Path("model_artifacts/label_configuration_study.json")); a=p.parse_args()
    frame=build_study_frame(pd.read_csv(a.input),pd.read_csv(a.input_15min),pd.read_csv(a.input_daily)); result=run_label_study(frame,cost_bps=a.cost_bps); save_study(result,a.output)
    print(json.dumps({"selected_configuration":result["selected_configuration"],"selected_final_test":result["selected_final_test"],"candidate_count":len(result["candidates"])},indent=2))
