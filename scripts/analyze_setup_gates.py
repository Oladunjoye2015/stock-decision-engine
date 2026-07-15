import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.backfill_training import build_backfill_dataset, evaluate_setup_gates


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Select deterministic setup gates without consulting the final period.")
    parser.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); parser.add_argument("--input-15min",type=Path,default=Path("data/candles_15min.csv")); parser.add_argument("--input-daily",type=Path,default=Path("data/candles_1day.csv")); parser.add_argument("--output",type=Path,default=Path("model_artifacts/setup_gate_analysis.json")); args=parser.parse_args()
    data=build_backfill_dataset(pd.read_csv(args.input),candles_15min=pd.read_csv(args.input_15min),candles_daily=pd.read_csv(args.input_daily)); times=np.array(sorted(data.timestamp.unique())); train_end=times[int(len(times)*.70)]; validation_end=times[int(len(times)*.85)]
    selected,report=evaluate_setup_gates(data,train_end,validation_end); result={"selection_rule":"positive 2:1 expected R and >=300 resolved rows in both train and validation; maximize validation expected R","train_end":str(pd.Timestamp(train_end)),"validation_end":str(pd.Timestamp(validation_end)),"selected_gate":selected,"gates":report}
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+"\n"); print(json.dumps(result,indent=2))
