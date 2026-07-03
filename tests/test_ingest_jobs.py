from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.adapters.nba.types import (
    NbaGameRow,
    NbaPlayerGameLogRow,
    SourceError,
    SourceResult,
)
from app.core.clock import FixedClock
from app.core.config import Settings, get_settings
from app.data.ingest import IngestSourceError, ingest_player_logs, ingest_schedule
from app.db.models import Game, JobRun, Player, PlayerGameLog, RawSourceSnapshot, Team
from app.db.session import dispose_engines, get_sessionmaker
from app.db.uow import UnitOfWork
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def ingest_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> async_sessionmaker[AsyncSession]:
    db_path = tmp_path / "ingest.db"
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


class FakeScheduleSource:
    def __init__(self, result: SourceResult[list[NbaGameRow]]) -> None:
        self.result = result
        self.calls: list[date] = []

    async def games_for_date(
        self,
        game_date: date,
    ) -> SourceResult[list[NbaGameRow]]:
        self.calls.append(game_date)
        return self.result


class FakePlayerLogSource:
    def __init__(self, result: SourceResult[list[NbaPlayerGameLogRow]]) -> None:
        self.result = result
        self.league_calls = 0
        self.player_calls: list[str | int] = []

    async def get_league_player_game_logs(
        self,
        *,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]:
        self.league_calls += 1
        return self.result

    async def get_player_game_logs(
        self,
        *,
        player_id: str | int,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]:
        self.player_calls.append(player_id)
        return self.result


async def test_ingest_schedule_records_snapshot_job_and_is_idempotent(
    ingest_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    fetched_at = datetime(2026, 1, 1, 12, tzinfo=UTC)
    source = FakeScheduleSource(
        SourceResult[list[NbaGameRow]](
            source="fake.schedule",
            fetched_at=fetched_at,
            status="success",
            data=[
                NbaGameRow(
                    external_game_id="0022500001",
                    game_date=date(2026, 4, 15),
                    season="2025-26",
                    status="scheduled",
                    start_time=fetched_at,
                    home_external_team_id="1610612738",
                    away_external_team_id="1610612747",
                    home_team_abbreviation="BOS",
                    away_team_abbreviation="LAL",
                    home_team_name="Boston Celtics",
                    away_team_name="Los Angeles Lakers",
                )
            ],
            warnings=["schedule warning"],
            raw_payload={"games": [{"gameId": "0022500001"}]},
        )
    )
    clock = FixedClock(fetched_at)

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(ingest_sessionmaker)

    first = await ingest_schedule(
        date(2026, 4, 15),
        source=source,
        uow_factory=uow_factory,
        clock=clock,
    )
    second = await ingest_schedule(
        date(2026, 4, 15),
        source=source,
        uow_factory=uow_factory,
        clock=clock,
    )

    assert first.detail["games_upserted"] == 1
    assert second.detail["games_upserted"] == 1
    assert "schedule warning" in second.detail["warnings"]
    assert source.calls == [date(2026, 4, 15), date(2026, 4, 15)]
    assert await _count(ingest_sessionmaker, Team) == 2
    assert await _count(ingest_sessionmaker, Game) == 1
    assert await _count(ingest_sessionmaker, RawSourceSnapshot) == 2
    assert await _count(ingest_sessionmaker, JobRun) == 2


async def test_ingest_schedule_records_source_failure(
    ingest_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    fetched_at = datetime(2026, 1, 1, 12, tzinfo=UTC)
    source = FakeScheduleSource(
        SourceResult[list[NbaGameRow]](
            source="fake.schedule",
            fetched_at=fetched_at,
            status="error",
            raw_payload={"error": True},
            error=SourceError(
                type="http_error",
                message="upstream unavailable",
                transient=True,
                attempt_count=2,
            ),
        )
    )

    with pytest.raises(IngestSourceError):
        await ingest_schedule(
            date(2026, 4, 15),
            source=source,
            uow_factory=lambda: UnitOfWork(ingest_sessionmaker),
            clock=FixedClock(fetched_at),
    )

    async with ingest_sessionmaker() as session:
        job = await session.scalar(
            select(JobRun).where(JobRun.job_name == "ingest.schedule")
        )

    assert job is not None
    assert job.status == "failure"
    assert job.error == "http_error: upstream unavailable"
    assert await _count(ingest_sessionmaker, RawSourceSnapshot) == 1


async def test_ingest_player_logs_skips_bad_rows_and_is_idempotent(
    ingest_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    fetched_at = datetime(2026, 1, 1, 12, tzinfo=UTC)
    rows = [
        NbaPlayerGameLogRow(
            external_player_id="2544",
            player_name="LeBron James",
            external_team_id="1610612747",
            external_game_id="0022500002",
            game_date=date(2025, 10, 22),
            season="2025-26",
            matchup="LAL @ GSW",
            is_home=False,
            pts=27,
            minutes=34,
            fga=20,
            fg_pct=0.5,
            reb=8,
            ast=9,
            fg3_pct=0.4,
            ft_pct=0.75,
            plus_minus=5,
            team_abbreviation="LAL",
            opponent_team_abbreviation="GSW",
        ),
        NbaPlayerGameLogRow(
            external_game_id="0022500003",
            game_date=date(2025, 10, 23),
            season="2025-26",
            matchup="BOS vs. NYK",
            is_home=True,
            team_abbreviation="BOS",
            opponent_team_abbreviation="NYK",
        ),
    ]
    source = FakePlayerLogSource(
        SourceResult[list[NbaPlayerGameLogRow]](
            source="fake.player_logs",
            fetched_at=fetched_at,
            status="success",
            data=rows,
            raw_payload={"rows": 2},
        )
    )

    def uow_factory() -> UnitOfWork:
        return UnitOfWork(ingest_sessionmaker)

    first = await ingest_player_logs(
        "2025-26",
        source=source,
        uow_factory=uow_factory,
        clock=FixedClock(fetched_at),
    )
    second = await ingest_player_logs(
        "2025-26",
        source=source,
        uow_factory=uow_factory,
        clock=FixedClock(fetched_at),
    )

    assert first.detail["logs_fetched"] == 2
    assert first.detail["logs_upserted"] == 1
    assert "missing player name and external player id" in first.detail["warnings"][0]
    assert second.detail["logs_upserted"] == 1
    assert source.league_calls == 2
    assert await _count(ingest_sessionmaker, Team) == 4
    assert await _count(ingest_sessionmaker, Player) == 1
    assert await _count(ingest_sessionmaker, Game) == 1
    assert await _count(ingest_sessionmaker, PlayerGameLog) == 1
    assert await _count(ingest_sessionmaker, RawSourceSnapshot) == 2
    assert await _count(ingest_sessionmaker, JobRun) == 2


async def _count(
    sessionmaker: async_sessionmaker[AsyncSession],
    model: type[object],
) -> int:
    async with sessionmaker() as session:
        return await session.scalar(select(func.count()).select_from(model)) or 0
