from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from typing import List, Optional
from schemas import GameCreate, GameRead, GameReadWithTeams
from adapters.db.sqlalchemy.tables import Game
from adapters.db.repositories import GameRepository
from sqlalchemy.orm import joinedload


class SQLAlchemyGameRepository(GameRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, game: GameCreate) -> GameRead:
        game_instance = Game(**game.dict())
        self.session.add(game_instance)
        await self.session.refresh(game_instance)
        return GameRead.from_orm(game_instance)

    async def add_batch(self, games: List[GameCreate]) -> List[GameRead]:
        game_instances = [Game(**game.dict()) for game in games]
        self.session.add_all(game_instances)
        return [GameRead.from_orm(game) for game in game_instances]

    async def get_by_id(self, game_id: int) -> Optional[GameRead]:
        game = await self.session.get(Game, game_id)
        return GameRead.from_orm(game) if game else None

    async def query(self, **kwargs) -> List[GameRead]:
        query = self.session.query(Game)
        return [GameRead.from_orm(game) for game in await query.all()]

    async def get_with_teams(self, game_id: int) -> Optional[GameReadWithTeams]:
        query = self.session.query(Game).options(
            joinedload(Game.home_team), joinedload(Game.away_team)
        )
        game = await query.filter(Game.game_id == game_id).first()
        return GameReadWithTeams.from_orm(game) if game else None

    async def query_by_date(self, game_date: date) -> List[GameRead]:
        query = self.session.query(Game)
        return [
            GameRead.from_orm(game)
            for game in await query.filter(Game.date == game_date).all()
        ]
