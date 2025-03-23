from agency.agent import Agent
from agency.agency_types import Tendencies
from services.prediction import PredictionService
from typing import Dict, Optional, Any
import json
from logger import logger
from datetime import datetime
from agents.helpers.prediction_helpers import parse_prediction_response, DEFAULT_PREDICTION

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
        player_name = context["player"]
        prediction_type = context["prediction_type"]
        opposing_team = context["game"]["opposing_team"]
        recent_form = context["recent_form"]
        vegas_factors = context["vegas_factors"]
        team_matchup = context["team_matchup"]
        season_stats = context["season_stats"]
        advanced_metrics = context["advanced_metrics"]

        logger.info(f"Agent Player Name: {player_name}")
        logger.info(f"Agent Prediction Type: {prediction_type}")
        logger.info(f"Agent Opposing Team: {opposing_team}")
        logger.info(f"Agent Recent Form: {recent_form}")
        logger.info(f"Agent Vegas Factors: {vegas_factors}")
        logger.info(f"Agent Team Matchup: {team_matchup}")
        logger.info(f"Agent Season Stats: {season_stats}")

        prompt = f"""
        I need you to predict how many {prediction_type} {player_name} will record against {opposing_team}.

        Here's all the relevant data:

      RECENT FORM (Last 5 games):
        - Average: {f"{recent_form['recent_average_5']:.1f}" if recent_form['recent_average_5'] is not None else 'N/A'}
        - 10-game average: {f"{recent_form['recent_average_10']:.1f}" if recent_form['recent_average_10'] else 'N/A'}
        - Recent high: {recent_form['recent_max']}
        - Recent low: {recent_form['recent_min']}
        - Trend: {recent_form['trend'] or 'Stable'}
        - Game values: {recent_form['recent_values']}
        - Standard deviation: {f"{recent_form['std_deviation']:.2f}" if recent_form['std_deviation'] else 'N/A'}

        SEASON STATS:
        - Season average: {f"{season_stats['season_average']:.1f}" if season_stats['season_average'] else 'N/A'}
        - Season high: {season_stats['season_high']}
        - Season low: {season_stats['season_low']}
        - Home average: {f"{season_stats['home_average']:.1f}" if season_stats['home_average'] else 'N/A'}
        - Away average: {f"{season_stats['away_average']:.1f}" if season_stats['away_average'] else 'N/A'}
        - Last 30 days average: {f"{season_stats['last_30_days_avg']:.1f}" if season_stats['last_30_days_avg'] else 'N/A'}
        - Total games: {season_stats['total_games']}

        TEAM MATCHUP vs {opposing_team}:
        - Games against opponent: {team_matchup['games_vs_opponent']}
        - Average vs opponent: {f"{team_matchup['avg_vs_opponent']:.1f}" if team_matchup['avg_vs_opponent'] else 'N/A'}
        - Max vs opponent: {team_matchup['max_vs_opponent']}
        - Last game vs opponent: {team_matchup['last_game_vs_opponent']} on {team_matchup['last_game_date'] or 'N/A'}
        - Performance vs opponent compared to season average: {f"{team_matchup['comparison_to_season_avg']:.1f}%"} {' higher' if team_matchup['comparison_to_season_avg'] and team_matchup['comparison_to_season_avg'] > 0 else ' lower' if team_matchup['comparison_to_season_avg'] and team_matchup['comparison_to_season_avg'] < 0 else ''} than season average


        VEGAS ODDS:
        - Game over/under: {vegas_factors['over_under']}
        - Team spread: {vegas_factors['team_spread']}
        - Implied team total: {vegas_factors['implied_team_total']}
        - Favorite status: {vegas_factors['favorite_status']}

        ADVANCED METRICS:
        - Consistency score (0-1, higher = more consistent): {advanced_metrics['consistency_score']}
        - Ceiling potential (0-1, higher = closer to ceiling): {advanced_metrics['ceiling_potential']}
        - Minutes to {prediction_type} correlation: {advanced_metrics['minutes_correlation']}
        
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

        response = await self.prompt(prompt)
        logger.info(f"Prediction prompt: {prompt}")
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
