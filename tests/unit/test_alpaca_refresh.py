import pandas as pd

from scripts.refresh_alpaca_candles import load_env,merge_bars,validate_bars


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
