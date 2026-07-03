from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings

_engines: dict[tuple[str, bool], AsyncEngine] = {}
_sessionmakers: dict[tuple[str, bool], async_sessionmaker[AsyncSession]] = {}


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    resolved_settings = settings or get_settings()
    key = (resolved_settings.DATABASE_URL, resolved_settings.SQL_ECHO)
    if key not in _engines:
        _engines[key] = create_async_engine(
            resolved_settings.DATABASE_URL,
            echo=resolved_settings.SQL_ECHO,
        )
    return _engines[key]


def get_sessionmaker(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    resolved_settings = settings or get_settings()
    key = (resolved_settings.DATABASE_URL, resolved_settings.SQL_ECHO)
    if key not in _sessionmakers:
        _sessionmakers[key] = async_sessionmaker(
            bind=get_engine(resolved_settings),
            expire_on_commit=False,
        )
    return _sessionmakers[key]


@asynccontextmanager
async def session_scope(
    settings: Settings | None = None,
) -> AsyncIterator[AsyncSession]:
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        yield session


async def dispose_engines() -> None:
    for engine in _engines.values():
        await engine.dispose()
    _engines.clear()
    _sessionmakers.clear()
