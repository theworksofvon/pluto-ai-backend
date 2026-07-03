from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )


class Team(CreatedAtMixin, Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_team_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    abbreviation: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(120))
    conference: Mapped[str | None] = mapped_column(String(32))
    division: Mapped[str | None] = mapped_column(String(64))


class Player(CreatedAtMixin, Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_player_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    position: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
    )


class Game(CreatedAtMixin, Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_game_id: Mapped[str] = mapped_column(String(64), unique=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    season: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)

    __table_args__ = (
        Index("ix_games_home_team_id_game_date", "home_team_id", "game_date"),
        Index("ix_games_away_team_id_game_date", "away_team_id", "game_date"),
    )


class PlayerGameLog(CreatedAtMixin, Base):
    __tablename__ = "player_game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    matchup: Mapped[str | None] = mapped_column(String(32))
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pts: Mapped[float | None] = mapped_column(Float)
    minutes: Mapped[float | None] = mapped_column(Float)
    fga: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    reb: Mapped[float | None] = mapped_column(Float)
    ast: Mapped[float | None] = mapped_column(Float)
    fg3_pct: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    plus_minus: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint(
            "player_id", "game_id", name="uq_player_game_logs_player_game"
        ),
        Index("ix_player_game_logs_player_id_game_id", "player_id", "game_id"),
    )


class TeamGameLog(CreatedAtMixin, Base):
    __tablename__ = "team_game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    matchup: Mapped[str | None] = mapped_column(String(32))
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pts: Mapped[float | None] = mapped_column(Float)
    minutes: Mapped[float | None] = mapped_column(Float)
    fga: Mapped[float | None] = mapped_column(Float)
    fg_pct: Mapped[float | None] = mapped_column(Float)
    reb: Mapped[float | None] = mapped_column(Float)
    ast: Mapped[float | None] = mapped_column(Float)
    fg3_pct: Mapped[float | None] = mapped_column(Float)
    ft_pct: Mapped[float | None] = mapped_column(Float)
    plus_minus: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("team_id", "game_id", name="uq_team_game_logs_team_game"),
        Index("ix_team_game_logs_team_id_game_id", "team_id", "game_id"),
    )


class PropLine(CreatedAtMixin, Base):
    __tablename__ = "prop_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), index=True)
    stat_type: Mapped[str] = mapped_column(String(32))
    line_value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_prop_lines_player_id_stat_type_fetched_at",
            "player_id",
            "stat_type",
            "fetched_at",
        ),
    )


class RawSourceSnapshot(CreatedAtMixin, Base):
    __tablename__ = "raw_source_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    endpoint: Mapped[str] = mapped_column(String(255), index=True)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    raw_json: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON)
    raw_hash: Mapped[str] = mapped_column(String(128), index=True)


class InjuryReport(CreatedAtMixin, Base):
    __tablename__ = "injury_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class FeatureSnapshot(CreatedAtMixin, Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    stat_type: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    feature_version: Mapped[str] = mapped_column(String(64), index=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "game_id",
            "stat_type",
            "as_of",
            "feature_version",
            name="uq_feature_snapshots_player_game_stat_as_of_version",
        ),
        Index("ix_feature_snapshots_player_id_game_id", "player_id", "game_id"),
    )


class ModelVersion(CreatedAtMixin, Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(512))
    feature_version: Mapped[str] = mapped_column(String(64), index=True)
    training_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
    )


class PromptVersion(CreatedAtMixin, Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(64))
    template: Mapped[str] = mapped_column(Text)
    schema: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_versions_name_version"),
    )


class PredictionRun(CreatedAtMixin, Base):
    __tablename__ = "prediction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("model_versions.id"), index=True
    )
    prompt_version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id"), index=True
    )
    feature_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("feature_snapshots.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    llm_model: Mapped[str] = mapped_column(String(120))
    context_hash: Mapped[str] = mapped_column(String(128), index=True)
    data_quality: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlayerPrediction(CreatedAtMixin, Base):
    __tablename__ = "player_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(
        ForeignKey("prediction_runs.id"), index=True
    )
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    stat_type: Mapped[str] = mapped_column(String(32))
    line: Mapped[float] = mapped_column(Float)
    base_prediction: Mapped[float | None] = mapped_column(Float)
    final_prediction: Mapped[float] = mapped_column(Float)
    predicted_range_low: Mapped[float | None] = mapped_column(Float)
    predicted_range_high: Mapped[float | None] = mapped_column(Float)
    over_under_recommendation: Mapped[str | None] = mapped_column(String(16))
    confidence: Mapped[float | None] = mapped_column(Float)
    raw_llm_output: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_player_predictions_player_id_game_id_stat_type",
            "player_id",
            "game_id",
            "stat_type",
        ),
    )


class PredictionEvaluation(CreatedAtMixin, Base):
    __tablename__ = "prediction_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_prediction_id: Mapped[int] = mapped_column(
        ForeignKey("player_predictions.id"),
        unique=True,
        index=True,
    )
    actual_value: Mapped[float] = mapped_column(Float)
    error: Mapped[float | None] = mapped_column(Float)
    line_hit: Mapped[bool | None] = mapped_column(Boolean)
    over_under_correct: Mapped[bool | None] = mapped_column(Boolean)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class JobRun(CreatedAtMixin, Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)


class LlmCallLog(CreatedAtMixin, Base):
    __tablename__ = "llm_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    prompt_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id"), index=True
    )
    request_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    validation_ok: Mapped[bool | None] = mapped_column(Boolean)


class SourceHealthCheck(CreatedAtMixin, Base):
    __tablename__ = "source_health_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(64), index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    sample_entity: Mapped[str | None] = mapped_column(String(120))
    response_shape_hash: Mapped[str | None] = mapped_column(String(128), index=True)
