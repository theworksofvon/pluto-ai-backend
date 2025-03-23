from sqlalchemy.ext.asyncio import AsyncSession
from adapters.db.repositories import PlayerRepository
from adapters.db.sqlalchemy.tables import Player
from schemas import (
    PlayerCreate,
    PlayerRead,
)
from typing import List, Optional


class SQLAlchemyPlayerRepository(PlayerRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, player: PlayerCreate) -> PlayerRead:
        player_instance = Player(**player.dict())
        self.session.add(player_instance)
        await self.session.refresh(player_instance)
        return PlayerRead.from_orm(player_instance)
