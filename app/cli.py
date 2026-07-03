from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Annotated, Awaitable, TypeVar

import typer
from alembic import command
from alembic.config import Config

from app.data.ingest import IngestSourceError, import_seed_csv, ingest_player_logs
from app.data.ingest import ingest_schedule as run_ingest_schedule
from app.db.session import dispose_engines
from app.db.uow import UnitOfWork

VERSION = "0.1.0"
T = TypeVar("T")

app = typer.Typer()
ingest_app = typer.Typer()
db_app = typer.Typer()
jobs_app = typer.Typer()

app.add_typer(ingest_app, name="ingest")
app.add_typer(db_app, name="db")
app.add_typer(jobs_app, name="jobs")


@app.callback()
def _main() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(VERSION)


@ingest_app.command("schedule")
def ingest_schedule(
    date_text: Annotated[str, typer.Option("--date", help="Game date YYYY-MM-DD")],
) -> None:
    game_date = _parse_date(date_text)
    try:
        result = _run(run_ingest_schedule(game_date))
    except IngestSourceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(_json(result.detail))


@ingest_app.command("player-logs")
def ingest_player_logs_command(
    season: Annotated[str, typer.Option("--season", help="NBA season, e.g. 2025-26")],
    player_external_id: Annotated[
        str | None,
        typer.Option("--player-external-id", help="Optional NBA player id"),
    ] = None,
    date_from: Annotated[
        str | None,
        typer.Option("--date-from", help="Optional start date YYYY-MM-DD"),
    ] = None,
    date_to: Annotated[
        str | None,
        typer.Option("--date-to", help="Optional end date YYYY-MM-DD"),
    ] = None,
) -> None:
    try:
        result = _run(
            ingest_player_logs(
                season,
                player_external_id=player_external_id,
                date_from=_parse_optional_date(date_from),
                date_to=_parse_optional_date(date_to),
            )
        )
    except IngestSourceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(_json(result.detail))


@app.command("seed")
def seed(
    csv_path: Annotated[
        Path,
        typer.Option("--csv", help="Historical player-game seed CSV"),
    ] = Path("shared/data/pluto_training_dataset_v1.csv"),
) -> None:
    result = _run(import_seed_csv(csv_path))
    typer.echo(_json(result.detail))


@db_app.command("upgrade")
def db_upgrade() -> None:
    command.upgrade(Config(str(Path("alembic.ini").resolve())), "head")
    typer.echo("database upgraded")


@jobs_app.command("recent")
def jobs_recent(
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 20,
    job_name: Annotated[str | None, typer.Option("--job-name")] = None,
) -> None:
    _run(_print_recent_jobs(limit=limit, job_name=job_name))


def main() -> None:
    app()


def _run(awaitable: Awaitable[T]) -> T:
    return asyncio.run(_run_with_cleanup(awaitable))


async def _run_with_cleanup(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    finally:
        await dispose_engines()


async def _print_recent_jobs(limit: int, job_name: str | None) -> None:
    async with UnitOfWork() as uow:
        runs = await uow.job_runs.list_recent(job_name=job_name, limit=limit)
    for run in runs:
        detail = _json(run.detail or {})
        if len(detail) > 180:
            detail = f"{detail[:177]}..."
        typer.echo(
            "\t".join(
                [
                    str(run.id),
                    run.job_name,
                    run.status,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else "",
                    run.error or "",
                    detail,
                ]
            )
        )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("expected YYYY-MM-DD") from exc


def _parse_optional_date(value: str | None) -> date | None:
    if value is None:
        return None
    return _parse_date(value)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


if __name__ == "__main__":
    main()
