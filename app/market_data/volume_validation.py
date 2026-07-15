import math
from datetime import datetime

from app.core.time_utils import age_seconds


def validate_previous_minute_volume(volume, candle_time, proposed_quantity: int, allowed_pct: float = 5, max_age_seconds: int = 180) -> dict:
    result = {"reference_candle_timestamp": str(candle_time) if candle_time else None, "reference_candle_volume": volume, "allowed_percentage": allowed_pct, "maximum_shares_allowed": 0, "proposed_shares": proposed_quantity, "passed": False, "reason": ""}
    if volume is None or candle_time is None: result["reason"] = "prior complete one-minute volume is unavailable"; return result
    try: timestamp = datetime.fromisoformat(str(candle_time).replace("Z", "+00:00")); volume = float(volume)
    except (TypeError, ValueError): result["reason"] = "one-minute volume data is invalid"; return result
    age = age_seconds(timestamp)
    if age < 0 or age > max_age_seconds: result["reason"] = "one-minute volume data is stale or future-dated"; return result
    maximum = math.floor(volume * allowed_pct / 100); result["maximum_shares_allowed"] = maximum
    result["passed"] = maximum >= 1 and proposed_quantity <= maximum
    result["reason"] = "passed" if result["passed"] else "position exceeds the volume rule"
    return result
