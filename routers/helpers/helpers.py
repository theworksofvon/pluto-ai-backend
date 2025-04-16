from agents import PlayerPredictionAgent, GamePredictionAgent
from services.player_prediction import PlayerPredictionService
from services.game_service import GameService
from services.data_pipeline import DataProcessor
from services.eval_service import EvaluationService
from adapters import Adapters
from services.player_service import PlayerService
from services.odds_service import OddsService


def get_player_prediction_agent() -> PlayerPredictionAgent:
    return PlayerPredictionAgent()


def get_player_prediction_service() -> PlayerPredictionService:
    return PlayerPredictionService()


def get_game_prediction_agent() -> GamePredictionAgent:
    return GamePredictionAgent()


def get_game_service() -> GameService:
    return GameService()


def get_data_pipeline() -> DataProcessor:
    return DataProcessor()


def get_evaluation_service() -> EvaluationService:
    return EvaluationService()


def get_data_pipeline():
    return DataProcessor()


def get_player_service():
    return PlayerService(Adapters())


def get_adapters():
    return Adapters()


def get_odds_service():
    return OddsService()
