from agency.agent import Agent
from agency.agency_types import Tendencies
from services.game_prediction import GamePredictionService
from typing import Dict, Optional, Any, List
from adapters import Adapters
from adapters.db.abstract_uow import AbstractUnitOfWork
from adapters.scheduler import AbstractScheduler
from logger import logger
from datetime import datetime
import json
import numpy as np
import traceback
from agents.helpers import (
    get_team_abbr_from_id,
    get_team_name_from_abbr,
    GAME_PREDICTION_PERSONALITY,
    DEFAULT_GAME_PREDICTION,
)
from schemas import GamePredictionCreate
import pandas as pd
from utils import FieldSchema, FieldType, SchemaJsonParser


class GamePredictionAgent(Agent):
    """
    Agent responsible for making NBA game winner predictions.
    Uses prepared data from GamePredictionService and leverages LLM for actual predictions.
    """

    prediction_service: Optional[GamePredictionService] = None
    adapters: Optional[Dict] = None
    uow: Optional[AbstractUnitOfWork] = None
    scheduler: Optional[AbstractScheduler] = None
    game_prediction_schema: List[FieldSchema] = []
    parser: SchemaJsonParser = None

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
            tendencies=GAME_PREDICTION_PERSONALITY,
            role="pilot",
            model="openai/gpt-4o",
            **kwargs,
        )
        self.prediction_service = GamePredictionService()
        self.adapters: Adapters = Adapters()
        self.uow = self.adapters.uow
        self.scheduler = self.adapters.scheduler
        self.game_prediction_schema = [
            FieldSchema(name="value", type=FieldType.STRING, required=True),
            FieldSchema(name="confidence", type=FieldType.NUMBER, required=True),
            FieldSchema(
                name="home_team_win_percentage", type=FieldType.NUMBER, required=True
            ),
            FieldSchema(
                name="opposing_team_win_percentage",
                type=FieldType.NUMBER,
                required=True,
            ),
            FieldSchema(name="explanation", type=FieldType.STRING, required=True),
            FieldSchema(name="prizepicks_line", type=FieldType.STRING, required=False),
            FieldSchema(
                name="prizepicks_reason", type=FieldType.STRING, required=False
            ),
            FieldSchema(
                name="additional_context", type=FieldType.STRING, required=False
            ),
        ]
        self.parser = SchemaJsonParser(self.game_prediction_schema)

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
    ) -> Dict[str, Any]:
        """
        Predict the winner of an NBA game using an agent.

        Args:
            home_team_abbr: Abbreviation of the home team.
            away_team_abbr: Abbreviation of the away team.
            game_id: Game ID.

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

        prediction_response = await self._generate_prediction(context)
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
            prediction_data = self.parser.parse(prediction_response)
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
            cleaned_context = self.prediction_service._clean_nan(context)
        except AttributeError:
            logger.warning(
                "GamePredictionService does not have _clean_nan, performing basic clean for prompt."
            )
            try:

                def json_converter(o):
                    if isinstance(o, (datetime, pd.Timestamp)):
                        return o.isoformat()
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
                    if isinstance(o, (np.void)):
                        return None
                    try:
                        json.dumps(o)
                        return o
                    except TypeError:
                        return str(o)

                json_string = json.dumps(context, default=json_converter)
                cleaned_context = json.loads(json_string)

            except Exception as clean_err:
                logger.error(f"Error during basic context cleaning: {clean_err}")
                cleaned_context = context

        safe_context = json.dumps(cleaned_context, separators=(",", ":"))

        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict "
            f"the winner of the game between {home_team_abbr} and {away_team_abbr}.\n\n"
            f"Because it is the NBA Play-Offs, consider that teams could potentially be highly motivated and rotations are likely to tighten. Starters may play heavier minutes, and coaches will prioritize winning over player rest. Weigh recent performance, matchup importance, and coaching tendencies accordingly when making your prediction."
            f"**Tool usage**: First, call the web search tool to fetch the very latest news, injury updates, and game recaps for {home_team_abbr} and {away_team_abbr} from reputable sports sites. Gather at least 3 of the most recent articles (include title, source name, and URL)."
            f"Then, use the web search results to inform your prediction. If there is no relevant information, just say 'No relevant information found'."
            f"You can also use the web search tool to find information about the {home_team_abbr} and {away_team_abbr} and their players."
            f"Finally, you can use the web search tool to find any verified gossip/rumors about the players and the team. Anything that you think will affect the performance of {home_team_abbr} or {away_team_abbr}. Do not make up any information, only use the information that you find that has been verified by a reputable source."
            "Here is the structured data you should analyze (JSON format):\n"
            f"{safe_context}\n\n"
            "Based on the provided data, strictly follow this JSON response schema:\n"
            "```json\n"
            "{\n"
            f'  "value": string (either "{home_team_abbr}" or "{away_team_abbr}"),\n'
            '  "confidence": float (0 to 1, confidence in the predicted "value"),\n'
            '  "home_team_win_percentage": float (0 to 1, estimated probability home team wins),\n'
            '  "opposing_team_win_percentage": float (0 to 1, estimated probability away team wins),\n'
            '  "explanation": string (valid string, with no apostrophes or quotes)\n'
            '  "additional_context": string (any additional context that you think is relevant to the prediction, this could be any gossip/rumors you found that are verified or relevant articles)\n'
            "}\n"
            "```\n\n"
            "Important: Ensure home_team_win_percentage + opposing_team_win_percentage sums to 1.0.\n\n"
            "In your explanation, provide detailed reasoning covering:\n"
            "1. Team performance trends and statistical advantages\n"
            "2. Head-to-head matchup history and implications\n"
            "3. Impact of Vegas odds and betting market signals (if available)\n"
            "4. Rest days, travel, and injury considerations\n"
            "5. Game context and motivational factors\n"
            "6. Additional context that you found that is relevant to the prediction"
        )

        response = await self.prompt(prompt, web_search=True)
        logger.info(f"Prediction response (V2): {response}...")
        logger.info(
            f"Prediction response for {home_team_abbr} vs {away_team_abbr} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response
