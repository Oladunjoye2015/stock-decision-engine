# TradingView hourly breakout alert

`tradingview/hourly_breakout_signal.pine` reproduces the frozen long-only hourly breakout conditions for the twelve supported symbols. It requires a confirmed 1-hour bar, a close above the prior 20-bar high, relative volume of at least 1.2, ADX of at least 20, the frozen per-symbol ATR/price cutoff, regular New York market hours, and a 16-bar cooldown. Alert output is disabled by default.

## SignalStack test setup

1. Open a supported symbol on a standard 1-hour TradingView chart.
2. Open Pine Editor, paste the script, save it, and add it to the chart.
3. Confirm the status table says `1 hour`, shows the expected symbol, and leaves `ALERTS OFF` while visually reviewing historical markers.
4. Enable TradingView two-factor authentication, which TradingView requires for webhook alerts.
5. In the script settings, enable `ENABLE SIGNALSTACK TEST ALERTS` only while using the SignalStack test webhook.
6. Create an alert with condition `SDE Hourly Breakout — SignalStack Test` → `Any alert() function call`, and select once per bar close.
7. Paste the SignalStack **test** webhook URL into TradingView's Webhook URL field. Do not put credentials in the message. The script generates the confirmed JSON automatically.

The emitted body is exactly `{"symbol":"AAPL","quantity":1,"action":"buy"}`, with the current supported chart symbol and configured test quantity substituted. The script emits entries only; it does not infer sell, stop, target, short, cancellation, or modification payloads.

## Important architecture boundary

This direct route is `TradingView → SignalStack`. It bypasses the Railway decision API, Finnhub filters, CatBoost comparison, risk reconciliation, queue, rate limiter, and PostgreSQL request records. Use it only against SignalStack's test webhook. It is not approved as the production route. A later `TradingView → Railway → SignalStack` integration requires a dedicated authenticated TradingView intake endpoint and a confirmed production order lifecycle.
