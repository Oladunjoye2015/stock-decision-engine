BLOCK_EVENTS = {"offering", "bankruptcy", "regulatory_action", "litigation", "trading_halt", "fraud"}


def evaluate(metadata: dict, enabled: bool = True, finnhub_news: list[dict] | None = None) -> dict:
    if not enabled: return {"passed": True, "reason": "disabled", "risk_level": "unknown", "headline_count": 0, "latest_headline_time": None, "event_types": [], "source_metadata": {}}
    news = metadata.get("news", {})
    headlines = finnhub_news if finnhub_news is not None else news.get("headlines", [])
    event_aliases = {
        "offering": ("offering", "dilution", "secondary sale"), "bankruptcy": ("bankruptcy", "chapter 11"),
        "regulatory_action": ("sec investigation", "regulatory action", "fda rejection", "clinical hold"),
        "litigation": ("lawsuit", "litigation", "fraud"), "trading_halt": ("trading halt", "halted"),
        "earnings": ("earnings",), "guidance": ("guidance",), "analyst_action": ("upgrade", "downgrade", "price target"),
        "merger_acquisition": ("merger", "acquisition"), "management_change": ("ceo resign", "management change"),
    }
    combined = " ".join(f"{x.get('headline', '')} {x.get('summary', '')}" for x in headlines if isinstance(x, dict)).lower()
    detected = {event for event, terms in event_aliases.items() if any(term in combined for term in terms)}
    events = {str(x).lower() for x in news.get("event_types", [])} | detected
    blocked = sorted(events & BLOCK_EVENTS)
    timestamps = [x.get("datetime") for x in headlines if isinstance(x, dict) and x.get("datetime")]
    sources = sorted({x.get("source") for x in headlines if isinstance(x, dict) and x.get("source")})
    return {"passed": not blocked, "reason": "passed" if not blocked else f"blocked events: {', '.join(blocked)}", "risk_level": "high" if blocked else news.get("risk_level", "low"), "headline_count": len(headlines), "latest_headline_time": max(timestamps) if timestamps else news.get("latest_headline_time"), "event_types": sorted(events), "source_metadata": {"provider": "finnhub" if finnhub_news is not None else "payload", "sources": sources}}
