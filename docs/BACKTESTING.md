# Deterministic strategy backtesting

`python3 scripts/run_backtest.py` runs four fixed long-only baselines against the explicit local 1-hour candle CSV. It never downloads broker data or transmits an order.

## Execution assumptions

- A signal calculated from an hourly close enters at the next hourly open.
- Entry and exit slippage are each 5 bps.
- Each trade risks 1% of current equity, capped at one-third of equity.
- At most three positions may overlap.
- The bracket uses a 2 ATR stop, 2R target and 16-bar maximum hold.
- If stop and target occur within the same OHLC candle, stop wins.
- Open positions are marked to candle closes and forcibly closed at the end of data.

Trades and equity curves are written under the ignored `data/backtests/` directory. The summary is stored in `model_artifacts/backtest_deterministic_baselines.json`.

## Initial baseline results

These are the corrected results after an audit found that the first implementation shifted the boolean entry signal but mistakenly used ATR and ranking values from the completed entry candle. The engine now shifts every sizing, ranking and diagnostic feature from the signal candle before entering at the next open. The earlier, higher results are superseded and must not be used.

| Strategy | Return | Max drawdown | Trades | Profit factor | Four chronological slice returns |
|---|---:|---:|---:|---:|---|
| SMA trend | 13.8% | -8.5% | 384 | 1.109 | -4.8%, 7.6%, 10.8%, 0.3% |
| Momentum | 9.2% | -23.2% | 710 | 1.033 | -18.3%, 10.5%, 15.4%, 4.8% |
| Breakout | **34.9%** | -18.3% | 927 | 1.100 | -10.7%, 23.6%, 11.7%, 9.3% |
| Pullback | 25.3% | -21.8% | 978 | 1.078 | 3.6%, 20.9%, -9.7%, 10.8% |

The refreshed equal-weight buy-and-hold comparison returned 23.0%. Breakout remains the strongest initial candidate and exceeded that comparison, but it lost 10.7% in the first fixed time slice and its profit factor is only 1.100. This is weak research evidence—not permission to trade.

## Required next validation

The four strategies were compared on the same history, which creates strategy-selection bias. Freeze the breakout definition before tuning it. Next evaluate results by symbol, calendar year and market regime, then test parameter sensitivity around—not merely at—the current 20-bar breakout, 1.2 relative-volume, ADX 20, 2 ATR stop and 16-bar holding assumptions. A useful result should survive nearby parameters, higher slippage and forward shadow evaluation.

## Breakout robustness and time restriction

The time-of-day comparison uses the actual next-bar entry timestamp in `America/New_York`: morning is before noon and afternoon is noon or later. Both are restricted to entry hours 09 through 15. Results include the same portfolio constraints and 5 bps slippage per side.

| Entry window | Return | Max drawdown | Trades | Profit factor | Four chronological slices |
|---|---:|---:|---:|---:|---|
| Morning | 21.4% | -14.2% | 839 | 1.074 | -8.1%, 2.0%, 19.8%, 8.1% |
| Afternoon | **48.7%** | -17.0% | 423 | **1.252** | 5.1%, 29.4%, 13.4%, -3.5% |

Historically, afternoon entries were more favorable overall and had a better profit factor, but not a better drawdown. The latest chronological slice lost 3.5%, while morning gained 8.1%. This does not justify an afternoon-only rule without fresh confirmation.

Breakout performance improved with volatility. The corrected base strategy's profit factors were 0.876, 1.081 and 1.230 in low-, medium- and high-volatility thirds. Afternoon profit factors were 1.138, 1.150 and 1.388 respectively. The frozen shadow blocks the low-volatility third, but this choice was made on seen data and needs forward confirmation.

Nearby corrected one-factor returns were 20.5% for a 15-bar high, 41.5% for a 30-bar high, 8.8% at relative volume 1.0, 29.3% at relative volume 1.4, 8.3% at ADX 15, and 17.9% at ADX 25. Nearby variants are mostly positive, but the wide deterioration reinforces that the edge is modest.

Cost sensitivity is a major concern: the corrected base returned 7.2% at 10 bps slippage per side and -18.2% at 15 bps per side. Any paper evaluation must record realistic spread, slippage and fill timing.

## Breakout confidence-gate experiment

