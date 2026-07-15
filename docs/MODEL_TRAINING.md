# Model training

## Data

The separation-safe Alpaca option is a user-created CSV export processed by `scripts/import_candles.py`. The importer contains no Alpaca client, credential, endpoint or source-repository dependency. It normalizes column aliases, timestamps and numeric fields; removes duplicates and invalid OHLCV rows; and marks every row `user_supplied_alpaca_export`.

`scripts/download_candles.py` calls Finnhub's official premium `/stock/candle` endpoint with resolution `60`. Because Finnhub limits intraday responses to one month per request, the script pages through non-overlapping 30-day UTC windows, deduplicates timestamps, validates OHLCV relationships and writes an independent CSV under `data/`.

Use a diversified, predetermined symbol universe and enough history to cover different volatility and market regimes. Do not choose symbols or dates after reviewing test results. Intraday candles are unadjusted according to Finnhub, so corporate-action handling must be reviewed before production training.

## Primary backfill method

`scripts/train_backfill_catboost.py` is the primary training path. It independently adapts the method audited in `tv-ml-trading-bot/scripts/backfill_historical_alerts.py`, `label_data.py`, and `train_model.py`: EMA 20/50/200, RSI, MACD histogram, DMI/ADX, ATR, Bollinger width, session VWAP, returns, EMA distances, relative volume, swing/Fibonacci levels, supply/demand zones, trend and categorical side/trigger context.

Each completed one-hour row proposes a side, a two-ATR stop and a 2:1 target. The next eight bars are scanned in order; stop wins ties for conservative labeling, and timeouts are excluded. Unlike the source label-fetch implementation, the current signal bar is explicitly excluded because an entry based on that bar's close cannot trade its earlier high/low. CatBoost uses class balancing, validation early stopping, and common-timestamp 70/15/15 periods. Probability means the probability that the proposed side reaches target before stop.

The optional `scripts/analyze_setup_gates.py` stage evaluates a fixed family of interpretable setup filters before another model is fit. A filter must have at least 300 resolved rows and positive 2:1 expected R independently in training and validation. Selection cannot use the final period. If no filter qualifies, training stops; a weak filter is not forced merely to produce another artifact.

`scripts/study_label_configurations.py` studies stop distance, target R and holding horizon before model fitting. Timeout setups are retained and marked to the horizon close rather than excluded. Selection uses only training and validation, includes estimated costs in R, and reads the final period only for the single selected configuration. A failed final result stops the pipeline before CatBoost training.

`scripts/study_direction_triggers.py` evaluates sparse, explicit long and short entry definitions separately. Its later historical period is exploratory after the prior studies inspected those dates. Any selected trigger must be frozen and confirmed with genuinely new candles or forward paper execution before model training or promotion.

## Forward shadow evaluation

The frozen candidate is stored in `model_artifacts/forward_shadow_config.json`. Its signal boundary is `2026-07-14T15:00:00Z`; candles at or before that timestamp are never counted as fresh. The evaluator transmits no orders and always records `promotion_blocked=true`, even after the 100-trade minimum is reached.

After refreshing the independent 1-hour, 15-minute and daily CSV files, run:

```bash
python3 scripts/run_forward_shadow.py
```

The ignored runtime state is written to `data/forward_shadow_state.json`. Re-running against the same candle files is idempotent because state is recomputed from the frozen boundary and signal IDs are deterministic. Signals without 16 later hourly bars remain pending. Completed signals include gross and estimated after-cost R. Reaching 100 completed trades triggers review only; it never enables a registry model or execution.

## Experimental normalized method

The older experimental ensemble path labels whether the close three bars ahead exceeds costs and uses normalized features. It remains for comparison only and is not used for model promotion.

## Selection

All symbols are separated by common timestamp boundaries into 70% training, 15% validation and 15% untouched final test periods. Base candidates include logistic regression, random forest, histogram gradient boosting and CatBoost when installed. A soft-voting ensemble is considered because diverse probabilistic estimators can reduce variance, but it is selected only when validation log loss improves by the configured minimum and balanced accuracy does not materially deteriorate. Selection occurs before final-test evaluation.

The report records log loss, Brier score, balanced accuracy, precision, ROC AUC, signal count and mean net signal return after the configured cost assumption. A trained artifact is not automatically evidence of a tradable edge. Require adequate sample size, positive after-cost behavior, probability calibration review, walk-forward stability and paper validation before enabling tickets.

The artifact, checksum, exact feature order, dependencies, symbols, timeframe, selection report and final-test metrics are written to the independent registry. The development baseline is disabled when the trained model is registered.
