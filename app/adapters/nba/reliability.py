from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar

import requests

from app.adapters.nba.types import (
    SourceError,
    SourceHealthCheck,
    SourceResult,
)
from app.core.clock import Clock, SystemClock

T = TypeVar("T")
RawPayload = object
Parser = Callable[[RawPayload], tuple[T, list[str]]]
Fetcher = Callable[[], RawPayload]
Sleeper = Callable[[float], Awaitable[None]]


class TransientSourceError(Exception):
    pass


class PermanentSourceError(Exception):
    pass


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 2.0


class AsyncRateLimiter:
    def __init__(
        self,
        *,
        min_interval_seconds: float,
        clock: Clock | None = None,
        sleeper: Sleeper | None = None,
    ) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock or SystemClock()
        self._sleeper = sleeper or asyncio.sleep
        self._last_started_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self._min_interval_seconds <= 0:
            return

        async with self._lock:
            now = self._clock.now()
            if self._last_started_at is not None:
                elapsed = (now - self._last_started_at).total_seconds()
                remaining = self._min_interval_seconds - elapsed
                if remaining > 0:
                    await self._sleeper(remaining)
                    now = self._clock.now()
            self._last_started_at = now


class ReliableSourceRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        retry_config: RetryConfig | None = None,
        min_interval_seconds: float = 0.6,
        clock: Clock | None = None,
        sleeper: Sleeper | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retry_config = retry_config or RetryConfig()
        self._clock = clock or SystemClock()
        self._sleeper = sleeper or asyncio.sleep
        self._rate_limiter = rate_limiter or AsyncRateLimiter(
            min_interval_seconds=min_interval_seconds,
            clock=self._clock,
            sleeper=self._sleeper,
        )

    async def run(
        self,
        *,
        source: str,
        fetch: Fetcher,
        parse: Parser[T],
    ) -> SourceResult[T]:
        warnings: list[str] = []
        raw_payload: RawPayload | None = None
        last_error: BaseException | None = None
        attempts = self.retry_config.max_attempts

        for attempt in range(1, attempts + 1):
            await self._rate_limiter.wait()
            try:
                raw_payload = await asyncio.wait_for(
                    asyncio.to_thread(fetch),
                    timeout=self.timeout_seconds,
                )
                data, parse_warnings = parse(raw_payload)
                return SourceResult[T](
                    source=source,
                    fetched_at=self._clock.now(),
                    status="success",
                    data=data,
                    warnings=[*warnings, *parse_warnings],
                    raw_payload=raw_payload,
                )
            except Exception as exc:
                last_error = exc
                transient = is_transient_error(exc)
                if not transient or attempt >= attempts:
                    return SourceResult[T](
                        source=source,
                        fetched_at=self._clock.now(),
                        status="error",
                        data=None,
                        warnings=warnings,
                        raw_payload=raw_payload,
                        error=SourceError(
                            type=type(exc).__name__,
                            message=str(exc),
                            transient=transient,
                            attempt_count=attempt,
                        ),
                    )

                warnings.append(
                    f"transient {type(exc).__name__} on attempt {attempt}: {exc}"
                )
                await self._sleeper(self._backoff_seconds(attempt))

        exc = last_error or RuntimeError("source call failed without an exception")
        return SourceResult[T](
            source=source,
            fetched_at=self._clock.now(),
            status="error",
            error=SourceError(
                type=type(exc).__name__,
                message=str(exc),
                transient=is_transient_error(exc),
                attempt_count=attempts,
            ),
        )

    async def health_check(
        self,
        *,
        source: str,
        probe: Callable[[], Awaitable[SourceResult[object]]],
        sample_entity: str | None = None,
    ) -> SourceHealthCheck:
        start = time.perf_counter()
        result = await probe()
        latency_ms = (time.perf_counter() - start) * 1000
        shape_hash = (
            response_shape_hash(result.raw_payload) if result.raw_payload else None
        )
        return SourceHealthCheck(
            source=source,
            checked_at=self._clock.now(),
            status=result.status,
            latency_ms=latency_ms,
            error_message=result.error.message if result.error else None,
            sample_entity=sample_entity,
            response_shape_hash=shape_hash,
        )

    def _backoff_seconds(self, attempt: int) -> float:
        return min(
            self.retry_config.base_backoff_seconds * (2 ** (attempt - 1)),
            self.retry_config.max_backoff_seconds,
        )


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, TransientSourceError | TimeoutError | asyncio.TimeoutError):
        return True
    if isinstance(exc, PermanentSourceError | ValueError):
        return False
    if isinstance(exc, requests.Timeout | requests.ConnectionError):
        return True
    if isinstance(exc, requests.HTTPError):
        status_code = getattr(exc.response, "status_code", None)
        return status_code in {408, 429, 500, 502, 503, 504}

    text = str(exc).lower()
    transient_terms = (
        "timed out",
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "too many requests",
        "rate limit",
    )
    return any(term in text for term in transient_terms)


def response_shape_hash(payload: object) -> str:
    shape = _shape(payload)
    encoded = json.dumps(shape, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _shape(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__
