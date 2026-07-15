def retry_delay(attempt: int, enabled: bool, max_retries: int, base_seconds: int) -> int | None:
    if not enabled or attempt >= max_retries: return None
    return max(30, base_seconds) * (2 ** attempt)

