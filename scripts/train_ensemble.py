import argparse, json, sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.training import train_and_select


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train base classifiers and retain an ensemble only when chronological validation improves.")
    parser.add_argument("--input", type=Path, default=Path("data/candles_60min.csv")); parser.add_argument("--model-id", default="ensemble-h1-v1"); parser.add_argument("--cost-bps", type=float, default=10); parser.add_argument("--min-ensemble-improvement", type=float, default=.002)
    args = parser.parse_args()
    if not args.input.is_file(): parser.error(f"Candle dataset not found: {args.input}")
    metadata = train_and_select(pd.read_csv(args.input), Path("model_artifacts/artifacts"), Path("model_artifacts/registry.json"), args.model_id, args.min_ensemble_improvement, args.cost_bps)
    print(json.dumps(metadata["training_metadata"], indent=2))
