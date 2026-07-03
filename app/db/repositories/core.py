from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, TypeVar

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import (
    FeatureSnapshot,
    Game,
    JobRun,
    LlmCallLog,
    ModelVersion,
    Player,
    PlayerGameLog,
    PlayerPrediction,
    PredictionEvaluation,
    PredictionRun,
    PromptVersion,
    PropLine,
    RawSourceSnapshot,
    SourceHealthCheck,
    Team,
    TeamGameLog,
    utc_now,
)

ModelT = TypeVar("ModelT")


@dataclass(frozen=True)
class GameWithTeams:
    game: Game
    home_team: Team
    away_team: Team


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def _upsert_one(
        self,
        model: type[ModelT],
        where_clause: ColumnElement[bool],
        values: Mapping[str, Any],
    ) -> ModelT:
        instance = await self.session.scalar(select(model).where(where_clause))
        if instance is None:
            instance = model(**values)
            self.session.add(instance)
        else:
            for field, value in values.items():
                setattr(instance, field, value)
        await self.session.flush()
        return instance


class TeamRepository(Repository):
    async def upsert_by_external_id(
        self,
        external_team_id: str,
        **values: Any,
    ) -> Team:
        values["external_team_id"] = external_team_id
        return await self._upsert_one(
            Team,
            Team.external_team_id == external_team_id,
            values,
        )

    async def get_by_abbreviation(self, abbreviation: str) -> Team | None:
        return await self.session.scalar(
            select(Team).where(Team.abbreviation == abbreviation)
        )

    async def list_all(self) -> list[Team]:
        return list(
            (
                await self.session.scalars(
                    select(Team).order_by(Team.abbreviation.asc(), Team.id.asc())
                )
            ).all()
        )


class PlayerRepository(Repository):
    async def upsert_by_external_id(
        self,
        external_player_id: str,
        **values: Any,
    ) -> Player:
        values["external_player_id"] = external_player_id
        return await self._upsert_one(
            Player,
            Player.external_player_id == external_player_id,
            values,
        )

    async def get_by_full_name(self, full_name: str) -> Player | None:
        return await self.session.scalar(
            select(Player).where(func.lower(Player.full_name) == full_name.lower())
        )

    async def get(self, player_id: int) -> Player | None:
        return await self.session.get(Player, player_id)

    async def list_by_team(self, team_id: int) -> list[Player]:
        return list(
            (
                await self.session.scalars(
                    select(Player)
                    .where(Player.team_id == team_id)
                    .order_by(Player.full_name.asc(), Player.id.asc())
                )
            ).all()
        )


class GameRepository(Repository):
    async def upsert_by_external_id(
        self,
        external_game_id: str,
        **values: Any,
    ) -> Game:
        values["external_game_id"] = external_game_id
        return await self._upsert_one(
            Game,
            Game.external_game_id == external_game_id,
            values,
        )

    async def get_by_external_id(self, external_game_id: str) -> Game | None:
        return await self.session.scalar(
            select(Game).where(Game.external_game_id == external_game_id)
        )

    async def list_by_date(self, game_date: date) -> list[Game]:
        return list(
            (
                await self.session.scalars(
                    select(Game)
                    .where(Game.game_date == game_date)
                    .order_by(Game.start_time.asc(), Game.id.asc())
                )
            ).all()
        )

    async def get_with_teams(self, game_id: int) -> GameWithTeams | None:
        home_team = aliased(Team)
        away_team = aliased(Team)
        row = (
            await self.session.execute(
                select(Game, home_team, away_team)
                .join(home_team, Game.home_team_id == home_team.id)
                .join(away_team, Game.away_team_id == away_team.id)
                .where(Game.id == game_id)
            )
        ).one_or_none()
        if row is None:
            return None
        game, home, away = row
        return GameWithTeams(game=game, home_team=home, away_team=away)


