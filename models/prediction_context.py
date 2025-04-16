from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

from models.player_analysis_models import PlayerFormAnalysis
from models.team_models import TeamMatchup, VegasFactors, PrizepicksFactors
from models.season_stats_model import SeasonStats


class Game(BaseModel):
    opposing_team: str
    game_id: str


class PlayerStats(BaseModel):
    player_stats: List[Dict[str, Any]]
    total_games_available: int


class AdvancedMetrics(BaseModel):
    """Model representing a player's advanced metrics."""

    consistency_score: Optional[float] = None
    ceiling_potential: Optional[float] = None
    minutes_correlation: Optional[float] = None

    class Config:
        extra = "allow"


class ModelPrediction(BaseModel):
    """Model representing a statistical model's prediction."""

    prediction: Optional[float] = None


class PredictionContext(BaseModel):
    """Complete context model for player predictions."""

    status: str = "success"
    player: str
    game: Game
    prediction_type: str
    recent_form: Optional[PlayerFormAnalysis] = None
    vegas_factors: Optional[VegasFactors] = None
    prizepicks_factors: Optional[PrizepicksFactors] = None
    team_matchup: Optional[TeamMatchup] = None
    season_stats: Optional[SeasonStats] = None
    model_prediction: Optional[Union[str, ModelPrediction]] = None
    historical_predictions: Optional[List[Dict[str, Any]]] = None
    advanced_metrics: Optional[AdvancedMetrics] = None
    raw_data: Optional[PlayerStats] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    class Config:
        """Configuration for the model."""

        extra = "allow"  # Allow additional fields not specified in the model
