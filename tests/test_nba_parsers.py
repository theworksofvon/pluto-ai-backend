from __future__ import annotations

from datetime import date

from app.adapters.nba.parsers import (
    parse_player_game_log,
    parse_scoreboard_v3,
    parse_team_game_log,
)


def test_parse_scoreboard_v3_maps_home_away_from_game_code() -> None:
    payload = {
        "resultSets": [
            {
                "name": "GameHeader",
                "headers": ["gameId", "gameCode", "gameStatusText", "gameTimeUTC"],
                "rowSet": [
                    [
                        "0022500001",
                        "20251021/NYKBOS",
                        "Final",
                        "2025-10-22T00:30:00Z",
                    ]
                ],
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
                    ["0022500001", 1610612738, "Boston", "Celtics", "BOS"],
                    ["0022500001", 1610612752, "New York", "Knicks", "NYK"],
                ],
            },
        ]
    }

    rows, warnings = parse_scoreboard_v3(
        payload,
        fallback_game_date=date(2025, 10, 21),
    )

    assert warnings == []
    assert len(rows) == 1
    assert rows[0].external_game_id == "0022500001"
    assert rows[0].game_date == date(2025, 10, 22)
    assert rows[0].season == "2025-26"
    assert rows[0].away_external_team_id == "1610612752"
    assert rows[0].home_external_team_id == "1610612738"
    assert rows[0].away_team_abbreviation == "NYK"
    assert rows[0].home_team_abbreviation == "BOS"


def test_parse_scoreboard_v3_warns_when_line_score_is_missing() -> None:
    payload = {
        "resultSets": [
            {
                "name": "GameHeader",
                "headers": ["gameId", "gameCode", "gameStatusText"],
                "rowSet": [["0022500001", "20251021/NYKBOS", "Final"]],
            }
        ]
    }

    rows, warnings = parse_scoreboard_v3(
        payload,
        fallback_game_date=date(2025, 10, 21),
    )

    assert len(rows) == 1
    assert rows[0].home_external_team_id is None
    assert "LineScore result set not found" in warnings
    assert "ScoreboardV3 game 0022500001 missing LineScore teams" in warnings


def test_parse_scoreboard_v3_handles_current_scoreboard_json_shape() -> None:
    payload = {
        "meta": {},
        "scoreboard": {
            "gameDate": "2026-04-15",
            "games": [
                {
                    "gameId": "0052500101",
                    "gameCode": "20260415/ORLPHI",
                    "gameStatusText": "Final",
                    "gameTimeUTC": "2026-04-15T23:30:00Z",
                    "homeTeam": {
                        "teamId": 1610612755,
                        "teamCity": "Philadelphia",
                        "teamName": "76ers",
                        "teamTricode": "PHI",
                    },
                    "awayTeam": {
                        "teamId": 1610612753,
                        "teamCity": "Orlando",
                        "teamName": "Magic",
                        "teamTricode": "ORL",
                    },
                }
            ],
        },
    }

    rows, warnings = parse_scoreboard_v3(
        payload,
        fallback_game_date=date(2026, 4, 15),
    )

    assert warnings == []
    assert len(rows) == 1
    assert rows[0].external_game_id == "0052500101"
    assert rows[0].home_external_team_id == "1610612755"
    assert rows[0].away_external_team_id == "1610612753"
    assert rows[0].home_team_abbreviation == "PHI"
    assert rows[0].away_team_abbreviation == "ORL"
    assert rows[0].home_team_name == "Philadelphia 76ers"
    assert rows[0].away_team_name == "Orlando Magic"


def test_parse_player_game_log_handles_per_player_shape_and_minutes() -> None:
    payload = {
        "resultSets": [
            {
                "name": "PlayerGameLog",
                "headers": [
                    "SEASON_ID",
                    "Player_ID",
                    "Game_ID",
                    "GAME_DATE",
                    "MATCHUP",
                    "MIN",
                    "FGA",
                    "FG_PCT",
                    "FG3_PCT",
                    "FT_PCT",
                    "REB",
                    "AST",
                    "PTS",
                    "PLUS_MINUS",
                ],
                "rowSet": [
                    [
                        "22025",
                        2544,
                        "0022500002",
                        "OCT 22, 2025",
                        "LAL @ GSW",
                        "34:30",
                        17,
                        0.529,
                        0.4,
                        1.0,
                        8,
                        9,
                        27,
                        4,
                    ]
                ],
            }
        ]
    }

    rows, warnings = parse_player_game_log(
        payload,
        season="2025-26",
        fallback_player_id="2544",
    )

    assert any("missing team id" in warning for warning in warnings)
    assert len(rows) == 1
    assert rows[0].external_player_id == "2544"
    assert rows[0].external_team_id is None
    assert rows[0].is_home is False
    assert rows[0].team_abbreviation == "LAL"
    assert rows[0].opponent_team_abbreviation == "GSW"
    assert rows[0].minutes == 34.5
    assert rows[0].pts == 27


def test_parse_team_game_log_handles_team_shape() -> None:
    payload = {
        "resultSets": [
            {
                "name": "TeamGameLog",
                "headers": [
                    "Team_ID",
                    "Game_ID",
                    "GAME_DATE",
                    "MATCHUP",
                    "MIN",
                    "FGA",
                    "FG_PCT",
                    "FG3_PCT",
                    "FT_PCT",
                    "REB",
                    "AST",
                    "PTS",
                ],
                "rowSet": [
                    [
                        1610612738,
                        "0022500001",
                        "2025-10-21",
                        "BOS vs. NYK",
                        240,
                        91,
                        0.47,
                        0.38,
                        0.82,
                        43,
                        28,
                        118,
                    ]
                ],
            }
        ]
    }

    rows, warnings = parse_team_game_log(payload, season="2025-26")

    assert warnings == []
    assert len(rows) == 1
    assert rows[0].external_team_id == "1610612738"
    assert rows[0].is_home is True
    assert rows[0].minutes == 240
    assert rows[0].fga == 91
    assert rows[0].pts == 118
