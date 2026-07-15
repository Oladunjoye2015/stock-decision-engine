from app.core.time_utils import age_seconds


def check(signal_time, max_age_seconds: int) -> dict:
    age = age_seconds(signal_time)
    return {"passed": 0 <= age <= max_age_seconds, "age_seconds": age, "reason": "fresh" if 0 <= age <= max_age_seconds else "stale or future-dated signal"}

