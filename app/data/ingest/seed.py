from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.clock import Clock

from .common import (
    IngestJobResult,
    UnitOfWorkFactory,
    finish_failure,
    resolve_clock,
    resolve_uow_factory,
    start_job,
)
from .jobs import _upsert_player, _upsert_team


async def import_seed_csv(
    csv_path: str | Path,
    *,
    uow_factory: UnitOfWorkFactory | None = None,
    clock: Clock | None = None,
) -> IngestJobResult:
    job_name = "seed.csv"
    resolved_clock = resolve_clock(clock)
    resolved_uow_factory = resolve_uow_factory(uow_factory)
    path = Path(csv_path)
    detail: dict[str, Any] = {
        "csv_path": str(path),
        "rows_read": 0,
        "logs_upserted": 0,
        "players_upserted": 0,
        "games_upserted": 0,
        "teams_upserted": 0,
        "warnings": [],
    }
    job_run_id = await start_job(
        resolved_uow_factory,
        job_name,
        detail,
        resolved_clock,
    )

    try:
        frame = pd.read_csv(path)
        detail["rows_read"] = len(frame)
        async with resolved_uow_factory() as uow:
            for index, raw_row in frame.iterrows():
                row = raw_row.to_dict()
                try:
                    mapped = _map_seed_row(row)
                    team = await _upsert_team(
                        uow,
                        abbreviation=mapped["team_abbreviation"],
                        external_team_id=None,
                        name=mapped["team_abbreviation"],
                    )
                    opponent = await _upsert_team(
                        uow,
                        abbreviation=mapped["opponent_abbreviation"],
                        external_team_id=None,
                        name=mapped["opponent_abbreviation"],
                    )
                    player = await _upsert_seed_player(
                        uow,
                        full_name=mapped["player_name"],
                        external_player_id=mapped["external_player_id"],
                        team_id=team.id,
                    )
                    home_team_id = team.id if mapped["is_home"] else opponent.id
                    away_team_id = opponent.id if mapped["is_home"] else team.id
                    game = await uow.games.upsert_by_external_id(
                        mapped["external_game_id"],
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        game_date=mapped["game_date"],
                        start_time=None,
                        season=_season_for_date(mapped["game_date"]),
                        status="final",
                    )
                    await uow.player_game_logs.bulk_upsert(
                        [
                            {
                                "player_id": player.id,
                                "team_id": team.id,
                                "game_id": game.id,
                                "matchup": mapped["matchup"],
                                "is_home": mapped["is_home"],
                                "pts": mapped["pts"],
                                "minutes": mapped["minutes"],
                                "fga": mapped["fga"],
                                "fg_pct": mapped["fg_pct"],
                                "reb": mapped["reb"],
                                "ast": mapped["ast"],
                                "fg3_pct": mapped["fg3_pct"],
                                "ft_pct": mapped["ft_pct"],
                                "plus_minus": mapped["plus_minus"],
                            }
                        ]
                    )
                    detail["teams_upserted"] += 2
                    detail["players_upserted"] += 1
                    detail["games_upserted"] += 1
                    detail["logs_upserted"] += 1
                except ValueError as exc:
                    detail["warnings"].append(f"seed row {index} skipped: {exc}")

            await uow.job_runs.finish_success(
                job_run_id,
                detail=detail,
                finished_at=resolved_clock.now(),
            )
            await uow.commit()
    except Exception as exc:
        detail["error"] = {"type": type(exc).__name__, "message": str(exc)}
        await finish_failure(
            resolved_uow_factory,
            job_run_id,
            str(exc),
            detail,
            resolved_clock,
        )
        raise

    return IngestJobResult(
        job_run_id=job_run_id,
        job_name=job_name,
        status="success",
        detail=detail,
    )


