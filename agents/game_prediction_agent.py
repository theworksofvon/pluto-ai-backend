from agency.agent import Agent
from agency.agency_types import Tendencies
from services.game_prediction import GamePredictionService
from typing import Dict, Optional, Any
from adapters import Adapters
from adapters.db.abstract_uow import AbstractUnitOfWork
from adapters.scheduler import AbstractScheduler
from logger import logger
from datetime import datetime
import json
import numpy as np
import traceback
from agents.helpers.prediction_helpers import (
    parse_prediction_response,
    DEFAULT_GAME_PREDICTION,
)
from agents.helpers.team_helpers import get_team_abbr_from_id, get_team_name_from_abbr
from schemas import GamePredictionCreate, PredictionType
import pandas as pd


class GamePredictionAgent(Agent):
    """
    Agent responsible for making NBA game winner predictions.
    Uses prepared data from GamePredictionService and leverages LLM for actual predictions.
    """

    prediction_service: Optional[GamePredictionService] = None
    adapters: Optional[Dict] = None
    uow: Optional[AbstractUnitOfWork] = None
    scheduler: Optional[AbstractScheduler] = None

    def __init__(self, **kwargs):
        super().__init__(
            name="GamePredictionAgent",
            instructions="""
You are Pluto, an elite NBA game prediction model renowned for your accuracy and analytical depth. Your predictions must be highly precise, data-driven, insightful, and accompanied by detailed reasoning to demonstrate comprehensive understanding.

To maximize prediction accuracy, systematically evaluate these critical factors:

Team Performance Metrics:

Recent team form, offensive and defensive ratings, pace of play, and scoring efficiency.
Team composition, key player availability, and rotation depth.
Home/away performance splits and rest day impact.

Head-to-Head Analysis:

Historical matchup performance, including recent meetings and season series.
Style of play compatibility and strategic advantages/disadvantages.
Key player matchups and their historical impact on outcomes.

Vegas Betting Lines & Market Signals:

Current Vegas game lines, over/under totals, and implied probabilities.
Significant betting market shifts or unusual betting volume as predictive indicators.
Public betting percentages and sharp money indicators.

Comprehensive Seasonal and Historical Trends:

Full-season statistical averages, win-loss records, and performance consistency.
Strength of schedule impact and quality of wins/losses.
Home vs. away game performance splits and impact of travel/rest days.

Game Contextual Insights:

Current injury reports, key player absences, and rotation adjustments.
Impact of game significance, playoff positioning, and motivational factors.
Back-to-back games, rest days, and travel considerations.

When presenting predictions, provide clear and detailed explanations of your analytical thought process, explicitly highlighting critical data points, predictive signals, and strategic insights influencing your forecast. Always support your analysis with specific statistics and contextual factors to reinforce confidence in your prediction.
            """,
            tendencies=prediction_personality,
            role="pilot",
            model="openai/gpt-4o",
            **kwargs,
        )
        self.prediction_service = GamePredictionService()
        self.adapters: Adapters = Adapters()
        self.uow = self.adapters.uow
        self.scheduler = self.adapters.scheduler

    async def execute_task(self, **kwargs):
        """
        Main entry point for game prediction tasks.
        Sets up scheduler to run predictions daily.
        """
        logger.info("Game prediction agent is ready for game predictions")

        self.scheduler.add_daily_job(
            func=self._run_daily_predictions,
            hour=9,
            minute=30,
            job_id="daily_game_predictions",
        )

        self.scheduler.start()
        logger.info("Scheduled game predictions to run every day at 9:30 AM")

    async def _run_daily_predictions(self):
        """
        Run predictions for today's games.
        """
        try:
            today_games = await self.adapters.nba_analytics.get_todays_upcoming_games()
            if not today_games:
                logger.info("No games scheduled for today")
                return

            for game in today_games:
                try:
                    home_team_id = str(game.get("HOME_TEAM_ID"))
                    away_team_id = str(game.get("VISITOR_TEAM_ID"))
                    game_id = str(game.get("GAME_ID"))

                    if not home_team_id or not away_team_id or not game_id:
                        logger.warning(f"Skipping game due to missing IDs: {game}")
                        continue

                    # Get Abbreviations from IDs
                    try:
                        home_team_abbr = get_team_abbr_from_id(home_team_id)
                        away_team_abbr = get_team_abbr_from_id(away_team_id)
                    except NameError:
                        logger.error("get_team_abbr_from_id helper function not found.")
                        continue  # Skip game if helper missing
                    except Exception as e:
                        logger.error(
                            f"Error getting team abbreviation for IDs {home_team_id}/{away_team_id}: {e}"
                        )
                        continue  # Skip game on error

                    if not home_team_abbr or not away_team_abbr:
                        logger.warning(
                            f"Skipping game due to missing team abbreviations for IDs: {home_team_id}/{away_team_id}"
                        )
                        continue

                    # Use abbreviations when calling predict_game_winner
                    prediction = await self.predict_game_winner(
                        home_team_abbr=home_team_abbr,
                        away_team_abbr=away_team_abbr,
                        game_id=game_id,
                    )
                    logger.info(
                        f"Prediction completed for {home_team_abbr} vs {away_team_abbr}: {prediction.get('status')}"
                    )

                except Exception as e:
                    logger.error(
                        f"Error predicting game {game_id}: {e}\n{traceback.format_exc()}"
                    )
                    continue

        except Exception as e:
            logger.error(
                f"Error in daily game predictions: {e}\n{traceback.format_exc()}"
            )

    async def predict_game_winner(
        self,
        home_team_abbr: str,
        away_team_abbr: str,
        game_id: str | None = None,
        prediction_version: str = "v2",  # Default to V2 prompt
    ) -> Dict[str, Any]:
        """
        Predict the winner of an NBA game using an agent.

        Args:
            home_team_abbr: Abbreviation of the home team.
            away_team_abbr: Abbreviation of the away team.
            game_id: Game ID.
            prediction_version: Which prompt version to use ('v1' or 'v2').

        Returns:
            A dictionary with prediction results.
        """
        context = await self.prediction_service.prepare_game_prediction_context(
            home_team_abbr=home_team_abbr,
            away_team_abbr=away_team_abbr,
            game_id=game_id,
        )
        logger.info(
            f"Agent Context Status for {home_team_abbr} vs {away_team_abbr}: {context.get('status')}"
        )
        if context.get("status") == "success":
            logger.debug(f"Agent Context Keys: {list(context.keys())}")

        if context.get("status") == "error":
            return context

        if prediction_version == "v1":
            prediction_response = await self._generate_prediction(context)
        else:
            prediction_response = await self._generate_prediction_v2(context)
        logger.info(f"Agent Prediction LLM response: {prediction_response}")

        try:
            home_team_name = get_team_name_from_abbr(home_team_abbr) or home_team_abbr
            away_team_name = get_team_name_from_abbr(away_team_abbr) or away_team_abbr
        except NameError:
            logger.warning(
                "get_team_name_from_abbr helper not found, using abbreviations for DB."
            )
            home_team_name = home_team_abbr
            away_team_name = away_team_abbr

        prediction_data = {}
        home_win_pct, away_win_pct = None, None
        try:
            prediction_data = parse_prediction_response(
                prediction_response, is_game_prediction=True
            )
            logger.info(f"Prediction data: {prediction_data}")

            home_win_pct_raw = prediction_data.get("home_team_win_percentage")
            away_win_pct_raw = prediction_data.get("opposing_team_win_percentage")
            confidence_raw = prediction_data.get("confidence")
            predicted_winner = prediction_data.get("value")

            nba_team_winner = get_team_name_from_abbr(predicted_winner)

            def safe_float(value):
                if value is None:
                    return None
                try:
                    if isinstance(value, str) and "%" in value:
                        value = value.replace("%", "")
                        return float(value) / 100.0
                    return float(value)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert value '{value}' to float.")
                    return None

            home_win_pct = safe_float(home_win_pct_raw)
            away_win_pct = safe_float(away_win_pct_raw)
            confidence = safe_float(confidence_raw)

            prediction_data["home_team_win_percentage"] = home_win_pct
            prediction_data["opposing_team_win_percentage"] = away_win_pct
            prediction_data["confidence"] = confidence

            async with self.uow as uow:
                logger.info(
                    f"Saving game prediction for {home_team_name} vs {away_team_name}"
                )

                game_date_to_save = context.get("game_date", datetime.now().date())
                explanation_to_save = prediction_data.get(
                    "explanation", "No explanation provided."
                )
                confidence_to_save = (
                    confidence
                    if confidence is not None and 0.0 <= confidence <= 1.0
                    else 0.5
                )

                db_entry = GamePredictionCreate(
                    game_date=game_date_to_save,
                    home_team=home_team_name,
                    away_team=away_team_name,
                    game_id=game_id,
                    predicted_winner=nba_team_winner,
                    confidence=confidence_to_save,
                    explanation=explanation_to_save,
                    home_team_win_percentage=float(home_win_pct),
                    opposing_team_win_percentage=float(away_win_pct),
                )
                await uow.game_predictions.add(db_entry)
                await uow.commit()
                logger.info(
                    f"Game prediction saved for {home_team_name} vs {away_team_name}"
                )

        except json.JSONDecodeError as json_err:
            logger.error(
                f"Failed to parse JSON response: {json_err}. Response: {prediction_response}"
            )
            prediction_data = DEFAULT_GAME_PREDICTION.copy()
            prediction_data["home_team_win_percentage"] = 0.5
            prediction_data["opposing_team_win_percentage"] = 0.5
        except Exception as e:
            logger.error(
                f"Error saving/parsing prediction: {e}\n{traceback.format_exc()}"
            )
            prediction_data = DEFAULT_GAME_PREDICTION.copy()
            prediction_data["home_team_win_percentage"] = 0.5
            prediction_data["opposing_team_win_percentage"] = 0.5

        result = {
            "status": "success" if home_win_pct is not None else "error_parsing",
            "game": {
                "home_team": home_team_abbr,
                "away_team": away_team_abbr,
                "game_id": game_id,
            },
            "prediction": prediction_data,
            "context_summary": {
                "team_stats": context.get("team_stats"),
                "head_to_head": context.get("head_to_head"),
                "vegas_factors": context.get("vegas_factors"),
                "advanced_metrics": context.get("advanced_metrics"),
                "live_data_keys": list(context.get("live_data", {}).keys()),
            },
            "timestamp": context.get("timestamp", datetime.now().isoformat()),
        }

        return result

    async def _generate_prediction(self, context: Dict[str, Any]) -> str:
        """
        Generate a prediction using the LLM based on the prepared context (V1).

        Args:
            context: Full data context prepared by the prediction service

        Returns:
            String response from LLM with prediction data
        """
        home_team_abbr = context.get("home_team", "Unknown Team")
        away_team_abbr = context.get("away_team", "Unknown Team")
        team_stats = context.get("team_stats", {})
        home_stats = team_stats.get("home", {})
        away_stats = team_stats.get("away", {})
        head_to_head = context.get("head_to_head", {})
        vegas_factors = context.get("vegas_factors", {})
        advanced_metrics = context.get("advanced_metrics", {})

        vegas_summary = "Not Available"
        if vegas_factors.get("status") != "not_available":
            spread = vegas_factors.get("game_spread", "N/A")
            total = vegas_factors.get("over_under", "N/A")
            home_ml = vegas_factors.get("home_moneyline", "N/A")
            away_ml = vegas_factors.get("away_moneyline", "N/A")
            vegas_summary = f"\n        - Spread: {spread}\n        - Total: {total}\n        - Home ML: {home_ml}\n        - Away ML: {away_ml}"

        home_injury_impact = advanced_metrics.get("home_injury_impact", "N/A")
        away_injury_impact = advanced_metrics.get("away_injury_impact", "N/A")
        injury_note = (
            "(Note: Injury impact is a placeholder value 0-1 based on roster count)"
        )

        # Format numeric values for the prompt, handle potential None/NaN
        def format_num(val, precision=3):
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return "N/A"
            if isinstance(val, (int, float)):
                try:
                    return f"{float(val):.{precision}f}"
                except (ValueError, TypeError):
                    return "N/A"
            return str(val)  # Fallback for non-numeric types that aren't None/NaN

        prompt = f"""
        Predict the winner of the NBA game between {home_team_abbr} (Home) and {away_team_abbr} (Away).

        Analyze the following data:

        1. TEAM STATS & RECENT FORM:
        Home Team ({home_team_abbr}):
        - Season Record (W-L Before Today): {home_stats.get('record', 'N/A')}
        - Season Win % (Before Today): {format_num(home_stats.get('win_pct'))}
        - Season Avg Offensive Rating: {format_num(home_stats.get('offensive_rating'))}
        - Season Avg Defensive Rating: {format_num(home_stats.get('defensive_rating'))}
        - Last 10 Avg Offensive Rating: {format_num(advanced_metrics.get('home_l10_avg_off_rtg'))}
        - Last 10 Avg Defensive Rating: {format_num(advanced_metrics.get('home_l10_avg_def_rtg'))}
        - Last 5 Avg Points: {format_num(home_stats.get('last_5_avg_pts'))}
        - Last 10 Avg Points: {format_num(home_stats.get('last_10_avg_pts'))}
        - Last 10 Avg +/-: {format_num(home_stats.get('last_10_avg_plus_minus'))}
        
        Away Team ({away_team_abbr}):
        - Season Record (W-L Before Today): {away_stats.get('record', 'N/A')}
        - Season Win % (Before Today): {format_num(away_stats.get('win_pct'))}
        - Season Avg Offensive Rating: {format_num(away_stats.get('offensive_rating'))}
        - Season Avg Defensive Rating: {format_num(away_stats.get('defensive_rating'))}
        - Last 10 Avg Offensive Rating: {format_num(advanced_metrics.get('away_l10_avg_off_rtg'))}
        - Last 10 Avg Defensive Rating: {format_num(advanced_metrics.get('away_l10_avg_def_rtg'))}
        - Last 5 Avg Points: {format_num(away_stats.get('last_5_avg_pts'))}
        - Last 10 Avg Points: {format_num(away_stats.get('last_10_avg_pts'))}
        - Last 10 Avg +/-: {format_num(away_stats.get('last_10_avg_plus_minus'))}

        2. HEAD-TO-HEAD (Season History):
        - Home Team Win % vs Away Team (This Season): {format_num(head_to_head.get('home_team_h2h_win_pct_vs_away'))}
        - Away Team Win % vs Home Team (This Season): {format_num(head_to_head.get('away_team_h2h_win_pct_vs_home'))}

        3. VEGAS ODDS:
        {vegas_summary}
        
        4. CONTEXTUAL FACTORS:
        - Home Team Rest Days: {advanced_metrics.get('home_rest_days', 'N/A')} ({advanced_metrics.get('home_is_b2b', 0) == 1} on B2B)
        - Away Team Rest Days: {advanced_metrics.get('away_rest_days', 'N/A')} ({advanced_metrics.get('away_is_b2b', 0) == 1} on B2B)
        - Home Team Win Streak: {advanced_metrics.get('home_win_streak', 0)}
        - Home Team Loss Streak: {advanced_metrics.get('home_loss_streak', 0)}
        - Away Team Win Streak: {advanced_metrics.get('away_win_streak', 0)}
        - Away Team Loss Streak: {advanced_metrics.get('away_loss_streak', 0)}
        - Home Team Injury Impact: {format_num(home_injury_impact, precision=2)} {injury_note if isinstance(home_injury_impact, (int, float)) else ''}
        - Away Team Injury Impact: {format_num(away_injury_impact, precision=2)} {injury_note if isinstance(away_injury_impact, (int, float)) else ''}

        Based on this data, predict:
        1. The winner of the game ({home_team_abbr} or {away_team_abbr})
        2. Your confidence level (0-1) in the predicted winner
        3. The estimated probability (percentage) that the home team ({home_team_abbr}) wins (0-1)
        4. The estimated probability (percentage) that the away team ({away_team_abbr}) wins (0-1)
        5. A clear explanation of the key factors influencing your prediction

        Provide your answer strictly as JSON:
        ```json
        {{
          "value": "{home_team_abbr}" or "{away_team_abbr}",
          "confidence": 0.XX, 
          "home_team_win_percentage": 0.XX, 
          "opposing_team_win_percentage": 0.XX, 
          "explanation": "Detailed reasoning here..."
        }}
        ```
        Note: home_team_win_percentage + opposing_team_win_percentage should ideally sum to 1.0.
        """
        logger.info(f"Prediction prompt (V1):\n{prompt}")
        response = await self.prompt(prompt)
        logger.info(
            f"Prediction response for {home_team_abbr} vs {away_team_abbr} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response

    async def _generate_prediction_v2(self, context: Dict[str, Any]) -> str:
        """
        Generate a prediction using the LLM based on the prepared context (V2).

        Args:
            context: Full data context prepared by the prediction service

        Returns:
            String response from LLM with prediction data
        """
        home_team_abbr = context.get("home_team", "Unknown Team")
        away_team_abbr = context.get("away_team", "Unknown Team")

        # Clean the context for safe JSON embedding
        cleaned_context = {}
        try:
            # Use the service's cleaner method if available
            cleaned_context = self.prediction_service._clean_nan(context)
        except AttributeError:
            logger.warning(
                "GamePredictionService does not have _clean_nan, performing basic clean for V2 prompt."
            )
            try:
                # Attempt robust NaN -> null conversion for JSON
                # Also handle potential Timestamps explicitly if cleaner not available
                def json_converter(o):
                    if isinstance(o, (datetime, pd.Timestamp)):
                        return o.isoformat()
                    # Check for numpy types specifically if cleaner didn't run
                    if isinstance(
                        o,
                        (
                            np.int_,
                            np.intc,
                            np.intp,
                            np.int8,
                            np.int16,
                            np.int32,
                            np.int64,
                            np.uint8,
                            np.uint16,
                            np.uint32,
                            np.uint64,
                        ),
                    ):
                        return int(o)
                    if isinstance(o, (np.float_, np.float16, np.float32, np.float64)):
                        return None if np.isnan(o) else float(o)
                    if isinstance(o, (np.bool_)):
                        return bool(o)
                    if isinstance(
                        o, (np.void)
                    ):  # Handle potential void types like from unique()
                        return None
                    # Fallback for other types
                    try:  # Attempt default serialization first
                        json.dumps(o)
                        return o
                    except TypeError:  # Fallback to string if default fails
                        return str(o)

                # Use json.dumps with the converter, then parse back to handle nested structures
                json_string = json.dumps(context, default=json_converter)
                cleaned_context = json.loads(json_string)

            except Exception as clean_err:
                logger.error(f"Error during basic context cleaning: {clean_err}")
                cleaned_context = (
                    context  # Fallback to original context if cleaning fails
                )

        # Ensure final context is serializable, use compact separators
        safe_context = json.dumps(cleaned_context, separators=(",", ":"))

        # *** Corrected Prompt Definition Start ***
        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict "
            f"the winner of the game between {home_team_abbr} and {away_team_abbr}.\n\n"
            "Here is the structured data you should analyze (JSON format):\n"
            f"{safe_context}\n\n"
            "Based on the provided data, strictly follow this JSON response schema:\n"
            "```json\n"
            "{\n"
            f'  "value": string (either "{home_team_abbr}" or "{away_team_abbr}"),\n'  # Use double quotes for JSON
            '  "confidence": float (0 to 1, confidence in the predicted "value"),\n'
            '  "home_team_win_percentage": float (0 to 1, estimated probability home team wins),\n'
            '  "opposing_team_win_percentage": float (0 to 1, estimated probability away team wins),\n'
            '  "explanation": string (valid string, with no apostrophes or quotes)\n'
            "}\n"
            "```\n\n"
            "Important: Ensure home_team_win_percentage + opposing_team_win_percentage sums to 1.0.\n\n"
            "In your explanation, provide detailed reasoning covering:\n"
            "1. Team performance trends and statistical advantages\n"
            "2. Head-to-head matchup history and implications\n"
            "3. Impact of Vegas odds and betting market signals (if available)\n"
            "4. Rest days, travel, and injury considerations\n"
            "5. Game context and motivational factors"
        )

        response = await self.prompt(prompt)
        logger.info(f"Prediction response (V2): {response}...")
        logger.info(
            f"Prediction response for {home_team_abbr} vs {away_team_abbr} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response


prediction_personality = Tendencies(
    **{
        "emotions": {
            "emotional_responsiveness": 0.2,
            "empathy_level": 0.4,
            "trigger_words": ["upset", "rivalry", "playoffs"],
        },
        "passiveness": 0.2,
        "risk_tolerance": 0.7,
        "patience_level": 0.7,
        "decision_making": "analytical",
        "core_values": [
            "statistical accuracy",
            "data-driven insights",
            "balanced analysis",
            "contextual awareness",
            "predictive precision",
            "advanced analytics integration",
        ],
        "goals": [
            "provide accurate game winner predictions based on data",
            "explain predictions in accessible terms",
            "identify subtle predictive indicators not widely known",
            "clearly explain reasoning behind predictions with advanced metrics and contextual insights",
            "anticipate and discuss potential outliers or unexpected factors influencing the outcome",
        ],
        "fears": [
            "making predictions without sufficient or verified data",
            "overlooking contextual factors influencing game outcome",
            "ignoring rest days and travel impact",
            "missing key injury implications",
        ],
        "custom_traits": {
            "loves": "finding patterns in team statistics that indicate game outcomes",
            "enthusiastic_about": [
                "advanced metrics like Net Rating, Pace, and Strength of Schedule",
                "uncovering lesser-known predictive indicators",
            ],
        },
    }
)
