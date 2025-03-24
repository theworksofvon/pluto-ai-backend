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
    uow: AbstractUnitOfWork
    static_auth: AuthInterface

    def __init__(self):
        self.vegas_odds = VegasOddsPipeline()
        self.nba_analytics = NbaAnalyticsPipeline()
        self.uow = SQLAlchemyUnitOfWork(Connections.db.session_factory)
        self.static_auth = StaticAuthAdapter()