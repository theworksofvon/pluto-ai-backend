from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.nba.sources import (
    NbaApiPlayerGameLogSource,
    NbaApiScheduleSource,
    NbaApiTeamGameLogSource,
)
from app.adapters.nba.types import NbaGameRow, NbaPlayerGameLogRow, NbaTeamGameLogRow


class FakeEndpoint:
    def __init__(self, payload: dict[str, Any], **kwargs: Any) -> None:
        self.payload = payload
        self.kwargs = kwargs

    def get_dict(self) -> dict[str, Any]:
        return self.payload


async def test_schedule_source_passes_timeout_and_date_to_scoreboard_factory() -> None:
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeEndpoint:
        calls.append(kwargs)
        return FakeEndpoint(
            {
                "resultSets": [
                    {
                        "name": "GameHeader",
                        "headers": ["gameId", "gameCode", "gameStatusText"],
                        "rowSet": [["0022500001", "20251021/NYKBOS", "Final"]],
                    },
                    {
                        "name": "LineScore",
                        "headers": [
                            "gameId",
                            "teamId",
                            "teamCity",
                            "teamName",
                            "teamTricode",
                        ],
                        "rowSet": [
                            ["0022500001", 1610612752, "New York", "Knicks", "NYK"],
                            ["0022500001", 1610612738, "Boston", "Celtics", "BOS"],
                        ],
                    },
                ]
            },
        )

    source = NbaApiScheduleSource(
        timeout_seconds=7,
        scoreboard_factory=factory,  # type: ignore[arg-type]
    )

    result = await source.games_for_date(date(2025, 10, 21))

    assert result.status == "success"
    assert isinstance(result.data, list)
    assert isinstance(result.data[0], NbaGameRow)
    assert calls == [{"game_date": "10/21/2025", "timeout": 7}]


async def test_player_source_uses_league_player_gamelog_endpoint() -> None:
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeEndpoint:
        calls.append(kwargs)
        return FakeEndpoint(
            {
                "resultSets": [
                    {
                        "name": "LeagueGameLog",
                        "headers": [
                            "SEASON_ID",
                            "PLAYER_ID",
                            "PLAYER_NAME",
                            "TEAM_ID",
                            "TEAM_ABBREVIATION",
                            "GAME_ID",
                            "GAME_DATE",
                            "MATCHUP",
                            "MIN",
                            "PTS",
                        ],
                        "rowSet": [
                            [
                                "22025",
                                2544,
                                "LeBron James",
                                1610612747,
                                "LAL",
                                "0022500002",
                                "OCT 22, 2025",
                                "LAL @ GSW",
                                34,
                                27,
                            ]
                        ],
                    }
                ]
            },
        )

    source = NbaApiPlayerGameLogSource(
        timeout_seconds=5,
        league_log_factory=factory,  # type: ignore[arg-type]
    )

    result = await source.get_league_player_game_logs(
        season="2025-26",
        date_from=date(2025, 10, 22),
        date_to=date(2025, 10, 23),
    )

    assert result.status == "success"
    assert isinstance(result.data, list)
    assert isinstance(result.data[0], NbaPlayerGameLogRow)
    assert calls[0]["player_or_team_abbreviation"] == "P"
    assert calls[0]["date_from_nullable"] == "10/22/2025"
    assert calls[0]["date_to_nullable"] == "10/23/2025"
    assert calls[0]["timeout"] == 5


async def test_team_source_uses_team_gamelog_endpoint() -> None:
    calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeEndpoint:
        calls.append(kwargs)
        return FakeEndpoint(
            {
                "resultSets": [
                    {
                        "name": "TeamGameLog",
                        "headers": [
                            "Team_ID",
                            "Game_ID",
                            "GAME_DATE",
                            "MATCHUP",
                            "MIN",
                            "PTS",
                        ],
                        "rowSet": [
                            [
                                1610612738,
                                "0022500001",
                                "2025-10-21",
                                "BOS vs. NYK",
                                240,
                                118,
                            ]
                        ],
                    }
                ]
            },
        )

    source = NbaApiTeamGameLogSource(
        timeout_seconds=4,
        team_log_factory=factory,  # type: ignore[arg-type]
    )

    result = await source.get_team_game_logs(
        team_id=1610612738,
        season="2025-26",
    )

    assert result.status == "success"
    assert isinstance(result.data, list)
    assert isinstance(result.data[0], NbaTeamGameLogRow)
    assert calls == [
        {
            "team_id": "1610612738",
            "season": "2025-26",
            "season_type_all_star": "Regular Season",
            "date_from_nullable": "",
            "date_to_nullable": "",
            "timeout": 4,
        }
    ]
