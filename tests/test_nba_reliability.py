from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.adapters.nba.reliability import (
    AsyncRateLimiter,
    ReliableSourceRunner,
    RetryConfig,
    TransientSourceError,
)
from app.core.clock import Clock


class AdvancingClock(Clock):
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 3, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


async def test_runner_retries_transient_errors() -> None:
    clock = AdvancingClock()
    sleeps: list[float] = []

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    calls = 0

    def fetch() -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientSourceError("temporary")
        return {"ok": True}

    runner = ReliableSourceRunner(
        retry_config=RetryConfig(max_attempts=3, base_backoff_seconds=0.1),
        min_interval_seconds=0,
        clock=clock,
        sleeper=sleeper,
    )

    result = await runner.run(
        source="test",
        fetch=fetch,
        parse=lambda raw: (raw, []),
    )

    assert result.status == "success"
    assert result.data == {"ok": True}
    assert calls == 3
    assert sleeps == [0.1, 0.2]
    assert len(result.warnings) == 2


async def test_runner_does_not_retry_permanent_errors() -> None:
    calls = 0
    runner = ReliableSourceRunner(min_interval_seconds=0)

    def fetch() -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise ValueError("bad request")

    result = await runner.run(
        source="test",
        fetch=fetch,
        parse=lambda raw: (raw, []),
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.transient is False
    assert result.error.attempt_count == 1
    assert calls == 1


async def test_rate_limiter_spaces_calls_with_injected_sleeper() -> None:
    clock = AdvancingClock()
    sleeps: list[float] = []

    async def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    limiter = AsyncRateLimiter(
        min_interval_seconds=1.5,
        clock=clock,
        sleeper=sleeper,
    )

    await limiter.wait()
    clock.advance(0.5)
    await limiter.wait()

    assert sleeps == [1.0]


async def test_health_check_returns_status_latency_and_shape_hash() -> None:
    runner = ReliableSourceRunner(min_interval_seconds=0)

    async def probe():
        return await runner.run(
            source="test",
            fetch=lambda: {"items": [{"id": 1, "name": "A"}]},
            parse=lambda raw: ([raw], []),
        )

    health = await runner.health_check(source="test", probe=probe, sample_entity="x")

    assert health.source == "test"
    assert health.status == "success"
    assert health.latency_ms >= 0
    assert health.sample_entity == "x"
    assert health.response_shape_hash is not None
