from datetime import date, timedelta

import httpx


class FinnhubError(RuntimeError):
    pass


class FinnhubClient:
    """Small official REST client using X-Finnhub-Token authentication."""

    def __init__(self, api_key: str, base_url: str = "https://finnhub.io/api/v1", timeout: float = 10, client: httpx.Client | None = None):
        if not api_key: raise FinnhubError("FINNHUB_API_KEY is not configured")
        self._owns_client = client is None
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), headers={"X-Finnhub-Token": api_key}, timeout=timeout)

    def _get(self, path: str, params: dict) -> dict | list:
        try:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FinnhubError(f"Finnhub request failed: {exc}") from exc
        if isinstance(data, dict) and data.get("error"): raise FinnhubError(f"Finnhub error: {data['error']}")
        return data

    def company_news(self, symbol: str, lookback_days: int = 3, limit: int = 50) -> list[dict]:
        end = date.today(); start = end - timedelta(days=max(1, lookback_days))
        data = self._get("/company-news", {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        if not isinstance(data, list): raise FinnhubError("Unexpected company-news response")
        return data[:max(1, limit)]

    def quote(self, symbol: str) -> dict:
        data = self._get("/quote", {"symbol": symbol})
        if not isinstance(data, dict): raise FinnhubError("Unexpected quote response")
        return data

    def stock_candles(self, symbol: str, resolution: str, start_unix: int, end_unix: int) -> list[dict]:
        data = self._get("/stock/candle", {"symbol": symbol, "resolution": resolution, "from": start_unix, "to": end_unix})
        if not isinstance(data, dict): raise FinnhubError("Unexpected stock-candle response")
        if data.get("s") == "no_data": return []
        if data.get("s") != "ok": raise FinnhubError(f"Stock-candle request did not succeed: {data.get('s', 'unknown')}")
        required = ("t", "o", "h", "l", "c", "v")
        if any(not isinstance(data.get(key), list) for key in required): raise FinnhubError("Stock-candle response is missing OHLCV arrays")
        lengths = {len(data[key]) for key in required}
        if len(lengths) != 1: raise FinnhubError("Stock-candle OHLCV arrays have different lengths")
        return [{"timestamp": data["t"][i], "open": data["o"][i], "high": data["h"][i], "low": data["l"][i], "close": data["c"][i], "volume": data["v"][i]} for i in range(len(data["t"]))]

    def bid_ask(self, symbol: str) -> dict:
        data = self._get("/stock/bidask", {"symbol": symbol})
        if not isinstance(data, dict): raise FinnhubError("Unexpected bid/ask response")
        return data

    def snapshot(self, symbol: str, lookback_days: int = 3, news_limit: int = 50, use_bid_ask: bool = False) -> dict:
        return {"provider": "finnhub", "news": self.company_news(symbol, lookback_days, news_limit), "quote": self.quote(symbol), "bid_ask": self.bid_ask(symbol) if use_bid_ask else {}}

    def close(self):
        if self._owns_client: self.client.close()
