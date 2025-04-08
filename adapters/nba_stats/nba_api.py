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
from datetime import datetime
from logger import logger
from agents.helpers.team_helpers import get_team_abbr_from_name

import pandas as pd
from typing import List, Dict, Any
from .interface import NbaAnalyticsInterface


class NbaAnalyticsPipeline(NbaAnalyticsInterface):
    """
    A pipeline to fetch and process NBA analytics data.
    """

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
        logger.info(f"Games: {games}")

        # Return just the fields we need
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
