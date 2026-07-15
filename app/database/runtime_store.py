from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database.engine import SessionLocal, engine, init_database
from app.database.models import MarketCandle, RuntimeState


def _as_utc_datetime(value) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC").to_pydatetime()


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def load_candles(timeframe: str) -> pd.DataFrame:
    init_database()
    with SessionLocal() as db:
        rows = db.execute(
            select(MarketCandle)
            .where(MarketCandle.timeframe == timeframe)
            .order_by(MarketCandle.timestamp_utc, MarketCandle.symbol)
        ).scalars().all()
    return pd.DataFrame(
        [{"timestamp": row.timestamp_utc, "symbol": row.symbol, "data_provider": row.data_provider,
          "open": row.open, "high": row.high, "low": row.low, "close": row.close, "volume": row.volume}
         for row in rows],
        columns=["timestamp", "symbol", "data_provider", "open", "high", "low", "close", "volume"],
    )


def load_recent_candles(timeframe: str, symbol: str, limit: int = 250) -> pd.DataFrame:
    init_database()
    statement = (select(MarketCandle).where(MarketCandle.timeframe == timeframe, MarketCandle.symbol == symbol)
                 .order_by(MarketCandle.timestamp_utc.desc()).limit(limit))
    with SessionLocal() as db:
        rows = list(reversed(db.execute(statement).scalars().all()))
    return pd.DataFrame(
        [{"timestamp": row.timestamp_utc, "symbol": row.symbol, "data_provider": row.data_provider,
          "open": row.open, "high": row.high, "low": row.low, "close": row.close, "volume": row.volume}
         for row in rows],
        columns=["timestamp", "symbol", "data_provider", "open", "high", "low", "close", "volume"],
    )


def upsert_candles(frame: pd.DataFrame, timeframe: str, chunk_size: int = 5000) -> int:
    if frame.empty:
        return 0
    init_database()
    records = [
        {"symbol": str(row.symbol), "timeframe": timeframe, "timestamp_utc": _as_utc_datetime(row.timestamp),
         "data_provider": str(row.data_provider), "open": float(row.open), "high": float(row.high),
         "low": float(row.low), "close": float(row.close), "volume": float(row.volume)}
        for row in frame.itertuples(index=False)
    ]
    dialect = engine.dialect.name
    insert_factory = postgres_insert if dialect == "postgresql" else sqlite_insert
    with SessionLocal.begin() as db:
        for offset in range(0, len(records), chunk_size):
            statement = insert_factory(MarketCandle).values(records[offset:offset + chunk_size])
            excluded = statement.excluded
            statement = statement.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "timestamp_utc"],
                set_={"data_provider": excluded.data_provider, "open": excluded.open, "high": excluded.high,
                      "low": excluded.low, "close": excluded.close, "volume": excluded.volume},
            )
            db.execute(statement)
    return len(records)


def save_runtime_state(key: str, payload: dict[str, Any]) -> None:
    init_database()
    insert_factory = postgres_insert if engine.dialect.name == "postgresql" else sqlite_insert
    statement = insert_factory(RuntimeState).values(
        key=key, payload=_json_safe(payload), updated_at_utc=datetime.now(timezone.utc)
    )
    statement = statement.on_conflict_do_update(
        index_elements=["key"],
        set_={"payload": statement.excluded.payload, "updated_at_utc": statement.excluded.updated_at_utc},
    )
    with SessionLocal.begin() as db:
        db.execute(statement)


def load_runtime_state(key: str) -> dict[str, Any] | None:
    init_database()
    with SessionLocal() as db:
        row = db.get(RuntimeState, key)
        return dict(row.payload) if row else None
