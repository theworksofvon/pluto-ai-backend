from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings, get_settings
from app.db.models import LlmCallLog, Team
from app.db.session import dispose_engines, get_sessionmaker
from app.db.uow import UnitOfWork
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
def migrated_sessionmaker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> async_sessionmaker[AsyncSession]:
    db_path = tmp_path / "repositories.db"
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


async def seed_graph(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    as_of = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    game_day = date(2026, 1, 14)
    prior_day = date(2026, 1, 12)
    future_day = date(2026, 1, 16)

    async with UnitOfWork(sessionmaker) as uow:
        bos = await uow.teams.upsert_by_external_id(
            "1610612738",
            abbreviation="BOS",
            name="Celtics",
            city="Boston",
            conference="East",
            division="Atlantic",
        )
        same_bos = await uow.teams.upsert_by_external_id(
            "1610612738",
            abbreviation="BOS",
            name="Boston Celtics",
            city="Boston",
            conference="East",
            division="Atlantic",
        )
        lal = await uow.teams.upsert_by_external_id(
            "1610612747",
            abbreviation="LAL",
            name="Lakers",
            city="Los Angeles",
            conference="West",
            division="Pacific",
        )
        lebron = await uow.players.upsert_by_external_id(
            "2544",
            team_id=lal.id,
            first_name="LeBron",
            last_name="James",
            full_name="LeBron James",
            position="F",
            active=True,
        )
        davis = await uow.players.upsert_by_external_id(
            "203076",
            team_id=lal.id,
            first_name="Anthony",
            last_name="Davis",
            full_name="Anthony Davis",
            position="F-C",
            active=True,
        )
        final_game = await uow.games.upsert_by_external_id(
            "0022500001",
            home_team_id=bos.id,
            away_team_id=lal.id,
            game_date=game_day,
            start_time=as_of,
            season="2025-26",
            status="final",
        )
        prior_game = await uow.games.upsert_by_external_id(
            "0022500000",
            home_team_id=lal.id,
            away_team_id=bos.id,
            game_date=prior_day,
            start_time=as_of - timedelta(days=2),
            season="2025-26",
            status="final",
        )
        future_game = await uow.games.upsert_by_external_id(
            "0022500002",
            home_team_id=lal.id,
            away_team_id=bos.id,
            game_date=future_day,
            start_time=as_of + timedelta(days=1),
            season="2025-26",
            status="scheduled",
        )
        await uow.commit()

    return {
        "as_of": as_of,
        "game_day": game_day,
        "prior_day": prior_day,
        "future_day": future_day,
        "bos_id": bos.id,
        "same_bos_id": same_bos.id,
        "lal_id": lal.id,
        "lebron_id": lebron.id,
        "davis_id": davis.id,
        "final_game_id": final_game.id,
        "prior_game_id": prior_game.id,
        "future_game_id": future_game.id,
    }


async def test_unit_of_work_rolls_back_on_exception(
    migrated_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with UnitOfWork(migrated_sessionmaker) as uow:
            await uow.teams.upsert_by_external_id(
                "rollback-team",
                abbreviation="RBK",
                name="Rollback",
                city=None,
                conference=None,
                division=None,
            )
            raise RuntimeError("boom")

    async with migrated_sessionmaker() as session:
        team = await session.scalar(
            select(Team).where(Team.external_team_id == "rollback-team")
        )

    assert team is None


async def test_core_repositories_and_game_logs(
    migrated_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    ids = await seed_graph(migrated_sessionmaker)

    async with UnitOfWork(migrated_sessionmaker) as uow:
        all_teams = await uow.teams.list_all()
        bos = await uow.teams.get_by_abbreviation("BOS")
        lebron = await uow.players.get(ids["lebron_id"])
        lebron_by_name = await uow.players.get_by_full_name("lebron james")
        lakers_players = await uow.players.list_by_team(ids["lal_id"])
        final_game = await uow.games.get_by_external_id("0022500001")
        games_by_date = await uow.games.list_by_date(ids["game_day"])
        game_with_teams = await uow.games.get_with_teams(ids["final_game_id"])

        player_logs = await uow.player_game_logs.bulk_upsert(
            [
                {
                    "player_id": ids["lebron_id"],
                    "team_id": ids["lal_id"],
                    "game_id": ids["prior_game_id"],
                    "matchup": "LAL vs BOS",
                    "is_home": True,
                    "pts": 31.0,
                    "minutes": 36.0,
                    "fga": 20.0,
                    "fg_pct": 0.55,
                    "reb": 8.0,
                    "ast": 9.0,
                    "fg3_pct": 0.4,
                    "ft_pct": 0.75,
                    "plus_minus": 7.0,
                }
            ]
        )
        player_logs_again = await uow.player_game_logs.bulk_upsert(
            [
                {
                    "player_id": ids["lebron_id"],
                    "team_id": ids["lal_id"],
                    "game_id": ids["prior_game_id"],
                    "matchup": "LAL vs BOS",
                    "is_home": True,
                    "pts": 33.0,
                    "minutes": 37.0,
                    "fga": 21.0,
                    "fg_pct": 0.57,
                    "reb": 8.0,
                    "ast": 9.0,
                    "fg3_pct": 0.4,
                    "ft_pct": 0.75,
                    "plus_minus": 8.0,
                }
            ]
        )
        team_logs = await uow.team_game_logs.bulk_upsert(
            [
                {
                    "team_id": ids["lal_id"],
                    "game_id": ids["prior_game_id"],
                    "matchup": "LAL vs BOS",
                    "is_home": True,
                    "pts": 122.0,
                    "minutes": 240.0,
                    "fga": 88.0,
                    "fg_pct": 0.49,
                    "reb": 44.0,
                    "ast": 28.0,
                    "fg3_pct": 0.38,
                    "ft_pct": 0.82,
                    "plus_minus": 5.0,
                }
            ]
        )
        team_logs_again = await uow.team_game_logs.bulk_upsert(
            [
                {
                    "team_id": ids["lal_id"],
                    "game_id": ids["prior_game_id"],
                    "matchup": "LAL vs BOS",
                    "is_home": True,
                    "pts": 125.0,
                    "minutes": 240.0,
                    "fga": 88.0,
                    "fg_pct": 0.5,
                    "reb": 44.0,
                    "ast": 28.0,
                    "fg3_pct": 0.38,
                    "ft_pct": 0.82,
                    "plus_minus": 8.0,
                }
            ]
        )
        recent_player_logs = await uow.player_game_logs.list_for_player_before(
            ids["lebron_id"],
            ids["game_day"],
            limit=5,
        )
        recent_team_logs = await uow.team_game_logs.list_for_team_before(
            ids["lal_id"],
            ids["game_day"],
            limit=5,
        )
        await uow.commit()

    assert ids["bos_id"] == ids["same_bos_id"]
    assert [team.abbreviation for team in all_teams] == ["BOS", "LAL"]
    assert bos is not None
    assert bos.name == "Boston Celtics"
    assert lebron is not None
    assert lebron_by_name is not None
    assert lebron_by_name.id == lebron.id
    assert [player.full_name for player in lakers_players] == [
        "Anthony Davis",
        "LeBron James",
    ]
    assert final_game is not None
    assert games_by_date == [final_game]
    assert game_with_teams is not None
    assert game_with_teams.home_team.abbreviation == "BOS"
    assert game_with_teams.away_team.abbreviation == "LAL"
    assert player_logs[0].id == player_logs_again[0].id
    assert recent_player_logs[0].pts == 33.0
    assert team_logs[0].id == team_logs_again[0].id
    assert recent_team_logs[0].pts == 125.0


async def test_snapshots_versions_runs_and_health_repositories(
    migrated_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    ids = await seed_graph(migrated_sessionmaker)
    as_of = ids["as_of"]

    async with UnitOfWork(migrated_sessionmaker) as uow:
        await uow.prop_lines.add_snapshot(
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            line_value=24.5,
            source="book",
            fetched_at=as_of - timedelta(minutes=10),
            stale=False,
        )
        latest_line = await uow.prop_lines.add_snapshot(
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            line_value=25.5,
            source="book",
            fetched_at=as_of,
            stale=False,
        )
        latest_rebounds = await uow.prop_lines.add_snapshot(
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="REB",
            line_value=7.5,
            source="book",
            fetched_at=as_of,
            stale=False,
        )
        latest_for_stat = await uow.prop_lines.latest_for_player_stat(
            ids["lebron_id"],
            "PTS",
            ids["final_game_id"],
        )
        latest_for_game = await uow.prop_lines.list_latest_for_game(
            ids["final_game_id"]
        )

        older_features = await uow.feature_snapshots.add(
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            as_of=as_of - timedelta(hours=1),
            feature_version="v1",
            features={"minutes_avg": 35.1},
        )
        newer_features = await uow.feature_snapshots.add(
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            as_of=as_of,
            feature_version="v1",
            features={"minutes_avg": 36.2},
        )
        exact_features = await uow.feature_snapshots.get_exact(
            ids["lebron_id"],
            ids["final_game_id"],
            "PTS",
            older_features.as_of,
            "v1",
        )
        latest_features = await uow.feature_snapshots.latest_for(
            ids["lebron_id"],
            ids["final_game_id"],
            "PTS",
        )

        model_v1 = await uow.model_versions.add(
            name="baseline",
            version="1",
            artifact_path="models/baseline-1.pkl",
            feature_version="v1",
            training_metadata={"rows": 100},
            metrics={"mae": 4.2},
        )
        model_v2 = await uow.model_versions.add(
            name="baseline",
            version="2",
            artifact_path="models/baseline-2.pkl",
            feature_version="v1",
            training_metadata={"rows": 200},
            metrics={"mae": 4.0},
        )
        prompt_v1 = await uow.prompt_versions.add(
            name="props",
            version="1",
            template="Predict",
            schema={"type": "object"},
        )
        prompt_v2 = await uow.prompt_versions.add(
            name="props",
            version="2",
            template="Predict better",
            schema={"type": "object"},
        )
        run = await uow.prediction_runs.create(
            model_version_id=model_v2.id,
            prompt_version_id=prompt_v2.id,
            feature_snapshot_id=newer_features.id,
            provider="openai",
            llm_model="gpt-test",
            context_hash="ctx-1",
            data_quality={"ok": True},
            status="running",
            started_at=as_of,
        )
        finished_run = await uow.prediction_runs.finish(
            run.id,
            "success",
            finished_at=as_of + timedelta(seconds=5),
        )
        job_success = await uow.job_runs.start("ingest", detail={"date": "today"})
        await uow.job_runs.finish_success(job_success.id, detail={"rows": 3})
        job_failure = await uow.job_runs.start("predict")
        await uow.job_runs.finish_failure(job_failure.id, "failed")
        recent_jobs = await uow.job_runs.list_recent(limit=5)

        await uow.raw_source_snapshots.add(
            source="nba",
            endpoint="/schedule",
            params={"date": "2026-01-14"},
            fetched_at=as_of - timedelta(minutes=5),
            status="ok",
            raw_json={"old": True},
            raw_hash="old",
        )
        latest_raw = await uow.raw_source_snapshots.add(
            source="nba",
            endpoint="/schedule",
            params={"date": "2026-01-14"},
            fetched_at=as_of,
            status="ok",
            raw_json={"new": True},
            raw_hash="new",
        )
        latest_raw_lookup = await uow.raw_source_snapshots.latest_for(
            "nba",
            "/schedule",
        )
        await uow.source_health_checks.add(
            source_name="nba",
            checked_at=as_of - timedelta(minutes=5),
            status="degraded",
            latency_ms=700,
            error_message="slow",
            sample_entity="schedule",
            response_shape_hash="shape-1",
        )
        latest_health = await uow.source_health_checks.add(
            source_name="nba",
            checked_at=as_of,
            status="ok",
            latency_ms=100,
            error_message=None,
            sample_entity="schedule",
            response_shape_hash="shape-2",
        )
        health_per_source = await uow.source_health_checks.latest_per_source()
        llm_log = await uow.llm_call_logs.add(
            provider="openai",
            model="gpt-test",
            prompt_version_id=prompt_v2.id,
            request_metadata={"request": 1},
            response_metadata={"response": 1},
            tokens_in=10,
            tokens_out=20,
            latency_ms=300,
            validation_ok=True,
        )
        model_by_version = await uow.model_versions.get_by_name_version(
            "baseline",
            "1",
        )
        latest_model = await uow.model_versions.latest_by_name("baseline")
        prompt_by_version = await uow.prompt_versions.get_by_name_version(
            "props",
            "1",
        )
        latest_prompt = await uow.prompt_versions.latest_by_name("props")
        await uow.commit()

    async with migrated_sessionmaker() as session:
        persisted_llm_log = await session.get(LlmCallLog, llm_log.id)

    assert latest_for_stat is not None
    assert latest_for_stat.id == latest_line.id
    assert {line.id for line in latest_for_game} == {
        latest_line.id,
        latest_rebounds.id,
    }
    assert exact_features is not None
    assert exact_features.id == older_features.id
    assert latest_features is not None
    assert latest_features.id == newer_features.id
    assert model_by_version is not None
    assert model_by_version.id == model_v1.id
    assert latest_model is not None
    assert latest_model.id == model_v2.id
    assert prompt_by_version is not None
    assert prompt_by_version.id == prompt_v1.id
    assert latest_prompt is not None
    assert latest_prompt.id == prompt_v2.id
    assert finished_run is not None
    assert finished_run.status == "success"
    assert [job.status for job in recent_jobs] == ["failure", "success"]
    assert latest_raw_lookup is not None
    assert latest_raw_lookup.id == latest_raw.id
    assert health_per_source == [latest_health]
    assert persisted_llm_log is not None
    assert persisted_llm_log.validation_ok is True


async def test_prediction_repositories_search_current_and_evaluations(
    migrated_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    ids = await seed_graph(migrated_sessionmaker)
    as_of = ids["as_of"]

    async with UnitOfWork(migrated_sessionmaker) as uow:
        model = await uow.model_versions.add(
            name="baseline",
            version="1",
            artifact_path="models/baseline-1.pkl",
            feature_version="v1",
            training_metadata=None,
            metrics=None,
        )
        prompt = await uow.prompt_versions.add(
            name="props",
            version="1",
            template="Predict",
            schema=None,
        )
        run = await uow.prediction_runs.create(
            model_version_id=model.id,
            prompt_version_id=prompt.id,
            feature_snapshot_id=None,
            provider="openai",
            llm_model="gpt-test",
            context_hash="ctx-1",
            data_quality=None,
            status="success",
            started_at=as_of,
            finished_at=as_of,
        )
        old_prediction = await uow.player_predictions.create_current(
            prediction_run_id=run.id,
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            line=25.5,
            base_prediction=26.0,
            final_prediction=27.0,
            predicted_range_low=24.0,
            predicted_range_high=30.0,
            over_under_recommendation="over",
            confidence=0.62,
            raw_llm_output={"pick": "over"},
            explanation="old",
        )
        current_prediction = await uow.player_predictions.create_current(
            prediction_run_id=run.id,
            player_id=ids["lebron_id"],
            game_id=ids["final_game_id"],
            stat_type="PTS",
            line=25.5,
            base_prediction=27.0,
            final_prediction=28.0,
            predicted_range_low=25.0,
            predicted_range_high=31.0,
            over_under_recommendation="over",
            confidence=0.91,
            raw_llm_output={"pick": "over"},
            explanation="current",
        )
        other_prediction = await uow.player_predictions.create_current(
            prediction_run_id=run.id,
            player_id=ids["davis_id"],
            game_id=ids["future_game_id"],
            stat_type="REB",
            line=11.5,
            base_prediction=10.0,
            final_prediction=10.5,
            predicted_range_low=8.0,
            predicted_range_high=13.0,
            over_under_recommendation="under",
            confidence=0.55,
            raw_llm_output={"pick": "under"},
            explanation="future",
        )
        old_after_flip = await uow.player_predictions.get(old_prediction.id)
        current_by_get = await uow.player_predictions.get(current_prediction.id)
        default_current = await uow.player_predictions.search()
        include_not_current = await uow.player_predictions.search(
            only_current=False,
            limit=10,
        )
        by_game_date = await uow.player_predictions.search(
            game_date=ids["game_day"]
        )
        by_game_id = await uow.player_predictions.search(
            game_id=ids["final_game_id"]
        )
        by_player_id = await uow.player_predictions.search(
            player_id=ids["lebron_id"]
        )
        by_player_name = await uow.player_predictions.search(player_name="bron")
        by_stat_type = await uow.player_predictions.search(stat_type="REB")
        by_confidence = await uow.player_predictions.search(min_confidence=0.9)
        paged = await uow.player_predictions.search(
            only_current=False,
            limit=1,
            offset=1,
        )
        await uow.prediction_evaluations.add_for_prediction(
            old_prediction.id,
            actual_value=29.0,
            error=2.0,
            line_hit=True,
            over_under_correct=True,
            evaluated_at=as_of,
        )
        unevaluated = await uow.prediction_evaluations.list_unevaluated_predictions(
            ids["game_day"]
        )
        await uow.commit()

    assert old_after_flip is not None
    assert old_after_flip.is_current is False
    assert current_by_get is not None
    assert current_by_get.is_current is True
    assert [prediction.id for prediction in default_current] == [
        other_prediction.id,
        current_prediction.id,
    ]
    assert {prediction.id for prediction in include_not_current} == {
        old_prediction.id,
        current_prediction.id,
        other_prediction.id,
    }
    assert [prediction.id for prediction in by_game_date] == [current_prediction.id]
    assert [prediction.id for prediction in by_game_id] == [current_prediction.id]
    assert [prediction.id for prediction in by_player_id] == [current_prediction.id]
    assert [prediction.id for prediction in by_player_name] == [current_prediction.id]
    assert [prediction.id for prediction in by_stat_type] == [other_prediction.id]
    assert [prediction.id for prediction in by_confidence] == [current_prediction.id]
    assert len(paged) == 1
    assert [prediction.id for prediction in unevaluated] == [current_prediction.id]
