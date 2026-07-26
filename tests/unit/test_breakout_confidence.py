import pandas as pd
from app.models.breakout_confidence import HOURLY_FEATURES,performance,select_research_threshold

def test_confidence_performance_counts_only_selected_returns():
    result=performance(pd.Series([.1,-.05,.2]),[True,False,True])
    assert result["signals"]==2 and result["win_rate"]==1 and abs(result["mean_net_return"]-.15)<1e-9

def test_hourly_confidence_features_exclude_other_timeframes():
    assert HOURLY_FEATURES and not any(name.startswith(("m15_","d1_")) for name in HOURLY_FEATURES)


def test_research_threshold_falls_back_to_covered_validation_level():
    table={"0.50":{"signals":85,"mean_net_return":-.005},
           "0.55":{"signals":13,"mean_net_return":-.013},
           "0.60":{"signals":0,"mean_net_return":None}}
    assert select_research_threshold(table)==(.50,"coverage_fallback")


def test_research_threshold_prefers_profitable_covered_level():
    table={"0.50":{"signals":85,"mean_net_return":.001},
           "0.55":{"signals":45,"mean_net_return":.004},
           "0.60":{"signals":10,"mean_net_return":.02}}
    assert select_research_threshold(table)==(.55,"profitable")
