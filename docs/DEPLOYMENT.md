# Railway deployment

Railway is the sole production runtime. Use three services in one Railway project:

1. `Postgres` — the shared durable store for application records, candles, refresh manifests and shadow results.
2. `stock-decision-engine` — the always-on FastAPI web service, using `railway.json`.
3. `market-refresh` — a cron service built from the same repository, using `railway.cron.json` and start command `python3 scripts/refresh_and_evaluate.py --storage database`.

Both application services must reference the same database with `DATABASE_URL=${{Postgres.DATABASE_URL}}`. Set these shared variables so both services receive them:

```text
APP_ENV=production
RUNTIME_STORAGE=database
EXECUTION_MODE=paper
ALPACA_API_KEY=<sealed secret>
ALPACA_API_SECRET=<sealed secret>
ALPACA_DATA_FEED=iex
FINNHUB_API_KEY=<sealed secret>
FINNHUB_FAIL_CLOSED=true
WEBHOOK_PASSPHRASE=<strong sealed secret>
```

In the web service, generate a public domain and verify `/health`, `/ready`, `/shadow/status`, and `/dashboard/`. The dashboard is read-only and refreshes its status data every minute. In the cron service, set its Railway config-file path to `/railway.cron.json`, then set the cron schedule. Railway schedules use UTC. To run at 4:30 PM New York throughout daylight-saving changes, create separate seasonal schedules or accept a one-hour seasonal shift; `30 20 * * 1-5` corresponds to 4:30 PM EDT and `30 21 * * 1-5` to 4:30 PM EST.

The first cron run bootstraps 15-minute and hourly candles from 2022-01-01 and daily candles from 2018-01-01. Later runs use overlapping incremental windows and upsert by symbol, timeframe and timestamp. A cron run exits after refresh and evaluation; overlapping Railway executions are therefore avoided. No persistent volume is required.

Keep `EXECUTION_MODE=paper`. Before selecting `signalstack`, configure and verify the current TTP program/rule version/date/limits, account-generated webhook, official payload and all live flags. The present implementation intentionally keeps outbound transport disabled and cannot be promoted to live transmission. Run `python scripts/validate_signalstack_config.py` and confirm daily risk reconciliation first.

For the Trade The Pool demo test webhook only, keep `EXECUTION_MODE=paper` and `SIGNALSTACK_LIVE_EXECUTION_ALLOWED=false`, then set `SIGNALSTACK_WEBHOOK_TYPE=test` and `SIGNALSTACK_TEST_TRANSPORT_ENABLED=true`. The authenticated `POST /signalstack/test-configuration` endpoint can then send the confirmed three-field test payload. This does not enable queued or production order transmission.

Use real values in Railway rather than copying angle-bracket placeholders. For example, `TTP_RULE_LAST_VERIFIED_AT=2026-07-15T00:00:00Z`. If this value is absent or a placeholder, the application starts but the TTP policy check remains incomplete and blocks SignalStack execution.

## CLI status

This local repository must be linked before deployment:

```bash
railway link
railway up
```

After linking, create or select the two application services in Railway and apply the config paths described above. Do not commit `.env`; Railway variables replace it in production.
