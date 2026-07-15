# Risk policy

Sizing is the minimum allowed by per-trade risk, buying power, symbol exposure, the 5% prior-complete-one-minute-volume cap for SignalStack, and any strategy cap. New tickets are blocked by stale signals, unreconciled daily state, Daily Pause, Maximum Loss buffer, kill switch, daily loss/trade limits, aggregate risk, open-position count, duplicates/conflicts, disabled shorts, invalid stops, insufficient reward/risk, unsafe request state, or stale policy. Conservative defaults are $75 per trade, $350 daily loss, $150 aggregate open risk, one open position and two trades per day.

Planned SignalStack exits record exact entry/exit timestamps and expected per-share movement for the configurable 30-second and 10-cent rules. Emergency behavior is not assumed when current policy interpretation is uncertain.
