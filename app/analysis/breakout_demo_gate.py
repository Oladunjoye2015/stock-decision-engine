from app.schemas.signals import SignalIn


ATR_CUTOFFS = {
    "AAPL": .00613449, "AMD": .01226962, "AMZN": .00762186, "AVGO": .00871582,
    "BABA": .00789124, "GOOG": .00707455, "META": .00808966, "MSFT": .00581686,
    "NVDA": .01087266, "QQQ": .00464406, "SPY": .00342031, "TSLA": .01305073,
}


def evaluate(signal: SignalIn, enabled: bool) -> dict:
    if signal.strategy != "breakout-medium-high-vol-shadow-v1":
        return {"applicable": False, "passed": False, "reason": "not the frozen breakout demo strategy"}
    i = signal.indicators
    cutoff = ATR_CUTOFFS.get(signal.symbol)
    values = {"prior_high20": i.get("prior_high20"), "vol_ratio": i.get("vol_ratio"),
              "adx": i.get("adx"), "atr_pct": i.get("atr_pct")}
    missing = [name for name, value in values.items() if value is None]
    checks = {
        "demo_enabled": enabled,
        "supported_symbol": cutoff is not None,
        "confirmed_hourly_bar": signal.timeframe == "60Min" and bool(signal.external_metadata.get("bar_confirmed")),
        "prior_high_break": not missing and signal.close > float(values["prior_high20"]),
        "relative_volume": not missing and float(values["vol_ratio"]) >= 1.2,
        "adx": not missing and float(values["adx"]) >= 20,
        "atr_regime": not missing and cutoff is not None and float(values["atr_pct"]) >= cutoff,
    }
    failed = missing + [name for name, passed in checks.items() if not passed]
    return {"applicable": True, "passed": not failed, "reason": "passed" if not failed else "failed: " + ", ".join(failed),
            "checks": checks, "frozen_atr_pct_cutoff": cutoff, "values": values}
