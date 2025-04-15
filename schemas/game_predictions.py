from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from adapters.db.sqlalchemy.tables import PredictionType


class GamePredictionCreate(BaseModel):
    game_date: date
    home_team: str
    away_team: str
    predicted_winner: str
    home_team_win_percentage: float
    opposing_team_win_percentage: float


class GamePredictionRead(BaseModel):
    prediction_id: int
    game_date: date
    home_team: str
    away_team: str
    predicted_winner: str
    home_team_win_percentage: float
    opposing_team_win_percentage: float
    timestamp: datetime

    class Config:
        from_attributes = True


class PlayerPredictionCreate(BaseModel):
    game_date: date
    player_name: str
    team: str
    opposing_team: str
    prediction_type: PredictionType
    predicted_value: float
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    prizepicks_prediction: Optional[str] = None
    prizepicks_line: Optional[float] = None
    prizepicks_reason: Optional[str] = None


class PlayerPredictionRead(BaseModel):
    prediction_id: int
    game_date: date
    player_name: str
    team: str
    opposing_team: str
    prediction_type: PredictionType
    predicted_value: float
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    prizepicks_prediction: Optional[str] = None
    prizepicks_line: Optional[float] = None
    prizepicks_reason: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
