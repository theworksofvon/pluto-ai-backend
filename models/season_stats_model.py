from pydantic import BaseModel
from typing import Optional


class SeasonStats(BaseModel):
    season_average: Optional[float] = None
    season_high: Optional[float] = None
    season_low: Optional[float] = None
    home_average: Optional[float] = None
    away_average: Optional[float] = None
    total_games: int = 0
    last_30_days_avg: Optional[float] = None

    class Config:
        extra = "allow"
