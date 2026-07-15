import argparse
from pathlib import Path

import pandas as pd


ALIASES = {
    "time": "timestamp", "datetime": "timestamp", "date": "timestamp", "t": "timestamp",
    "ticker": "symbol", "s": "symbol", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume",
}


def normalize_export(source: Path, output: Path, default_symbol: str | None = None) -> pd.DataFrame:
    frame = pd.read_csv(source); frame.columns = [ALIASES.get(str(name).strip().lower(), str(name).strip().lower()) for name in frame.columns]
    if "symbol" not in frame:
        if not default_symbol: raise ValueError("Export has no symbol column; pass --symbol for a single-symbol file")
        frame["symbol"] = default_symbol.upper()
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}; missing = required-set(frame)
    if missing: raise ValueError(f"Export is missing columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"): frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=list(required)).drop_duplicates(["symbol", "timestamp"]).sort_values(["timestamp", "symbol"])
    valid = (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)) & (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)) & (frame[["open", "high", "low", "close", "volume"]] >= 0).all(axis=1)
    frame = frame.loc[valid, ["timestamp", "symbol", "open", "high", "low", "close", "volume"]]
    if frame.empty: raise ValueError("No valid candles remain after validation")
    frame.insert(2, "data_provider", "user_supplied_alpaca_export")
    output.parent.mkdir(parents=True, exist_ok=True); frame.to_csv(output, index=False)
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a user-supplied candle CSV without connecting to Alpaca.")
    parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, default=Path("data/candles_60min.csv")); parser.add_argument("--symbol")
    args = parser.parse_args(); result = normalize_export(args.input, args.output, args.symbol); print(f"imported {len(result)} validated candles for {result.symbol.nunique()} symbols into {args.output}")
