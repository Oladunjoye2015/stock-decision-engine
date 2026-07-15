from app.market_data.base import MarketDataProvider


class PayloadMarketDataProvider(MarketDataProvider):
    """Uses authenticated payload context only; performs no broker/network calls."""
    def __init__(self, supplied: dict | None = None): self.supplied = supplied or {}
    def context(self, symbol: str, timeframe: str) -> dict: return dict(self.supplied)

