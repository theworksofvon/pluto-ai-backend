from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings, get_settings
from app.db.models import Game, Player, PlayerGameLog, PropLine, Team
from app.db.session import dispose_engines, get_sessionmaker
from sqlalchemy import select


@pytest.fixture
def migrated_database_url(monkeypatch, tmp_path) -> str:
    db_path = tmp_path / "models.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    command.upgrade(Config(str(Path("alembic.ini").resolve())), "head")

    get_settings.cache_clear()
    return database_url


@pytest.fixture(autouse=True)
async def _dispose_engines() -> None:
    yield
    await dispose_engines()


async def test_async_session_round_trips_core_model_rows(
    migrated_database_url: str,
) -> None:
    settings = Settings(DATABASE_URL=migrated_database_url)
    sessionmaker = get_sessionmaker(settings)
    start_time = datetime(2026, 1, 15, 1, 30, tzinfo=UTC)

    async with sessionmaker() as session:
        home_team = Team(
            external_team_id="1610612738",
            abbreviation="BOS",
            name="Celtics",
            city="Boston",
        )
        away_team = Team(
            external_team_id="1610612747",
            abbreviation="LAL",
            name="Lakers",
            city="Los Angeles",
        )
        session.add_all([home_team, away_team])
        await session.flush()

        player = Player(
            external_player_id="2544",
            team_id=away_team.id,
            first_name="LeBron",
            last_name="James",
            full_name="LeBron James",
            position="F",
        )
        game = Game(
            external_game_id="0022500001",
            home_team_id=home_team.id,
            away_team_id=away_team.id,
            game_date=date(2026, 1, 14),
            start_time=start_time,
            season="2025-26",
            status="scheduled",
        )
        session.add_all([player, game])
        await session.flush()

        session.add_all(
            [
                PlayerGameLog(
                    player_id=player.id,
                    team_id=away_team.id,
                    game_id=game.id,
                    matchup="LAL @ BOS",
                    is_home=False,
                    pts=28.0,
                    minutes=35.5,
                    fga=19.0,
                    fg_pct=0.526,
                    reb=8.0,
                    ast=9.0,
                    fg3_pct=0.4,
                    ft_pct=0.8,
                    plus_minus=6.0,
                ),
                PropLine(
                    player_id=player.id,
                    game_id=game.id,
                    stat_type="PTS",
                    line_value=25.5,
                    source="fixture",
                    fetched_at=start_time,
                ),
            ]
        )
        await session.commit()

    async with sessionmaker() as session:
        log = await session.scalar(
            select(PlayerGameLog).where(PlayerGameLog.matchup == "LAL @ BOS")
        )
        line = await session.scalar(
            select(PropLine).where(
                PropLine.player_id == log.player_id,
                PropLine.stat_type == "PTS",
            )
        )

    assert log is not None
    assert log.pts == 28.0
    assert line is not None
    assert line.line_value == 25.5
    assert line.stale is False
