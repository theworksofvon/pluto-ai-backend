from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic
from schemas import (
    PlayerPredictionCreate,
    PlayerPredictionRead,
    GamePredictionCreate,
    GamePredictionRead,
    GameCreate,
    GameRead,
    GameReadWithTeams,
    PlayerCreate,
    PlayerRead,
    TeamCreate,
    TeamRead,
    TeamReadWithPlayers,
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

class GameRepository(AbstractRepository):
    @abstractmethod
    async def add(self, game: GameCreate) -> GameRead:
        raise NotImplementedError()

    @abstractmethod
    async def add_batch(self, games: List[GameCreate]) -> List[GameRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(self, game_id: int) -> Optional[GameRead]:
        raise NotImplementedError()

    @abstractmethod
    async def query(self, **kwargs) -> List[GameRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_with_teams(self, game_id: int) -> Optional[GameReadWithTeams]:
        raise NotImplementedError()

    @abstractmethod
    async def query_by_date(self, game_date: date) -> List[GameRead]:
        raise NotImplementedError()


class PlayerRepository(AbstractRepository):
    @abstractmethod
    async def add(self, player: PlayerCreate) -> PlayerRead:
        raise NotImplementedError()

    @abstractmethod
    async def add_batch(self, players: List[PlayerCreate]) -> List[PlayerRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(self, player_id: int) -> Optional[PlayerRead]:
        raise NotImplementedError()

    @abstractmethod
    async def query(self, **kwargs) -> List[PlayerRead]:
        raise NotImplementedError()


class TeamRepository(AbstractRepository):
    @abstractmethod
    async def add(self, team: TeamCreate) -> TeamRead:
        raise NotImplementedError()

    @abstractmethod
    async def add_batch(self, teams: List[TeamCreate]) -> List[TeamRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_by_id(self, team_id: int) -> Optional[TeamRead]:
        raise NotImplementedError()

    @abstractmethod
    async def query(self, **kwargs) -> List[TeamRead]:
        raise NotImplementedError()

    @abstractmethod
    async def get_with_players(self, team_id: int) -> Optional[TeamReadWithPlayers]:
        raise NotImplementedError()
