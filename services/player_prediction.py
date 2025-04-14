import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Any
from .data_pipeline import DataProcessor
from logger import logger
import os
import joblib
from adapters import Adapters


class PlayerPredictionService:
    """
    Service responsible for preparing data for NBA player performance predictions.
    Prepares context for the LLM to make intelligent predictions.
    """

    def __init__(self):
        super().__init__()
        self.data_processor = DataProcessor()
        self.adapters = Adapters()
        self.prizepicks = self.adapters.prizepicks

        self.models = {}
        self.scalers = {}
        self.encoders = {}

        model_types = ["points", "rebounds", "assists"]
        model_dir = "ai_models"

        for model_type in model_types:
            self._load_model(model_type, model_dir)

    def _load_model(self, model_type, model_dir):
        """
        Load a prediction model and its associated components.

        Args:
            model_type: Type of model (points, rebounds, assists)
            model_dir: Directory containing model files
        """
        model_path = os.path.join(model_dir, f"pluto_{model_type}_model.pkl")
        scaler_path = os.path.join(model_dir, f"pluto_{model_type}_scaler.pkl")
        encoder_path = os.path.join(model_dir, f"pluto_{model_type}_encoder.pkl")

        if not all(
            os.path.exists(path) for path in [model_path, scaler_path, encoder_path]
        ):
            logger.info(f"{model_type.capitalize()} prediction model files not found")
            return

        try:
            self.models[model_type] = joblib.load(model_path)
            self.scalers[model_type] = joblib.load(scaler_path)
            self.encoders[model_type] = joblib.load(encoder_path)
            logger.info(
                f"{model_type.capitalize()} prediction model loaded successfully"
            )
        except Exception as e:
            logger.error(f"Error loading {model_type} model: {e}")
            if model_type in self.models:
                del self.models[model_type]
            if model_type in self.scalers:
                del self.scalers[model_type]
            if model_type in self.encoders:
                del self.encoders[model_type]

    async def prepare_prediction_context(
        self,
        player_name: str,
        opposing_team: str,
        prediction_type: str = "points",
        game_id: Optional[str] = None,
        model_type: Optional[str] = "points",
    ) -> Dict[str, Any]:
        """
        Prepare all relevant context and data for a player prediction.

        Args:
            player_name: Name of the player to predict
            opposing_team: The opposing team name
            prediction_type: Type of prediction (points, rebounds, assists, etc.)
            game_id: Specific game ID if available

        Returns:
            Dict containing all relevant data for making a prediction
        """
        logger.info(
            f"Preparing prediction context for {player_name} against {opposing_team}"
        )

        data = await self.data_processor.get_latest_data(player_name=player_name)
        logger.info(f"Data: {data}")
        player_stats = data["player_stats"]
        logger.info(f"Player stats: {player_stats}")
        odds_data = data["odds_data"]

        if len(player_stats) < 3:
            message = f"Insufficient data for {player_name}. Only {len(player_stats)} games found."
            logger.warning(message)
            return {
                "status": "error",
                "message": message,
                "player": player_name,
                "data": None,
            }

        recent_form = self._analyze_player_form(player_stats, prediction_type)

        vegas_factors = self._extract_vegas_factors(
            odds_data, player_name, opposing_team
        )

        prizepicks_factors = await self._extract_prizepicks_factors(
            player_name, opposing_team
        )

        team_matchup = self._analyze_team_matchup(
            player_stats, prediction_type, opposing_team
        )

        season_stats = self._get_season_stats(player_stats, prediction_type)

        advanced_metrics = self._calculate_advanced_metrics(
            player_stats, prediction_type
        )

        if model_type:
            model_prediction = self._get_model_prediction(player_stats, prediction_type)

        return {
            "status": "success",
            "player": player_name,
            "game": {"opposing_team": opposing_team, "game_id": game_id},
            "prediction_type": prediction_type,
            "recent_form": recent_form,
            "vegas_factors": vegas_factors,
            "prizepicks_factors": prizepicks_factors,
            "team_matchup": team_matchup,
            "season_stats": season_stats,
            "model_prediction": model_prediction,
            "advanced_metrics": advanced_metrics,
            "raw_data": {
                "player_stats": player_stats.to_dict("records")[-10:],  # Last 10 games
                "total_games_available": len(player_stats),
            },
            "timestamp": datetime.now().isoformat(),
        }

    async def _extract_prizepicks_factors(
        self, player_name: str, opposing_team: str
    ) -> Dict[str, Any]:
        """
        Extracts PrizePicks factors for a player filtered by the opposing team.
        For each stat type, the highest line score is kept.

        Args:
            player_name (str): The name of the player.
            opposing_team (str): The name of the opposing team to filter props.

        Returns:
            Dict[str, Any]: A dictionary mapping keys formatted as
                            "{player_name}: {stat_type}" to the highest line score.
        """
        if not player_name:
            logger.warning("No player name provided for PrizePicks factors")
            return {}

        try:
            prizepicks_data = await self.prizepicks.get_nba_lines(
                player_name=player_name
            )
            if not prizepicks_data:
                logger.warning(f"No PrizePicks data found for player: {player_name}")
                return {}

            best_props: Dict[str, Any] = {}

            for prop in prizepicks_data:
                stat_type = prop.get("stat_type")
                line_score = prop.get("line_score")
                if not stat_type or line_score is None:
                    logger.debug(
                        f"Skipping prop due to missing data - stat_type: {stat_type}, line_score: {line_score}"
                    )
                    continue

                # Keep the highest line score for each stat type.
                best_props[stat_type] = max(
                    best_props.get(stat_type, line_score), line_score
                )

            result = {
                f"{player_name}: {stat_type}": score
                for stat_type, score in best_props.items()
            }
            logger.info(f"Formatted PrizePicks data for {player_name}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error extracting PrizePicks factors for {player_name}: {e}")
            return {}

    def _analyze_player_form(
        self, player_stats: pd.DataFrame, stat_type: str
    ) -> Dict[str, Any]:
        """
        Analyze player's recent form based on historical stats.

        Args:
            player_stats: DataFrame with player statistics
            stat_type: Type of stat to analyze (points, rebounds, etc.)

        Returns:
            Dict with form analysis
        """
        # Sort by date to ensure proper ordering
        player_stats = player_stats.sort_values(by="game_date_parsed", ascending=False)

        # Map prediction type to column name
        column_mapping = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "steals": "STL",
            "blocks": "BLK",
            "three_pointers": "FG3M",
        }

        # Get column name for the stat type
        stat_column = column_mapping.get(stat_type.lower(), "PTS")

        # If the specific stat column is not available, use rolling_pts_5 for points or return default
        if stat_column not in player_stats.columns and stat_type.lower() == "points":
            stat_column = "rolling_pts_5"

        # Calculate metrics if the column exists
        if stat_column in player_stats.columns:
            last_5_games = player_stats.head(5)
            last_10_games = player_stats.head(10)

            # Get recent game values
            recent_values = (
                last_5_games[stat_column].tolist() if len(last_5_games) > 0 else []
            )

            # Calculate trends
            trend = None
            trend_values = []
            if len(recent_values) >= 3:
                # Simple trend: positive if recent games show increase
                differences = [
                    recent_values[i] - recent_values[i + 1]
                    for i in range(len(recent_values) - 1)
                ]
                trend = "increasing" if sum(differences) > 0 else "decreasing"
                trend_values = differences

            return {
                "recent_average_5": np.mean(recent_values) if recent_values else None,
                "recent_average_10": (
                    np.mean(last_10_games[stat_column])
                    if len(last_10_games) > 0
                    else None
                ),
                "recent_max": max(recent_values) if recent_values else None,
                "recent_min": min(recent_values) if recent_values else None,
                "recent_values": recent_values,
                "trend": trend,
                "trend_values": trend_values,
                "games_analyzed": len(recent_values),
                "std_deviation": np.std(recent_values) if recent_values else None,
            }
        else:
            logger.warning(f"Column {stat_column} not found for {stat_type} analysis")
            return {
                "recent_average_5": None,
                "recent_average_10": None,
                "recent_max": None,
                "recent_min": None,
                "recent_values": [],
                "trend": None,
                "trend_values": [],
                "games_analyzed": 0,
                "std_deviation": None,
            }

    def _extract_vegas_factors(
        self, odds_data: pd.DataFrame, player_name: str, opposing_team: str
    ) -> Dict[str, Any]:
        """
        Extract relevant Vegas odds factors for the prediction.

        Args:
            odds_data: DataFrame with Vegas odds
            player_name: Player name
            opposing_team: Opposing team name

        Returns:
            Dict with extracted Vegas factors
        """
        # Default values
        factors = {
            "over_under": None,
            "player_prop": None,
            "team_spread": None,
            "implied_team_total": None,
            "favorite_status": None,
        }

        # If we have no odds data, return default values
        if odds_data.empty:
            return factors

        try:
            # Find relevant game based on team names
            # This is simplified and would need to be adapted to your actual odds data structure
            relevant_games = odds_data[
                odds_data.apply(
                    lambda row: opposing_team.lower() in str(row).lower(), axis=1
                )
            ]

            if not relevant_games.empty:
                game = relevant_games.iloc[0]

                # Extract game total (over/under)
                if "totals" in game and "points" in game["totals"]:
                    factors["over_under"] = game["totals"]["points"]

                # Extract team spread
                if "spreads" in game:
                    factors["team_spread"] = game["spreads"].get("points")

                # Calculate implied team total
                if (
                    factors["over_under"] is not None
                    and factors["team_spread"] is not None
                ):
                    # Simple calculation assuming equal distribution adjusted by spread
                    factors["implied_team_total"] = (factors["over_under"] / 2) + (
                        factors["team_spread"] / 2
                    )

                # Determine favorite status
                if factors["team_spread"] is not None:
                    factors["favorite_status"] = (
                        "favorite" if factors["team_spread"] > 0 else "underdog"
                    )

        except Exception as e:
            logger.error(f"Error extracting Vegas factors: {e}")

        return factors

    def _analyze_team_matchup(
        self, player_stats: pd.DataFrame, prediction_type: str, opposing_team: str
    ) -> Dict[str, Any]:
        """
        Analyze how the player has performed against this specific team.

        Args:
            player_stats: DataFrame with player statistics
            prediction_type: Type of stat to analyze
            opposing_team: Name of opposing team

        Returns:
            Dict with team matchup analysis
        """
        # Map prediction type to column name
        column_mapping = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "steals": "STL",
            "blocks": "BLK",
            "three_pointers": "FG3M",
        }
        stat_column = column_mapping.get(prediction_type.lower(), "PTS")

        # Default response
        matchup_data = {
            "games_vs_opponent": 0,
            "avg_vs_opponent": None,
            "max_vs_opponent": None,
            "last_game_vs_opponent": None,
            "last_game_date": None,
            "comparison_to_season_avg": None,
            "history": [],
        }

        if (
            "opponent" not in player_stats.columns
            or stat_column not in player_stats.columns
        ):
            return matchup_data

        opponent_games = player_stats[player_stats["opponent"] == opposing_team]

        if opponent_games.empty:
            return matchup_data

        opponent_games = opponent_games.sort_values(
            by="game_date_parsed", ascending=False
        )

        opponent_values = opponent_games[stat_column].tolist()
        season_avg = player_stats[stat_column].mean()
        opponent_avg = opponent_games[stat_column].mean()

        history = []
        for _, game in opponent_games.iterrows():
            game_date = game["game_date_parsed"]
            if isinstance(game_date, pd.Timestamp):
                game_date = game_date.strftime("%Y-%m-%d")
            elif isinstance(game_date, str):
                game_date = datetime.strptime(game_date, "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )

            history.append(
                {
                    "date": game_date,
                    "value": game[stat_column],
                    "minutes": game.get("MIN", None),
                    "result": game.get("W/L", None),
                }
            )

        last_game_date = opponent_games.iloc[0]["game_date_parsed"]
        if isinstance(last_game_date, pd.Timestamp):
            last_game_date = last_game_date.strftime("%Y-%m-%d")
        elif isinstance(last_game_date, str):
            last_game_date = datetime.strptime(last_game_date, "%Y-%m-%d").strftime(
                "%Y-%m-%d"
            )

        return {
            "games_vs_opponent": len(opponent_games),
            "avg_vs_opponent": opponent_avg,
            "max_vs_opponent": (
                opponent_games[stat_column].max() if not opponent_games.empty else None
            ),
            "last_game_vs_opponent": opponent_values[0] if opponent_values else None,
            "last_game_date": last_game_date,
            "comparison_to_season_avg": (
                (opponent_avg / season_avg - 1) * 100 if season_avg else None
            ),  # percentage difference
            "history": history[:5],  # Last 5 games only
        }

    def _get_season_stats(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> Dict[str, Any]:
        """
        Get season-long stats for the player.

        Args:
            player_stats: DataFrame with player statistics
            prediction_type: Type of prediction

        Returns:
            Dict with season statistics
        """

        column_mapping = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "steals": "STL",
            "blocks": "BLK",
            "three_pointers": "FG3M",
        }
        stat_column = column_mapping.get(prediction_type.lower(), "PTS")

        season_stats = {
            "season_average": None,
            "season_high": None,
            "season_low": None,
            "home_average": None,
            "away_average": None,
            "total_games": len(player_stats),
            "last_30_days_avg": None,
        }

        if stat_column not in player_stats.columns:
            return season_stats

        # Basic season stats
        season_stats["season_average"] = player_stats[stat_column].mean()
        season_stats["season_high"] = player_stats[stat_column].max()
        season_stats["season_low"] = player_stats[stat_column].min()

        # Home vs away splits
        if "home_away" in player_stats.columns:
            home_games = player_stats[
                player_stats["home_away"] == 1
            ]  # Assuming 1 = home
            away_games = player_stats[
                player_stats["home_away"] == 0
            ]  # Assuming 0 = away

            season_stats["home_average"] = (
                home_games[stat_column].mean() if not home_games.empty else None
            )
            season_stats["away_average"] = (
                away_games[stat_column].mean() if not away_games.empty else None
            )

        # Last 30 days average
        if "game_date_parsed" in player_stats.columns:
            thirty_days_ago = datetime.now() - pd.Timedelta(days=30)

            # Convert the entire column to datetime objects first
            player_stats["game_date_parsed"] = pd.to_datetime(
                player_stats["game_date_parsed"]
            )

            # Now you can do the comparison directly
            last_30_days = player_stats[
                player_stats["game_date_parsed"] > thirty_days_ago
            ]

            season_stats["last_30_days_avg"] = (
                last_30_days[stat_column].mean() if not last_30_days.empty else None
            )

        return season_stats

    def _calculate_advanced_metrics(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> Dict[str, Any]:
        """
        Calculate advanced metrics that might be helpful for predictions.

        Args:
            player_stats: DataFrame with player statistics
            prediction_type: Type of prediction

        Returns:
            Dict with advanced metrics
        """
        # Map prediction type to column name
        column_mapping = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "steals": "STL",
            "blocks": "BLK",
            "three_pointers": "FG3M",
        }
        stat_column = column_mapping.get(prediction_type.lower(), "PTS")

        # Default values
        metrics = {
            "consistency_score": None,  # How consistent the player is game-to-game
            "ceiling_potential": None,  # How close to their ceiling they've been playing
            "minutes_correlation": None,  # Correlation between minutes and stat
        }

        if stat_column not in player_stats.columns:
            return metrics

        # Calculate consistency score (inverse of coefficient of variation)
        if len(player_stats) >= 5:
            mean = player_stats[stat_column].mean()
            std = player_stats[stat_column].std()
            if mean > 0:
                cv = std / mean  # Coefficient of variation
                metrics["consistency_score"] = round(
                    1 - min(cv, 1), 2
                )  # Higher = more consistent

        # Calculate ceiling potential
        if len(player_stats) >= 5:
            season_high = player_stats[stat_column].max()
            recent_avg = player_stats.head(5)[stat_column].mean()
            if season_high > 0:
                metrics["ceiling_potential"] = round(recent_avg / season_high, 2)

        # Calculate correlation with minutes
        if "MIN" in player_stats.columns and len(player_stats) >= 5:
            correlation = player_stats[[stat_column, "MIN"]].corr().iloc[0, 1]
            metrics["minutes_correlation"] = round(correlation, 2)

        return metrics

    def _get_model_prediction(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> Dict[str, Any]:
        """
        Get the model prediction for the player.
        """
        if prediction_type == "points":
            return self._get_points_model_prediction(player_stats)
        if prediction_type == "rebounds":
            return self._get_rebounds_model_prediction(player_stats)
        if prediction_type == "assists":
            return self._get_assists_model_prediction(player_stats)
        return None

    def _get_points_model_prediction(
        self, player_stats: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Get the points model prediction for the player.
        """
        if (
            "points" not in self.models
            or "points" not in self.scalers
            or "points" not in self.encoders
        ):
            logger.error("Points prediction model or its components are not loaded.")
            return {"prediction": None}

        points_model = self.models["points"]
        points_scaler = self.scalers["points"]
        points_encoder = self.encoders["points"]

        processed_stats = points_scaler.transform(player_stats)
        encoded_stats = points_encoder.transform(processed_stats)
        prediction = points_model.predict(encoded_stats)
        return {"prediction": prediction}

    def _get_rebounds_model_prediction(
        self, player_stats: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Get the rebounds model prediction for the player.
        """
        # TODO: Implement the rebounds model prediction
        return None

    def _get_assists_model_prediction(
        self, player_stats: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Get the assists model prediction for the player.
        """
        # TODO: Implement the assists model prediction
        return None
