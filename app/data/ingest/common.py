from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, AsyncContextManager, Protocol

from pydantic import BaseModel

from app.adapters.nba.types import SourceError, SourceResult
from app.core.clock import Clock, SystemClock
from app.db.uow import UnitOfWork


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> AsyncContextManager[UnitOfWork]: ...


@dataclass
class IngestJobResult:
    job_run_id: int
    job_name: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


class IngestSourceError(RuntimeError):
    def __init__(self, job_name: str, source_error: SourceError | None) -> None:
        self.job_name = job_name
        self.source_error = source_error
        message = (
            source_error.message
            if source_error is not None
            else "Source returned an error without details"
        )
        super().__init__(f"{job_name} failed: {message}")


def resolve_clock(clock: Clock | None) -> Clock:
    return clock or SystemClock()


def resolve_uow_factory(
    uow_factory: UnitOfWorkFactory | None,
) -> UnitOfWorkFactory:
    return uow_factory or UnitOfWork


async def start_job(
    uow_factory: UnitOfWorkFactory,
    job_name: str,
    detail: dict[str, Any],
    clock: Clock,
) -> int:
    async with uow_factory() as uow:
        job = await uow.job_runs.start(
            job_name,
            detail=detail,
            started_at=clock.now(),
        )
        await uow.commit()
        return job.id


async def finish_success(
    uow_factory: UnitOfWorkFactory,
    job_run_id: int,
    detail: dict[str, Any],
    clock: Clock,
) -> None:
    async with uow_factory() as uow:
        await uow.job_runs.finish_success(
            job_run_id,
            detail=detail,
            finished_at=clock.now(),
        )
        await uow.commit()


async def finish_failure(
    uow_factory: UnitOfWorkFactory,
    job_run_id: int,
    error: str,
    detail: dict[str, Any],
    clock: Clock,
) -> None:
    async with uow_factory() as uow:
        await uow.job_runs.finish_failure(
            job_run_id,
            error,
            detail=detail,
            finished_at=clock.now(),
        )
        await uow.commit()


def source_error_detail(error: SourceError | None) -> dict[str, Any] | None:
    if error is None:
        return None
    return error.model_dump(mode="json")


def source_error_message(error: SourceError | None) -> str:
    if error is None:
        return "Source returned an error without details"
    return f"{error.type}: {error.message}"


async def add_raw_source_snapshot(
    uow: UnitOfWork,
    *,
    result: SourceResult[Any],
    endpoint: str,
    params: dict[str, Any],
) -> None:
    raw_json = _result_payload(result)
    await uow.raw_source_snapshots.add(
        source=result.source,
        endpoint=endpoint,
        params=params,
        fetched_at=result.fetched_at,
        status=result.status,
        raw_json=raw_json,
        raw_hash=hash_payload(raw_json),
    )


def hash_payload(payload: Any) -> str:
    body = json.dumps(_jsonable(payload), sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _result_payload(result: SourceResult[Any]) -> dict[str, Any] | list[Any]:
    payload = result.raw_payload if result.raw_payload is not None else result.data
    jsonable = _jsonable(payload)
    if isinstance(jsonable, dict | list):
        return jsonable
    return {"value": jsonable}


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
