from adapters import Adapters
from typing import Dict, Any, Optional
from logger import logger
from connections import Connections


class PlayerService:
    def __init__(self, adapters: Adapters):
        self.adapters = adapters

    async def get_player_prediction(
        self,
        player_name: str,
        prediction_type: str,
        opposing_team: Optional[str] = None,
        game_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get the most recent player prediction for the player.

        Args:
            player_name: The name of the player
            prediction_type: The type of prediction (e.g., 'points', 'rebounds', etc.)
            opposing_team: Optional opposing team to filter predictions
            game_date: Optional game date to filter predictions

        Returns:
            Dict containing the most recent prediction data or None if not found
        """
        try:
            # Build the query
            query = Connections.supabase.table("player_predictions").select("*")

            # Apply filters
            query = query.eq("player_name", player_name)
            query = query.eq("prediction_type", prediction_type)

            if opposing_team:
                query = query.eq("opposing_team", opposing_team)

            if game_date:
                query = query.eq("game_date", game_date)

            query = query.order("timestamp", desc=True).limit(1)

            result = query.execute()
            logger.info(f"Result: {result}")

            if result.data and len(result.data) > 0:
                logger.info(f"Result data: {result.data}")
                logger.info(f"Result data[0]: {result.data[0]}")
                return result.data[0]

            logger.warning(
                f"No prediction found for player {player_name} with type {prediction_type}"
            )
            return None

        except Exception as e:
            logger.error(f"Error fetching player prediction: {str(e)}")
            return None

    async def get_formatted_predictions_by_date(
        self, game_date: str, prediction_type: str
    ) -> list[Dict[str, Any]]:
        """
        Get all predictions for a specific date in the format required by the frontend.

        Args:
            game_date: The date to get predictions for (format: YYYY-MM-DD)

        Returns:
            List of formatted predictions
        """
        try:
            query = Connections.supabase.table("player_predictions").select("*")
            query = query.eq("game_date", game_date)
            query = query.eq("prediction_type", prediction_type)
            query = query.order("timestamp", desc=True)

            result = query.execute()

            if not result.data:
                logger.warning(f"No predictions found for date {game_date}")
                return []

            formatted_predictions = []

            for prediction in result.data:
                nba = self.adapters.nba_analytics
                image_url = await nba.get_player_image(
                    player_name=prediction["player_name"]
                )

                formatted_prediction = {
                    "name": prediction["player_name"],
                    "team": prediction["team"],
                    "opponent": prediction["opposing_team"],
                    "gameDate": prediction.get("game_date", "TBD"),
                    "statLabel": prediction["prediction_type"].capitalize(),
                    "displayStat": prediction["predicted_value"],
                    "predictedStat": prediction["predicted_value"],
                    "imageUrl": image_url,
                    "confidence": prediction["confidence"],
                    "range": {
                        "low": prediction["range_low"],
                        "high": prediction["range_high"],
                    },
                }

                formatted_predictions.append(formatted_prediction)

            return formatted_predictions

        except Exception as e:
            logger.error(f"Error getting formatted predictions: {str(e)}")
            return []

    async def get_formatted_predictions_by_players(
        self, player_names: list[str], prediction_type: str
    ) -> list[Dict[str, Any]]:
        """
        Get predictions for specific players in the format required by the frontend.

        Args:
            player_names: List of player names to get predictions for

        Returns:
            List of formatted predictions
        """
        try:
            formatted_predictions = []

            for player_name in player_names:
                prediction = await self.get_player_prediction(
                    player_name=player_name, prediction_type=prediction_type
                )

                if prediction:
                    nba = self.adapters.nba_analytics
                    image_url = await nba.get_player_image(player_name=player_name)

                    formatted_prediction = {
                        "name": prediction["player_name"],
                        "team": prediction["team"],
                        "opponent": prediction["opposing_team"],
                        "gameDate": prediction.get("game_date", "TBD"),
                        "statLabel": prediction["prediction_type"].capitalize(),
                        "predictedStat": prediction["predicted_value"],
                        "imageUrl": image_url,
                        "confidence": prediction["confidence"],
                        "range": {
                            "low": prediction["range_low"],
                            "high": prediction["range_high"],
                        },
                    }

                    formatted_predictions.append(formatted_prediction)

            return formatted_predictions

        except Exception as e:
            logger.error(f"Error getting formatted predictions for players: {str(e)}")
            return []