The confidence dataset contained 1,574 medium/high-volatility breakout candidates with entries at the next bar open and all features frozen at the signal candle. Calibrated logistic regression, random forest, CatBoost and XGBoost were compared. CatBoost had the best validation Brier score (0.2480) and validation ROC AUC of 0.5465; XGBoost validation ROC AUC was 0.5246.

The validation-selected CatBoost threshold of 0.50 retained 87 candidates with 1.203 profit factor. It failed in the later period: ROC AUC 0.4550, 66 selected candidates, -0.032% mean return and 0.973 profit factor. Accepting all 204 breakouts in that period produced +0.265% mean return and 1.248 profit factor. The confidence gate made the strategy worse and is disabled.

An expanded v2 experiment added breakout distance in ATR, volume acceleration, ADX change, rolling volatility percentile, gap and candle structure, SPY/QQQ relative strength, 12-symbol breadth, and completed 15-minute/daily context. More features did not help. Calibrated logistic regression was selected with validation ROC AUC 0.5090; CatBoost and XGBoost validation AUCs were 0.4628 and 0.4675. The 0.50 and 0.55 validation gates both had negative mean returns and profit factors below 1.0. With no eligible threshold, the fail-closed 0.60 fallback allowed zero later trades. V2 is disabled and is not connected to the shadow strategy.

This demonstrates why simply adding enough filters is unsafe: a filter can reduce trade count without increasing its ability to rank outcomes. Confidence may control allowance only after calibrated probabilities show positive expectancy with adequate samples in multiple unseen periods. Until then, deterministic shadow rules remain the only candidate path.

The requested hourly-only experiment used the deterministic 1-hour breakout and 32 features derived exclusively from completed 1-hour candles, with calibrated CatBoost as the sole estimator. Validation ROC AUC was 0.4682. At confidence 0.50, 85 trades had 0.693 profit factor; at 0.55, 13 trades had 0.367 profit factor. No threshold qualified, and the 0.60 fail-closed threshold selected no later trades.

The ML allowance mechanism is implemented as a parallel research shadow. `breakout-hourly-catboost-shadow-v1` scores only fresh 1-hour breakout candidates after `2026-07-14T19:00:00Z`, checksum-verifies the disabled hourly CatBoost artifact, and uses the frozen 0.60 threshold. It records `allowed` or `rejected` for comparison with the unfiltered breakout shadow. These labels do not transmit or authorize a trade; the model failed validation and the configuration enforces `research_only=true` and `execution_enabled=false`.

## Frozen breakout shadow

`breakout-medium-high-vol-shadow-v1` is frozen in `model_artifacts/breakout_shadow_config.json`. It accepts signals strictly after `2026-07-14T15:00:00Z` and uses fixed per-symbol 33rd-percentile ATR/price cutoffs calculated only from candles at or before that boundary. This blocks the historically unprofitable low-volatility third without allowing future observations to redefine the threshold.

The candidate keeps the 20-bar prior-high breakout, relative volume at least 1.2, ADX at least 20, 2 ATR stop, 2R target, 16-hour limit, 1% risk and three-position cap. Morning and afternoon entries are tracked separately rather than selectively enabled. Assumed slippage is 5 bps per side; the configured maximum acceptable level is 10 bps per side.

After importing newer hourly candles, run:

```bash
python3 scripts/refresh_and_evaluate.py
```

The refresh script is an incremental adaptation of the downloader stored beside the original candle exports. It refreshes 15-minute, 1-hour and daily files with overlap, validates OHLCV, deduplicates symbol/timestamps and atomically replaces each output only when every requested symbol for that timeframe succeeds. It calls Alpaca market data only; it contains no trading, account, position or order endpoint.

Runtime state is written to the ignored `data/breakout_shadow_state.json`. Open positions remain pending at the data boundary rather than being artificially closed. The evaluator requires at least 100 completed fresh trades and profit factor of at least 1.15, but these gates only trigger a new review. `promotion_blocked` always remains true and no orders are transmitted.

The consolidated command also writes `data/shadow_status.json`, validates all three candle files and recomputes the frozen long-trend shadow. Use `python3 scripts/refresh_and_evaluate.py --skip-refresh` to recompute reports without making a network request. When the API is running, `GET /shadow/status` returns the refresh manifest, both detailed shadow states and the consolidated summary without exposing credentials or allowing mutation.
