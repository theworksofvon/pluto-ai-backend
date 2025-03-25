import sys
from clients.sqlalchemy import SQLAlchemyClient
from config import config
from logger import logger

sqlalchemy_client = SQLAlchemyClient()


class Connections:
    db: SQLAlchemyClient = None

    @classmethod
    async def create_connections(cls):
        """Create and initialize all connections"""
        cls.db = await sqlalchemy_client.connect(
            config.DATABASE_URI, echo=config.SQL_ECHO
        )
        logger.info("Connections created successfully")
        return cls

    @classmethod
    async def close_connections(cls):
        """Close all active connections"""
        if cls.db:
            await cls.db.close()
            cls.db = None
