from datetime import UTC, datetime, timedelta, timezone

import pytest
from app.core.clock import FixedClock, SystemClock


def test_system_clock_returns_aware_utc_datetime() -> None:
    now = SystemClock().now()

    assert now.tzinfo is UTC


def test_fixed_clock_returns_fixed_time_in_utc() -> None:
    fixed = datetime(2026, 7, 3, 8, 30, tzinfo=timezone(timedelta(hours=-5)))

    assert FixedClock(fixed).now() == datetime(2026, 7, 3, 13, 30, tzinfo=UTC)


def test_fixed_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 7, 3, 8, 30))
