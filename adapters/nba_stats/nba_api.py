"""Module to fetch and store relevant NBA Analytics"""

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    commonplayerinfo,
    playercareerstats,
    teamgamelog,
    playergamelog,
    playbyplayv2,
    scoreboardv2,
    commonteamroster,
)
from nba_api.live.nba.endpoints import scoreboard
from datetime import datetime, date
from logger import logger
from agents.helpers.team_helpers import (
    get_team_abbr_from_name,
    get_team_name_from_id,
    get_team_id,
)

import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from .interface import NbaAnalyticsInterface


class NbaAnalyticsPipeline(NbaAnalyticsInterface):
    """
    A pipeline to fetch and process NBA analytics data.
    """

    STAT_TYPE_COLUMN_MAP = {
        "points": "PTS",
        "rebounds": "REB",
        "assists": "AST",
    }

    # ------------------------------
    # PLAYER METHODS
    # ------------------------------

    def find_player_info(self, name: str) -> pd.DataFrame:
        """
        Find detailed information about a player by name.

        Args:
            name (str): Full name of the player.

        Returns:
            pd.DataFrame: DataFrame containing player details.
        """
        player_dict = players.find_players_by_full_name(name)

        if not player_dict:
            raise ValueError(f"No player found with name: {name}")

        player_id = player_dict[0]["id"]

        # Fetch player information
        player_info = commonplayerinfo.CommonPlayerInfo(player_id)
        info_df = player_info.get_data_frames()[0]
        return info_df

    def get_all_active_players(self, minimized: bool = False) -> list[dict]:
        active_players = players.get_active_players()

        if minimized:
            minimized_player_list = []
            for player in active_players:
                minimized_player_list.append(player["full_name"])
            return minimized_player_list

        return active_players

    def get_player_career_stats(self, name: str) -> pd.DataFrame:
        """
        Fetch career stats for a player by name.

        Args:
            name (str): Full name of the player.

        Returns:
            pd.DataFrame: DataFrame containing career stats.
        """
        player_dict = players.find_players_by_full_name(name)

        if not player_dict:
            raise ValueError(f"No player found with name: {name}")

        player_id = player_dict[0]["id"]

        # Fetch player career stats
        career_stats = playercareerstats.PlayerCareerStats(player_id)
        stats_df = career_stats.get_data_frames()[0]
        return stats_df.to_dict()

    def get_player_game_logs(self, name: str, season: str = "2024-25") -> pd.DataFrame:
        """
        Fetch player game logs for a specific season.

        Args:
            name (str): Full name of the player.
            season (str): NBA season (e.g., '2023-24').

        Returns:
            pd.DataFrame: DataFrame containing game logs.
        """
        player_dict = players.find_players_by_full_name(name)

        if not player_dict:
            raise ValueError(f"No player found with name: {name}")

        player_id = player_dict[0]["id"]

        # Fetch player game logs
        logs = playergamelog.PlayerGameLog(player_id=player_id, season=season)
        logs_df = logs.get_data_frames()[0]
        return logs_df.to_dict()

    # ------------------------------
    # TEAM METHODS
    # ------------------------------

    def get_teams(self) -> List[Dict]:
        """
        Get a list of all NBA teams.

        Returns:
            List[Dict]: List of team details.
        """
        return teams.get_teams()

    def get_team_game_logs(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Fetch team game logs for a specific season.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').
            season (str): NBA season (e.g., '2023-24').

        Returns:
            pd.DataFrame: DataFrame containing team game logs.
        """
        # Get team ID
        team_dict = teams.find_teams_by_full_name(team_name)

        if not team_dict:
            raise ValueError(f"No team found with name: {team_name}")

        team_id = team_dict[0]["id"]

        # Fetch game logs
        logs = teamgamelog.TeamGameLog(team_id=team_id, season=season)
        logs_df = logs.get_data_frames()[0]
        return logs_df

    # ------------------------------
    # PLAY-BY-PLAY METHODS
    # ------------------------------

    def get_play_by_play(self, game_id: str) -> pd.DataFrame:
        """
        Fetch play-by-play data for a specific game.

        Args:
            game_id (str): NBA game ID.

        Returns:
            pd.DataFrame: DataFrame containing play-by-play data.
        """
        pbp = playbyplayv2.PlayByPlayV2(game_id=game_id)
        pbp_df = pbp.get_data_frames()[0]
        return pbp_df

    # ------------------------------
    # LIVE GAME METHODS
    # ------------------------------

    def get_todays_game_scoreboard(self):
        """
        Get today's game scoreboard.

        Returns:
            Dict: Dictionary containing today's game data.
        """
        games = scoreboard.ScoreBoard()
        return games.get_dict()

    async def get_todays_upcoming_games(self):
        """
        Get today's upcoming games.

        Returns:
            List[Dict]: List of dicts containing game info with fields:
                - HOME_TEAM_ID: ID of the home team
                - VISITOR_TEAM_ID: ID of the visiting team
                - GAME_STATUS_TEXT: Game status/time
                - GAME_ID: Unique game identifier
        """
        today = datetime.today().strftime("%m/%d/%Y")
        scoreboard = scoreboardv2.ScoreboardV2(game_date=today)
        games = scoreboard.get_normalized_dict()["GameHeader"]

        return [
            {
                "HOME_TEAM_ID": game["HOME_TEAM_ID"],
                "VISITOR_TEAM_ID": game["VISITOR_TEAM_ID"],
                "GAME_STATUS_TEXT": game["GAME_STATUS_TEXT"],
                "GAME_ID": game["GAME_ID"],
            }
            for game in games
        ]

    async def get_starting_lineup(self, team_name: str):
        """
        Get the starting lineup for a team.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').

        Returns:
            List[Dict]: List of dicts containing starting lineup info
        """
        nba_teams = self.get_teams()
        logger.info(f"NBA Teams in get_starting_lineup: {nba_teams}")
        team = next(
            (
                team
                for team in nba_teams
                if team["full_name"].lower() == team_name.lower()
            ),
            None,
        )
        logger.info(f"Team in get_starting_lineup: {team}")

        if not team:
            raise ValueError(f"Team '{team_name}' not found.")

        roster = commonteamroster.CommonTeamRoster(team_id=team["id"])
        logger.info(f"Roster in get_starting_lineup: {roster}")
        players = roster.get_normalized_dict()["CommonTeamRoster"]
        logger.info(f"Players in get_starting_lineup: {players}")
        starters = [player for player in players if player["POSITION"] != ""][:5]
        logger.info(f"Starters in get_starting_lineup: {starters}")
        lineup = [
            {
                "player_name": player["PLAYER"],
                "position": player["POSITION"],
                "jersey_number": player["NUM"],
            }
            for player in starters
        ]

        return lineup

    async def get_player_image(self, player_name: str) -> str:
        """
        Get the image URL for a player by their name.

        Args:
            player_name (str): NBA player name.

        Returns:
            str: Image URL for the player.
        """
        player_dict = players.find_players_by_full_name(player_name)
        if not player_dict:
            logger.error("No player found with name: %s", player_name)
            return "https://path/to/default/image.png"
        player_id = player_dict[0]["id"]

        return f"https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"

    async def get_team_info(self, team_name: str) -> Dict[str, Any]:
        """
        Get team information by team name.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').

        Returns:
            Dict[str, Any]: Dictionary containing team information including logo URL.
        """
        nba_teams = self.get_teams()
        team = next(
            (
                team
                for team in nba_teams
                if team["full_name"].lower() == team_name.lower()
            ),
            None,
        )

        if team:
            team_id = team["id"]
            return {
                "id": team_id,
                "name": team["full_name"],
                "abbreviation": team["abbreviation"],
                "logo": f"https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg",
            }
        return None

    async def get_team_logo_url(self, team_name: str) -> str:
        """
        Get the logo URL for a team by team name.
        """
        team_abbr = get_team_abbr_from_name(team_name)
        return f"https://a.espncdn.com/i/teamlogos/nba/500/{team_abbr}.png"

    async def get_player_actual_stats(
        self, player_name: str, game_date: str, stat_type: str
    ) -> Optional[float]:
        """
        Get the actual value for a specific stat for a player on a given game date.
        Kept concise using date filtering in the API call.

        Args:
            player_name (str): The name of the player to fetch stats for.
            game_date (str): The date of the game to fetch stats for in format YYYY-MM-DD.
            stat_type (str): The type of stat to fetch.

        Returns:
            float: The actual value for the stat.
        """
        logger.debug(f"Fetching actual {stat_type} for {player_name} on {game_date}")

        nba_stat_column = self.STAT_TYPE_COLUMN_MAP.get(stat_type.lower())
        if not nba_stat_column:
            logger.error(f"Unknown stat_type: {stat_type}")
            return None

        try:
            player_dict = players.find_players_by_full_name(player_name)
            if not player_dict:
                logger.warning(f"Player not found: {player_name}")
                return None
            player_id = player_dict[0]["id"]

            if isinstance(game_date, str):
                game_date = datetime.strptime(game_date, "%Y-%m-%d")
            formatted_date = game_date.strftime("%m/%d/%Y")

            loop = asyncio.get_running_loop()
            game_log = await loop.run_in_executor(
                None,
                lambda: playergamelog.PlayerGameLog(
                    player_id=player_id,
                    date_from_nullable=formatted_date,
                    date_to_nullable=formatted_date,
                ),
            )
            game_logs_df = game_log.get_data_frames()

            if not game_logs_df or game_logs_df[0].empty:
                logger.warning(
                    f"No game log found for {player_name} (ID: {player_id}) on {formatted_date}"
                )
                return None

            actual_value = game_logs_df[0].iloc[0][nba_stat_column]
            logger.info(
                f"Found actual {stat_type} for {player_name} on {game_date}: {actual_value}"
            )
            return float(actual_value)

        except KeyError:
            logger.error(
                f"Stat column '{nba_stat_column}' not found in game log for {player_name} on {game_date}."
            )
            return None
        except IndexError:
            logger.error(
                f"Game log DataFrame was empty or malformed for {player_name} on {game_date}."
            )
            return None
        except Exception as e:
            logger.error(
                f"Error fetching/processing stats for {player_name} on {game_date}: {e}",
                exc_info=True,
            )
            return None

    async def get_game_players(self, games: List[Dict]) -> List[Tuple[str, str, str]]:
        """
        Get all players from today's games.
        Returns a list of tuples containing (player_name, team, opposing_team).
        """
        players = []
        try:
            for game in games:
                home_team_id = str(game.get("HOME_TEAM_ID"))
                away_team_id = str(game.get("VISITOR_TEAM_ID"))

                if not home_team_id or not away_team_id:
                    logger.warning(f"Skipping game due to missing team IDs: {game}")
                    continue

                home_team_name = get_team_name_from_id(home_team_id)
                away_team_name = get_team_name_from_id(away_team_id)

                if not home_team_name or not away_team_name:
                    logger.warning(f"Skipping game due to missing team names: {game}")
                    continue
                home_players = await self.get_starting_lineup(home_team_name)
                away_players = await self.get_starting_lineup(away_team_name)

                for player in home_players:
                    players.append(
                        (player.get("player_name"), home_team_name, away_team_name)
                    )

                for player in away_players:
                    players.append(
                        (player.get("player_name"), away_team_name, home_team_name)
                    )

            return players
        except Exception as e:
            logger.error(f"Error getting players: {e}")
            return []

    async def get_game_winner(
        self, game_date: str, home_team: str, away_team: str
    ) -> dict:
        """Fetch the game winner for a given game date and team abbreviations.

        Args:
            game_date (str): Date of the game in YYYY-MM-DD format.
            home_team (str): Abbreviation or Name for the home team.
            away_team (str): Abbreviation or Name for the away team.

        Returns:
            dict: A dictionary with key 'actual_winner' containing the winning team's abbreviation, 'Tie' if scores are equal, or None if not found.
        """
        try:
            dt = datetime.strptime(game_date, "%Y-%m-%d")
            formatted_date = dt.strftime("%m/%d/%Y")
            scoreboard = scoreboardv2.ScoreboardV2(game_date=formatted_date)
            data = scoreboard.get_normalized_dict()
            games = data.get("GameHeader", [])

            home_team_id = get_team_id(home_team)
            away_team_id = get_team_id(away_team)
            if home_team_id is None or away_team_id is None:
                logger.error("Could not find team IDs for the given abbreviations")
                raise ValueError("Could not find team IDs for the given abbreviations")

            game_found = None
            for game in games:
                if (
                    game.get("HOME_TEAM_ID") == home_team_id
                    and game.get("VISITOR_TEAM_ID") == away_team_id
                ):
                    game_found = game
                    break
            if game_found is None:
                logger.error("No matching game found for the given date and teams")
                raise ValueError("No matching game found for the given date and teams")

            game_id = game_found.get("GAME_ID")
            if not game_id:
                logger.error("No game ID found for the matching game")
                raise ValueError("No game ID found for the matching game")

            line_scores = data.get("LineScore", [])
            home_score = None
            away_score = None
            for record in line_scores:
                if record.get("GAME_ID") == game_id:
                    if record.get("TEAM_ID") == home_team_id:
                        home_score = int(record.get("PTS") or 0)
                    elif record.get("TEAM_ID") == away_team_id:
                        away_score = int(record.get("PTS") or 0)
            if home_score is None or away_score is None:
                logger.error("Scores not found for the matching game")
                raise ValueError("Scores not found for the matching game")

            actual_winner = home_team if home_score > away_score else away_team
            return {"actual_winner": actual_winner}
        except Exception as e:
            logger.error(f"Error fetching game winner: {e}", exc_info=True)
            raise e
