from datetime import datetime, timezone, timedelta
from rollagent.engine import age_seconds, iso

def test_age_seconds_nonneg():
    past = iso(datetime.now(timezone.utc) - timedelta(seconds=30))
    assert age_seconds(past) >= 0
