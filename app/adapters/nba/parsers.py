from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Any

from app.adapters.nba.types import (
    NbaGameRow,
    NbaPlayerGameLogRow,
    NbaTeamGameLogRow,
)


def parse_scoreboard_v3(
    payload: object,
    *,
    fallback_game_date: date,
) -> tuple[list[NbaGameRow], list[str]]:
    raw = _as_dict(payload)
    scoreboard = raw.get("scoreboard")
    if isinstance(scoreboard, dict) and isinstance(scoreboard.get("games"), list):
        return _parse_scoreboard_games(
            scoreboard.get("games", []),
            fallback_game_date=fallback_game_date,
            source_label="ScoreboardV3",
        )

    warnings: list[str] = []
    headers = _rows_by_name(raw, "GameHeader", warnings)
    line_scores = _rows_by_name(raw, "LineScore", warnings)
    lines_by_game: dict[str, list[dict[str, Any]]] = {}
    for row in line_scores:
        game_id = _to_str(row.get("gameId"))
        if game_id:
            lines_by_game.setdefault(game_id, []).append(row)

    games: list[NbaGameRow] = []
    for header in headers:
        game_id = _to_str(header.get("gameId"))
        if not game_id:
            warnings.append("ScoreboardV3 GameHeader row missing gameId; row skipped")
            continue

        game_date = (
            _parse_date(header.get("gameTimeUTC"), warnings) or fallback_game_date
        )
        game_code = _to_str(header.get("gameCode"))
        away_tri, home_tri = _team_order_from_game_code(game_code)
        lines = lines_by_game.get(game_id, [])
        home = _line_for_tricode(lines, home_tri)
        away = _line_for_tricode(lines, away_tri)

        if (home is None or away is None) and len(lines) >= 2:
            warnings.append(
                f"ScoreboardV3 game {game_id} could not map home/away from gameCode"
            )
            away = away or lines[0]
            home = home or lines[1]
        if home is None or away is None:
            warnings.append(f"ScoreboardV3 game {game_id} missing LineScore teams")

        games.append(
            NbaGameRow(
                external_game_id=game_id,
                game_date=game_date,
                season=_season_for_date(game_date),
                status=_status_text(header),
                start_time=_parse_datetime(header.get("gameTimeUTC"), warnings),
                home_external_team_id=_team_id(home),
                away_external_team_id=_team_id(away),
                home_team_abbreviation=_team_tricode(home),
                away_team_abbreviation=_team_tricode(away),
                home_team_name=_team_name(home),
                away_team_name=_team_name(away),
            )
        )

    return games, warnings


def parse_live_scoreboard(
    payload: object,
    *,
    fallback_game_date: date,
) -> tuple[list[NbaGameRow], list[str]]:
    raw = _as_dict(payload)
    games = raw.get("scoreboard", {}).get("games", raw.get("games", []))
    return _parse_scoreboard_games(
        games,
        fallback_game_date=fallback_game_date,
        source_label="live scoreboard",
    )


def _parse_scoreboard_games(
    games_payload: object,
    *,
    fallback_game_date: date,
    source_label: str,
) -> tuple[list[NbaGameRow], list[str]]:
    warnings: list[str] = []
    games: list[NbaGameRow] = []
    for game in _as_list(games_payload):
        if not isinstance(game, dict):
            warnings.append(f"{source_label} game entry was not an object; skipped")
            continue
        game_id = _to_str(game.get("gameId"))
        if not game_id:
            warnings.append(f"{source_label} game missing gameId; skipped")
            continue
        game_date = _parse_date(game.get("gameTimeUTC"), warnings) or fallback_game_date
        home = _as_dict(game.get("homeTeam", {}))
        away = _as_dict(game.get("awayTeam", {}))
        games.append(
            NbaGameRow(
                external_game_id=game_id,
                game_date=game_date,
                season=_season_for_date(game_date),
                status=_to_str(game.get("gameStatusText")) or "unknown",
                start_time=_parse_datetime(game.get("gameTimeUTC"), warnings),
                home_external_team_id=_to_str(home.get("teamId")),
                away_external_team_id=_to_str(away.get("teamId")),
                home_team_abbreviation=_to_str(home.get("teamTricode")),
                away_team_abbreviation=_to_str(away.get("teamTricode")),
                home_team_name=_team_name(home),
                away_team_name=_team_name(away),
            )
        )
    return games, warnings


