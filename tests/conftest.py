import os
from pathlib import Path

os.environ.update({"APP_ENV": "test", "DATABASE_URL": "sqlite:////tmp/stock_decision_engine_tests.db", "WEBHOOK_PASSPHRASE": "test-secret",
                   "FINNHUB_API_KEY":"", "FINNHUB_FAIL_CLOSED":"false", "EXTERNAL_AI_REVIEW_ENABLED":"false",
                   "DEMO_SIGNALSTACK_ROUTING_ENABLED":"false", "DETERMINISTIC_BREAKOUT_DEMO_ENABLED":"false"})
Path("/tmp/stock_decision_engine_tests.db").unlink(missing_ok=True)

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as value: yield value


@pytest.fixture
def headers(): return {"x-webhook-passphrase": "test-secret"}


@pytest.fixture
def fresh_signal():
    from datetime import datetime, timezone
    return {"signal_id": "sig-base", "symbol": "AAPL", "timeframe": "60Min", "side_hint": "long", "strategy": "test", "signal_time_utc": datetime.now(timezone.utc).isoformat(), "current_price": 101, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000000, "indicators": {"atr": 2, "rsi": 55, "ema20": 101, "ema50": 100, "vol_ratio": 1.2}, "higher_timeframe_context": {"daily_regime": "bullish", "4hour_trend": "bullish", "15min_confirmation": "bullish"}}
