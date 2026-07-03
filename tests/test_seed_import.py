from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.core.clock import FixedClock
from app.core.config import Settings, get_settings
from app.data.ingest import import_seed_csv
from app.db.models import Game, JobRun, Player, PlayerGameLog, Team
from app.db.session import dispose_engines, get_sessionmaker
from app.db.uow import UnitOfWork
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def seed_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> async_sessionmaker[AsyncSession]:
    db_path = tmp_path / "seed.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    command.upgrade(Config(str(Path("alembic.ini").resolve())), "head")

    get_settings.cache_clear()
    return get_sessionmaker(Settings(DATABASE_URL=database_url))


@pytest.fixture(autouse=True)
async def _dispose_engines() -> None:
    yield
    await dispose_engines()


async def test_import_seed_csv_is_idempotent(
    seed_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    csv_path = Path("tests/fixtures/pluto_training_dataset_seed_sample.csv")
    clock = FixedClock(datetime(2026, 1, 1, 12, tzinfo=UTC))

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(seed_sessionmaker)

    first = await import_seed_csv(csv_path, uow_factory=uow_factory, clock=clock)
    second = await import_seed_csv(csv_path, uow_factory=uow_factory, clock=clock)

    assert first.detail["rows_read"] == 3
    assert first.detail["logs_upserted"] == 3
    assert second.detail["logs_upserted"] == 3
    assert first.detail["warnings"] == []
    assert await _count(seed_sessionmaker, Team) == 4
    assert await _count(seed_sessionmaker, Player) == 1
    assert await _count(seed_sessionmaker, Game) == 3
    assert await _count(seed_sessionmaker, PlayerGameLog) == 3
    assert await _count(seed_sessionmaker, JobRun) == 2

    async with seed_sessionmaker() as session:
        log = await session.scalar(select(PlayerGameLog).limit(1))
        game = await session.scalar(
            select(Game).where(Game.external_game_id == "0022200033")
        )

    assert log is not None
    assert log.minutes is None
    assert game is not None
    assert game.season == "2022-23"


async def _count(
    sessionmaker: async_sessionmaker[AsyncSession],
    model: type[object],
) -> int:
    async with sessionmaker() as session:
        return await session.scalar(select(func.count()).select_from(model)) or 0
