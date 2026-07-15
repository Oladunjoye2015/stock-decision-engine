import pandas as pd
import httpx

from scripts.refresh_alpaca_candles import load_env,merge_bars,validate_bars
from app.config import Settings
from app.market_data.alpaca_candles import AlpacaCandleClient


def test_alpaca_refresh_validates_regular_hours_and_merges_overlap():
    raw=pd.DataFrame({"timestamp":["2026-07-15T13:00:00Z","2026-07-15T14:00:00Z"],"symbol":"AAPL","open":100,"high":102,"low":99,"close":101,"volume":1000}); valid=validate_bars(raw,True)
    assert len(valid)==1 and valid.iloc[0].data_provider=="alpaca_market_data_api"
    old=valid.copy(); old.loc[:,"close"]=100; merged=merge_bars(old,valid)
    assert len(merged)==1 and merged.iloc[0].close==101


def test_env_file_fills_empty_inherited_value_without_replacing_nonempty(tmp_path,monkeypatch):
    path=tmp_path/".env"; path.write_text("A=from_file\nB=from_file\n"); monkeypatch.setenv("A",""); monkeypatch.setenv("B","shell")
    load_env(path)
    import os
    assert os.environ["A"]=="from_file" and os.environ["B"]=="shell"


def test_runtime_alpaca_client_is_market_data_only_and_normalizes_bars():
    def handler(request):
        assert request.url.path=="/v2/stocks/AAPL/bars"
        assert request.headers["apca-api-key-id"]=="key"
        return httpx.Response(200,json={"bars":[{"t":"2026-07-15T14:30:00Z","o":100,"h":102,"l":99,"c":101,"v":1000}],"next_page_token":None})
    settings=Settings(alpaca_api_key="key",alpaca_api_secret="secret")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        frame=AlpacaCandleClient(settings,client).recent_hourly("AAPL",pd.Timestamp("2026-07-15T16:00:00Z"))
    assert len(frame)==1 and frame.iloc[0].data_provider=="alpaca_market_data_api"
