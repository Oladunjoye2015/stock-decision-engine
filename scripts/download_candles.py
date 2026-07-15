import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.market_data.finnhub import FinnhubClient, FinnhubError


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def month_windows(start: datetime, end: datetime):
    cursor = start
    while cursor < end:
        window_end = min(cursor + timedelta(days=30) - timedelta(seconds=1), end)
        yield cursor, window_end
        cursor = window_end + timedelta(seconds=1)


def validate_frame(frame: pd.DataFrame, symbol: str, provider: str = "finnhub") -> pd.DataFrame:
    if frame.empty: raise RuntimeError(f"No candles returned for {symbol}")
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp")
    numeric = ["open", "high", "low", "close", "volume"]
    frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["timestamp", *numeric])
    valid = (frame["high"] >= frame[["open", "close", "low"]].max(axis=1)) & (frame["low"] <= frame[["open", "close", "high"]].min(axis=1)) & (frame[numeric] >= 0).all(axis=1)
    frame = frame.loc[valid]
    if frame.empty: raise RuntimeError(f"All returned candles failed OHLCV validation for {symbol}")
    frame["symbol"] = symbol
    frame["data_provider"] = provider
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="s", utc=True)
    return frame[["timestamp", "symbol", "data_provider", *numeric]]


def download(symbols: list[str], start: datetime, end: datetime, output: Path, resolution: str = "60") -> pd.DataFrame:
    settings = get_settings(); client = FinnhubClient(settings.finnhub_api_key, settings.finnhub_base_url, settings.finnhub_timeout_seconds); frames = []
    try:
        for symbol in symbols:
            rows = []
            for window_start, window_end in month_windows(start, end):
                rows.extend(client.stock_candles(symbol, resolution, int(window_start.timestamp()), int(window_end.timestamp())))
            frames.append(validate_frame(pd.DataFrame(rows), symbol))
    finally: client.close()
    combined = pd.concat(frames, ignore_index=True).sort_values(["timestamp", "symbol"])
    output.parent.mkdir(parents=True, exist_ok=True); combined.to_csv(output, index=False)
    return combined


def main():
    parser = argparse.ArgumentParser(description="Download independent Finnhub OHLCV candles (premium Stock Candles access required).")
    parser.add_argument("--symbols", required=True, help="Comma-separated US stock symbols")
    parser.add_argument("--start", required=True, help="UTC ISO date/time")
    parser.add_argument("--end", default=datetime.now(timezone.utc).isoformat(), help="UTC ISO date/time")
    parser.add_argument("--resolution", default="60", choices=["1", "5", "15", "30", "60", "D"])
    parser.add_argument("--output", type=Path, default=Path("data/candles_60min.csv"))
    args = parser.parse_args(); symbols = sorted({x.strip().upper() for x in args.symbols.split(",") if x.strip()})
    if not symbols: parser.error("At least one symbol is required")
    try: frame = download(symbols, parse_utc(args.start), parse_utc(args.end), args.output, args.resolution)
    except FinnhubError as exc: raise SystemExit(f"Finnhub download failed: {exc}") from exc
    print(f"wrote {len(frame)} validated candles for {len(symbols)} symbols to {args.output}")


if __name__ == "__main__": main()
