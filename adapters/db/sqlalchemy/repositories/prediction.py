from adapters.db.repositories import (
    PlayerPredictionRepository,
    GamePredictionRepository,
)
from adapters.db.sqlalchemy.tables import PlayerPrediction, GamePrediction
from schemas import (
    PlayerPredictionCreate,
    PlayerPredictionRead,
    GamePredictionCreate,
    GamePredictionRead,
)
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional


class SQLAlchemyPlayerPredictionRepository(PlayerPredictionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, prediction: PlayerPredictionCreate) -> PlayerPredictionRead:
        prediction_dict = prediction.dict()
        prediction_dict['prediction_type'] = prediction_dict['prediction_type'].value
        
        prediction_instance = PlayerPrediction(**prediction_dict)
        self.session.add(prediction_instance)
        await self.session.flush()
        await self.session.refresh(prediction_instance)
        return PlayerPredictionRead.from_orm(prediction_instance)

    # async def get_by_id(self, prediction_id: int) -> Optional[PlayerPredictionRead]:
    #     prediction = await self.session.get(PlayerPrediction, prediction_id)
    #     return PlayerPredictionRead.from_orm(prediction) if prediction else None

    async def query(self, **kwargs) -> List[PlayerPredictionRead]:
        query = self.session.query(PlayerPrediction)
        for key, value in kwargs.items():
            if hasattr(PlayerPrediction, key):
                query = query.filter(getattr(PlayerPrediction, key) == value)
        return [
            PlayerPredictionRead.from_orm(prediction)
            for prediction in await query.all()
        ]


class SQLAlchemyGamePredictionRepository(GamePredictionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, prediction: GamePredictionCreate) -> GamePredictionRead:
        prediction_instance = GamePrediction(**prediction.dict())
        self.session.add(prediction_instance)
        await self.session.flush()
        await self.session.refresh(prediction_instance)
        return GamePredictionRead.from_orm(prediction_instance)

    async def get_by_id(self, prediction_id: int) -> Optional[GamePredictionRead]:
        prediction = await self.session.get(GamePrediction, prediction_id)
        return GamePredictionRead.from_orm(prediction) if prediction else None

    async def query(self, **kwargs) -> List[GamePredictionRead]:
        query = self.session.query(GamePrediction)
        for key, value in kwargs.items():
            if hasattr(GamePrediction, key):
                query = query.filter(getattr(GamePrediction, key) == value)
        return [
            GamePredictionRead.from_orm(prediction) for prediction in await query.all()
        ]
