from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.core.config import get_settings
from app.db import models
from app.db.base import Base
from sqlalchemy import create_engine


def alembic_config() -> Config:
    return Config(str(Path("alembic.ini").resolve()))


def test_alembic_upgrade_head_and_downgrade_base(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "alembic.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()

    config = alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert db_path.exists()
    get_settings.cache_clear()


def test_alembic_schema_has_no_autogenerate_drift(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "drift.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()

    config = alembic_config()
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diffs = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()
        get_settings.cache_clear()

    assert models.Team.__table__.metadata is Base.metadata
    assert diffs == []
