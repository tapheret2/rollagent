from datetime import datetime, timedelta, timezone
from rollagent.engine import is_past_finalize, seconds_until_finalize

def test_seconds_until_finalize():
    now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    future = (now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    past = (now - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    assert abs(seconds_until_finalize(future, now=now) - 30) < 1e-6
    assert is_past_finalize(past, now=now) is True
    assert is_past_finalize(future, now=now) is False
