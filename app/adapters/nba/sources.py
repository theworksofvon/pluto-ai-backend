from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from nba_api.live.nba.endpoints.scoreboard import ScoreBoard
from nba_api.stats.endpoints.leaguegamelog import LeagueGameLog
from nba_api.stats.endpoints.playergamelog import PlayerGameLog
from nba_api.stats.endpoints.scoreboardv3 import ScoreboardV3
from nba_api.stats.endpoints.teamgamelog import TeamGameLog

from app.adapters.nba.parsers import (
    parse_live_scoreboard,
    parse_player_game_log,
    parse_scoreboard_v3,
    parse_team_game_log,
)
from app.adapters.nba.reliability import ReliableSourceRunner
from app.adapters.nba.types import (
    NbaGameRow,
    NbaPlayerGameLogRow,
    NbaTeamGameLogRow,
    SourceHealthCheck,
    SourceResult,
)
from app.core.clock import Clock, SystemClock


class Endpoint(Protocol):
    def get_dict(self) -> dict[str, Any]: ...


class NbaApiScheduleSource:
    source_name = "nba_api.scoreboardv3"
    live_source_name = "nba_api.live.scoreboard"

    def __init__(
        self,
        *,
        runner: ReliableSourceRunner | None = None,
        timeout_seconds: float = 10.0,
        clock: Clock | None = None,
        scoreboard_factory: type[ScoreboardV3] = ScoreboardV3,
        live_scoreboard_factory: type[ScoreBoard] = ScoreBoard,
    ) -> None:
        self._runner = runner or ReliableSourceRunner(timeout_seconds=timeout_seconds)
        self._timeout_seconds = timeout_seconds
        self._clock = clock or SystemClock()
        self._scoreboard_factory = scoreboard_factory
        self._live_scoreboard_factory = live_scoreboard_factory

    async def games_for_date(
        self,
        game_date: date,
    ) -> SourceResult[list[NbaGameRow]]:
        def fetch() -> dict[str, Any]:
            endpoint = self._scoreboard_factory(
                game_date=_nba_date(game_date),
                timeout=self._timeout_seconds,
            )
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.source_name,
            fetch=fetch,
            parse=lambda raw: parse_scoreboard_v3(
                raw,
                fallback_game_date=game_date,
            ),
        )

    async def live_games(self) -> SourceResult[list[NbaGameRow]]:
        today = self._clock.now().date()

        def fetch() -> dict[str, Any]:
            endpoint = self._live_scoreboard_factory(timeout=self._timeout_seconds)
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.live_source_name,
            fetch=fetch,
            parse=lambda raw: parse_live_scoreboard(
                raw,
                fallback_game_date=today,
            ),
        )

    async def health_check(self) -> SourceHealthCheck:
        sample_date = self._clock.now().date()
        return await self._runner.health_check(
            source=self.source_name,
            probe=lambda: self.games_for_date(sample_date),
            sample_entity=sample_date.isoformat(),
        )


class NbaApiPlayerGameLogSource:
    source_name = "nba_api.playergamelog"
    league_source_name = "nba_api.leaguegamelog.players"

    def __init__(
        self,
        *,
        runner: ReliableSourceRunner | None = None,
        timeout_seconds: float = 10.0,
        player_log_factory: type[PlayerGameLog] = PlayerGameLog,
        league_log_factory: type[LeagueGameLog] = LeagueGameLog,
    ) -> None:
        self._runner = runner or ReliableSourceRunner(timeout_seconds=timeout_seconds)
        self._timeout_seconds = timeout_seconds
        self._player_log_factory = player_log_factory
        self._league_log_factory = league_log_factory

    async def get_player_game_logs(
        self,
        *,
        player_id: str | int,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]:
        player_id_text = str(player_id)

        def fetch() -> dict[str, Any]:
            endpoint = self._player_log_factory(
                player_id=player_id_text,
                season=season,
                season_type_all_star=season_type,
                date_from_nullable=_nba_date_or_empty(date_from),
                date_to_nullable=_nba_date_or_empty(date_to),
                timeout=self._timeout_seconds,
            )
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.source_name,
            fetch=fetch,
            parse=lambda raw: parse_player_game_log(
                raw,
                season=season,
                fallback_player_id=player_id_text,
            ),
        )

    async def get_league_player_game_logs(
        self,
        *,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaPlayerGameLogRow]]:
        def fetch() -> dict[str, Any]:
            endpoint = self._league_log_factory(
                player_or_team_abbreviation="P",
                season=season,
                season_type_all_star=season_type,
                date_from_nullable=_nba_date_or_empty(date_from),
                date_to_nullable=_nba_date_or_empty(date_to),
                timeout=self._timeout_seconds,
            )
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.league_source_name,
            fetch=fetch,
            parse=lambda raw: parse_player_game_log(raw, season=season),
        )

    async def health_check(self) -> SourceHealthCheck:
        return await self._runner.health_check(
            source=self.league_source_name,
            probe=lambda: self.get_league_player_game_logs(season=_current_season()),
            sample_entity=_current_season(),
        )


class NbaApiTeamGameLogSource:
    source_name = "nba_api.teamgamelog"
    league_source_name = "nba_api.leaguegamelog.teams"

    def __init__(
        self,
        *,
        runner: ReliableSourceRunner | None = None,
        timeout_seconds: float = 10.0,
        team_log_factory: type[TeamGameLog] = TeamGameLog,
        league_log_factory: type[LeagueGameLog] = LeagueGameLog,
    ) -> None:
        self._runner = runner or ReliableSourceRunner(timeout_seconds=timeout_seconds)
        self._timeout_seconds = timeout_seconds
        self._team_log_factory = team_log_factory
        self._league_log_factory = league_log_factory

    async def get_team_game_logs(
        self,
        *,
        team_id: str | int,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaTeamGameLogRow]]:
        team_id_text = str(team_id)

        def fetch() -> dict[str, Any]:
            endpoint = self._team_log_factory(
                team_id=team_id_text,
                season=season,
                season_type_all_star=season_type,
                date_from_nullable=_nba_date_or_empty(date_from),
                date_to_nullable=_nba_date_or_empty(date_to),
                timeout=self._timeout_seconds,
            )
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.source_name,
            fetch=fetch,
            parse=lambda raw: parse_team_game_log(
                raw,
                season=season,
                fallback_team_id=team_id_text,
            ),
        )

    async def get_league_team_game_logs(
        self,
        *,
        season: str,
        date_from: date | None = None,
        date_to: date | None = None,
        season_type: str = "Regular Season",
    ) -> SourceResult[list[NbaTeamGameLogRow]]:
        def fetch() -> dict[str, Any]:
            endpoint = self._league_log_factory(
                player_or_team_abbreviation="T",
                season=season,
                season_type_all_star=season_type,
                date_from_nullable=_nba_date_or_empty(date_from),
                date_to_nullable=_nba_date_or_empty(date_to),
                timeout=self._timeout_seconds,
            )
            return endpoint.get_dict()

        return await self._runner.run(
            source=self.league_source_name,
            fetch=fetch,
            parse=lambda raw: parse_team_game_log(raw, season=season),
        )

    async def health_check(self) -> SourceHealthCheck:
        return await self._runner.health_check(
            source=self.league_source_name,
            probe=lambda: self.get_league_team_game_logs(season=_current_season()),
            sample_entity=_current_season(),
        )


def _nba_date(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def _nba_date_or_empty(value: date | None) -> str:
    return _nba_date(value) if value else ""


def _current_season(today: date | None = None) -> str:
    value = today or date.today()
    start_year = value.year if value.month >= 9 else value.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"
