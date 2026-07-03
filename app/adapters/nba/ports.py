from __future__ import annotations

from datetime import date
from typing import Protocol

from app.adapters.nba.types import (
    NbaGameRow,
    NbaPlayerGameLogRow,
    NbaTeamGameLogRow,
    SourceHealthCheck,
    SourceResult,
)


class NbaScheduleSource(Protocol):
    async def games_for_date(
        self,
        game_date: date,
    ) -> SourceResult[list[NbaGameRow]]: ...

    async def health_check(self) -> SourceHealthCheck: ...


class NbaPlayerGameLogSource(Protocol):
    async def get_player_game_logs(
        self,
        *,
        player_id: str | int,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]: ...

    async def get_league_player_game_logs(
        self,
        *,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]: ...

    async def health_check(self) -> SourceHealthCheck: ...


class NbaTeamGameLogSource(Protocol):
    async def get_team_game_logs(
        self,
        *,
        team_id: str | int,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaTeamGameLogRow]]: ...

    async def get_league_team_game_logs(
        self,
        *,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaTeamGameLogRow]]: ...

    async def health_check(self) -> SourceHealthCheck: ...
