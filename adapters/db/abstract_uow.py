import abc
from typing import TypeVar, Generic

from .repositories import AbstractRepository

R = TypeVar("R", bound=AbstractRepository)
U = TypeVar("U", bound="AbstractUnitOfWork")


class AbstractUnitOfWork(abc.ABC, Generic[R, U]):
    """Abstract base class for unit of work pattern implementation"""

    _used: bool

    async def __aenter__(self) -> U:
        """Context manager enter method - prevents reusing a unit of work"""
        if getattr(self, "_used", False):
            raise Exception("Cannot use the same unit of work twice")
        setattr(self, "_used", True)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Context manager exit method - performs rollback and cleanup"""
        await self.rollback()
        self._used = True
        await self.close()

    @abc.abstractmethod
    async def commit(self) -> None:
        """Commit the unit of work transaction"""
        raise NotImplementedError

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Rollback the unit of work transaction"""
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        """Close resources used by the unit of work"""
        raise NotImplementedError
