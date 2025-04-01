from adapters import Adapters
from logger import logger
from datetime import datetime
from typing import Dict, Any
from connections import Connections


class GameService:
    """
    Service for handling game-related data, including fetching predictions.
    """
    def __init__(self):
        self.adapters = Adapters()
        self.supabase = Connections.supabase 

    async def get_todays_games(self):
        try:
            return self.adapters.nba_analytics.get_todays_game_scoreboard()
        except Exception as e:
            logger.error(f"Error getting today's games in game_service: {e}")
            raise e

    async def get_game(self, game_id: str):
        try:
            return self.adapters.nba_analytics.get_game(game_id)
        except Exception as e:
            logger.error(f"Error getting game in game_service: {e}")
            raise e
        
    async def get_game_prediction(self, game_id: str):
        try:
            return self.adapters.nba_analytics.get_game_prediction(game_id)
        except Exception as e:
            logger.error(f"Error getting game prediction in game_service: {e}")
            raise e

    async def get_formatted_game_predictions_by_date(
        self, game_date: str
    ) -> list[Dict[str, Any]]:
        """
        Get all game predictions for a specific date, formatted for the frontend.

        Args:
            game_date: The date to get predictions for (format: YYYY-MM-DD)

        Returns:
            List of formatted game predictions.
        """
        logger.info(f"Fetching formatted game predictions for date: {game_date}")
        formatted_predictions = []
        try:
            query = (
                self.supabase.table("game_predictions")
                .select("*")
                .eq("game_date", game_date)
                .order("timestamp", desc=True) 
            )
            
            result = query.execute()
            print(result)

            if not result.data:
                logger.warning(f"No game predictions found for date {game_date}")
                return []

            # Get the nba_analytics adapter once
            nba = self.adapters.nba_analytics 
            if not nba:
                 logger.error("NBA Analytics adapter not available in GameService.")
                 return []

            for prediction in result.data:
                try:
                    home_logo = await nba.get_team_logo_url(team_name=prediction.get("home_team"))
                    away_logo = await nba.get_team_logo_url(team_name=prediction.get("away_team"))

                    try:
                        date_obj = datetime.strptime(prediction.get("game_date", ""), "%Y-%m-%d")
                        formatted_date_str = date_obj.strftime('%b %d')
                    except (ValueError, TypeError):
                        formatted_date_str = "N/A"

                    pred_winner = prediction.get("predicted_winner")
                    conf = prediction.get("confidence")
                    
                    formatted_prediction = {
                        "date": formatted_date_str,
                        "homeTeam": prediction.get("home_team", "N/A"),
                        "awayTeam": prediction.get("away_team", "N/A"),
                        "predictedWinner": pred_winner or "N/A",
                        "winProbability": conf,
                        "homeTeamLogo": home_logo or "",
                        "awayTeamLogo": away_logo or "",
                    }
                    formatted_predictions.append(formatted_prediction)

                except Exception as inner_e:
                     logger.error(f"Error processing individual game prediction {prediction.get('id', 'N/A')}: {inner_e}", exc_info=True)

            logger.info(f"Successfully formatted {len(formatted_predictions)} game predictions for {game_date}")
            return formatted_predictions

        except Exception as e:
            logger.error(f"Error getting formatted game predictions for {game_date}: {e}", exc_info=True)
            return []
