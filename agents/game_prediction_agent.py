from agency.agent import Agent
from agency.agency_types import Tendencies
from services.game_prediction import GamePredictionService
from typing import Dict, Optional, Any, List, Tuple
from adapters import Adapters
from adapters.db.abstract_uow import AbstractUnitOfWork
from adapters.scheduler import AbstractScheduler
from logger import logger
from datetime import datetime
import json
from agents.helpers.prediction_helpers import (
    parse_prediction_response,
    DEFAULT_PREDICTION,
)
from agents.helpers.team_helpers import get_team_name_from_id
from schemas import GamePredictionCreate, PredictionType


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
            name="Pluto",
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
            model="openai-deepseek-reasoner",
            **kwargs,
        )
        self.prediction_service = GamePredictionService()
        self.adapters: Adapters = Adapters()
        self.uow = self.adapters.uow
        self.scheduler = self.adapters.scheduler

    async def execute_task(self, **kwargs):
        """
        Main entry point for game prediction tasks.
        Sets up scheduler to run predictions every 2 minutes for testing.
        """
        logger.info("Game prediction agent is ready for game predictions")

        # Schedule daily predictions
        self.scheduler.add_daily_job(
            func=self._run_daily_predictions,
            hour=9,
            minute=30,
            job_id="daily_game_predictions",
        )

        # Start the scheduler
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

                    home_team = get_team_name_from_id(home_team_id)
                    away_team = get_team_name_from_id(away_team_id)

                    if not home_team or not away_team:
                        logger.warning(
                            f"Skipping game due to missing team names: {game}"
                        )
                        continue

                    prediction = await self.predict_game_winner(
                        home_team=home_team,
                        away_team=away_team,
                        game_id=game_id,
                    )
                    logger.info(
                        f"Prediction completed for {home_team} vs {away_team}: {prediction}"
                    )

                except Exception as e:
                    logger.error(f"Error predicting game {game_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in daily game predictions: {e}")

    async def predict_game_winner(
        self,
        home_team: str,
        away_team: str,
        game_id: str,
        prediction_version: str = "v1",
    ) -> Dict[str, Any]:
        """
        Predict the winner of an NBA game using an agent.

        Args:
            home_team: Name of the home team.
            away_team: Name of the away team.
            game_id: Game ID.

        Returns:
            A dictionary with prediction results.
        """
        context = await self.prediction_service.prepare_game_prediction_context(
            home_team=home_team,
            away_team=away_team,
            game_id=game_id,
        )
        logger.info(f"Agent Context: {context}")

        if context.get("status") == "error":
            return context

        if prediction_version == "v1":
            prediction_response = await self._generate_prediction(context)
        else:
            prediction_response = await self._generate_prediction_v2(context)
        logger.info(f"Agent Prediction response: {prediction_response}")

        try:
            prediction_data = parse_prediction_response(prediction_response)
            async with self.uow as uow:
                logger.info(f"Saving game prediction for {home_team} vs {away_team}")
                await uow.game_predictions.add(
                    GamePredictionCreate(
                        game_date=context.get("game_date", datetime.now().date()),
                        home_team=home_team,
                        away_team=away_team,
                        game_id=game_id,
                        prediction_type=PredictionType("game_winner"),
                        predicted_winner=prediction_data["value"],
                        confidence=prediction_data["confidence"],
                        explanation=prediction_data["explanation"],
                    )
                )
                await uow.commit()
                logger.info(f"Game prediction saved for {home_team} vs {away_team}")
        except Exception as e:
            logger.error(f"Error saving/parsing prediction: {e}")
            prediction_data = DEFAULT_PREDICTION.copy()

        result = {
            "status": "success",
            "game": {
                "home_team": home_team,
                "away_team": away_team,
                "game_id": game_id,
            },
            "prediction": prediction_data,
            "team_stats": context.get("team_stats"),
            "head_to_head": context.get("head_to_head"),
            "vegas_factors": context.get("vegas_factors"),
            "timestamp": context.get("timestamp"),
            "model_prediction": context.get("model_prediction", "not available"),
        }

        return result

    async def _generate_prediction(self, context: Dict[str, Any]) -> str:
        """
        Generate a prediction using the LLM based on the prepared context.

        Args:
            context: Full data context prepared by the prediction service

        Returns:
            String response from LLM with prediction data
        """
        home_team = context.get("home_team", "Unknown Team")
        away_team = context.get("away_team", "Unknown Team")
        team_stats = context.get("team_stats", {})
        head_to_head = context.get("head_to_head", {})
        vegas_factors = context.get("vegas_factors", {})
        advanced_metrics = context.get("advanced_metrics", {})

        prompt = f"""
        I need you to predict the winner of the NBA game between {home_team} and {away_team}.

        Here's all the relevant data:

        TEAM STATS:
        Home Team ({home_team}):
        - Record: {team_stats.get('home_record', 'N/A')}
        - Home record: {team_stats.get('home_home_record', 'N/A')}
        - Last 10 games: {team_stats.get('home_last_10', 'N/A')}
        - Offensive rating: {team_stats.get('home_offensive_rating', 'N/A')}
        - Defensive rating: {team_stats.get('home_defensive_rating', 'N/A')}
        - Net rating: {team_stats.get('home_net_rating', 'N/A')}
        - Pace: {team_stats.get('home_pace', 'N/A')}

        Away Team ({away_team}):
        - Record: {team_stats.get('away_record', 'N/A')}
        - Away record: {team_stats.get('away_away_record', 'N/A')}
        - Last 10 games: {team_stats.get('away_last_10', 'N/A')}
        - Offensive rating: {team_stats.get('away_offensive_rating', 'N/A')}
        - Defensive rating: {team_stats.get('away_defensive_rating', 'N/A')}
        - Net rating: {team_stats.get('away_net_rating', 'N/A')}
        - Pace: {team_stats.get('away_pace', 'N/A')}

        HEAD TO HEAD:
        - Season series: {head_to_head.get('season_series', 'N/A')}
        - Last meeting: {head_to_head.get('last_meeting', 'N/A')}
        - Last meeting date: {head_to_head.get('last_meeting_date', 'N/A')}
        - Average margin: {head_to_head.get('average_margin', 'N/A')}

        VEGAS ODDS:
        - Game spread: {vegas_factors.get('game_spread', 'N/A')}
        - Over/under: {vegas_factors.get('over_under', 'N/A')}
        - Home team moneyline: {vegas_factors.get('home_moneyline', 'N/A')}
        - Away team moneyline: {vegas_factors.get('away_moneyline', 'N/A')}
        - Public betting percentages: {vegas_factors.get('public_betting', 'N/A')}

        ADVANCED METRICS:
        - Home team strength of schedule: {advanced_metrics.get('home_sos', 'N/A')}
        - Away team strength of schedule: {advanced_metrics.get('away_sos', 'N/A')}
        - Home team rest days: {advanced_metrics.get('home_rest_days', 'N/A')}
        - Away team rest days: {advanced_metrics.get('away_rest_days', 'N/A')}
        - Home team injury impact: {advanced_metrics.get('home_injury_impact', 'N/A')}
        - Away team injury impact: {advanced_metrics.get('away_injury_impact', 'N/A')}

        LINEAR REGRESSION MODEL PREDICTION:
        - The linear regression model predicts {context.get('model_prediction', 'not available')}

        Based on this data, predict:
        1. The winner of the game (home team or away team)
        2. Your confidence level (0-1)
        3. A clear explanation of the key factors influencing your prediction

        Provide your answer as JSON in this format:
        ```json
        {{
          'value': 'home_team' or 'away_team',
          'confidence': 0.75,
          'explanation': 'Detailed reasoning here...'
        }}
        ```
        """
        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt)
        logger.info(
            f"Prediction response for {home_team} vs {away_team} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response

    async def _generate_prediction_v2(self, context: Dict[str, Any]) -> str:
        """
        Generate a prediction using the LLM based on the prepared context.

        Args:
            context: Full data context prepared by the prediction service

        Returns:
            String response from LLM with prediction data
        """
        home_team = context.get("home_team", "Unknown Team")
        away_team = context.get("away_team", "Unknown Team")

        safe_context = json.dumps(context).replace("'", "")

        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict "
            f"the winner of the game between {home_team} and {away_team}.\n\n"
            "Here is the structured data you should analyze (JSON format):\n"
            f"{safe_context}\n\n"
            "Based on the provided data, strictly follow this JSON response schema:\n"
            "```json\n"
            "{\n"
            "  \"value\": string (either 'home_team' or 'away_team'),\n"
            '  "confidence": float (0 to 1),\n'
            '  "explanation": string (avoid using apostrophes to ensure valid JSON)\n'
            "}\n"
            "```\n\n"
            "In your explanation, provide detailed reasoning covering:\n"
            "1. Team performance trends and statistical advantages\n"
            "2. Head-to-head matchup history and implications\n"
            "3. Impact of Vegas odds and betting market signals\n"
            "4. Rest days, travel, and injury considerations\n"
            "5. Game context and motivational factors"
        )

        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt)
        logger.info(
            f"Prediction response for {home_team} vs {away_team} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
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
