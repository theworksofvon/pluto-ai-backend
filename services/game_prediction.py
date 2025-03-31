from .data_pipeline import DataProcessor
from adapters import Adapters
from logger import logger
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np


class GamePredictionService:
    """
    Service responsible for preparing data for NBA game winner predictions.
    Prepares context for the LLM to make intelligent predictions.
    """

    def __init__(self):
        self.data_processor = DataProcessor()
        self.adapters = Adapters()
        self.prizepicks = self.adapters.prizepicks

    async def prepare_game_prediction_context(
        self,
        home_team: str,
        away_team: str,
        game_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Prepare all relevant context and data for a game winner prediction.

        Args:
            home_team: Name of the home team
            away_team: Name of the away team
            game_id: Specific game ID if available

        Returns:
            Dict containing all relevant data for making a game winner prediction
        """
        logger.info(f"Preparing game prediction context for {home_team} vs {away_team}")

        # Get team data from NBA API
        home_team_data = await self.data_processor.get_team_data(team_name=home_team)
        away_team_data = await self.data_processor.get_team_data(team_name=away_team)

        if not home_team_data or not away_team_data:
            message = f"Insufficient data for {home_team} vs {away_team}"
            logger.warning(message)
            return {
                "status": "error",
                "message": message,
                "home_team": home_team,
                "away_team": away_team,
                "data": None,
            }

        # Get team stats and recent games
        home_team_stats = home_team_data["team_stats"]
        away_team_stats = away_team_data["team_stats"]
        home_recent_games = home_team_data["recent_games"]
        away_recent_games = away_team_data["recent_games"]

        # Get current rosters and injury reports
        home_roster = await self.data_processor.get_team_roster(team_name=home_team)
        away_roster = await self.data_processor.get_team_roster(team_name=away_team)
        home_injuries = await self.data_processor.get_team_injuries(team_name=home_team)
        away_injuries = await self.data_processor.get_team_injuries(team_name=away_team)

        # Get head-to-head matchup data
        head_to_head = await self.data_processor.get_head_to_head(
            team1=home_team,
            team2=away_team,
        )

        # Get Vegas odds data
        vegas_factors = await self.data_processor.get_game_odds(
            home_team=home_team,
            away_team=away_team,
            game_id=game_id,
        )

        # Calculate team performance metrics
        home_performance = self._analyze_team_performance(
            home_team_stats, home_recent_games
        )
        away_performance = self._analyze_team_performance(
            away_team_stats, away_recent_games
        )

        # Calculate advanced metrics
        advanced_metrics = self._calculate_team_advanced_metrics(
            home_team_stats,
            away_team_stats,
            home_recent_games,
            away_recent_games,
        )

        # Get rest days and travel impact
        rest_and_travel = self._analyze_rest_and_travel(
            home_recent_games,
            away_recent_games,
            home_team,
            away_team,
        )

        # Calculate injury impact
        injury_impact = self._calculate_injury_impact(
            home_injuries,
            away_injuries,
            home_roster,
            away_roster,
        )

        # Get model prediction if available
        model_prediction = self._get_game_model_prediction(
            home_team_stats,
            away_team_stats,
            head_to_head,
        )

        return {
            "status": "success",
            "home_team": home_team,
            "away_team": away_team,
            "game_id": game_id,
            "game_date": datetime.now().date(),
            "team_stats": {
                "home": home_performance,
                "away": away_performance,
            },
            "head_to_head": head_to_head,
            "vegas_factors": vegas_factors,
            "advanced_metrics": {
                **advanced_metrics,
                **rest_and_travel,
                **injury_impact,
            },
            "rosters": {
                "home": home_roster,
                "away": away_roster,
            },
            "injuries": {
                "home": home_injuries,
                "away": away_injuries,
            },
            "model_prediction": model_prediction,
            "timestamp": datetime.now().isoformat(),
        }

    def _analyze_team_performance(
        self,
        team_stats: pd.DataFrame,
        recent_games: List[Dict],
    ) -> Dict[str, Any]:
        """
        Analyze team performance metrics from stats and recent games.
        """
        if len(recent_games) < 3:
            return {
                "record": "N/A",
                "home_record": "N/A",
                "away_record": "N/A",
                "last_10": "N/A",
                "offensive_rating": "N/A",
                "defensive_rating": "N/A",
                "net_rating": "N/A",
                "pace": "N/A",
            }

        # Calculate basic stats
        wins = sum(1 for game in recent_games if game["result"] == "W")
        losses = sum(1 for game in recent_games if game["result"] == "L")
        record = f"{wins}-{losses}"

        # Calculate home/away records
        home_games = [g for g in recent_games if g["is_home"]]
        away_games = [g for g in recent_games if not g["is_home"]]
        home_record = f"{sum(1 for g in home_games if g['result'] == 'W')}-{sum(1 for g in home_games if g['result'] == 'L')}"
        away_record = f"{sum(1 for g in away_games if g['result'] == 'W')}-{sum(1 for g in away_games if g['result'] == 'L')}"

        # Calculate last 10 games
        last_10 = recent_games[-10:]
        last_10_record = f"{sum(1 for g in last_10 if g['result'] == 'W')}-{sum(1 for g in last_10 if g['result'] == 'L')}"

        # Get advanced stats from team_stats
        offensive_rating = (
            team_stats["offensive_rating"].iloc[-1] if not team_stats.empty else "N/A"
        )
        defensive_rating = (
            team_stats["defensive_rating"].iloc[-1] if not team_stats.empty else "N/A"
        )
        net_rating = (
            team_stats["net_rating"].iloc[-1] if not team_stats.empty else "N/A"
        )
        pace = team_stats["pace"].iloc[-1] if not team_stats.empty else "N/A"

        return {
            "record": record,
            "home_record": home_record,
            "away_record": away_record,
            "last_10": last_10_record,
            "offensive_rating": offensive_rating,
            "defensive_rating": defensive_rating,
            "net_rating": net_rating,
            "pace": pace,
        }

    def _calculate_team_advanced_metrics(
        self,
        home_team_stats: pd.DataFrame,
        away_team_stats: pd.DataFrame,
        home_recent_games: List[Dict],
        away_recent_games: List[Dict],
    ) -> Dict[str, Any]:
        """
        Calculate advanced metrics for both teams.
        """
        # Calculate strength of schedule
        home_sos = self._calculate_strength_of_schedule(home_recent_games)
        away_sos = self._calculate_strength_of_schedule(away_recent_games)

        # Calculate performance consistency
        home_consistency = self._calculate_performance_consistency(home_recent_games)
        away_consistency = self._calculate_performance_consistency(away_recent_games)

        # Calculate momentum score
        home_momentum = self._calculate_momentum_score(home_recent_games)
        away_momentum = self._calculate_momentum_score(away_recent_games)

        return {
            "home_sos": home_sos,
            "away_sos": away_sos,
            "home_consistency": home_consistency,
            "away_consistency": away_consistency,
            "home_momentum": home_momentum,
            "away_momentum": away_momentum,
        }

    def _analyze_rest_and_travel(
        self,
        home_recent_games: List[Dict],
        away_recent_games: List[Dict],
        home_team: str,
        away_team: str,
    ) -> Dict[str, Any]:
        """
        Analyze rest days and travel impact for both teams.
        """
        # Calculate rest days
        home_rest_days = self._calculate_rest_days(home_recent_games)
        away_rest_days = self._calculate_rest_days(away_recent_games)

        # Calculate travel impact
        home_travel = self._calculate_travel_impact(home_team, home_recent_games)
        away_travel = self._calculate_travel_impact(away_team, away_recent_games)

        return {
            "home_rest_days": home_rest_days,
            "away_rest_days": away_rest_days,
            "home_travel_impact": home_travel,
            "away_travel_impact": away_travel,
        }

    def _calculate_injury_impact(
        self,
        home_injuries: List[Dict],
        away_injuries: List[Dict],
        home_roster: List[Dict],
        away_roster: List[Dict],
    ) -> Dict[str, Any]:
        """
        Calculate the impact of injuries on both teams.
        """
        # Calculate home team injury impact
        home_impact = self._evaluate_injury_impact(
            injuries=home_injuries,
            roster=home_roster,
        )

        # Calculate away team injury impact
        away_impact = self._evaluate_injury_impact(
            injuries=away_injuries,
            roster=away_roster,
        )

        return {
            "home_injury_impact": home_impact,
            "away_injury_impact": away_impact,
        }

    def _calculate_strength_of_schedule(self, recent_games: List[Dict]) -> float:
        """
        Calculate the strength of schedule based on opponent records and ratings.
        """
        if not recent_games or len(recent_games) < 3:
            return 0.0

        total_opponent_rating = 0
        games_counted = 0

        for game in recent_games:
            if (
                "opponent_net_rating" in game
                and game["opponent_net_rating"] is not None
            ):
                total_opponent_rating += game["opponent_net_rating"]
                games_counted += 1

        if games_counted == 0:
            return 0.0

        # Normalize the strength of schedule to a 0-1 scale
        # Assuming net ratings typically range from -10 to +10
        normalized_sos = (total_opponent_rating / games_counted + 10) / 20
        return max(0.0, min(1.0, normalized_sos))

    def _calculate_performance_consistency(self, recent_games: List[Dict]) -> float:
        """
        Calculate how consistent the team's performance has been.
        """
        if not recent_games or len(recent_games) < 3:
            return 0.0

        # Extract point differentials
        point_differentials = []
        for game in recent_games:
            if "points_for" in game and "points_against" in game:
                diff = game["points_for"] - game["points_against"]
                point_differentials.append(diff)

        if not point_differentials:
            return 0.0

        # Calculate coefficient of variation (lower = more consistent)
        mean_diff = np.mean(point_differentials)
        std_diff = np.std(point_differentials)

        if mean_diff == 0:
            return 1.0 if std_diff == 0 else 0.0

        cv = std_diff / abs(mean_diff)
        # Convert to consistency score (higher = more consistent)
        consistency = 1 - min(cv, 1)
        return max(0.0, min(1.0, consistency))

    def _calculate_momentum_score(self, recent_games: List[Dict]) -> float:
        """
        Calculate a momentum score based on recent performance.
        """
        if not recent_games or len(recent_games) < 3:
            return 0.0

        # Calculate win percentage in last 5 games
        last_5_games = recent_games[-5:]
        wins = sum(1 for game in last_5_games if game["result"] == "W")
        win_percentage = wins / len(last_5_games)

        # Calculate average point differential in last 5 games
        point_diffs = []
        for game in last_5_games:
            if "points_for" in game and "points_against" in game:
                diff = game["points_for"] - game["points_against"]
                point_diffs.append(diff)

        if not point_diffs:
            return win_percentage

        avg_point_diff = np.mean(point_diffs)
        # Normalize point differential (assuming typical range of -30 to +30)
        normalized_diff = (avg_point_diff + 30) / 60

        # Combine win percentage and point differential
        momentum = (win_percentage + normalized_diff) / 2
        return max(0.0, min(1.0, momentum))

    def _calculate_rest_days(self, recent_games: List[Dict]) -> int:
        """
        Calculate the number of rest days since the last game.
        """
        if not recent_games:
            return 0

        last_game = recent_games[0]
        if "game_date" not in last_game:
            return 0

        try:
            last_game_date = datetime.strptime(last_game["game_date"], "%Y-%m-%d")
            today = datetime.now()
            rest_days = (today - last_game_date).days
            return max(0, rest_days)
        except (ValueError, TypeError):
            return 0

    def _calculate_travel_impact(
        self,
        team: str,
        recent_games: List[Dict],
    ) -> float:
        """
        Calculate the impact of travel on team performance.
        """
        if not recent_games or len(recent_games) < 3:
            return 0.0

        # Calculate average performance in back-to-back games
        back_to_back_games = []
        for i in range(len(recent_games) - 1):
            if self._calculate_rest_days([recent_games[i + 1]]) == 0:
                back_to_back_games.append(recent_games[i])

        if not back_to_back_games:
            return 0.0

        # Calculate performance in back-to-back games
        b2b_performance = []
        for game in back_to_back_games:
            if "points_for" in game and "points_against" in game:
                diff = game["points_for"] - game["points_against"]
                b2b_performance.append(diff)

        if not b2b_performance:
            return 0.0

        # Compare back-to-back performance to overall performance
        overall_performance = []
        for game in recent_games:
            if "points_for" in game and "points_against" in game:
                diff = game["points_for"] - game["points_against"]
                overall_performance.append(diff)

        if not overall_performance:
            return 0.0

        b2b_avg = np.mean(b2b_performance)
        overall_avg = np.mean(overall_performance)

        # Calculate impact (negative means worse performance in back-to-backs)
        impact = (b2b_avg - overall_avg) / 20  # Normalize to roughly -1 to 1 range
        return max(-1.0, min(1.0, impact))

    def _evaluate_injury_impact(
        self,
        injuries: List[Dict],
        roster: List[Dict],
    ) -> float:
        """
        Evaluate the impact of injuries on team performance.
        """
        if not injuries or not roster:
            return 0.0

        # Calculate minutes per game lost due to injuries
        total_minutes_lost = 0
        total_roster_minutes = 0

        # Calculate total available minutes from roster
        for player in roster:
            if "minutes_per_game" in player:
                total_roster_minutes += player["minutes_per_game"]

        # Calculate minutes lost to injuries
        for injury in injuries:
            if "minutes_per_game" in injury:
                total_minutes_lost += injury["minutes_per_game"]

        if total_roster_minutes == 0:
            return 0.0

        # Calculate impact as ratio of lost minutes to total minutes
        impact = total_minutes_lost / total_roster_minutes
        return max(0.0, min(1.0, impact))

    def _get_game_model_prediction(
        self,
        home_team_stats: pd.DataFrame,
        away_team_stats: pd.DataFrame,
        head_to_head: Dict[str, Any],
    ) -> Optional[str]:
        """
        Get the model's prediction for the game winner.
        """
        if home_team_stats.empty or away_team_stats.empty:
            return None

        try:
            # Calculate team ratings
            home_net_rating = (
                home_team_stats["net_rating"].iloc[-1]
                if "net_rating" in home_team_stats
                else 0
            )
            away_net_rating = (
                away_team_stats["net_rating"].iloc[-1]
                if "net_rating" in away_team_stats
                else 0
            )

            # Add home court advantage (typically worth about 3.5 points)
            home_advantage = 3.5
            adjusted_home_rating = home_net_rating + home_advantage

            # Compare ratings to predict winner
            if adjusted_home_rating > away_net_rating:
                return "home_team"
            elif adjusted_home_rating < away_net_rating:
                return "away_team"
            else:
                return "toss_up"

        except Exception as e:
            logger.error(f"Error in game model prediction: {e}")
            return None
