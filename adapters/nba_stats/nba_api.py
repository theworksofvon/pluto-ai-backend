"""Module to fetch and store relevant NBA Analytics"""

from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    commonplayerinfo,
    playercareerstats,
    teamgamelog,
    playergamelog,
    playbyplayv2,
)
from nba_api.live.nba.endpoints import scoreboard


import pandas as pd
from typing import List, Dict
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
        games = scoreboard.ScoreBoard()
        return games.get_dict()
