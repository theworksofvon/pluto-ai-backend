from .vegas_odds import VegasOddsInterface, VegasOddsPipeline
from .nba_stats import NbaAnalyticsPipeline, NbaAnalyticsInterface
from .db.sqlalchemy import SQLAlchemyUnitOfWork
from .db.abstract_uow import AbstractUnitOfWork
from .auth.interface import AuthInterface
from .auth.auth import StaticAuthAdapter
from connections import Connections


class Adapters:
    vegas_odds: VegasOddsInterface
    nba_analytics: NbaAnalyticsInterface
    _uow: AbstractUnitOfWork
    auth: AuthInterface

    def __init__(self):
        self.vegas_odds = VegasOddsPipeline()
        self.nba_analytics = NbaAnalyticsPipeline()
        self.auth = StaticAuthAdapter()
        
    @property
    def uow(self) -> AbstractUnitOfWork:
        if self._uow is None:
            if Connections.db is None:
                raise Exception("Database connection not initialized yet. Ensure startup events have completed.")
            self._uow = SQLAlchemyUnitOfWork(Connections.db.session_factory)
        return self._uow
        
