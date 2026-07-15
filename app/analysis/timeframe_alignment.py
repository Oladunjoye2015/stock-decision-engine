def evaluate(side: str, context: dict, allow_neutral: bool = True, enabled: bool = True) -> dict:
    if not enabled: return {"passed": True, "status": "disabled", "reason": "disabled"}
    daily = str(context.get("daily_regime", "neutral")).lower()
    h4 = str(context.get("4hour_trend", context.get("4Hour", "neutral"))).lower()
    m15 = str(context.get("15min_confirmation", context.get("15Min", "neutral"))).lower()
    opposite = "bearish" if side == "long" else "bullish"
    conflicts = [name for name, value in (("daily", daily), ("4hour", h4), ("15min", m15)) if value == opposite]
    neutrals = [name for name, value in (("daily", daily), ("4hour", h4), ("15min", m15)) if value in {"neutral", "unknown", ""}]
    passed = not conflicts and (allow_neutral or not neutrals)
    return {"passed": passed, "status": "aligned" if passed else "misaligned", "reason": "aligned" if passed else f"conflicts={conflicts}, neutral={neutrals}", "daily": daily, "4hour": h4, "15min": m15}

