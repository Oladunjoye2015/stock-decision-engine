from datetime import datetime,timezone

import pandas as pd

import app.analysis.server_market_context as context
from app.config import Settings
from app.schemas.signals import SignalIn


def test_scanner_confirmed_bar_replaces_alpaca_bar_at_its_start(monkeypatch):
    timestamps=pd.date_range("2026-07-08T03:00:00Z",periods=60,freq="h")
    frame=pd.DataFrame({"timestamp":timestamps,"symbol":"AAPL","data_provider":"alpaca_market_data_api",
                        "open":100.0,"high":101.0,"low":99.0,"close":100.0,"volume":1000.0})
    frame.loc[frame.index[-1],"timestamp"]=pd.Timestamp("2026-07-16T14:00:00Z")
    class Client:
        def __init__(self,settings): pass
        def recent_hourly(self,symbol,end): return frame.copy()
    monkeypatch.setattr(context,"AlpacaCandleClient",Client)
    monkeypatch.setattr(context,"upsert_candles",lambda value,timeframe:len(value))
    signal=SignalIn(signal_id="scanner-alignment",symbol="AAPL",timeframe="60Min",side_hint="long",strategy="breakout-medium-high-vol-shadow-v1",
        signal_time_utc=datetime(2026,7,16,15,tzinfo=timezone.utc),current_price=103,open=100,high=104,low=99,close=103,volume=2000,
        external_metadata={"source":"railway_hourly_scanner","bar_confirmed":True,"bar_start_utc":"2026-07-16T14:00:00Z"})
    result=context._frame_with_signal(signal,"AAPL",Settings())
    assert len(result)==len(frame)
    assert result.iloc[-1].timestamp==pd.Timestamp("2026-07-16T14:00:00Z")
    assert result.iloc[-1].close==103 and result.iloc[-1].data_provider=="railway_hourly_scanner_confirmed_bar"
