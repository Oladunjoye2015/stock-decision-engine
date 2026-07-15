# Training results

## Dataset

- Source export: `Alapca candle/data/alpaca/combined/training_1hour_iex.csv`
- Feed recorded by source manifest: IEX
- Period: 2022-01-03 through 2026-07-14
- Symbols: AAPL, AMD, AMZN, AVGO, BABA, GOOG, META, MSFT, NVDA, QQQ, SPY, TSLA
- Imported rows: 81,238; usable labeled rows: 81,154
- Chronological split: 56,797 train; 12,177 validation; 12,180 final test
- Data-quality audit: zero duplicate symbol/timestamps, invalid OHLCV rows, bad timestamps or zero-volume rows

## Selection outcome

The soft-voting ensemble did not beat the best single validation model. Histogram gradient boosting was selected:

| Model | Validation log loss | Validation ROC AUC | Validation net signal return |
|---|---:|---:|---:|
| Logistic regression | 0.6902 | 0.5538 | 0.1628% |
| Random forest | 0.6933 | 0.5286 | 0.0894% |
| Histogram gradient boosting | **0.6860** | 0.5456 | 0.7295% |
| Soft-voting ensemble | 0.6871 | 0.5430 | -0.0702% |

On the untouched final test, the selected model produced log loss 0.6847, ROC AUC 0.5260, balanced accuracy 0.5007 and mean net signal return -0.0369% over 124 threshold signals after the 10 bps assumption.

## Promotion decision

The artifact is retained for research but `enabled=false` and `production_eligible=false`. It failed the positive after-cost test-return and balanced-accuracy gates. Therefore no normal paper, manual or SignalStack proposal can use it. Further feature/label research and walk-forward evaluation are required; validation performance must not be presented as final performance.

## Backfill CatBoost run

The primary backfill method produced 35,640 resolved stop/target labels: 24,794 train, 5,246 validation and 5,600 untouched test rows. Validation AUC peaked at 0.5860. Validation selected a 0.55 probability threshold from thresholds with at least 100 signals.

Untouched test results were weaker: ROC AUC 0.5396, balanced accuracy 0.5122, 782 signals, precision 0.2545, and expected value -0.2366 R before costs at the selected threshold. The test set contained 1,255 wins and 4,345 losses. The validation-to-test deterioration means the backfill artifact is retained but disabled; sticking to the backfill method does not justify promoting this particular run.

## Multi-timeframe backfill CatBoost run

The second backfill run kept 1-hour candles as the sole setup and barrier-label timeframe, then joined only completed 15-minute confirmation and prior-day regime features. It used the same 35,640 resolved labels and chronological 24,794/5,246/5,600 split. The availability rules were source timestamp + 15 minutes for intraday confirmation and source timestamp + one calendar day for daily regime data.

Validation AUC was 0.5623 and selected 0.55 from thresholds having at least 100 signals. The untouched final result failed promotion: ROC AUC 0.5272, balanced accuracy 0.5122, 764 signals, precision 0.2552, and expected value -0.2343 R before costs. Results were negative for both buy and sell hints and for trend, range, and high-volatility regimes. Only AAPL had positive expected R with at least 50 final signals; SPY and QQQ had too few selected signals to support a conclusion.

Expanding-window tests at a predeclared 0.55 threshold were also unstable:

| Forward period end | ROC AUC | Signals | Expected R before costs |
|---|---:|---:|---:|
| 2025-03-07 | 0.5247 | 1,061 | -0.1602 |
| 2025-11-10 | 0.5611 | 586 | +0.0802 |
| 2026-07-13 | 0.5123 | 967 | -0.3113 |

Artifact `catboost-h1-mtf-backfill-v2` is retained for reproducibility with `enabled=false` and `production_eligible=false`. Multi-timeframe context did not fix the out-of-sample weakness, so it must not be used for paper, manual, or SignalStack decisions.

## Deterministic setup-gate analysis

The next stage evaluated eleven predeclared filters covering regular-session timing, 1-hour/15-minute/daily direction agreement, relative volume, opposing supply/demand zones, and moderate ADX. Gate selection was restricted to training and validation: each gate needed at least 300 resolved setups and positive 2:1 expected R in both periods. Final-period outcomes could not affect selection, which is enforced by a unit test.

No gate qualified. Training win rates ranged from 21.4% to 24.8%, while validation win rates ranged from 22.2% to 27.5%. A 2:1 target requires a win rate above 33.3% before costs. Because every candidate was already negative in both development periods, no filtered CatBoost model was trained and the registry was left unchanged. The complete machine-readable table is stored in `model_artifacts/setup_gate_analysis.json`.

