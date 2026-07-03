from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")
SourceStatus = Literal["success", "error"]


class SourceError(BaseModel):
    type: str
    message: str
    transient: bool = False
    attempt_count: int = Field(default=1, ge=1)


class SourceResult(BaseModel, Generic[T]):
    source: str
    fetched_at: datetime
    status: SourceStatus
    data: T | None = None
    warnings: list[str] = Field(default_factory=list)
    raw_payload: Any | None = None
    error: SourceError | None = None


class SourceHealthCheck(BaseModel):
    source: str
    checked_at: datetime
    status: SourceStatus
    latency_ms: float
    error_message: str | None = None
    sample_entity: str | None = None
    response_shape_hash: str | None = None


class NbaGameRow(BaseModel):
    external_game_id: str
    game_date: date
    season: str
    status: str
    start_time: datetime | None = None
    home_external_team_id: str | None = None
    away_external_team_id: str | None = None
    home_team_abbreviation: str | None = None
    away_team_abbreviation: str | None = None
    home_team_name: str | None = None
    away_team_name: str | None = None


class NbaStatLine(BaseModel):
    external_game_id: str
    game_date: date
    season: str
    matchup: str | None = None
    is_home: bool
    pts: float | None = None
    minutes: float | None = None
    fga: float | None = None
    fg_pct: float | None = None
    reb: float | None = None
    ast: float | None = None
    fg3_pct: float | None = None
    ft_pct: float | None = None
    plus_minus: float | None = None
    team_abbreviation: str | None = None
    opponent_team_abbreviation: str | None = None


class NbaPlayerGameLogRow(NbaStatLine):
    external_player_id: str | None = None
    player_name: str | None = None
    external_team_id: str | None = None


class NbaTeamGameLogRow(NbaStatLine):
    external_team_id: str | None = None
    team_name: str | None = None
