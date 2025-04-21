from agency.agent import Agent
from agency.agency_types import Tendencies
from services.player_prediction import PlayerPredictionService
from typing import Dict, Optional, Any, List
from adapters import Adapters
from adapters.db.abstract_uow import AbstractUnitOfWork
from adapters.scheduler import AbstractScheduler
from logger import logger
from datetime import datetime
import json
from utils import FieldSchema, FieldType, SchemaJsonParser
from agents.helpers import DEFAULT_PLAYER_PREDICTION, PLAYER_PREDICTION_PERSONALITY
from schemas import PlayerPredictionCreate, PredictionType
import numpy as np
import pandas as pd
from models.prediction_models import PlayerPredictionResponse, Game, PredictionData
from models.prediction_context import PredictionContext

import numpy as np
import pandas as pd
import json


def convert_numpy_types(obj):
    """Convert NumPy and Pydantic types to native Python types for JSON serialization."""
    if hasattr(obj, "model_dump"):
        return convert_numpy_types(obj.model_dump())
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    return obj


class PlayerPredictionAgent(Agent):
    """
    Agent responsible for making NBA player predictions.
    Uses prepared data from PlayerPredictionService and leverages LLM for actual predictions.
    """

    prediction_service: Optional[PlayerPredictionService] = None
    adapters: Optional[Dict] = None
    uow: Optional[AbstractUnitOfWork] = None
    scheduler: Optional[AbstractScheduler] = None
    player_prediction_schema: List[FieldSchema] = []
    parser: SchemaJsonParser = None

    def __init__(self, **kwargs):
        super().__init__(
            name="PlayerPredictionAgent",
            instructions="""
You are Pluto, an elite NBA player-points prediction model renowned for your accuracy and analytical depth. Your predictions must be highly precise, data-driven, insightful, and accompanied by detailed reasoning to demonstrate comprehensive understanding.

To maximize prediction accuracy, systematically evaluate these critical factors:

Player Performance Metrics:

Recent scoring form, field-goal percentage, three-point shooting accuracy, and free-throw efficiency.

Player usage rate, minutes played trends, and offensive role within the team.

Advanced Matchup Analysis:

Historical performance versus the specific opponent, noting defensive strategies, individual defender assignments, and positional vulnerabilities.

Defensive rating and pace of play of the opponent team.

Comparative analysis of player position vs. opponents defensive efficiency.

Vegas Betting Lines & Market Signals:

Current Vegas player props, betting lines, over/under points totals, and implied probability.

Significant betting market shifts or unusual betting volume as predictive indicators.

Comprehensive Seasonal and Historical Trends:

Full-season statistical averages, scoring volatility, and consistency metrics.

Home vs. away game performance splits and impact of travel/rest days.

Game and Player Contextual Insights:

Current injury reports, teammate absences, rotation adjustments, and coaching decisions.

Impact of game significance, rivalry intensity, playoff positioning, and motivational factors.

When presenting predictions, provide clear and detailed explanations of your analytical thought process, explicitly highlighting critical data points, predictive signals, and strategic insights influencing your forecast. Always support your analysis with specific statistics and contextual factors to reinforce confidence in your prediction.
            """,
            tendencies=PLAYER_PREDICTION_PERSONALITY,
            role="pilot",
            model="openai-gpt-4o-mini",
            **kwargs,
        )
        self.prediction_service = PlayerPredictionService()
        self.adapters: Adapters = Adapters()
        self.uow = self.adapters.uow
        self.scheduler = self.adapters.scheduler
        self.player_prediction_schema = [
            FieldSchema(name="value", type=FieldType.NUMBER, required=True),
            FieldSchema(name="range_low", type=FieldType.NUMBER, required=False),
            FieldSchema(name="range_high", type=FieldType.NUMBER, required=False),
            FieldSchema(name="confidence", type=FieldType.NUMBER, required=True),
            FieldSchema(name="explanation", type=FieldType.STRING, required=True),
            FieldSchema(name="prizepicks_line", type=FieldType.STRING, required=False),
            FieldSchema(
                name="prizepicks_reason", type=FieldType.STRING, required=False
            ),
            FieldSchema(
                name="additional_context", type=FieldType.STRING, required=False
            ),
        ]
        self.parser = SchemaJsonParser(self.player_prediction_schema)

    async def execute_task(self, **kwargs):
        """
        Main entry point for player prediction tasks.
        Sets up scheduler to run predictions every 2 minutes for testing.
        """
        logger.info("Player prediction agent is ready for player predictions")

        self.scheduler.add_daily_job(
            func=self._run_daily_predictions,
            hour=9,
            minute=30,
            job_id="daily_player_predictions",
        )

        self.scheduler.start()
        logger.info("Scheduled predictions to run every day at 9:30 AM")

    async def _run_daily_predictions(self, retry_count: int = 0, max_retries: int = 2):
        """
        Run predictions for today's games and key players.
        Includes retry logic with a maximum of 2 retries.

        Args:
            retry_count: Current number of retry attempts
            max_retries: Maximum number of retry attempts allowed
        """
        logger.info("Running daily player predictions...")
        try:
            today_games = await self.adapters.nba_analytics.get_todays_upcoming_games()
            logger.info(f"Today's games: {today_games}")
            if not today_games:
                logger.info("No games scheduled for today")
                return
            game_players = await self.adapters.nba_analytics.get_game_players(
                today_games
            )
            logger.info(f"Game players: {game_players}")
            if not game_players:
                logger.info("No key players identified for today's games")
                return

            for player, team, opposing_team in game_players:
                try:
                    prediction = await self.predict_player_performance(
                        player_name=player,
                        team=team,
                        opposing_team=opposing_team,
                        prediction_type="points",
                    )
                    logger.info(f"Prediction completed for {player}: {prediction}")

                except Exception as e:
                    logger.error(f"Error predicting for player {player}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in daily player predictions: {e}")
            if retry_count < max_retries:
                logger.info(
                    f"Retrying daily player predictions (attempt {retry_count + 1}/{max_retries})"
                )
                await self._run_daily_predictions(retry_count + 1, max_retries)
            else:
                logger.error("Max retries reached for daily predictions")

    async def predict_player_performance(
        self,
        player_name: str,
        opposing_team: str,
        prediction_type: str = "points",
        team: Optional[str] = None,
        prizepicks_line: Optional[str] = None,
        additional_context: Optional[str] = None,
    ) -> PlayerPredictionResponse:
        """
        Predict a player's performance using an agent.

        Args:
            player_name: Name of the player.
            opposing_team: Name of opposing team.
            prediction_type: Type of prediction (points, rebounds, assists, etc.).

        Returns:
            A dictionary with prediction results.
        """
        context = await self.prediction_service.prepare_prediction_context(
            player_name=player_name,
            opposing_team=opposing_team,
            prediction_type=prediction_type,
            model_type=prediction_type,
            additional_context=additional_context,
        )
        logger.info(f"Agent Context: {context}")

        if context.status == "error":
            return context

        prediction_response = await self._generate_prediction(context, prizepicks_line)
        logger.info(f"Agent Prediction response: {prediction_response}")

        try:
            prediction_data = self.parser.parse(prediction_response)
            async with self.uow as uow:
                logger.info(
                    f"Saving player prediction for {player_name} vs {opposing_team}"
                )
                if prediction_response is not None:
                    await uow.player_predictions.add(
                        PlayerPredictionCreate(
                            game_date=context.game.game_date,
                            player_name=player_name,
                            team=team or "",
                            opposing_team=opposing_team,
                            prediction_type=PredictionType(prediction_type.lower()),
                            predicted_value=prediction_data["value"],
                            range_low=prediction_data["range_low"],
                            range_high=prediction_data["range_high"],
                            confidence=prediction_data["confidence"],
                            explanation=prediction_data["explanation"],
                            prizepicks_prediction=prediction_data["prizepicks_line"],
                            prizepicks_reason=prediction_data["prizepicks_reason"],
                            prizepicks_line=float(prizepicks_line),
                        )
                    )
                await uow.commit()
                logger.info(
                    f"Player prediction saved for {player_name} vs {opposing_team}"
                )
        except Exception as e:
            logger.error(f"Error saving/parsing prediction: {e}")
            prediction_data = DEFAULT_PLAYER_PREDICTION.copy()

        return PlayerPredictionResponse(
            status="success",
            player=player_name,
            game=Game(opposing_team=opposing_team, game_date=context.game.game_date),
            prediction_type=prediction_type,
            prediction=PredictionData(**prediction_data),
            recent_form=context.recent_form,
            prizepicks_factors=context.prizepicks_factors,
            vegas_factors=context.vegas_factors,
            timestamp=context.timestamp,
            model_prediction=context.model_prediction,
        )

    async def _generate_prediction(
        self, context: PredictionContext, prizepicks_line: str
    ) -> str:
        """
        Generate a prediction using the LLM based on the prepared context.

        Args:
            context: Full data context prepared by the prediction service

        Returns:
            String response from LLM with prediction data
        """
        player_name = context.player
        prediction_type = context.prediction_type
        opposing_team = context.game.opposing_team
        # Convert NumPy types before JSON serialization
        safe_context = json.dumps(convert_numpy_types(context)).replace("'", "")

        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict"
            f"Use statistical reasoning and weigh recent trends more heavily than season averages if there is a strong deviation. Favor matchups and recent minutes played when uncertainty is high. Only include values that are well-supported by the data. Prioritize predictive signal over noise."
            f"Because it is the NBA Play-Offs, consider that teams could potentially be highly motivated and rotations are likely to tighten. Starters may play heavier minutes, and coaches will prioritize winning over player rest. Weigh recent performance, matchup importance, and coaching tendencies accordingly when making your prediction."
            f"**Tool usage**: First, call the web search tool to fetch the very latest news, injury updates, and game recaps for {player_name} from reputable sports sites. Gather at least 3 of the most recent articles (include title, source name, and URL)."
            f"Then, use the web search results to inform your prediction. If there is no relevant information, just say 'No relevant information found'."
            f"You can also use the web search tool to find information about the {opposing_team} and their players."
            f"Finally, you can use the web search tool to find any verified gossip/rumors about the players and the team. Anything that you think will affect the points of {player_name}. Do not make up any information, only use the information that you find that has been verified by a reputable source."
            f"REMINDER: Only use information thats relevant to current date and time. {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            f"Here is all the relevant data:"
            f"how many {prediction_type} the player {player_name} will record against the {opposing_team}.\n\n"
            f"The PrizePicks line is at {prizepicks_line} points for {player_name}.\n\n"
            "Here is the structured data you should analyze (JSON format):\n"
            f"{safe_context}\n\n"
            "Pay close attention to the 'historical_predictions' section within the data. This shows your past predictions for this exact matchup and the actual results. Analyze your past performance, noting any discrepancies, and use this analysis to refine your current prediction and reasoning.\n\n"
            "Based on the provided data, strictly follow this JSON response schema:\n"
            "A reasonable prediction range (low-high) that is no wider than 5 points unless absolutely necessary, based on the data."
            "```json\n"
            "{\n"
            '  "value": float,\n'
            '  "range_low": float,\n'
            '  "range_high": float,\n'
            '  "confidence": float (0 to 1),\n'
            '  "explanation": string (avoid using apostrophes to ensure valid JSON)\n'
            '  "prizepicks_line": "over" or "under",\n'
            '  "prizepicks_reason": "Reasoning for the line choice"\n'
            '  "additional_context": "Any additional context that you think is relevant to the prediction, this could be any gossip/rumors you found that are verified or relevant articles"\n'
            "}\n"
            "```\n\n"
            f"*****REMINDER: Always respond in the appropriate format if a player is injured or not playing, but provide the reason for your prediction.*****"
            "In your explanation, provide detailed reasoning covering:\n"
            "1. Recent player performance trends\n"
            "2. Historical matchup performance\n"
            "3. Impact of Vegas odds and betting lines\n"
            "4. Season-long statistical insights and advanced metrics\n"
            "5. Contextual factors (e.g., injuries, rotations, importance of the game)\n"
            "6. Over/Under on the PrizePicks line and why.\n"
        )

        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt, web_search=True)
        logger.info(
            f"Prediction response for player {player_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response
