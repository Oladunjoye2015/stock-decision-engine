def evaluate(context: dict, enabled: bool = True) -> dict:
    if not enabled: return {"passed": True, "regime": "unknown", "reason": "disabled"}
    regime = str(context.get("daily_regime", "neutral")).lower()
    return {"passed": regime in {"bullish", "bearish", "neutral", "unknown"}, "regime": regime, "reason": f"daily regime: {regime}"}

