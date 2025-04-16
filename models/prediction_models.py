from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union
from datetime import datetime


class PredictionRequest(BaseModel):
    player_name: str
    opposing_team: str
    prediction_type: Optional[str] = "points"
    game_id: Optional[str] = None
    team: Optional[str] = None
    prizepicks_line: Optional[str] = None


class PredictionValue(BaseModel):
    value: float
    range_low: float
    range_high: float
    confidence: float
    explanation: str
    prizepicks_line: str
    prizepicks_reason: str


class PredictionResponse(BaseModel):
    status: str
    player: str
    prediction_type: str
    opposing_team: str
    timestamp: datetime
    prediction: Optional[PredictionValue] = None


# --- Game Prediction Models ---


class GamePredictionRequest(BaseModel):
    home_team_abbr: str = Field(
        ..., description="Abbreviation of the home team (e.g., LAL)"
    )
    away_team_abbr: str = Field(
        ..., description="Abbreviation of the away team (e.g., DEN)"
    )
    game_id: Optional[str] = Field(None, description="Optional specific Game ID")


class GamePredictionValue(BaseModel):
    value: Optional[str] = Field(
        None, description="Predicted winner team abbreviation (e.g., LAL or DEN)"
    )
    confidence: Optional[float] = Field(
        None, description="Confidence level (0-1) in the predicted winner"
    )
    home_team_win_percentage: Optional[float] = Field(
        None, description="Estimated win probability for the home team (0-1)"
    )
    opposing_team_win_percentage: Optional[float] = Field(
        None, description="Estimated win probability for the away team (0-1)"
    )
    explanation: Optional[str] = Field(
        None, description="Explanation for the prediction"
    )


class GamePredictionResponse(BaseModel):
    status: str
    game: Optional[Dict[str, Any]] = Field(
        None, description="Details of the game requested"
    )
    prediction: Optional[GamePredictionValue] = Field(
        None, description="The prediction details"
    )
    context_summary: Optional[Dict[str, Any]] = Field(
        None, description="Summary of the context used for prediction"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    message: Optional[str] = None


class Game(BaseModel):
    """Game information for player predictions."""

    opposing_team: str
    game_id: str


class PredictionData(BaseModel):
    """Detailed prediction data for player performance."""

    value: Optional[float] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    confidence: float = 0.0
    explanation: str = "No explanation provided"
    prizepicks_line: Optional[str] = None
    prizepicks_reason: Optional[str] = None


class PlayerPredictionResponse(BaseModel):
    """Complete player prediction response structure."""

    status: str = "success"
    player: str
    game: Game
    prediction_type: str
    prediction: PredictionData
    recent_form: Optional[Dict[str, Any]] = None
    prizepicks_factors: Optional[Dict[str, Any]] = None
    vegas_factors: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    model_prediction: Union[str, Dict[str, Any]] = "not available"

    class Config:
        """Configuration for the Pydantic model."""

        json_schema_extra = {
            "example": {
                "status": "success",
                "player": "LeBron James",
                "game": {
                    "opposing_team": "Brooklyn Nets",
                    "game_id": "20231015-LAL-BKN",
                },
                "prediction_type": "points",
                "prediction": {
                    "value": 28.5,
                    "range_low": 24.0,
                    "range_high": 33.0,
                    "confidence": 0.85,
                    "explanation": "LeBron has averaged 29.3 points against the Nets in the last 3 games.",
                },
                "timestamp": "2023-10-15T12:00:00Z",
            }
        }