def parse_player_game_log(
    payload: object,
    *,
    season: str,
    fallback_player_id: str | None = None,
) -> tuple[list[NbaPlayerGameLogRow], list[str]]:
    rows, warnings = _single_result_rows(payload, "PlayerGameLog", "LeagueGameLog")
    parsed: list[NbaPlayerGameLogRow] = []
    for row in rows:
        game_id = _to_str(row.get("Game_ID") or row.get("GAME_ID"))
        if not game_id:
            warnings.append("player game log row missing Game_ID; row skipped")
            continue
        game_date = _parse_required_game_date(row.get("GAME_DATE"), warnings, game_id)
        matchup = _to_str(row.get("MATCHUP"))
        team_abbr, opponent_abbr, is_home = _parse_matchup(matchup, warnings, game_id)
        external_player_id = _to_str(
            row.get("Player_ID") or row.get("PLAYER_ID") or row.get("PERSON_ID")
        )
        if external_player_id is None:
            external_player_id = fallback_player_id
            warnings.append(f"player game log {game_id} missing player id")
        external_team_id = _to_str(row.get("TEAM_ID") or row.get("Team_ID"))
        if external_team_id is None:
            warnings.append(f"player game log {game_id} missing team id")

        parsed.append(
            NbaPlayerGameLogRow(
                external_player_id=external_player_id,
                player_name=_to_str(row.get("PLAYER_NAME") or row.get("Player")),
                external_team_id=external_team_id,
                external_game_id=game_id,
                game_date=game_date,
                season=_season_from_row(row, season),
                matchup=matchup,
                is_home=is_home,
                pts=_float(row.get("PTS")),
                minutes=_minutes(row.get("MIN"), warnings, game_id),
                fga=_float(row.get("FGA")),
                fg_pct=_float(row.get("FG_PCT")),
                reb=_float(row.get("REB")),
                ast=_float(row.get("AST")),
                fg3_pct=_float(row.get("FG3_PCT")),
                ft_pct=_float(row.get("FT_PCT")),
                plus_minus=_float(row.get("PLUS_MINUS")),
                team_abbreviation=team_abbr or _to_str(row.get("TEAM_ABBREVIATION")),
                opponent_team_abbreviation=opponent_abbr,
            )
        )
    return parsed, warnings


def parse_team_game_log(
    payload: object,
    *,
    season: str,
    fallback_team_id: str | None = None,
) -> tuple[list[NbaTeamGameLogRow], list[str]]:
    rows, warnings = _single_result_rows(payload, "TeamGameLog", "LeagueGameLog")
    parsed: list[NbaTeamGameLogRow] = []
    for row in rows:
        game_id = _to_str(row.get("Game_ID") or row.get("GAME_ID"))
        if not game_id:
            warnings.append("team game log row missing Game_ID; row skipped")
            continue
        game_date = _parse_required_game_date(row.get("GAME_DATE"), warnings, game_id)
        matchup = _to_str(row.get("MATCHUP"))
        team_abbr, opponent_abbr, is_home = _parse_matchup(matchup, warnings, game_id)
        external_team_id = _to_str(row.get("TEAM_ID") or row.get("Team_ID"))
        if external_team_id is None:
            external_team_id = fallback_team_id
            warnings.append(f"team game log {game_id} missing team id")

        parsed.append(
            NbaTeamGameLogRow(
                external_team_id=external_team_id,
                team_name=_to_str(row.get("TEAM_NAME")),
                external_game_id=game_id,
                game_date=game_date,
                season=_season_from_row(row, season),
                matchup=matchup,
                is_home=is_home,
                pts=_float(row.get("PTS")),
                minutes=_minutes(row.get("MIN"), warnings, game_id),
                fga=_float(row.get("FGA")),
                fg_pct=_float(row.get("FG_PCT")),
                reb=_float(row.get("REB")),
                ast=_float(row.get("AST")),
                fg3_pct=_float(row.get("FG3_PCT")),
                ft_pct=_float(row.get("FT_PCT")),
                plus_minus=_float(row.get("PLUS_MINUS")),
                team_abbreviation=team_abbr or _to_str(row.get("TEAM_ABBREVIATION")),
                opponent_team_abbreviation=opponent_abbr,
            )
        )
    return parsed, warnings


