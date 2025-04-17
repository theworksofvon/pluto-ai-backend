from pydantic import ConfigDict
from typing import Optional
from models import BaseSchema


class SeasonStats(BaseSchema):
    season_average: Optional[float] = None
    season_high: Optional[float] = None
    season_low: Optional[float] = None
    home_average: Optional[float] = None
    away_average: Optional[float] = None
    total_games: int = 0
    last_30_days_avg: Optional[float] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
