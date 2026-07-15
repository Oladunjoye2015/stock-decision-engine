def evaluate(signal, enabled: bool = True, finnhub_quote: dict | None = None, finnhub_bid_ask: dict | None = None) -> dict:
    if not enabled: return {"passed": True, "reason": "disabled", "failed_checks": []}
    i, failed = signal.indicators, []
    candle_range = signal.high - signal.low
    atr = float(i.get("atr") or candle_range)
    atr_pct = atr / signal.close * 100
    if atr_pct < .1: failed.append("insufficient_expected_movement")
    if atr_pct > 15: failed.append("abnormal_candle_range")
    if signal.volume <= 0 or float(i.get("vol_ratio", 1)) < .25: failed.append("poor_liquidity")
    gap = abs(signal.open - float(i.get("previous_close", signal.open))) / signal.open * 100
    if gap > 12: failed.append("abnormal_gap")
    quote = finnhub_quote or {}
    previous_close, quote_open = float(quote.get("pc") or 0), float(quote.get("o") or 0)
    finnhub_gap = abs(quote_open-previous_close)/previous_close*100 if previous_close and quote_open else None
    if finnhub_gap is not None and finnhub_gap > 12 and "abnormal_gap" not in failed: failed.append("abnormal_gap")
    bid_ask = finnhub_bid_ask or {}; bid, ask = float(bid_ask.get("b") or 0), float(bid_ask.get("a") or 0)
    spread_pct = (ask-bid)/((ask+bid)/2)*100 if ask > 0 and bid > 0 and ask >= bid else None
    if spread_pct is not None and spread_pct > .5: failed.append("wide_spread")
    return {"passed": not failed, "reason": "passed" if not failed else ", ".join(failed), "failed_checks": failed, "atr_pct": atr_pct, "gap_pct": finnhub_gap if finnhub_gap is not None else gap, "spread_pct": spread_pct, "source_metadata": {"provider": "finnhub" if finnhub_quote is not None else "payload", "quote_timestamp": quote.get("t")}}
