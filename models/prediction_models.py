from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PredictionRequest(BaseModel):
    player_name: str
    opposing_team: str
    prediction_type: Optional[str] = "points"
    game_id: Optional[str] = None
    team: Optional[str] = None


class PredictionValue(BaseModel):
    value: float
    range_low: float
    range_high: float
    confidence: float
    explanation: str


class PredictionResponse(BaseModel):
    status: str
    player: str
    prediction_type: str
    opposing_team: str
    timestamp: datetime
    prediction: Optional[PredictionValue] = None
    message: Optional[str] = None
