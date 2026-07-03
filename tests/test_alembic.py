from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import get_settings


def test_alembic_upgrade_head_and_downgrade_base(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "alembic.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()

    config = Config(str(Path("alembic.ini").resolve()))
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    assert db_path.exists()
    get_settings.cache_clear()
