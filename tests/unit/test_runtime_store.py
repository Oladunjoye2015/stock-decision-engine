from datetime import datetime, timezone

from app.database.runtime_store import _json_safe


def test_runtime_payload_is_postgres_json_safe():
    result = _json_safe({"infinite": float("inf"), "number": 2.0, "at": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    assert result == {"infinite": None, "number": 2.0, "at": "2026-01-01T00:00:00+00:00"}
