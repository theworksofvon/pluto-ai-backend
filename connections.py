import sys
from clients.sqlalchemy import SQLAlchemyClient
from config import config
from logger import logger
from supabase import create_client, Client

sqlalchemy_client = SQLAlchemyClient()


class Connections:
    db: SQLAlchemyClient = None
    supabase: Client = None

    @classmethod
    async def create_connections(cls):
        """Create and initialize all connections"""
        cls.db = await sqlalchemy_client.connect(
            config.DATABASE_URI, echo=config.SQL_ECHO
        )
        logger.info(f"Database connection created successfully: {cls.db}")
        cls.supabase = create_client(
            config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY
        )
        logger.info("Supabase connection created successfully")
        logger.info("Connections created successfully")
        return cls

    @classmethod
    async def close_connections(cls):
        """Close all active connections"""
        if cls.db:
            await cls.db.close()
            cls.db = None
        if cls.supabase:
            cls.supabase = None
