from dataclasses import asdict, dataclass, field

from app.schemas.signals import SignalIn


@dataclass
class TechnicalGateResult:
    passed: bool
    score: float
    reason: str
    failed_checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    setup_type: str = "trend"
    trend_direction: str = "neutral"
    volatility_state: str = "normal"

    def dict(self): return asdict(self)


def evaluate(signal: SignalIn, enabled: bool = True) -> TechnicalGateResult:
    if not enabled:
        return TechnicalGateResult(True, 100, "technical gate disabled")
    i, failures, warnings, score = signal.indicators, [], [], 100.0
    side = "long" if signal.side_hint in {"long", "buy", None} else "short"
    ema20, ema50 = i.get("ema20"), i.get("ema50")
    if ema20 is not None and ema50 is not None and ((side == "long" and ema20 < ema50) or (side == "short" and ema20 > ema50)):
        failures.append("ema_alignment"); score -= 30
    rsi = i.get("rsi")
    if rsi is not None and ((side == "long" and rsi >= 75) or (side == "short" and rsi <= 25)):
        failures.append("rsi_condition"); score -= 25
    atr = i.get("atr", signal.high - signal.low)
    if not atr or atr <= 0:
        failures.append("atr_sufficiency"); score -= 30
    vol_ratio = i.get("vol_ratio")
    if vol_ratio is not None and vol_ratio < .5:
        failures.append("relative_volume"); score -= 20
    candle_range = signal.high - signal.low
    body_ratio = abs(signal.close - signal.open) / candle_range if candle_range > 0 else 0
    if body_ratio < .1: warnings.append("weak_candle_body"); score -= 10
    trend = "bullish" if ema20 and ema50 and ema20 > ema50 else "bearish" if ema20 and ema50 else "neutral"
    volatility = "high" if atr / signal.close > .08 else "low" if atr / signal.close < .003 else "normal"
    passed = not failures and score >= 60
    return TechnicalGateResult(passed, max(score, 0), "passed" if passed else ", ".join(failures), failures, warnings, "trend", trend, volatility)

