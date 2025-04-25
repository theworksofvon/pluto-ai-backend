from agency.agent import Agent
from agency.agency_types import Tendencies
from services.player_prediction import PlayerPredictionService
from typing import Dict, Optional, Any, List, Literal
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
You are Pluto, an elite agentic AI specializing in NBA player points predictions, with a particular focus on accurately forecasting Over/Under outcomes for player props. You are built for extreme accuracy, deep analytical reasoning, and clear, data-supported explanations.

Your primary objectives are:
1. Maximize prediction accuracy through rigorous, multi-factor analysis.
2. Justify every prediction with detailed, transparent reasoning based on verifiable data.
3. Identify actionable insights for Over/Under betting decisions.

Always systematically evaluate the following dimensions:

Player Performance Metrics:
- Analyze recent scoring trends, field-goal percentage, three-point shooting accuracy, free-throw efficiency.
- Evaluate player usage rate, minutes played trajectory, shot volume, and offensive role.
- Incorporate advanced shooting metrics (effective field goal %, true shooting %).

Matchup and Opponent Analysis:
- Compare historical player performance against the current opponent.
- Assess individual defender matchups, defensive schemes, and positional vulnerabilities.
- Account for opponent defensive rating, pace of play, and recent defensive form.
- Analyze player position vs. opponent positional defensive efficiency.

Market and Betting Signals:
- Integrate Vegas player prop lines, team totals, betting over/unders, and implied probabilities.
- Detect unusual market movement or betting volume patterns.
- Adjust predictions based on market consensus strength.

Contextual and Environmental Factors:
- Consider injury reports, teammate absences, starting lineups, rotations, and coaching strategies.
- Adjust for home vs. away splits, travel fatigue, back-to-backs, and rest advantages.
- Incorporate motivational factors such as playoff positioning, rivalries, or elimination games.

Historical and Long-Term Trends:
- Examine season averages, scoring volatility, and consistency patterns.
- Cross-reference game logs under comparable matchup types and conditions.

Prediction Requirements:
- Explicitly state the final predicted points value, low-high prediction range (no wider than 5 points unless necessary), and a confidence rating (0-1).
- Clearly state the Over/Under recommendation relative to the PrizePicks line.
- Provide a detailed, logically ordered explanation referencing critical data points and context.
- Always follow strict chain-of-thought reasoning — explain your decision process step-by-step.

Formatting Requirements:
- Start with a one-sentence summary prediction.
- Follow with a bullet-point breakdown of major supporting factors.
- End with a final Over/Under verdict including confidence level.

Important Behavior Rules:
- Be objective, rigorous, and transparent.
- Never fabricate statistics or trends.
- Communicate uncertainty clearly if predictive signals conflict.
- Prioritize predictive signal over noise.
- If the player is ruled out or injured, still respond using the schema but clearly explain the situation in the fields.
- ALWAYS RESPOND IN THE STRICTLY SPECIFIED JSON FORMAT.
You have web search capabilities. When possible, enrich your predictions with verified news, late-breaking injury updates, and betting market shifts. If no useful information is found, rely on core statistical and historical analysis.
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
        season_mode: Literal["regular_season", "playoffs", "finals"] = "regular_season",
    ) -> PlayerPredictionResponse:
        """
        Predict a player's performance using an agent.

        Args:
            player_name: Name of the player.
            opposing_team: Name of opposing team.
            season_mode: Mode of the season (regular_season, playoffs, finals).
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
            season_mode=season_mode,
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
            prizepicks_line: The current PrizePicks line for the player

        Returns:
            String response from LLM with prediction data
        """
        player_name = context.player
        prediction_type = context.prediction_type
        opposing_team = context.game.opposing_team
        season_mode = context.season_mode

        safe_context = json.dumps(convert_numpy_types(context)).replace("'", "")

        playoff_context = (
            "Because it is the NBA Playoffs, consider that teams are highly motivated, rotations tighten, and star players often play heavier minutes. "
            "Weigh recent performance, matchup importance, and coaching behavior accordingly.\n\n"
        )
        finals_context = (
            "Because it is the NBA Finals, assume maximum motivation, maximum minutes for starters, and extremely short rotations. "
            "Teams will fully optimize matchups and coaching adjustments will be aggressive. "
            "Clutch performance under pressure, historical Finals experience, and mental toughness should be considered. "
            "Weigh recent Finals performance more heavily than season-long or even playoff trends. "
            "Blowouts are less common — expect games to be tightly contested.\n\n"
        )
        regular_season_context = (
            "Because it is the NBA Regular Season, consider that teams may manage player minutes based on rest schedules, injuries, or playoff positioning. "
            "Weigh recent performance trends carefully, and be mindful of back-to-back games, travel fatigue, and potential rest days when projecting minutes and production.\n\n"
        )
        season_context_note = (
            finals_context
            if season_mode == "finals"
            else (
                playoff_context if season_mode == "playoffs" else regular_season_context
            )
        )

        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict the number of {prediction_type} {player_name} will record against the {opposing_team}.\n\n"
            f"Use rigorous statistical reasoning and weigh recent trends more heavily than season averages if deviations are significant. When uncertainty is high, favor matchup quality and recent minutes played. Only include values supported by strong data. Prioritize predictive signal over noise.\n\n"
            f"{season_context_note}"
            f"**Tool Usage**: First, call the web search tool to fetch the latest news, injury reports, and game recaps for {player_name} from reputable sports sites. Gather at least three recent articles (include title, source, and URL). If no relevant information is found, say 'No relevant information found.'\n"
            f"Optionally search for updates about the {opposing_team} or verified rumors that may affect {player_name}'s points projection.\n\n"
            f"REMINDER: Only use information that is timely and relevant to {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
            f"Here is the structured game and player data you must analyze (JSON format):\n"
            f"The PrizePicks line is at {prizepicks_line} {prediction_type} for {player_name}.\n\n"
            f"{safe_context}\n\n"
            f"Pay close attention to the 'historical_predictions' section. Analyze your past predictions for similar matchups, note any discrepancies between forecast and actual result, and refine your current prediction accordingly.\n\n"
            f"***IMPORTANT***: Based on all inputs, return ONLY in the following strict JSON format:\n"
            "```json\n"
            "{\n"
            '  "value": float,\n'
            '  "range_low": float,\n'
            '  "range_high": float,\n'
            '  "confidence": float (0 to 1),\n'
            '  "explanation": string (avoid using apostrophes to ensure valid JSON),\n'
            '  "prizepicks_line": "over" or "under",\n'
            '  "prizepicks_reason": string (explaining why you chose over/under based on the line),\n'
            '  "additional_context": string (optional; verified rumors or news found during search)\n'
            "}\n"
            "```\n\n"
            f"If {player_name} is ruled out or injured, still respond using the schema but clearly explain the situation in the fields.\n\n"
            "In your explanation, address these critical factors:\n"
            "1. Recent player performance trends\n"
            "2. Historical performance versus the opponent\n"
            "3. Vegas odds and betting market signals\n"
            "4. Season-long and advanced statistical insights\n"
            "5. Contextual factors (injuries, rotations, motivation)\n"
            "6. Clear Over/Under recommendation for PrizePicks line\n"
        )

        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt, web_search=True)
        logger.info(
            f"Prediction response for player {player_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response
