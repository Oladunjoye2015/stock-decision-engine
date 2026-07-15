# Stock Decision Engine

An independent, broker-neutral FastAPI application for stock analysis, paper simulation, manual trade tickets, and conditionally approved SignalStack order intents. It has no Alpaca dependency and no direct Trade The Pool integration. SignalStack validation and queueing are implemented; outbound transport remains disabled until the exact official account payload is supplied.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Set `FINNHUB_API_KEY` to enable company-news and quote-based noise checks. Set `FINNHUB_FAIL_CLOSED=true` in production if decisions must be blocked whenever Finnhub is unavailable. `FINNHUB_USE_BID_ASK=true` enables the premium bid/ask spread check when your plan supports it.

Reconcile risk state with `POST /risk/reconcile` before proposing a trade when daily reconciliation is required. OpenAPI is at `/docs`.

## Import candles and train

The preferred separation-safe Alpaca workflow is to export historical candles outside this application, then import the CSV. This repository never receives Alpaca credentials or calls an Alpaca endpoint:

```bash
python scripts/import_candles.py --input /path/to/alpaca_60min_export.csv --output data/candles_60min.csv
python scripts/train_backfill_catboost.py --input data/candles_60min.csv --model-id catboost-h1-backfill-v1
python scripts/validate_models.py
```

The importer accepts case-insensitive `timestamp`, `symbol`, `open`, `high`, `low`, `close`, and `volume` columns. For a single-symbol file without a symbol column, add `--symbol AAPL`.

### Optional Finnhub download

Finnhub Stock Candles is a premium endpoint. After setting `FINNHUB_API_KEY`, download independent 60-minute history and train candidates:

```bash
python scripts/download_candles.py --symbols AAPL,MSFT,NVDA,AMD,AMZN,META,GOOGL,TSLA --start 2024-01-01T00:00:00Z --resolution 60 --output data/candles_60min.csv
python scripts/train_ensemble.py --input data/candles_60min.csv --model-id ensemble-h1-v1 --cost-bps 10
python scripts/validate_models.py
```

The primary trainer reproduces the source backfill method independently: full technical feature rows, side-aware ATR stop/target brackets, conservative future-barrier labels, CatBoost categorical features, and chronological train/validation/test periods. The experimental ensemble trainer remains available for research but is not the promotion path. See [training documentation](docs/MODEL_TRAINING.md).

## Deterministic backtests

Run the broker-neutral SMA trend, momentum, breakout and pullback portfolio baselines with:

```bash
python3 scripts/run_backtest.py
```

The summary is written to `model_artifacts/backtest_deterministic_baselines.json`; detailed trade and equity CSVs remain under the Git-ignored `data/backtests/`. See [backtesting methodology and results](docs/BACKTESTING.md).

Run the frozen, execution-disabled breakout shadow after refreshing the independent hourly candle CSV:

```bash
python3 scripts/refresh_and_evaluate.py
```

The Alpaca credentials in `.env` are used only by the explicit refresh script against `data.alpaca.markets`; the application has no Alpaca account or order integration.
Read the consolidated result at `GET /shadow/status`. This endpoint is read-only and always reports execution and automatic promotion as disabled.
The status includes both the unfiltered breakout control and a parallel research-only ML filter that records whether confidence would allow or reject each fresh candidate. The ML path does not authorize execution because its historical validation failed.

## Railway

```bash
railway login
railway init
railway add --database postgres
railway variables set APP_ENV=production EXECUTION_MODE=paper WEBHOOK_PASSPHRASE='<strong-secret>'
railway up
```

Set `DATABASE_URL` to Railway's PostgreSQL variable. Keep live SignalStack flags false until every prerequisite in [the integration guide](docs/SIGNALSTACK_INTEGRATION.md) is verified. See [deployment guidance](docs/DEPLOYMENT.md).