async def _upsert_seed_player(
    uow: Any,
    *,
    full_name: str,
    external_player_id: str | None,
    team_id: int,
) -> Any:
    from app.adapters.nba.types import NbaPlayerGameLogRow

    return await _upsert_player(
        uow,
        NbaPlayerGameLogRow(
            external_player_id=external_player_id,
            player_name=full_name,
            external_team_id=None,
            external_game_id="seed-player-placeholder",
            game_date=date.min,
            season="seed",
            is_home=False,
        ),
        team_id,
    )


def _map_seed_row(row: dict[str, Any]) -> dict[str, Any]:
    game_date = _parse_seed_date(_first_present(row, "game_date_parsed", "GAME_DATE"))
    matchup = _required_text(_first_present(row, "MATCHUP"), "MATCHUP")
    team_abbreviation, opponent_from_matchup, is_home = _parse_matchup(
        matchup,
        _optional_bool(_first_present(row, "home_away_flag")),
    )
    opponent = _clean_text(_first_present(row, "opponent")) or opponent_from_matchup
    if opponent is None:
        msg = "missing opponent abbreviation"
        raise ValueError(msg)

    player_name = _required_text(
        _first_present(row, "player_name", "PLAYER_NAME", "Player"),
        "player_name",
    )
    external_player_id = _clean_text(
        _first_present(row, "player_id", "PLAYER_ID", "external_player_id")
    )
    return {
        "external_game_id": _external_game_id(
            row,
            game_date,
            team_abbreviation,
            opponent,
        ),
        "game_date": game_date,
        "matchup": matchup,
        "team_abbreviation": team_abbreviation,
        "opponent_abbreviation": opponent,
        "is_home": is_home,
        "player_name": player_name,
        "external_player_id": external_player_id,
        "pts": _float_or_none(_first_present(row, "PTS", "pts")),
        "minutes": _float_or_none(_first_present(row, "MIN", "minutes")),
        "fga": _float_or_none(_first_present(row, "FGA", "fga")),
        "fg_pct": _float_or_none(_first_present(row, "FG_PCT", "fg_pct")),
        "reb": _float_or_none(_first_present(row, "REB", "reb")),
        "ast": _float_or_none(_first_present(row, "AST", "ast")),
        "fg3_pct": _float_or_none(_first_present(row, "FG3_PCT", "fg3_pct")),
        "ft_pct": _float_or_none(_first_present(row, "FT_PCT", "ft_pct")),
        "plus_minus": _float_or_none(
            _first_present(row, "PLUS_MINUS", "plus_minus")
        ),
    }


def _external_game_id(
    row: dict[str, Any],
    game_date: date,
    team_abbreviation: str,
    opponent_abbreviation: str,
) -> str:
    raw_game_id = _clean_text(_first_present(row, "Game_ID", "GAME_ID", "game_id"))
    if raw_game_id is not None:
        digits = raw_game_id.removesuffix(".0")
        if digits.isdigit() and len(digits) == 8:
            return f"00{digits}"
        return raw_game_id
    return f"seed:{game_date.isoformat()}:{team_abbreviation}:{opponent_abbreviation}"


def _parse_matchup(
    matchup: str,
    home_away_flag: bool | None,
) -> tuple[str, str | None, bool]:
    if " vs. " in matchup:
        team, opponent = matchup.split(" vs. ", 1)
        return team.strip(), opponent.strip(), True
    if " @ " in matchup:
        team, opponent = matchup.split(" @ ", 1)
        return team.strip(), opponent.strip(), False
    parts = matchup.split()
    if not parts:
        msg = "missing team abbreviation in matchup"
        raise ValueError(msg)
    return parts[0].strip(), None, bool(home_away_flag)


def _parse_seed_date(value: Any) -> date:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        msg = "missing or invalid game date"
        raise ValueError(msg)
    return parsed.date()


def _season_for_date(game_date: date) -> str:
    start_year = game_date.year if game_date.month >= 9 else game_date.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if not _is_missing(value):
            return value
    return None


def _required_text(value: Any, field: str) -> str:
    text = _clean_text(value)
    if text is None:
        msg = f"missing {field}"
        raise ValueError(msg)
    return text


def _clean_text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return None


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False
