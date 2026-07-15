import pandas as pd
from app.models.breakout_confidence import HOURLY_FEATURES,performance,prepare_breakout_feature_frame

def test_confidence_performance_counts_only_selected_returns():
    result=performance(pd.Series([.1,-.05,.2]),[True,False,True])
    assert result["signals"]==2 and result["win_rate"]==1 and abs(result["mean_net_return"]-.15)<1e-9

def test_hourly_confidence_features_exclude_other_timeframes():
    assert HOURLY_FEATURES and not any(name.startswith(("m15_","d1_")) for name in HOURLY_FEATURES)
