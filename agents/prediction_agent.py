from agency.agent import Agent
from agency.agency_types import Tendencies
from services.prediction import PredictionService
from typing import Dict, Optional, Any
import json
from logger import logger
from datetime import datetime
from agents.helpers.prediction_helpers import (
    parse_prediction_response,
    DEFAULT_PREDICTION,
)


class PredictionAgent(Agent):
    """
    Agent responsible for making NBA player predictions.
    Uses prepared data from PredictionService and leverages LLM for actual predictions.
    """

    prediction_service: Optional[PredictionService] = None

    def __init__(self, **kwargs):
        super().__init__(
            name="Prediction",
            instructions="""You are an expert NBA prediction agent that analyzes player data and Vegas odds to make accurate predictions.
            You can utilize internet access and search to get more information about the player and the opponent.
            When making predictions, you should carefully consider:
            1. Player's recent form and trends
            2. Matchup against the specific opponent
            3. Vegas betting lines and implications
            4. Season-long patterns and statistics
            Your predictions should be data-driven and well-reasoned. You should clearly explain your thought process
            and highlight the key factors that influenced your prediction.
            """,
            tendencies=prediction_personality,
            role="pilot",
            model="openai-deepseek-reasoner",
            **kwargs,
        )
        self.prediction_service = PredictionService()

    async def execute_task(self, **kwargs):
        """
        Main entry point for prediction tasks.
        This is automatically called when the agent runs.
        """
        logger.info("Prediction agent is ready for player predictions")

        # TODO:
        # 1. Identify upcoming games
        # 2. Get a list of key players
        # 3. Make predictions for each player
        # 4. Store or publish these predictions

    async def predict_player_performance(
        self,
        player_name: str,
        opposing_team: str,
        prediction_type: str = "points",
        game_id: Optional[str] = None,
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

        prediction_response = await self._generate_prediction(context)
        logger.info(f"Agent Prediction response: {prediction_response}")

        try:
            prediction_data = parse_prediction_response(prediction_response)
        except Exception as e:
            logger.error(f"Error parsing prediction response: {e}")
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


# Agent personality
prediction_personality = Tendencies(
    **{
        "emotions": {
            "emotional_responsiveness": 0.3,
            "empathy_level": 0.4,
            "trigger_words": ["trade", "injury", "breakout"],
        },
        "passiveness": 0.3,
        "risk_tolerance": 0.6,
        "patience_level": 0.7,
        "decision_making": "analytical",
        "core_values": [
            "statistical accuracy",
            "data-driven insights",
            "balanced analysis",
        ],
        "goals": [
            "provide accurate predictions based on data",
            "explain predictions in accessible terms",
        ],
        "fears": ["making predictions without sufficient data"],
        "custom_traits": {"loves": "finding patterns in player statistics"},
    }
)
