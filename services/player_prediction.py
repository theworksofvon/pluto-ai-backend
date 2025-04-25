import numpy as np
from datetime import datetime
from typing import Dict, Optional, Any, List, Literal
from .data_pipeline import DataProcessor
from logger import logger
import os
import joblib
from adapters import Adapters
from models.prediction_context import PredictionContext, PlayerStats, Game
from models.player_analysis_models import PlayerFormAnalysis
from models.season_stats_model import SeasonStats
from models.prediction_context import ModelPrediction, AdvancedMetrics
from models.team_models import VegasFactors, PrizepicksFactors, TeamMatchup


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
        self.supabase = self.adapters.supabase.get_supabase_client()

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
        model_type: Optional[str] = "points",
        additional_context: Optional[str] = None,
        season_mode: Literal["regular_season", "playoffs", "finals"] = "regular_season",
    ) -> PredictionContext:
        """
        Prepare all relevant context and data for a player prediction.

        Args:
            player_name: Name of the player to predict
            opposing_team: The opposing team name
            prediction_type: Type of prediction (points, rebounds, assists, etc.)

        Returns:
            Dict containing all relevant data for making a prediction
        """
        logger.info(
            f"Preparing prediction context for {player_name} against {opposing_team}"
        )

        data = await self.data_processor.get_latest_data(player_name=player_name)
        player_stats = data.player_stats
        odds_data = data.odds_data

        if len(player_stats) < 3:
            message = f"Insufficient data for {player_name}. Only {len(player_stats)} games found."
            logger.warning(message)
            return PredictionContext(
                status="error",
                message=message,
                player=player_name,
                game=Game(
                    opposing_team=opposing_team,
                    game_date=datetime.now().date().isoformat(),
                ),
                prediction_type=prediction_type,
            )

        recent_form = self._analyze_player_form(player_stats, prediction_type)

        vegas_factors = self._extract_vegas_factors(odds_data, opposing_team)

        prizepicks_factors = await self._extract_prizepicks_factors(player_name)

        team_matchup = self._analyze_team_matchup(
            player_stats, prediction_type, opposing_team
        )

        season_stats = self._get_season_stats(player_stats, prediction_type)

        advanced_metrics = self._calculate_advanced_metrics(
            player_stats, prediction_type
        )

        if model_type:
            model_prediction = self._get_model_prediction(player_stats, prediction_type)

        predictions_to_send: List[Dict[str, Any]] = []
        previous_predictions = (
            self.supabase.table("player_predictions")
            .select("*")
            .eq("player_name", player_name)
            .eq("prediction_type", prediction_type)
            .eq("opposing_team", opposing_team)
            .execute()
        )

        logger.info(f"Previous predictions: {previous_predictions}")

        if previous_predictions.data:
            for prediction in previous_predictions.data:
                if prediction.get("actual") is not None:
                    predictions_to_send.append(
                        {
                            "prediction_id": prediction.get("prediction_id"),
                            "actual": prediction.get("actual"),
                            "predicted_value": prediction.get("predicted_value"),
                            "range_low": prediction.get("range_low"),
                            "range_high": prediction.get("range_high"),
                            "confidence": prediction.get("confidence"),
                            "explanation": prediction.get("explanation"),
                            "prizepicks_prediction": prediction.get(
                                "prizepicks_prediction"
                            ),
                            "prizepicks_line": prediction.get("prizepicks_line"),
                            "game_date": prediction.get("game_date"),
                        }
                    )
            predictions_to_send = sorted(
                predictions_to_send,
                key=lambda x: x.get("game_date", "1970-01-01"),
                reverse=True,
            )[:5]

        return PredictionContext(
            status="success",
            player=player_name,
            game=Game(
                opposing_team=opposing_team, game_date=datetime.now().date().isoformat()
            ),
            prediction_type=prediction_type,
            recent_form=recent_form,
            vegas_factors=vegas_factors,
            prizepicks_factors=prizepicks_factors,
            team_matchup=team_matchup,
            season_stats=season_stats,
            model_prediction=model_prediction,
            historical_predictions=predictions_to_send,
            advanced_metrics=advanced_metrics,
            additional_context=additional_context,
            season_mode=season_mode,
            raw_data=PlayerStats(
                player_stats=player_stats.to_dict("records")[-10:],
                total_games_available=len(player_stats),
            ),
            timestamp=datetime.now().isoformat(),
        )

    async def _extract_prizepicks_factors(self, player_name: str) -> PrizepicksFactors:
        """
        Extracts PrizePicks factors for a player filtered by the opposing team.
        For each stat type, the highest line score is kept.

        Args:
            player_name (str): The name of the player.

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
                return PrizepicksFactors()

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
            return PrizepicksFactors(**result)

        except Exception as e:
            logger.error(f"Error extracting PrizePicks factors for {player_name}: {e}")
            return PrizepicksFactors()

    def _analyze_player_form(
        self, player_stats: pd.DataFrame, stat_type: str
    ) -> PlayerFormAnalysis:
        """
        Analyze player's recent form based on historical stats.

        Args:
            player_stats: DataFrame with player statistics
            stat_type: Type of stat to analyze (points, rebounds, etc.)

        Returns:
            PlayerFormAnalysis model with form analysis
        """

        player_stats = player_stats.sort_values(by="game_date_parsed", ascending=False)

        column_mapping = {
            "points": "PTS",
            "rebounds": "REB",
            "assists": "AST",
            "steals": "STL",
            "blocks": "BLK",
            "three_pointers": "FG3M",
        }
        stat_column = column_mapping.get(stat_type.lower(), "PTS")

        if stat_column not in player_stats.columns and stat_type.lower() == "points":
            stat_column = "rolling_pts_5"

        if stat_column not in player_stats.columns:
            logger.warning(f"Column {stat_column} not found for {stat_type} analysis")
            return PlayerFormAnalysis()

        return PlayerFormAnalysis.from_stats(player_stats, stat_column)

    def _extract_vegas_factors(
        self, odds_data: pd.DataFrame, opposing_team: str
    ) -> VegasFactors:
        """
        Extract relevant Vegas odds factors for the prediction.

        Args:
            odds_data: DataFrame with Vegas odds
            player_name: Player name
            opposing_team: Opposing team name

        Returns:
            VegasFactors model with extracted Vegas factors
        """
        factors = VegasFactors(
            over_under=None,
            player_prop=None,
            team_spread=None,
            implied_team_total=None,
            favorite_status=None,
        )

        if odds_data.empty:
            return factors

        try:
            relevant_games = odds_data[
                odds_data.apply(
                    lambda row: opposing_team.lower() in str(row).lower(), axis=1
                )
            ]
            if not relevant_games.empty:
                game = relevant_games.iloc[0]
                over_under = None
                team_spread = None
                implied_team_total = None
                favorite_status = None

                if "totals" in game and "points" in game["totals"]:
                    over_under = game["totals"]["points"]

                if "spreads" in game:
                    team_spread = game["spreads"].get("points")

                if over_under is not None and team_spread is not None:
                    implied_team_total = (over_under / 2) + (team_spread / 2)

                if team_spread is not None:
                    favorite_status = "favorite" if team_spread > 0 else "underdog"

                factors = VegasFactors(
                    over_under=over_under,
                    player_prop=factors.player_prop,
                    team_spread=team_spread,
                    implied_team_total=implied_team_total,
                    favorite_status=favorite_status,
                )

        except Exception as e:
            logger.error(f"Error extracting Vegas factors: {e}")

        return factors

    def _analyze_team_matchup(
        self, player_stats: pd.DataFrame, prediction_type: str, opposing_team: str
    ) -> TeamMatchup:
        """
        Analyze how the player has performed against this specific team.

        Args:
            player_stats: DataFrame with player statistics
            prediction_type: Type of stat to analyze
            opposing_team: Name of opposing team

        Returns:
            TeamMatchup model with analysis data
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

        player_team = ""
        if "team" in player_stats.columns and not player_stats.empty:
            player_team = player_stats.iloc[0].get("team", "")

        matchup = TeamMatchup(player_team=player_team, opposing_team=opposing_team)

        if (
            "opponent" not in player_stats.columns
            or stat_column not in player_stats.columns
        ):
            return matchup

        opponent_games = player_stats[player_stats["opponent"] == opposing_team]

        if opponent_games.empty:
            return matchup

        opponent_games = opponent_games.sort_values(
            by="game_date_parsed", ascending=False
        )

        last_matchup_date = None
        last_matchup_result = None

        if not opponent_games.empty:
            if "game_date_parsed" in opponent_games.columns:
                last_date = opponent_games.iloc[0]["game_date_parsed"]
                if isinstance(last_date, pd.Timestamp):
                    last_matchup_date = last_date.strftime("%Y-%m-%d")
                elif isinstance(last_date, str):
                    last_matchup_date = datetime.strptime(
                        last_date, "%Y-%m-%d"
                    ).strftime("%Y-%m-%d")

            if "W/L" in opponent_games.columns:
                last_matchup_result = opponent_games.iloc[0].get("W/L")

        historical_matchups = []
        for _, game in opponent_games.iterrows():
            game_date = game.get("game_date_parsed")
            if isinstance(game_date, pd.Timestamp):
                game_date = game_date.strftime("%Y-%m-%d")
            elif isinstance(game_date, str):
                game_date = datetime.strptime(game_date, "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )

            historical_matchups.append(
                {
                    "date": game_date,
                    "value": game.get(stat_column),
                    "minutes": game.get("MIN"),
                    "result": game.get("W/L"),
                }
            )

        player_performances = historical_matchups.copy()

        player_avg = {}
        if not opponent_games.empty:
            player_avg[prediction_type] = opponent_games[stat_column].mean()

        return TeamMatchup(
            player_team=player_team,
            opposing_team=opposing_team,
            last_matchup_date=last_matchup_date,
            last_matchup_result=last_matchup_result,
            historical_matchups=historical_matchups[:5],
            player_performances=player_performances[:5],
            player_avg_vs_team=player_avg,
        )

    def _get_season_stats(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> SeasonStats:
        """
        Get season-long stats for the player.

        Args:
            player_stats: DataFrame with player statistics.
            prediction_type: Type of prediction (e.g., "points", "rebounds", etc).

        Returns:
            SeasonStats model with season statistics populated.
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
        total_games = len(player_stats)

        if stat_column not in player_stats.columns:
            return SeasonStats(
                season_average=None,
                season_high=None,
                season_low=None,
                home_average=None,
                away_average=None,
                total_games=total_games,
                last_30_days_avg=None,
            )

        stats_series = player_stats[stat_column]

        season_stats = {
            "season_average": stats_series.mean(),
            "season_high": stats_series.max(),
            "season_low": stats_series.min(),
            "home_average": None,
            "away_average": None,
            "total_games": total_games,
            "last_30_days_avg": None,
        }

        if "home_away" in player_stats.columns:
            home_games = player_stats.loc[player_stats["home_away"] == 1, stat_column]
            away_games = player_stats.loc[player_stats["home_away"] == 0, stat_column]
            season_stats["home_average"] = (
                home_games.mean() if not home_games.empty else None
            )
            season_stats["away_average"] = (
                away_games.mean() if not away_games.empty else None
            )

        if "game_date_parsed" in player_stats.columns:
            dates = pd.to_datetime(player_stats["game_date_parsed"], errors="coerce")
            thirty_days_ago = pd.Timestamp.now() - pd.Timedelta(days=30)
            last_30_days = stats_series[dates > thirty_days_ago]
            season_stats["last_30_days_avg"] = (
                last_30_days.mean() if not last_30_days.empty else None
            )

        return SeasonStats(**season_stats)

    def _calculate_advanced_metrics(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> AdvancedMetrics:
        """
        Calculate advanced metrics that might be helpful for predictions.

        Args:
            player_stats: DataFrame with player statistics.
            prediction_type: Type of prediction (e.g., "points", "rebounds", etc).

        Returns:
            AdvancedMetrics model with calculated advanced metrics.
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

        metrics = {
            "consistency_score": None,
            "ceiling_potential": None,
            "minutes_correlation": None,
        }

        if stat_column not in player_stats.columns:
            return AdvancedMetrics(**metrics)

        n = len(player_stats)
        if n < 5:
            return AdvancedMetrics(**metrics)

        stat_series = player_stats[stat_column]

        mean_val = stat_series.mean()
        std_val = stat_series.std()
        if mean_val > 0:
            cv = std_val / mean_val
            metrics["consistency_score"] = round(1 - min(cv, 1), 2)

        season_high = stat_series.max()
        recent_avg = stat_series.head(5).mean()
        if season_high > 0:
            metrics["ceiling_potential"] = round(recent_avg / season_high, 2)

        if "MIN" in player_stats.columns:
            correlation = player_stats[[stat_column, "MIN"]].corr().iloc[0, 1]
            metrics["minutes_correlation"] = round(correlation, 2)

        return AdvancedMetrics(**metrics)

    def _get_model_prediction(
        self, player_stats: pd.DataFrame, prediction_type: str
    ) -> ModelPrediction:
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
    ) -> ModelPrediction:
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

        player_stats = player_stats.sort_values(by="game_date_parsed", ascending=True)

        if player_stats.empty:
            logger.error("Player stats DataFrame is empty, cannot make prediction.")
            return {"prediction": None}

        latest_game_stats = player_stats.iloc[-1:].copy()
        logger.info(f"Using latest game stats for prediction: {latest_game_stats}")

        latest_game_stats = latest_game_stats.drop(
            columns=["Game_ID", "GAME_DATE", "MATCHUP", "WL", "PTS"], errors="ignore"
        )
        latest_game_stats = latest_game_stats.fillna(0)

        numeric_cols = [
            "home_away_flag",
            "rolling_pts_5",
            "rolling_min_5",
            "rolling_fga_5",
            "rolling_fg_pct_5",
            "days_since_last_game",
            "back_to_back_flag",
        ]
        categorical_cols = ["player_name", "opponent", "game_date_parsed"]

        required_cols = numeric_cols + categorical_cols
        missing_cols = [
            col for col in required_cols if col not in latest_game_stats.columns
        ]
        if missing_cols:
            logger.error(f"Missing required columns for prediction: {missing_cols}")
            return ModelPrediction(prediction=None)

        numeric_data = latest_game_stats[numeric_cols]
        categorical_data = latest_game_stats[categorical_cols].copy()
        # Convert categorical columns to strings to match training; for datetime columns, format as 'YYYY-MM-DD'
        for col in categorical_cols:
            if pd.api.types.is_datetime64_any_dtype(categorical_data[col]):
                categorical_data[col] = categorical_data[col].dt.strftime("%Y-%m-%d")
            else:
                categorical_data[col] = categorical_data[col].astype(str)
        encoded_cat = points_encoder.transform(categorical_data)
        encoded_cat_df = pd.DataFrame(
            encoded_cat,
            columns=points_encoder.get_feature_names_out(categorical_cols),
            index=latest_game_stats.index,
        )

        new_features = pd.concat([numeric_data, encoded_cat_df], axis=1)

        processed_stats = points_scaler.transform(new_features)

        prediction = points_model.predict(processed_stats)

        single_prediction = (
            prediction[0] if prediction.ndim > 0 and len(prediction) > 0 else None
        )

        logger.info(f"Prediction for next game: {single_prediction}")
        return ModelPrediction(
            prediction=single_prediction,
        )

    def _get_rebounds_model_prediction(
        self, player_stats: pd.DataFrame
    ) -> ModelPrediction:
        """
        Get the rebounds model prediction for the player.
        """
        # TODO: Implement the rebounds model prediction
        return None

    def _get_assists_model_prediction(
        self, player_stats: pd.DataFrame
    ) -> ModelPrediction:
        """
        Get the assists model prediction for the player.
        """
        # TODO: Implement the assists model prediction
        return None
