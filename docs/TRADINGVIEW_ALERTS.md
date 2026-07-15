# TradingView hourly breakout alert

`tradingview/hourly_breakout_signal.pine` reproduces the frozen long-only hourly breakout conditions for the twelve supported symbols. It requires a confirmed 1-hour bar, a close above the prior 20-bar high, relative volume of at least 1.2, ADX of at least 20, the frozen per-symbol ATR/price cutoff, regular New York market hours, and a 16-bar cooldown. Alert output is disabled by default.

## Railway demo setup

1. Open a supported symbol on a standard 1-hour TradingView chart.
2. Open Pine Editor, paste the script, save it, and add it to the chart.
3. Confirm the status table says `1 hour`, shows the expected symbol, and leaves `ALERTS OFF` while visually reviewing historical markers.
4. Generate a separate random `TRADINGVIEW_WEBHOOK_TOKEN` of at least 32 bytes, store it as a sealed Railway variable, and enter the same value in the private script input. Do not reuse the main webhook passphrase.
5. Enable TradingView two-factor authentication, which TradingView requires for webhook alerts.
6. In the script settings, enable `ENABLE RAILWAY DEMO ALERTS`.
7. Create an alert with condition `SDE Hourly Breakout — Railway Demo` → `Any alert() function call`, and select once per bar close.
8. Use `https://stock-decision-engine-production.up.railway.app/tradingview/signals` as the Webhook URL. The script generates the structured JSON automatically.

The payload contains the confirmed hourly bar, technical indicators, completed higher-timeframe direction and the dedicated token. Railway rechecks authentication, freshness, the frozen breakout definition, Finnhub news/noise, timeframe alignment, risk and daily reconciliation. It stores every signal and decision. Only a fully approved breakout can be transformed into the exact SignalStack test payload.

## Important architecture boundary

The route is `TradingView → Railway → SignalStack test webhook`. Set `DETERMINISTIC_BREAKOUT_DEMO_ENABLED=true` and `DEMO_SIGNALSTACK_ROUTING_ENABLED=true` only for the demo. Keep `EXECUTION_MODE=paper`, `SIGNALSTACK_WEBHOOK_TYPE=test`, `SIGNALSTACK_LIVE_EXECUTION_ALLOWED=false`, and `SIGNALSTACK_ENABLED=false`. The disabled CatBoost artifact is recorded as comparison-only and cannot authorize execution. The dedicated token is necessarily present in the TradingView alert configuration; keep the script private, restrict access to the TradingView account with 2FA, and rotate the token if it is exposed.
