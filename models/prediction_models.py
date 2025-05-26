from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Union, Literal
from datetime import datetime
from models.prediction_context import Game
from models.player_analysis_models import PlayerFormAnalysis
from models.team_models import PrizepicksFactors, VegasFactors
from models.prediction_context import ModelPrediction
from models.base import BaseSchema


class PredictionRequest(BaseSchema):
    player_name: str
    opposing_team: str
    prediction_type: Optional[str] = "points"
    game_id: Optional[str] = None
    team: Optional[str] = None
    prizepicks_line: Optional[str] = None
    additional_context: Optional[str] = None
    season_mode: Optional[Literal["regular_season", "playoffs", "finals"]] = (
        "regular_season"
    )


class PredictionValue(BaseSchema):
    value: float
    range_low: float
    range_high: float
    confidence: float
    explanation: str
    prizepicks_line: str
    prizepicks_reason: str

    model_config = ConfigDict(from_attributes=True)


class PredictionResponse(BaseSchema):
    status: str
    player: str
    prediction_type: str
    opposing_team: str
    timestamp: datetime
    prediction: PredictionValue


class PredictionRange(BaseSchema):
    low: float
    high: float


class FormattedPrediction(BaseSchema):
    name: str
    team: str
    opponent: str
    gameDate: str
    statLabel: str
    displayStat: float
    predictedStat: float
    explanation: str
    imageUrl: Optional[str] = None
    confidence: float
    range: PredictionRange
    prizepicks_line: Optional[float] = None
    prizepicks_reason: Optional[str] = None
    prizepicks_prediction: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# --- Game Prediction Models ---


class GamePredictionRequest(BaseSchema):
    home_team_abbr: str = Field(
        ..., description="Abbreviation of the home team (e.g., LAL)"
    )
    away_team_abbr: str = Field(
        ..., description="Abbreviation of the away team (e.g., DEN)"
    )
    game_id: Optional[str] = Field(None, description="Optional specific Game ID")
    additional_context: Optional[str] = Field(
        None,
        description="Additional context that you found that is relevant to the prediction",
    )
    

class GamePredictionValue(BaseSchema):
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
    additional_context: Optional[str] = Field(
        None,
        description="Additional context that you found that is relevant to the prediction",
    )


class GamePredictionResponse(BaseSchema):
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


class PredictionData(BaseSchema):
    """Detailed prediction data for player performance."""

    value: Optional[float] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    confidence: float = 0.0
    explanation: str = "No explanation provided"
    prizepicks_line: Optional[str] = None
    prizepicks_reason: Optional[str] = None
    additional_context: Optional[str] = None


class PlayerPredictionResponse(BaseSchema):
    """Complete player prediction response structure."""

    status: str = "success"
    player: str
    game: Game
    prediction_type: str
    prediction: PredictionData
    recent_form: Optional[PlayerFormAnalysis] = None
    prizepicks_factors: Optional[PrizepicksFactors] = None
    vegas_factors: Optional[VegasFactors] = None
    timestamp: Optional[str] = None
    model_prediction: Union[str, ModelPrediction] = "not available"
    model_config = ConfigDict(from_attributes=True)


class PredictionMetrics(BaseSchema):
    timeframe: Literal["7_days", "14_days", "30_days", "all_time"]
    prediction_type: str
    total_evaluated: int
    exact_accuracy: float
    range_accuracy: float
    over_under_accuracy: float
    exact_correct: int
    range_correct: int
    over_under_correct: int
    over_under_evaluable: int
    error: Optional[str] = None


class AllTimeframeMetrics(BaseSchema):
    metrics: Dict[
        Literal["7_days", "14_days", "30_days", "all_time"], PredictionMetrics
    ]


class MetricWithChange(BaseSchema):
    value: str
    change: str


class PlayerInfo(BaseSchema):
    name: str
    count: Optional[int] = None
    accuracy: Optional[str] = None


class KeyMetrics(BaseSchema):
    prediction_accuracy: MetricWithChange
    win_rate: MetricWithChange
    most_picked_player: PlayerInfo
    timeframe: str


class PromptPlutoRequest(BaseSchema):
    prompt: str
