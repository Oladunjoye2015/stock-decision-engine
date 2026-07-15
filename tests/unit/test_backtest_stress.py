import pandas as pd

from app.backtesting.stress import add_breakout_stress_variants


def test_time_restrictions_use_next_entry_bar_in_new_york():
    times=pd.date_range("2025-06-02 13:30",periods=60,freq="h",tz="UTC"); frame=pd.DataFrame({"timestamp":times,"symbol":"AAPL","high":99,"close":100,"vol_ratio":2,"adx":30})
    result=add_breakout_stress_variants(frame)
    assert result.breakout_morning.any() and result.breakout_afternoon.any()
    assert not (result.breakout_morning&result.breakout_afternoon).any()
