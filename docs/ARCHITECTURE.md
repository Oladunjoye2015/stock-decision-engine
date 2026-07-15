# Architecture

The authenticated `POST /signals` pipeline persists the signal, enforces idempotency/freshness/timeframe policy, runs deterministic regime/alignment/technical/noise/news gates, validates the registered primary-timeframe model, reviews structured context, applies risk limits, and persists a decision and ticket. Paper and manual adapters share a broker-neutral interface. The source Alpaca service is neither imported nor contacted.

Each repository owns its configuration, database tables, model registry, risk state, logs, tests, and deployment. Finnhub supplies company news and quote data for the news/noise gates when configured. The client is isolated behind a provider boundary, authenticated with `X-Finnhub-Token`, and can be replaced with an offline mock in tests. It does not provide execution.
