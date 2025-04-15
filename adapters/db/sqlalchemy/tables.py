from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Enum, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime
from enum import Enum

Base = declarative_base()


class PredictionType(Enum):
    POINTS = "points"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"


class GamePrediction(Base):
    """
    Model for predicting the outcome of a game.
    Stores the prediction for a specific game with home and away teams.
    """

    __tablename__ = "game_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    game_date = Column(Date, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    predicted_winner = Column(String, nullable=False)
    home_team_win_percentage = Column(Float, nullable=False)
    opposing_team_win_percentage = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<GamePrediction(prediction_id={self.prediction_id}, "
            f"game_date={self.game_date}, home_team={self.home_team}, "
            f"away_team={self.away_team}, predicted_winner={self.predicted_winner})>"
        )


class PlayerPrediction(Base):
    """
    Model for an individual player's prediction in a game.
    Stores predictions for a specific player's stats in a specific game.
    """

    __tablename__ = "player_predictions"
    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    game_date = Column(Date, nullable=False)
    player_name = Column(String, nullable=False)
    team = Column(String, nullable=False)
    opposing_team = Column(String, nullable=False)
    prediction_type = Column(String, nullable=False)
    predicted_value = Column(Float, nullable=False)
    range_low = Column(Float, nullable=True)
    range_high = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)
    prizepicks_line = Column(Float, nullable=True)
    prizepicks_prediction = Column(String, nullable=True)
    prizepicks_reason = Column(String, nullable=True)
    llm_used = Column(String, nullable=False, default="deepseek-v3")
    prompt_template = Column(String, nullable=False, default="v2")
    was_exactly_correct = Column(Boolean, nullable=True)
    was_range_correct = Column(Boolean, nullable=True)
    was_over_under_correct = Column(Boolean, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return (
            f"<PlayerPrediction(prediction_id={self.prediction_id}, "
            f"game_date={self.game_date}, player_name={self.player_name}, "
            f"team={self.team}, prediction_type={self.prediction_type.value}, "
            f"predicted_value={self.predicted_value})>"
        )
