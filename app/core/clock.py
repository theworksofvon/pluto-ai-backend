from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    def __init__(self, fixed_time: datetime) -> None:
        if fixed_time.tzinfo is None:
            msg = "fixed_time must be timezone-aware"
            raise ValueError(msg)
        self._fixed_time = fixed_time.astimezone(UTC)

    def now(self) -> datetime:
        return self._fixed_time
