from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.nba import (
    NbaApiPlayerGameLogSource,
    NbaApiScheduleSource,
    NbaGameRow,
    NbaPlayerGameLogRow,
    NbaPlayerGameLogSource,
    NbaScheduleSource,
)
from app.core.clock import Clock
from app.db.models import Player, Team
from app.db.uow import UnitOfWork

from .common import (
    IngestJobResult,
    IngestSourceError,
    UnitOfWorkFactory,
    add_raw_source_snapshot,
    finish_failure,
    resolve_clock,
    resolve_uow_factory,
    source_error_detail,
    source_error_message,
    start_job,
)


async def ingest_schedule(
    game_date: date,
    *,
    source: NbaScheduleSource | None = None,
    uow_factory: UnitOfWorkFactory | None = None,
    clock: Clock | None = None,
) -> IngestJobResult:
    job_name = "ingest.schedule"
    resolved_clock = resolve_clock(clock)
    resolved_uow_factory = resolve_uow_factory(uow_factory)
    detail: dict[str, Any] = {
        "date": game_date.isoformat(),
        "games_fetched": 0,
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
        result = await (source or NbaApiScheduleSource()).games_for_date(game_date)
        detail["warnings"].extend(result.warnings)

        async with resolved_uow_factory() as uow:
            await add_raw_source_snapshot(
                uow,
                result=result,
                endpoint="games_for_date",
                params={"date": game_date.isoformat()},
            )

            if result.status == "error":
                detail["error"] = source_error_detail(result.error)
                await uow.commit()
                error = source_error_message(result.error)
                await finish_failure(
                    resolved_uow_factory,
                    job_run_id,
                    error,
                    detail,
                    resolved_clock,
                )
                raise IngestSourceError(job_name, result.error)

            rows = result.data or []
            detail["games_fetched"] = len(rows)
            for row in rows:
                try:
                    home_team, away_team, team_count = await _upsert_schedule_teams(
                        uow,
                        row,
                    )
                    detail["teams_upserted"] += team_count
                    await uow.games.upsert_by_external_id(
                        row.external_game_id,
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        game_date=row.game_date,
                        start_time=row.start_time,
                        season=row.season,
                        status=row.status,
                    )
                    detail["games_upserted"] += 1
                except ValueError as exc:
                    detail["warnings"].append(
                        f"schedule row {row.external_game_id} skipped: {exc}"
                    )

            await uow.job_runs.finish_success(
                job_run_id,
                detail=detail,
                finished_at=resolved_clock.now(),
            )
            await uow.commit()
    except IngestSourceError:
        raise
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


async def ingest_player_logs(
    season: str,
    *,
    player_external_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    source: NbaPlayerGameLogSource | None = None,
    uow_factory: UnitOfWorkFactory | None = None,
    clock: Clock | None = None,
) -> IngestJobResult:
    job_name = "ingest.player_logs"
    resolved_clock = resolve_clock(clock)
    resolved_uow_factory = resolve_uow_factory(uow_factory)
    detail: dict[str, Any] = {
        "season": season,
        "player_external_id": player_external_id,
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "logs_fetched": 0,
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
        resolved_source = source or NbaApiPlayerGameLogSource()
        if player_external_id is not None:
            endpoint = "get_player_game_logs"
            result = await resolved_source.get_player_game_logs(
                player_id=player_external_id,
                season=season,
                date_from=date_from,
                date_to=date_to,
            )
        else:
            endpoint = "get_league_player_game_logs"
            result = await resolved_source.get_league_player_game_logs(
                season=season,
                date_from=date_from,
                date_to=date_to,
            )
        detail["warnings"].extend(result.warnings)

        async with resolved_uow_factory() as uow:
            await add_raw_source_snapshot(
                uow,
                result=result,
                endpoint=endpoint,
                params={
                    "season": season,
                    "player_external_id": player_external_id,
                    "date_from": date_from.isoformat() if date_from else None,
                    "date_to": date_to.isoformat() if date_to else None,
                },
            )

            if result.status == "error":
                detail["error"] = source_error_detail(result.error)
                await uow.commit()
                error = source_error_message(result.error)
                await finish_failure(
                    resolved_uow_factory,
                    job_run_id,
                    error,
                    detail,
                    resolved_clock,
                )
                raise IngestSourceError(job_name, result.error)

            rows = result.data or []
            detail["logs_fetched"] = len(rows)
            for row in rows:
                try:
                    row_counts = await _upsert_player_log_row(uow, row)
                    detail["teams_upserted"] += row_counts["teams_upserted"]
                    detail["players_upserted"] += row_counts["players_upserted"]
                    detail["games_upserted"] += row_counts["games_upserted"]
                    detail["logs_upserted"] += 1
                except ValueError as exc:
                    label = row.external_game_id or "unknown-game"
                    detail["warnings"].append(f"player log row {label} skipped: {exc}")

            await uow.job_runs.finish_success(
                job_run_id,
                detail=detail,
                finished_at=resolved_clock.now(),
            )
            await uow.commit()
    except IngestSourceError:
        raise
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


async def _upsert_schedule_teams(
    uow: UnitOfWork,
    row: NbaGameRow,
) -> tuple[Team, Team, int]:
    home_team = await _upsert_team(
        uow,
        abbreviation=row.home_team_abbreviation,
        external_team_id=row.home_external_team_id,
        name=row.home_team_name,
    )
    away_team = await _upsert_team(
        uow,
        abbreviation=row.away_team_abbreviation,
        external_team_id=row.away_external_team_id,
        name=row.away_team_name,
    )
    return home_team, away_team, 2


async def _upsert_player_log_row(
    uow: UnitOfWork,
    row: NbaPlayerGameLogRow,
) -> dict[str, int]:
    team = await _upsert_team(
        uow,
        abbreviation=row.team_abbreviation,
        external_team_id=row.external_team_id,
        name=row.team_abbreviation,
    )
    opponent = await _upsert_team(
        uow,
        abbreviation=row.opponent_team_abbreviation,
        external_team_id=None,
        name=row.opponent_team_abbreviation,
    )
    player = await _upsert_player(uow, row, team.id)

    home_team_id = team.id if row.is_home else opponent.id
    away_team_id = opponent.id if row.is_home else team.id
    game = await uow.games.upsert_by_external_id(
        row.external_game_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        game_date=row.game_date,
        start_time=None,
        season=row.season,
        status="final",
    )
    await uow.player_game_logs.bulk_upsert(
        [
            {
                "player_id": player.id,
                "team_id": team.id,
                "game_id": game.id,
                "matchup": row.matchup,
                "is_home": row.is_home,
                "pts": row.pts,
                "minutes": row.minutes,
                "fga": row.fga,
                "fg_pct": row.fg_pct,
                "reb": row.reb,
                "ast": row.ast,
                "fg3_pct": row.fg3_pct,
                "ft_pct": row.ft_pct,
                "plus_minus": row.plus_minus,
            }
        ]
    )
    return {"teams_upserted": 2, "players_upserted": 1, "games_upserted": 1}


async def _upsert_team(
    uow: UnitOfWork,
    *,
    abbreviation: str | None,
    external_team_id: str | None,
    name: str | None,
) -> Team:
    clean_abbreviation = _clean_text(abbreviation)
    if clean_abbreviation is None:
        msg = "missing team abbreviation"
        raise ValueError(msg)

    clean_external_team_id = _clean_text(external_team_id)
    clean_name = _clean_text(name) or clean_abbreviation
    if clean_external_team_id is not None:
        return await uow.teams.upsert_by_external_id(
            clean_external_team_id,
            abbreviation=clean_abbreviation,
            name=clean_name,
            city=None,
            conference=None,
            division=None,
        )

    team = await uow.teams.get_by_abbreviation(clean_abbreviation)
    if team is None:
        if uow.session is None:
            msg = "UnitOfWork has not been entered"
            raise RuntimeError(msg)
        team = Team(
            external_team_id=None,
            abbreviation=clean_abbreviation,
            name=clean_name,
            city=None,
            conference=None,
            division=None,
        )
        uow.session.add(team)
    else:
        team.name = clean_name
    if uow.session is None:
        msg = "UnitOfWork has not been entered"
        raise RuntimeError(msg)
    await uow.session.flush()
    return team


async def _upsert_player(
    uow: UnitOfWork,
    row: NbaPlayerGameLogRow,
    team_id: int,
) -> Player:
    full_name = _clean_text(row.player_name)
    external_player_id = _clean_text(row.external_player_id)
    if full_name is None and external_player_id is None:
        msg = "missing player name and external player id"
        raise ValueError(msg)

    first_name, last_name = _split_name(full_name)
    if external_player_id is not None:
        return await uow.players.upsert_by_external_id(
            external_player_id,
            team_id=team_id,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name or external_player_id,
            position=None,
            active=True,
        )

    player = await uow.players.get_by_full_name(full_name or "")
    if player is None:
        if uow.session is None:
            msg = "UnitOfWork has not been entered"
            raise RuntimeError(msg)
        player = Player(
            external_player_id=None,
            team_id=team_id,
            first_name=first_name,
            last_name=last_name,
            full_name=full_name or "",
            position=None,
            active=True,
        )
        uow.session.add(player)
    else:
        player.team_id = team_id
    if uow.session is None:
        msg = "UnitOfWork has not been entered"
        raise RuntimeError(msg)
    await uow.session.flush()
    return player


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if full_name is None:
        return None, None
    parts = full_name.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]
