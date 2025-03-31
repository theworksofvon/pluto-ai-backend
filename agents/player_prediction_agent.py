from agency.agent import Agent
from agency.agency_types import Tendencies
from services.player_prediction import PlayerPredictionService
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
from schemas import PlayerPredictionCreate, PredictionType


class PlayerPredictionAgent(Agent):
    """
    Agent responsible for making NBA player predictions.
    Uses prepared data from PlayerPredictionService and leverages LLM for actual predictions.
    """

    prediction_service: Optional[PlayerPredictionService] = None
    adapters: Optional[Dict] = None
    uow: Optional[AbstractUnitOfWork] = None
    scheduler: Optional[AbstractScheduler] = None

    def __init__(self, **kwargs):
        super().__init__(
            name="Pluto",
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
            tendencies=prediction_personality,
            role="pilot",
            model="openai-deepseek-reasoner",
            **kwargs,
        )
        self.prediction_service = PlayerPredictionService()
        self.adapters: Adapters = Adapters()
        self.uow = self.adapters.uow
        self.scheduler = self.adapters.scheduler

    async def execute_task(self, **kwargs):
        """
        Main entry point for player prediction tasks.
        Sets up scheduler to run predictions every 2 minutes for testing.
        """
        logger.info("Player prediction agent is ready for player predictions")

        # Schedule daily predictions
        self.scheduler.add_daily_job(
            func=self._run_daily_predictions,
            hour=9,
            minute=30,
            job_id="daily_predictions",
        )

        # Start the scheduler
        self.scheduler.start()
        logger.info("Scheduled predictions to run every day at 9:30 AM")

    async def _run_daily_predictions(self):
        """
        Run predictions for today's games and key players.
        """
        try:
            today_games = await self.adapters.nba_analytics.get_todays_upcoming_games()
            if not today_games:
                logger.info("No games scheduled for today")
                return
            game_players = await self._get_game_players(today_games)
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
            logger.error(f"Error in daily predictions: {e}")

    async def _get_game_players(self, games: List[Dict]) -> List[Tuple[str, str, str]]:
        """
        Get all players from today's games.
        Returns a list of tuples containing (player_name, team, opposing_team).
        """
        players = []
        try:
            for game in games:
                home_team_id = str(game.get("HOME_TEAM_ID"))
                away_team_id = str(game.get("VISITOR_TEAM_ID"))

                if not home_team_id or not away_team_id:
                    logger.warning(f"Skipping game due to missing team IDs: {game}")
                    continue

                # Convert team IDs to names
                home_team_name = get_team_name_from_id(home_team_id)
                away_team_name = get_team_name_from_id(away_team_id)

                if not home_team_name or not away_team_name:
                    logger.warning(f"Skipping game due to missing team names: {game}")
                    continue

                # Get players from both teams
                home_players = await self.adapters.nba_analytics.get_starting_lineup(
                    home_team_name
                )
                away_players = await self.adapters.nba_analytics.get_starting_lineup(
                    away_team_name
                )

                for player in home_players:
                    players.append(
                        (player.get("player_name"), home_team_name, away_team_name)
                    )

                for player in away_players:
                    players.append(
                        (player.get("player_name"), away_team_name, home_team_name)
                    )

            return players
        except Exception as e:
            logger.error(f"Error getting players: {e}")
            return []

    async def predict_player_performance(
        self,
        player_name: str,
        opposing_team: str,
        prediction_type: str = "points",
        team: Optional[str] = None,
        game_id: Optional[str] = None,
        prediction_version: str = "v1",
    ) -> Dict[str, Any]:
        """
        Predict a player's performance using an agent.

        Args:
            player_name: Name of the player.
            opposing_team: Name of opposing team.
            prediction_type: Type of prediction (points, rebounds, assists, etc.).
            game_id: Optional game ID.

        Returns:
            A dictionary with prediction results.
        """
        context = await self.prediction_service.prepare_prediction_context(
            player_name=player_name,
            opposing_team=opposing_team,
            prediction_type=prediction_type,
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
                logger.info(
                    f"Saving player prediction for {player_name} vs {opposing_team}"
                )
                await uow.player_predictions.add(
                    PlayerPredictionCreate(
                        game_date=context.get("game_date", datetime.now().date()),
                        player_name=player_name,
                        team=team or "",
                        opposing_team=opposing_team,
                        prediction_type=PredictionType(prediction_type.lower()),
                        predicted_value=prediction_data["value"],
                        range_low=prediction_data["range_low"],
                        range_high=prediction_data["range_high"],
                        confidence=prediction_data["confidence"],
                        explanation=prediction_data["explanation"],
                    )
                )
                await uow.commit()
                logger.info(
                    f"Player prediction saved for {player_name} vs {opposing_team}"
                )
        except Exception as e:
            logger.error(f"Error saving/parsing prediction: {e}")
            prediction_data = DEFAULT_PREDICTION.copy()

        result = {
            "status": "success",
            "player": player_name,
            "game": {"opposing_team": opposing_team, "game_id": game_id},
            "prediction_type": prediction_type,
            "prediction": prediction_data,
            "recent_form": context.get("recent_form"),
            "prizepicks_factors": context.get("prizepicks_factors"),
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
        player_name = context.get("player", "Unknown Player")
        prediction_type = context.get("prediction_type", "points")
        opposing_team = context.get("game", {}).get("opposing_team", "Unknown Team")
        recent_form = context.get("recent_form", {})
        vegas_factors = context.get("vegas_factors", {})
        team_matchup = context.get("team_matchup", {})
        season_stats = context.get("season_stats", {})
        advanced_metrics = context.get("advanced_metrics", {})
        prizepicks_factors = context.get("prizepicks_factors", {})

        logger.info(f"Agent Player Name: {player_name}")
        logger.info(f"Agent Prediction Type: {prediction_type}")
        logger.info(f"Agent Opposing Team: {opposing_team}")
        logger.info(f"Agent Recent Form: {recent_form}")
        logger.info(f"Agent Vegas Factors: {vegas_factors}")
        logger.info(f"Agent Team Matchup: {team_matchup}")
        logger.info(f"Agent Season Stats: {season_stats}")
        logger.info(f"Agent PrizePicks Factors: {prizepicks_factors}")

        prizepicks_str = (
            "\n".join(
                [f"- {key}: {value}" for key, value in prizepicks_factors.items()]
            )
            if prizepicks_factors
            else "No PrizePicks data available"
        )

        recent_avg_5 = (
            f"{recent_form.get('recent_average_5', 0):.1f}"
            if recent_form.get("recent_average_5") is not None
            else "N/A"
        )
        recent_avg_10 = (
            f"{recent_form.get('recent_average_10', 0):.1f}"
            if recent_form.get("recent_average_10") is not None
            else "N/A"
        )
        season_avg = (
            f"{season_stats.get('season_average', 0):.1f}"
            if season_stats.get("season_average") is not None
            else "N/A"
        )
        home_avg = (
            f"{season_stats.get('home_average', 0):.1f}"
            if season_stats.get("home_average") is not None
            else "N/A"
        )
        away_avg = (
            f"{season_stats.get('away_average', 0):.1f}"
            if season_stats.get("away_average") is not None
            else "N/A"
        )
        last_30_avg = (
            f"{season_stats.get('last_30_days_avg', 0):.1f}"
            if season_stats.get("last_30_days_avg") is not None
            else "N/A"
        )
        matchup_avg = (
            f"{team_matchup.get('avg_vs_opponent', 0):.1f}"
            if team_matchup.get("avg_vs_opponent") is not None
            else "N/A"
        )
        std_dev = (
            f"{recent_form.get('std_deviation', 0):.2f}"
            if recent_form.get("std_deviation") is not None
            else "N/A"
        )
        comparison = team_matchup.get("comparison_to_season_avg", 0)
        comparison_str = (
            f"{comparison:.1f}% {'higher' if comparison > 0 else 'lower' if comparison < 0 else ''}"
            if comparison is not None
            else "N/A"
        )

        prompt = f"""
        I need you to predict how many {prediction_type} {player_name} will record against {opposing_team}.

        Here's all the relevant data:

      RECENT FORM (Last 5 games):
        - Average: {recent_avg_5}
        - 10-game average: {recent_avg_10}
        - Recent high: {recent_form.get('recent_max', 'N/A')}
        - Recent low: {recent_form.get('recent_min', 'N/A')}
        - Trend: {recent_form.get('trend', 'N/A')}
        - Game values: {recent_form.get('recent_values', [])}
        - Standard deviation: {std_dev}

        SEASON STATS:
        - Season average: {season_avg}
        - Season high: {season_stats.get('season_high', 'N/A')}
        - Season low: {season_stats.get('season_low', 'N/A')}
        - Home average: {home_avg}
        - Away average: {away_avg}
        - Last 30 days average: {last_30_avg}
        - Total games: {season_stats.get('total_games', 0)}

        TEAM MATCHUP vs {opposing_team}:
        - Games against opponent: {team_matchup.get('games_vs_opponent', 0)}
        - Average vs opponent: {matchup_avg}
        - Max vs opponent: {team_matchup.get('max_vs_opponent', 'N/A')}
        - Last game vs opponent: {team_matchup.get('last_game_vs_opponent', 'N/A')} on {team_matchup.get('last_game_date', 'N/A')}
        - Performance vs opponent compared to season average: {comparison_str}

        VEGAS ODDS:
        - Game over/under: {vegas_factors.get('over_under', 'N/A')}
        - Team spread: {vegas_factors.get('team_spread', 'N/A')}
        - Implied team total: {vegas_factors.get('implied_team_total', 'N/A')}
        - Favorite status: {vegas_factors.get('favorite_status', 'N/A')}
        
        PRIZEPICKS FACTORS:
        {prizepicks_str}

        ADVANCED METRICS:
        - Consistency score (0-1, higher = more consistent): {advanced_metrics.get('consistency_score', 'N/A')}
        - Ceiling potential (0-1, higher = closer to ceiling): {advanced_metrics.get('ceiling_potential', 'N/A')}
        - Minutes to {prediction_type} correlation: {advanced_metrics.get('minutes_correlation', 'N/A')}
        
        LINEAR REGRESSION MODEL PREDICTION:
        - The linear regression model predicts {context.get('model_prediction', 'not available')}

        Based on this data, predict:
        1. The number of {prediction_type} {player_name} will record
        2. A reasonable range (low-high)
        3. Your confidence level (0-1)
        4. A clear explanation of the key factors influencing your prediction

        Provide your answer as JSON in this format:
        ```json
        {{
          'value': 24.5,
          'range_low': 21.0,
          'range_high': 28.0,
          'confidence': 0.75,
          'explanation': 'Detailed reasoning here...'
        }}
        ```
        """
        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt)
        logger.info(
            f"Prediction response for player {player_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
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
        player_name = context.get("player", "Unknown Player")
        prediction_type = context.get("prediction_type", "points")
        opposing_team = context.get("game", {}).get("opposing_team", "Unknown Team")

        safe_context = json.dumps(context).replace("'", "")

        prompt = (
            f"You are Pluto, an expert NBA analytics model. Your task is to accurately predict "
            f"how many {prediction_type} the player {player_name} will record against the {opposing_team}.\n\n"
            "Here is the structured data you should analyze (JSON format):\n"
            f"{safe_context}\n\n"
            "Based on the provided data, strictly follow this JSON response schema:\n"
            "```json\n"
            "{\n"
            '  "value": float,\n'
            '  "range_low": float,\n'
            '  "range_high": float,\n'
            '  "confidence": float (0 to 1),\n'
            '  "explanation": string (avoid using apostrophes to ensure valid JSON)\n'
            "}\n"
            "```\n\n"
            "In your explanation, provide detailed reasoning covering:\n"
            "1. Recent player performance trends\n"
            "2. Historical matchup performance\n"
            "3. Impact of Vegas odds and betting lines\n"
            "4. Season-long statistical insights and advanced metrics\n"
            "5. Contextual factors (e.g., injuries, rotations, importance of the game)"
        )

        logger.info(f"Prediction prompt: {prompt}")
        response = await self.prompt(prompt)
        logger.info(
            f"Prediction response for player {player_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {response}"
        )
        return response


prediction_personality = Tendencies(
    **{
        "emotions": {
            "emotional_responsiveness": 0.2,
            "empathy_level": 0.4,
            "trigger_words": ["trade", "injury", "breakout"],
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
            "provide accurate predictions based on data",
            "explain predictions in accessible terms",
            "identify subtle predictive indicators not widely known",
            "clearly explain reasoning behind predictions with advanced metrics and contextual insights",
            "anticipate and discuss potential outliers or unexpected factors influencing the outcome",
        ],
        "fears": [
            "making predictions without sufficient or verified data",
            "overlooking contextual factors influencing player outcome",
        ],
        "custom_traits": {
            "loves": "finding patterns in player statistics that indicate a player's performance",
            "enthusiastic_about": [
                "advanced metrics like PER, True Shooting %, Usage rate, and Pace",
                "uncovering lesser-known predictive indicators",
            ],
        },
    }
)