class PlayerGameLogRepository(Repository):
    async def bulk_upsert(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> list[PlayerGameLog]:
        logs: list[PlayerGameLog] = []
        for row in rows:
            values = dict(row)
            logs.append(
                await self._upsert_one(
                    PlayerGameLog,
                    and_(
                        PlayerGameLog.player_id == values["player_id"],
                        PlayerGameLog.game_id == values["game_id"],
                    ),
                    values,
                )
            )
        return logs

    async def list_for_player_before(
        self,
        player_id: int,
        before_date: date,
        limit: int,
    ) -> list[PlayerGameLog]:
        return list(
            (
                await self.session.scalars(
                    select(PlayerGameLog)
                    .join(Game, PlayerGameLog.game_id == Game.id)
                    .where(
                        PlayerGameLog.player_id == player_id,
                        Game.game_date < before_date,
                    )
                    .order_by(Game.game_date.desc(), Game.id.desc())
                    .limit(limit)
                )
            ).all()
        )


class TeamGameLogRepository(Repository):
    async def bulk_upsert(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> list[TeamGameLog]:
        logs: list[TeamGameLog] = []
        for row in rows:
            values = dict(row)
            logs.append(
                await self._upsert_one(
                    TeamGameLog,
                    and_(
                        TeamGameLog.team_id == values["team_id"],
                        TeamGameLog.game_id == values["game_id"],
                    ),
                    values,
                )
            )
        return logs

    async def list_for_team_before(
        self,
        team_id: int,
        before_date: date,
        limit: int,
    ) -> list[TeamGameLog]:
        return list(
            (
                await self.session.scalars(
                    select(TeamGameLog)
                    .join(Game, TeamGameLog.game_id == Game.id)
                    .where(
                        TeamGameLog.team_id == team_id,
                        Game.game_date < before_date,
                    )
                    .order_by(Game.game_date.desc(), Game.id.desc())
                    .limit(limit)
                )
            ).all()
        )


class PropLineRepository(Repository):
    async def add_snapshot(self, **values: Any) -> PropLine:
        return await self._add(PropLine(**values))

    async def latest_for_player_stat(
        self,
        player_id: int,
        stat_type: str,
        game_id: int | None = None,
    ) -> PropLine | None:
        query = select(PropLine).where(
            PropLine.player_id == player_id,
            PropLine.stat_type == stat_type,
        )
        if game_id is not None:
            query = query.where(PropLine.game_id == game_id)
        return await self.session.scalar(
            query.order_by(PropLine.fetched_at.desc(), PropLine.id.desc()).limit(1)
        )

    async def list_latest_for_game(self, game_id: int) -> list[PropLine]:
        ranked = (
            select(
                PropLine.id.label("prop_line_id"),
                func.row_number()
                .over(
                    partition_by=(PropLine.player_id, PropLine.stat_type),
                    order_by=(PropLine.fetched_at.desc(), PropLine.id.desc()),
                )
                .label("row_number"),
            )
            .where(PropLine.game_id == game_id)
            .subquery()
        )
        return list(
            (
                await self.session.scalars(
                    select(PropLine)
                    .join(ranked, PropLine.id == ranked.c.prop_line_id)
                    .where(ranked.c.row_number == 1)
                    .order_by(PropLine.player_id.asc(), PropLine.stat_type.asc())
                )
            ).all()
        )


class FeatureSnapshotRepository(Repository):
    async def add(self, **values: Any) -> FeatureSnapshot:
        return await self._add(FeatureSnapshot(**values))

    async def get_exact(
        self,
        player_id: int,
        game_id: int,
        stat_type: str,
        as_of: datetime,
        feature_version: str,
    ) -> FeatureSnapshot | None:
        return await self.session.scalar(
            select(FeatureSnapshot).where(
                FeatureSnapshot.player_id == player_id,
                FeatureSnapshot.game_id == game_id,
                FeatureSnapshot.stat_type == stat_type,
                FeatureSnapshot.as_of == as_of,
                FeatureSnapshot.feature_version == feature_version,
            )
        )

    async def latest_for(
        self,
        player_id: int,
        game_id: int,
        stat_type: str,
    ) -> FeatureSnapshot | None:
        return await self.session.scalar(
            select(FeatureSnapshot)
            .where(
                FeatureSnapshot.player_id == player_id,
                FeatureSnapshot.game_id == game_id,
                FeatureSnapshot.stat_type == stat_type,
            )
            .order_by(FeatureSnapshot.as_of.desc(), FeatureSnapshot.id.desc())
            .limit(1)
        )


class ModelVersionRepository(Repository):
    async def add(self, **values: Any) -> ModelVersion:
        return await self._add(ModelVersion(**values))

    async def get_by_name_version(
        self,
        name: str,
        version: str,
    ) -> ModelVersion | None:
        return await self.session.scalar(
            select(ModelVersion).where(
                ModelVersion.name == name,
                ModelVersion.version == version,
            )
        )

    async def latest_by_name(self, name: str) -> ModelVersion | None:
        return await self.session.scalar(
            select(ModelVersion)
            .where(ModelVersion.name == name)
            .order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
            .limit(1)
        )


class PromptVersionRepository(Repository):
    async def add(self, **values: Any) -> PromptVersion:
        return await self._add(PromptVersion(**values))

    async def get_by_name_version(
        self,
        name: str,
        version: str,
    ) -> PromptVersion | None:
        return await self.session.scalar(
            select(PromptVersion).where(
                PromptVersion.name == name,
                PromptVersion.version == version,
            )
        )

    async def latest_by_name(self, name: str) -> PromptVersion | None:
        return await self.session.scalar(
            select(PromptVersion)
            .where(PromptVersion.name == name)
            .order_by(PromptVersion.created_at.desc(), PromptVersion.id.desc())
            .limit(1)
        )


class PredictionRunRepository(Repository):
    async def create(self, **values: Any) -> PredictionRun:
        return await self._add(PredictionRun(**values))

    async def finish(
        self,
        prediction_run_id: int,
        status: str,
        finished_at: datetime | None = None,
    ) -> PredictionRun | None:
        run = await self.session.get(PredictionRun, prediction_run_id)
        if run is None:
            return None
        run.status = status
        run.finished_at = finished_at or utc_now()
        await self.session.flush()
        return run


class PlayerPredictionRepository(Repository):
    async def create_current(self, **values: Any) -> PlayerPrediction:
        await self.session.execute(
            update(PlayerPrediction)
            .where(
                PlayerPrediction.player_id == values["player_id"],
                PlayerPrediction.game_id == values["game_id"],
                PlayerPrediction.stat_type == values["stat_type"],
                PlayerPrediction.is_current.is_(True),
            )
            .values(is_current=False)
        )
        values["is_current"] = True
        return await self._add(PlayerPrediction(**values))

    async def search(
        self,
        *,
        game_date: date | None = None,
        game_id: int | None = None,
        player_id: int | None = None,
        player_name: str | None = None,
        stat_type: str | None = None,
        min_confidence: float | None = None,
        only_current: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PlayerPrediction]:
        query: Select[tuple[PlayerPrediction]] = select(PlayerPrediction)
        if game_date is not None:
            query = query.join(Game, PlayerPrediction.game_id == Game.id).where(
                Game.game_date == game_date
            )
        if player_name is not None:
            query = query.join(Player, PlayerPrediction.player_id == Player.id).where(
                func.lower(Player.full_name).like(f"%{player_name.lower()}%")
            )
        if game_id is not None:
            query = query.where(PlayerPrediction.game_id == game_id)
        if player_id is not None:
            query = query.where(PlayerPrediction.player_id == player_id)
        if stat_type is not None:
            query = query.where(PlayerPrediction.stat_type == stat_type)
        if min_confidence is not None:
            query = query.where(PlayerPrediction.confidence >= min_confidence)
        if only_current:
            query = query.where(PlayerPrediction.is_current.is_(True))

        return list(
            (
                await self.session.scalars(
                    query.order_by(
                        PlayerPrediction.created_at.desc(),
                        PlayerPrediction.id.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        )

    async def get(self, player_prediction_id: int) -> PlayerPrediction | None:
        return await self.session.get(PlayerPrediction, player_prediction_id)


class PredictionEvaluationRepository(Repository):
    async def add_for_prediction(
        self,
        player_prediction_id: int,
        **values: Any,
    ) -> PredictionEvaluation:
        values["player_prediction_id"] = player_prediction_id
        return await self._add(PredictionEvaluation(**values))

    async def list_unevaluated_predictions(
        self,
        game_date_cutoff: date,
    ) -> list[PlayerPrediction]:
        final_statuses = ("final", "closed", "complete", "completed")
        return list(
            (
                await self.session.scalars(
                    select(PlayerPrediction)
                    .join(Game, PlayerPrediction.game_id == Game.id)
                    .outerjoin(
                        PredictionEvaluation,
                        PredictionEvaluation.player_prediction_id
                        == PlayerPrediction.id,
                    )
                    .where(
                        Game.game_date <= game_date_cutoff,
                        func.lower(Game.status).in_(final_statuses),
                        PredictionEvaluation.id.is_(None),
                    )
                    .order_by(Game.game_date.asc(), PlayerPrediction.id.asc())
                )
            ).all()
        )


class JobRunRepository(Repository):
    async def start(
        self,
        job_name: str,
        *,
        detail: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> JobRun:
        return await self._add(
            JobRun(
                job_name=job_name,
                status="running",
                started_at=started_at or utc_now(),
                detail=detail,
            )
        )

    async def finish_success(
        self,
        job_run_id: int,
        *,
        detail: dict[str, Any] | None = None,
        finished_at: datetime | None = None,
    ) -> JobRun | None:
        run = await self.session.get(JobRun, job_run_id)
        if run is None:
            return None
        run.status = "success"
        run.finished_at = finished_at or utc_now()
        if detail is not None:
            run.detail = detail
        await self.session.flush()
        return run

    async def finish_failure(
        self,
        job_run_id: int,
        error: str,
        *,
        detail: dict[str, Any] | None = None,
        finished_at: datetime | None = None,
    ) -> JobRun | None:
        run = await self.session.get(JobRun, job_run_id)
        if run is None:
            return None
        run.status = "failure"
        run.finished_at = finished_at or utc_now()
        run.error = error
        if detail is not None:
            run.detail = detail
        await self.session.flush()
        return run

    async def list_recent(
        self,
        job_name: str | None = None,
        *,
        limit: int = 20,
    ) -> list[JobRun]:
        query = select(JobRun)
        if job_name is not None:
            query = query.where(JobRun.job_name == job_name)
        return list(
            (
                await self.session.scalars(
                    query.order_by(JobRun.started_at.desc(), JobRun.id.desc()).limit(
                        limit
                    )
                )
            ).all()
        )


class RawSourceSnapshotRepository(Repository):
    async def add(self, **values: Any) -> RawSourceSnapshot:
        return await self._add(RawSourceSnapshot(**values))

    async def latest_for(
        self,
        source: str,
        endpoint: str,
    ) -> RawSourceSnapshot | None:
        return await self.session.scalar(
            select(RawSourceSnapshot)
            .where(
                RawSourceSnapshot.source == source,
                RawSourceSnapshot.endpoint == endpoint,
            )
            .order_by(
                RawSourceSnapshot.fetched_at.desc(),
                RawSourceSnapshot.id.desc(),
            )
            .limit(1)
        )


class SourceHealthCheckRepository(Repository):
    async def add(self, **values: Any) -> SourceHealthCheck:
        return await self._add(SourceHealthCheck(**values))

    async def latest_per_source(self) -> list[SourceHealthCheck]:
        ranked = (
            select(
                SourceHealthCheck.id.label("health_check_id"),
                func.row_number()
                .over(
                    partition_by=SourceHealthCheck.source_name,
                    order_by=(
                        SourceHealthCheck.checked_at.desc(),
                        SourceHealthCheck.id.desc(),
                    ),
                )
                .label("row_number"),
            ).subquery()
        )
        return list(
            (
                await self.session.scalars(
                    select(SourceHealthCheck)
                    .join(
                        ranked,
                        SourceHealthCheck.id == ranked.c.health_check_id,
                    )
                    .where(ranked.c.row_number == 1)
                    .order_by(SourceHealthCheck.source_name.asc())
                )
            ).all()
        )


class LlmCallLogRepository(Repository):
    async def add(self, **values: Any) -> LlmCallLog:
        return await self._add(LlmCallLog(**values))
