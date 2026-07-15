import httpx

from app.analysis.news_filter import evaluate as evaluate_news
from app.analysis.noise_filter import evaluate as evaluate_noise
from app.market_data.finnhub import FinnhubClient
from app.schemas.signals import SignalIn


def test_finnhub_snapshot_uses_header_and_official_routes():
    routes = []
    def handler(request):
        assert request.headers["X-Finnhub-Token"] == "secret"
        routes.append(request.url.path)
        if request.url.path.endswith("company-news"):
            assert request.url.params["symbol"] == "AAPL"
            return httpx.Response(200, json=[{"headline": "Company announces secondary offering", "datetime": 100, "source": "wire"}])
        if request.url.path.endswith("quote"): return httpx.Response(200, json={"o": 110, "pc": 100, "t": 123})
        return httpx.Response(200, json={"a": 101, "b": 100})
    http = httpx.Client(base_url="https://finnhub.io/api/v1", transport=httpx.MockTransport(handler), headers={"X-Finnhub-Token": "secret"})
    client = FinnhubClient("secret", client=http)
    snapshot = client.snapshot("AAPL", use_bid_ask=True)
    assert routes == ["/api/v1/company-news", "/api/v1/quote", "/api/v1/stock/bidask"]
    assert snapshot["provider"] == "finnhub"


def test_finnhub_news_and_quote_drive_filters():
    news = evaluate_news({}, finnhub_news=[{"headline": "Issuer announces offering", "datetime": 100, "source": "wire"}])
    assert news["passed"] is False and news["source_metadata"]["provider"] == "finnhub"
    signal = SignalIn(signal_id="s", symbol="AAPL", timeframe="60Min", strategy="x", signal_time_utc="2026-07-14T12:00:00Z", current_price=100, open=100, high=101, low=99, close=100, volume=1000, indicators={"atr": 1})
    noise = evaluate_noise(signal, finnhub_quote={"o": 110, "pc": 100, "t": 123}, finnhub_bid_ask={"a": 101, "b": 100})
    assert noise["gap_pct"] == 10
    assert noise["spread_pct"] > .5
    assert noise["source_metadata"]["provider"] == "finnhub"


def test_stock_candles_are_normalized():
    def handler(request):
        assert request.url.path.endswith("/stock/candle") and request.url.params["resolution"] == "60"
        return httpx.Response(200, json={"s": "ok", "t": [1, 2], "o": [10, 11], "h": [12, 13], "l": [9, 10], "c": [11, 12], "v": [100, 200]})
    http = httpx.Client(base_url="https://finnhub.io/api/v1", transport=httpx.MockTransport(handler))
    rows = FinnhubClient("secret", client=http).stock_candles("AAPL", "60", 1, 2)
    assert rows[1] == {"timestamp": 2, "open": 11, "high": 13, "low": 10, "close": 12, "volume": 200}
