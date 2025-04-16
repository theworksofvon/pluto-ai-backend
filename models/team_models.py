from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TeamMatchup(BaseModel):
    """Model representing a team matchup analysis for predictions."""

    player_team: str
    opposing_team: str
    player_team_stats: Optional[Dict[str, Any]] = None
    opposing_team_stats: Optional[Dict[str, Any]] = None
    last_matchup_date: Optional[str] = None
    last_matchup_result: Optional[str] = None
    historical_matchups: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    player_performances: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    player_avg_vs_team: Optional[Dict[str, float]] = None
    player_outlier_games: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    team_pace_factor: Optional[float] = None
    player_team_rank: Optional[Dict[str, int]] = None
    opposing_team_rank: Optional[Dict[str, int]] = None
    team_win_probability: Optional[float] = None


class VegasFactors(BaseModel):
    """Model representing Vegas betting lines and factors."""

    over_under: Optional[float] = None
    player_prop: Optional[float] = None
    team_spread: Optional[float] = None
    implied_team_total: Optional[float] = None
    favorite_status: Optional[str] = None


class PrizepicksFactors(BaseModel):
    """Model representing Prizepicks lines and factors."""

    line: Optional[float] = None
    average_line_last_week: Optional[float] = None
    line_trend: Optional[str] = None
    hit_rate: Optional[float] = None
    recent_hit_rate: Optional[float] = None
    last_5_results: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    over_under_recommendation: Optional[str] = None