## Label-configuration study

The label study tested the predeclared Cartesian grid of four stop distances (1, 1.5, 2 and 2.5 ATR), three targets (1, 1.5 and 2R), and four maximum holds (4, 8, 12 and 16 one-hour bars). Unlike the earlier resolved-only labels, timeouts were retained, exited at the horizon close, clipped to the bracket, and included in expectancy. A 10 bps round-trip estimate was converted into R using each setup's ATR risk distance.

Twenty-two of 48 configurations were positive in both training and validation with at least 1,000 rows and a train/validation expectancy difference no larger than 0.15R. Selection occurred before the final period was read. The selected `2.5 ATR / 2R / 16 bars` configuration produced +0.0450R in training and +0.1055R in validation after estimated costs, with timeout rates of 44.5% and 46.3%.

It failed the untouched final period: 12,000 setups, 40.2% timeouts, 24.4% resolved win rate, +0.0132R before costs and **-0.0383R after costs**. Buy setups averaged -0.0270R and sell setups -0.0937R. AAPL, AMD and GOOG were positive after costs, and AVGO was marginally positive, but selecting symbols from this final-period observation would contaminate the test. Therefore no CatBoost model was trained and every registry entry remains disabled.

## Separate direction-trigger study

Eight sparse triggers were predeclared: long/short trend continuation, breakout/breakdown, pullback, and demand/supply reversal. Long and short candidates were selected separately using training and validation only with the `2.5 ATR / 2R / 16 bars` label configuration. At least 200 setups and positive after-cost expectancy were required in both periods.

Only `long_trend_continuation` qualified. It required regular-session timing, adequate relative volume, aligned 1-hour and daily uptrends, price above session VWAP, positive 15-minute MACD histogram, and 1-hour RSI from 50 to 68. It produced 1,106 training setups at +0.0063R and 424 validation setups at +0.1625R after estimated costs. No short trigger qualified; the available short samples were also sparse.

The selected long trigger produced 241 setups at +0.0605R after costs in the later historical period. This is encouraging but **not an untouched test** because that period was inspected by earlier studies. It cannot support model promotion. The candidate must be frozen and evaluated on newly arriving candles or forward paper trades without changing its rules. No CatBoost model was trained and all registry entries remain disabled.

## Forward shadow baseline

`long-trend-continuation-shadow-v1` is frozen after the last existing hourly candle at `2026-07-14T15:00:00Z`. The initial shadow run correctly contains zero completed trades and zero pending signals because no candle newer than the boundary exists in the imported data. The evaluator requires fresh 15-minute and daily context, tracks pending 16-bar outcomes, and requires at least 100 completed trades before a new human review. Automatic promotion is prohibited.

## Breakout confidence gate

A timestamp audit found and corrected leakage in the deterministic portfolio engine: the boolean signal was shifted to the next open, but ATR sizing and candidate ranking had been read from the completed entry candle. All backtests and stress reports were regenerated with signal-candle-only values. The corrected breakout returned 34.9% with 18.3% maximum drawdown, 1.100 profit factor and a -10.7% first chronological slice; previous breakout figures are superseded.

The corrected confidence study produced 1,574 breakout candidates. Calibrated CatBoost beat calibrated logistic regression, random forest and XGBoost on validation Brier score. Its final ROC AUC was 0.4550. The validation-selected 0.50 gate reduced 204 later candidates to 66 and reduced profit factor from 1.248 to 0.973, with negative mean selected return. Artifact `breakout-confidence-v1` is retained for reproducibility but is disabled and not production eligible.

The v2 confidence study added 25 market-relative, volatility, gap/candle, breadth and completed multi-timeframe features. Calibrated logistic regression was selected, but validation ROC AUC was 0.5090 and both populated confidence thresholds lost money. No threshold met the minimum 40-signal positive-expectancy rule; the fail-closed fallback allowed zero later trades. Artifact `breakout-confidence-v2` remains disabled. More filters did not produce usable confidence.

The dedicated hourly-only CatBoost experiment used no 15-minute, daily, Finnhub or ensemble inputs. It produced validation ROC AUC 0.4682 and final ROC AUC 0.4890. Its populated validation gates had profit factors 0.693 at 0.50 and 0.367 at 0.55. Artifact `breakout-hourly-catboost-v1` is disabled; its parallel shadow uses the no-trade 0.60 fallback solely to collect fresh comparisons.
