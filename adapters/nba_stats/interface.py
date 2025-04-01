from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict, Any


class NbaAnalyticsInterface(ABC):
    """Abstract interface for NBA analytics operations."""

    # ------------------------------
    # PLAYER METHODS
    # ------------------------------
    @abstractmethod
    async def find_player_info(self, name: str) -> pd.DataFrame:
        """
        Find detailed information about a player by name.

        Args:
            name (str): Full name of the player.

        Returns:
            pd.DataFrame: DataFrame containing player details.
        """
        pass

    async def get_all_active_players(self, minimized: bool = False) -> list[dict]:
        """
        Returns a list of all the active players currently in NBA.

        Args:
        minimized (bool): Return minimized player object. Defaults to False.

        Returns:
            list[dict]: List of dicts containing player info
        """
        pass

    @abstractmethod
    async def get_player_career_stats(self, name: str) -> pd.DataFrame:
        """
        Fetch career stats for a player by name.

        Args:
            name (str): Full name of the player.

        Returns:
            pd.DataFrame: DataFrame containing career stats.
        """
        pass

    @abstractmethod
    async def get_player_game_logs(self, name: str, season: str) -> pd.DataFrame:
        """
        Fetch player game logs for a specific season.

        Args:
            name (str): Full name of the player.
            season (str): NBA season (e.g., '2023-24').

        Returns:
            pd.DataFrame: DataFrame containing game logs.
        """
        pass

    # ------------------------------
    # TEAM METHODS
    # ------------------------------
    @abstractmethod
    async def get_teams(self) -> List[Dict]:
        """
        Get a list of all NBA teams.

        Returns:
            List[Dict]: List of team details.
        """
        pass

    @abstractmethod
    async def get_team_game_logs(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Fetch team game logs for a specific season.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').
            season (str): NBA season (e.g., '2023-24').

        Returns:
            pd.DataFrame: DataFrame containing team game logs.
        """
        pass

    # ------------------------------
    # PLAY-BY-PLAY METHODS
    # ------------------------------
    @abstractmethod
    async def get_play_by_play(self, game_id: str) -> pd.DataFrame:
        """
        Fetch play-by-play data for a specific game.

        Args:
            game_id (str): NBA game ID.

        Returns:
            pd.DataFrame: DataFrame containing play-by-play data.
        """
        pass

    # ------------------------------
    # LIVE GAME METHODS
    # ------------------------------
    @abstractmethod
    async def get_todays_game_scoreboard(self) -> Dict:
        """
        Get today's game scoreboard.

        Returns:
            Dict: Dictionary containing today's game data.
        """
        pass

    @abstractmethod
    async def get_todays_upcoming_games(self) -> List[Dict]:
        """
        Get today's upcoming games.

        Returns:
            List[Dict]: List of dicts containing game info
        """
        pass

    @abstractmethod
    async def get_starting_lineup(self, team_name: str) -> List[Dict]:
        """
        Get the starting lineup for a team.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').

        Returns:
            List[Dict]: List of dicts containing starting lineup info
        """
        pass

    @abstractmethod
    async def get_player_image(self, player_id: str) -> str:
        """
        Get the image URL for a player by their ID.

        Args:
            player_id (str): NBA player ID.

        Returns:
            str: Image URL for the player.
        """
        pass

    @abstractmethod
    async def get_team_info(self, team_name: str) -> Dict[str, Any]:
        """
        Get team information by team name.

        Args:
            team_name (str): Full name of the team (e.g., 'Los Angeles Lakers').

        Returns:
            Dict[str, Any]: Dictionary containing team information including logo URL.
        """
        pass

    @abstractmethod
    async def get_team_logo_url(self, team_name: str) -> str:
        """
        Get the logo URL for a team by team name.
        """
        pass
