from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def age_seconds(value: datetime, now: datetime | None = None) -> float:
    return ((now or utc_now()) - ensure_utc(value)).total_seconds()

