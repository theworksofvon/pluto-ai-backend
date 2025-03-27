from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic
from schemas import (
    PlayerPredictionCreate,
    PlayerPredictionRead,
    GamePredictionCreate,
    GamePredictionRead,
)
from datetime import date
import abc

T = TypeVar("T")  # Type of entity


class AbstractRepository(abc.ABC, Generic[T]):
    """Abstract base class for repository pattern implementation"""

    @abc.abstractmethod
    async def add(self, entity: T) -> T:
        """Add a new entity to the repository"""
        raise NotImplementedError

    @abc.abstractmethod
    async def query(self, **kwargs) -> List[T]:
        """Query entities matching the criteria"""
        raise NotImplementedError


class PlayerPredictionRepository(AbstractRepository):
    @abstractmethod
    async def add(
        self, player_prediction: PlayerPredictionCreate
    ) -> PlayerPredictionRead:
        raise NotImplementedError()

    @abstractmethod
    async def query(self, **kwargs) -> List[PlayerPredictionRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_prediction_and_player(
        self, prediction_id: int, player_id: int
    ) -> Optional[PlayerPredictionRead]:
        raise NotImplementedError()


class GamePredictionRepository(AbstractRepository):
    @abstractmethod
    async def add(self, game_prediction: GamePredictionCreate) -> GamePredictionRead:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(self, prediction_id: int) -> Optional[GamePredictionRead]:
        raise NotImplementedError()

    @abstractmethod
    async def query(self, **kwargs) -> List[GamePredictionRead]:
        raise NotImplementedError()

