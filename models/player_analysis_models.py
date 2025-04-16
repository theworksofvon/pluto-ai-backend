from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import numpy as np


class PlayerFormAnalysis(BaseModel):
    """Model representing a player's recent form analysis."""

    recent_average_5: Optional[float] = None
    recent_average_10: Optional[float] = None
    recent_max: Optional[float] = None
    recent_min: Optional[float] = None
    recent_values: List[float] = Field(default_factory=list)
    trend: Optional[Literal["increasing", "decreasing"]] = None
    trend_values: List[float] = Field(default_factory=list)
    games_analyzed: int = 0
    std_deviation: Optional[float] = None

    class Config:
        """Configuration for the model."""

        arbitrary_types_allowed = True

    @classmethod
    def from_stats(cls, player_stats, stat_column: str):
        """
        Factory method to create PlayerFormAnalysis from player stats DataFrame.

        Args:
            player_stats: DataFrame with recent player games
            stat_column: Column name for the stat to analyze

        Returns:
            PlayerFormAnalysis instance
        """
        if (
            player_stats is None
            or len(player_stats) == 0
            or stat_column not in player_stats.columns
        ):
            return cls()

        last_5_games = player_stats.head(5)
        last_10_games = player_stats.head(10)

        # Get recent game values
        recent_values = (
            last_5_games[stat_column].tolist() if len(last_5_games) > 0 else []
        )

        # Calculate trends
        trend = None
        trend_values = []
        if len(recent_values) >= 3:
            # Simple trend: positive if recent games show increase
            differences = [
                recent_values[i] - recent_values[i + 1]
                for i in range(len(recent_values) - 1)
            ]
            trend = "increasing" if sum(differences) > 0 else "decreasing"
            trend_values = differences

        return cls(
            recent_average_5=float(np.mean(recent_values)) if recent_values else None,
            recent_average_10=(
                float(np.mean(last_10_games[stat_column]))
                if len(last_10_games) > 0
                else None
            ),
            recent_max=float(max(recent_values)) if recent_values else None,
            recent_min=float(min(recent_values)) if recent_values else None,
            recent_values=recent_values,
            trend=trend,
            trend_values=trend_values,
            games_analyzed=len(recent_values),
            std_deviation=float(np.std(recent_values)) if recent_values else None,
        )
