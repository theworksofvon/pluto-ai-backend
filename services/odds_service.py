from datetime import date, datetime
from typing import List, Optional, Dict, Any, Set

from pydantic import BaseModel

from adapters import Adapters, VegasOddsInterface
from config import config
from logger import logger
from adapters.prizepicks import PrizePicksAdapter


class TeamOdds(BaseModel):
    team_name: str
    moneyline: Optional[float] = None
    spread: Optional[float] = None
    spread_odds: Optional[int] = None
    total_over: Optional[float] = None
    total_over_odds: Optional[int] = None
    total_under: Optional[float] = None
    total_under_odds: Optional[int] = None


class GameOdds(BaseModel):
    game_id: Optional[str] = None
    sport_key: str
    start_time: datetime
    home_team: TeamOdds
    away_team: TeamOdds
    bookmaker: str


class OddsService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.ODDS_API_KEY
        self.adapters = Adapters()
        self.odds_api: VegasOddsInterface = self.adapters.vegas_odds
        self.prizepicks: PrizePicksAdapter = self.adapters.prizepicks

    async def get_prizepicks_lines(
        self, player_name: str, stat_types: Set[str] = {"Points"}
    ) -> List[Dict[str, Any]]:
        """Get PrizePicks lines for the specified stat types and player name."""
        try:
            logger.info(f"Getting PrizePicks lines for player: {player_name}")
            result = await self.prizepicks.get_nba_lines(stat_types, player_name)
            return result
        except Exception as e:
            logger.error(f"Error in get_prizepicks_lines: {str(e)}")
            raise

    async def get_sports(self) -> List[Dict[str, Any]]:
        """Get available sports from the Odds API."""
        try:
            result = await self.odds_api.get_sports()
            if result.status_code != 200:
                logger.error(f"Error fetching sports: {result.response}")
                raise Exception(f"Error fetching sports: {result.response}")
            return result.response
        except Exception as e:
            logger.error(f"Error in get_sports: {str(e)}")
            raise

    async def get_todays_odds(
        self, sport: str = "basketball_nba", team: str = None
    ) -> List[GameOdds]:
        """Get today's odds for the specified sport."""
        try:
            result = await self.odds_api.get_current_odds(
                sport=sport,
                regions="us",
                markets="h2h,spreads,totals",
            )

            logger.info(f"Result: {result}")

            if result.status_code != 200:
                logger.error(f"Error fetching odds: {result.response}")
                raise Exception(f"Error fetching odds: {result.response}")

            games_odds = []
            for game in result.response:
                game_date = datetime.fromisoformat(
                    game["commence_time"].replace("Z", "+00:00")
                )

                # Skip games with no bookmakers data.
                if not game.get("bookmakers"):
                    continue

                if team and game["home_team"] != team and game["away_team"] != team:
                    continue

                for bookmaker in game["bookmakers"]:
                    markets = {
                        market["key"]: market["outcomes"]
                        for market in bookmaker["markets"]
                    }
                    home_data, away_data = self._parse_markets(game, markets)
                    games_odds.append(
                        GameOdds(
                            game_id=game.get("id"),
                            sport_key=game["sport_key"],
                            start_time=game_date,
                            home_team=home_data,
                            away_team=away_data,
                            bookmaker=bookmaker["key"],
                        )
                    )
            return games_odds

        except Exception as e:
            logger.error(f"Error in get_todays_odds: {str(e)}")
            raise

    def _parse_markets(
        self, game: Dict[str, Any], markets: Dict[str, List[Dict[str, Any]]]
    ):
        """
        Parse market data to extract odds for both teams.

        Returns:
            A tuple (home_team_data, away_team_data, bookmaker_key).
        """
        home_team = game["home_team"]
        away_team = game["away_team"]

        home_data = TeamOdds(team_name=home_team)
        away_data = TeamOdds(team_name=away_team)

        # Parse moneyline (head-to-head).
        if "h2h" in markets:
            for outcome in markets["h2h"]:
                if outcome["name"] == home_team:
                    home_data.moneyline = outcome["price"]
                elif outcome["name"] == away_team:
                    away_data.moneyline = outcome["price"]

        # Parse spreads.
        if "spreads" in markets:
            for outcome in markets["spreads"]:
                if outcome["name"] == home_team:
                    home_data.spread = outcome["point"]
                    home_data.spread_odds = outcome["price"]
                elif outcome["name"] == away_team:
                    away_data.spread = outcome["point"]
                    away_data.spread_odds = outcome["price"]

        # Parse totals.
        if "totals" in markets:
            for outcome in markets["totals"]:
                point = outcome["point"]
                if outcome["name"] == "Over":
                    home_data.total_over = point
                    home_data.total_over_odds = outcome["price"]
                    away_data.total_over = point
                    away_data.total_over_odds = outcome["price"]
                elif outcome["name"] == "Under":
                    home_data.total_under = point
                    home_data.total_under_odds = outcome["price"]
                    away_data.total_under = point
                    away_data.total_under_odds = outcome["price"]

        return home_data, away_data
