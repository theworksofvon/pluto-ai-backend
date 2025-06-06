from typing import Dict, List, Optional, Any, Union, Literal
from pydantic import Field, ConfigDict
from datetime import datetime
from models import BaseSchema
from models.player_analysis_models import PlayerFormAnalysis
from models.team_models import TeamMatchup, VegasFactors, PrizepicksFactors
from models.season_stats_model import SeasonStats


class Game(BaseSchema):
    opposing_team: str
    game_date: Optional[str] = Field(default_factory=lambda: datetime.now().date())


class PlayerStats(BaseSchema):
    player_stats: List[Dict[str, Any]]
    total_games_available: int


class AdvancedMetrics(BaseSchema):
    """Model representing a player's advanced metrics."""

    consistency_score: Optional[float] = None
    ceiling_potential: Optional[float] = None
    minutes_correlation: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ModelPrediction(BaseSchema):
    """Model representing a statistical model's prediction."""

    prediction: Optional[float] = None


class PredictionContext(BaseSchema):
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
    additional_context: Optional[str] = None
    season_mode: Literal["regular_season", "playoffs", "finals"]

    model_config = ConfigDict(arbitrary_types_allowed=True)
