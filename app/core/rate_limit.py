from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from app.core.time_utils import ensure_utc, utc_now


@dataclass
class RateLimitState:
    allowed: bool
    reason: str
    sent_last_minute: int
    retry_after_seconds: float

    def as_dict(self): return asdict(self)


class RollingRateLimiter:
    def __init__(self, max_per_minute: int = 2, min_interval_seconds: int = 30, clock=utc_now):
        self.max_per_minute = min(max_per_minute, 2)
        self.min_interval_seconds = max(min_interval_seconds, 30)
        self.clock = clock

    def evaluate(self, sent_at: list[datetime]) -> RateLimitState:
        now = ensure_utc(self.clock()); recent = sorted(ensure_utc(x) for x in sent_at if ensure_utc(x) > now - timedelta(seconds=60)); waits = []
        if recent and (now-recent[-1]).total_seconds() < self.min_interval_seconds: waits.append(self.min_interval_seconds-(now-recent[-1]).total_seconds())
        if len(recent) >= self.max_per_minute: waits.append(60-(now-recent[-self.max_per_minute]).total_seconds())
        wait = max(waits, default=0)
        return RateLimitState(wait <= 0, "available" if wait <= 0 else "rate limited", len(recent), max(0, wait))

