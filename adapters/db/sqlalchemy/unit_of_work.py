from ..abstract_uow import AbstractUnitOfWork
from .repositories.prediction import (
    SQLAlchemyPlayerPredictionRepository,
    SQLAlchemyGamePredictionRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._used = False
        self.session: AsyncSession = None

    async def __aenter__(self):
        await super().__aenter__()
        self.session = self.session_factory()
        self.player_predictions = SQLAlchemyPlayerPredictionRepository(self.session)
        self.game_predictions = SQLAlchemyGamePredictionRepository(self.session)
        return self

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
