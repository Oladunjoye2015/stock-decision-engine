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

The payload contains the confirmed hourly bar, technical indicators, completed higher-timeframe direction and the dedicated token. Railway then downloads current hourly market-data-only candles for the symbol, SPY and QQQ, upserts them to PostgreSQL, appends the confirmed TradingView bar, and rebuilds technical indicators server-side. It checks candle and benchmark freshness, the frozen breakout definition, Finnhub news/noise, timeframe alignment, risk and daily reconciliation. It stores every signal and decision. Only a fully approved breakout can be transformed into the exact SignalStack test payload.

An optional OpenAI structured-output review is the final veto after every deterministic and risk check. Enable it with `EXTERNAL_AI_REVIEW_ENABLED=true`, a sealed `OPENAI_API_KEY`, and an approved `OPENAI_REVIEW_MODEL`. The reviewer receives the structured evidence and a fixed-weight 0–100 scorecard covering strategy, technical quality, market context, timeframe, regime, news, noise, risk and compliance. It must return `allow` or `block`, an AI viability score, confidence and reasons. It has no order tools, cannot change quantity/prices, and fails closed on timeout, invalid output, low confidence, or disagreement. Neither score can override a failed hard gate.

The Pine trigger is evaluated only on a confirmed hourly close. Daily, four-hour and fifteen-minute context values are also read from completed bars so an open higher-timeframe candle cannot change the evidence after an alert. After updating the script or any private input, delete and recreate the TradingView alert because TradingView alerts retain a snapshot of the script and its inputs.

The Railway `hourly-scanner` is an independent primary source for the demo. It fetches newly completed Alpaca hourly bars and submits deterministic breakout candidates through the same decision pipeline. TradingView alerts use deterministic TradingView IDs and the scanner uses deterministic `railway-hourly-breakout-*` IDs. A database-enforced canonical claim combines symbol, frozen strategy, timeframe and nearest hourly close, so a TradingView session-aligned close and Alpaca clock-aligned close for the same decision window cannot both progress. The first source owns the claim; the second is audited as `cross_source_signal_duplicate` and linked to the original signal and decision. Neither source can bypass a failed gate, and the scanner never converts the daily shadow report into an order.

Server revalidation inserts the confirmed source candle at its bar-start timestamp, replacing the matching Alpaca row rather than appending the same candle at its close time. This keeps the prior-20-bar breakout calculation source-consistent and prevents the current candle's high from being mistaken for prior resistance.

## Important architecture boundary

The route is `TradingView → Railway → SignalStack test webhook`. Set `DETERMINISTIC_BREAKOUT_DEMO_ENABLED=true` and `DEMO_SIGNALSTACK_ROUTING_ENABLED=true` only for the demo. Keep `EXECUTION_MODE=paper`, `SIGNALSTACK_WEBHOOK_TYPE=test`, `SIGNALSTACK_LIVE_EXECUTION_ALLOWED=false`, and `SIGNALSTACK_ENABLED=false`. The disabled CatBoost artifact is recorded as comparison-only and cannot authorize execution. The dedicated token is necessarily present in the TradingView alert configuration; keep the script private, restrict access to the TradingView account with 2FA, and rotate the token if it is exposed.
