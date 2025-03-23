from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .client import Client


class SQLAlchemyClient(Client):
    """SQLAlchemy client for database connections"""

    name = "SQLAlchemyClient"

    def __init__(self):
        super().__init__()
        self.engine = None
        self.session_factory = None

    async def _connect(self, connection_uri, **kwargs):
        self.engine = create_async_engine(connection_uri, **kwargs)
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        return self

    async def _close(self):
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    async def _monitor(self):
        """Monitor database connection health"""
        if not self.engine:
            raise ConnectionError("Database engine not initialized")
        if not self.engine.driver:
            raise ConnectionError("Database driver not available")

    async def connect(self, connection_uri, **kwargs):
        self.engine = create_async_engine(connection_uri, **kwargs)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
