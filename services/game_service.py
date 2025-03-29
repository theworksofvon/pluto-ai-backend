from adapters import Adapters
from logger import logger


class GameService:
    def __init__(self):
        self.adapters = Adapters()

    async def get_todays_games(self):
        try:
            return self.adapters.nba_analytics.get_todays_game_scoreboard()
        except Exception as e:
            logger.error(f"Error getting today's games in game_service: {e}")
            raise e

    async def get_game(self, game_id: str):
        try:
            return self.adapters.nba_analytics.get_game(game_id)
        except Exception as e:
            logger.error(f"Error getting game in game_service: {e}")
            raise e