def _single_result_rows(
    payload: object,
    preferred_name: str,
    fallback_name: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows = _rows_by_name(_as_dict(payload), preferred_name, warnings)
    if not rows:
        rows = _rows_by_name(_as_dict(payload), fallback_name, warnings)
    return rows, warnings


def _rows_by_name(
    payload: dict[str, Any],
    name: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    for result_set in _result_sets(payload):
        if str(result_set.get("name", "")).lower() != name.lower():
            continue
        headers = result_set.get("headers")
        row_set = result_set.get("rowSet")
        if not isinstance(headers, list) or not isinstance(row_set, list):
            warnings.append(f"{name} result set missing headers or rowSet")
            return []
        return [
            dict(zip([str(header) for header in headers], row, strict=False))
            for row in row_set
            if isinstance(row, list)
        ]
    warnings.append(f"{name} result set not found")
    return []


def _result_sets(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    result_sets = payload.get("resultSets", [])
    if isinstance(result_sets, list):
        yield from (item for item in result_sets if isinstance(item, dict))
    result_set = payload.get("resultSet")
    if isinstance(result_set, dict):
        yield result_set


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _to_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _minutes(value: object, warnings: list[str], game_id: str) -> float | None:
    if value in (None, ""):
        warnings.append(f"game log {game_id} missing minutes")
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    if ":" in text:
        minutes, seconds = text.split(":", 1)
        try:
            return float(minutes) + (float(seconds) / 60)
        except ValueError:
            warnings.append(f"game log {game_id} has unparsable minutes: {text}")
            return None
    try:
        return float(text)
    except ValueError:
        warnings.append(f"game log {game_id} has unparsable minutes: {text}")
        return None


def _parse_matchup(
    matchup: str | None,
    warnings: list[str],
    game_id: str,
) -> tuple[str | None, str | None, bool]:
    if matchup is None:
        warnings.append(f"game log {game_id} missing matchup")
        return None, None, False
    if " vs. " in matchup:
        team, opponent = matchup.split(" vs. ", 1)
        return team.strip(), opponent.strip(), True
    if " @ " in matchup:
        team, opponent = matchup.split(" @ ", 1)
        return team.strip(), opponent.strip(), False
    warnings.append(f"game log {game_id} has unrecognized matchup: {matchup}")
    return None, None, False


def _parse_required_game_date(
    value: object,
    warnings: list[str],
    game_id: str,
) -> date:
    parsed = _parse_date(value, warnings)
    if parsed is None:
        warnings.append(f"game log {game_id} missing or invalid GAME_DATE")
        return date.min
    return parsed


def _parse_date(value: object, warnings: list[str]) -> date | None:
    dt = _parse_datetime(value, warnings)
    if dt is not None:
        return dt.date()
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.title(), fmt).date()
        except ValueError:
            continue
    warnings.append(f"unparsable date: {text}")
    return None


def _parse_datetime(value: object, warnings: list[str]) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def _season_for_date(game_date: date) -> str:
    start_year = game_date.year if game_date.month >= 9 else game_date.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _season_from_row(row: dict[str, Any], fallback: str) -> str:
    season_id = _to_str(row.get("SEASON_ID"))
    if season_id and len(season_id) >= 4:
        try:
            start_year = int(season_id[-4:])
        except ValueError:
            return fallback
        else:
            return f"{start_year}-{(start_year + 1) % 100:02d}"
    return fallback


def _team_order_from_game_code(game_code: str | None) -> tuple[str | None, str | None]:
    if not game_code or len(game_code) < 6:
        return None, None
    suffix = game_code[-6:]
    return suffix[:3], suffix[3:]


def _line_for_tricode(
    lines: list[dict[str, Any]],
    tricode: str | None,
) -> dict[str, Any] | None:
    if tricode is None:
        return None
    return next(
        (
            line
            for line in lines
            if str(line.get("teamTricode", "")).upper() == tricode.upper()
        ),
        None,
    )


def _team_id(line: dict[str, Any] | None) -> str | None:
    return _to_str(line.get("teamId")) if line else None


def _team_tricode(line: dict[str, Any] | None) -> str | None:
    return _to_str(line.get("teamTricode")) if line else None


def _team_name(line: dict[str, Any] | None) -> str | None:
    if not line:
        return None
    city = _to_str(line.get("teamCity"))
    name = _to_str(line.get("teamName"))
    if city and name:
        return f"{city} {name}"
    return name or city


def _status_text(header: dict[str, Any]) -> str:
    return (
        _to_str(header.get("gameStatusText"))
        or _to_str(header.get("gameStatus"))
        or "unknown"
    )
