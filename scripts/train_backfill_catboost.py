import argparse,json,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models.backfill_training import train_backfill_catboost

if __name__=="__main__":
    p=argparse.ArgumentParser(description="Train CatBoost with 1-hour labels plus completed 15-minute/daily context."); p.add_argument("--input",type=Path,default=Path("data/candles_60min.csv")); p.add_argument("--input-15min",type=Path,default=Path("data/candles_15min.csv")); p.add_argument("--input-daily",type=Path,default=Path("data/candles_1day.csv")); p.add_argument("--model-id",default="catboost-h1-mtf-backfill-v2"); a=p.parse_args(); print(json.dumps(train_backfill_catboost(pd.read_csv(a.input),Path("model_artifacts/artifacts"),Path("model_artifacts/registry.json"),a.model_id,pd.read_csv(a.input_15min),pd.read_csv(a.input_daily))["training_metadata"],indent=2))
