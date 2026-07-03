from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.repositories import (
    FeatureSnapshotRepository,
    GameRepository,
    JobRunRepository,
    LlmCallLogRepository,
    ModelVersionRepository,
    PlayerGameLogRepository,
    PlayerPredictionRepository,
    PlayerRepository,
    PredictionEvaluationRepository,
    PredictionRunRepository,
    PromptVersionRepository,
    PropLineRepository,
    RawSourceSnapshotRepository,
    SourceHealthCheckRepository,
    TeamGameLogRepository,
    TeamRepository,
)
from app.db.session import get_sessionmaker


class UnitOfWork:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession] | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._sessionmaker = sessionmaker or get_sessionmaker(settings)
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> UnitOfWork:
        self.session = self._sessionmaker()
        self.teams = TeamRepository(self.session)
        self.players = PlayerRepository(self.session)
        self.games = GameRepository(self.session)
        self.player_game_logs = PlayerGameLogRepository(self.session)
        self.team_game_logs = TeamGameLogRepository(self.session)
        self.prop_lines = PropLineRepository(self.session)
        self.feature_snapshots = FeatureSnapshotRepository(self.session)
        self.model_versions = ModelVersionRepository(self.session)
        self.prompt_versions = PromptVersionRepository(self.session)
        self.prediction_runs = PredictionRunRepository(self.session)
        self.player_predictions = PlayerPredictionRepository(self.session)
        self.prediction_evaluations = PredictionEvaluationRepository(self.session)
        self.job_runs = JobRunRepository(self.session)
        self.raw_source_snapshots = RawSourceSnapshotRepository(self.session)
        self.source_health_checks = SourceHealthCheckRepository(self.session)
        self.llm_call_logs = LlmCallLogRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is None:
            return

        try:
            if exc_type is not None:
                await self.session.rollback()
            elif self.session.in_transaction():
                await self.session.rollback()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        await self.session.commit()

    async def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("UnitOfWork has not been entered")
        await self.session.rollback()
