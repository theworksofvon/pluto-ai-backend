import pytest
from app.core.config import Settings
from app.db.session import dispose_engines, get_sessionmaker
from sqlalchemy import text


@pytest.fixture(autouse=True)
async def _dispose_engines() -> None:
    yield
    await dispose_engines()


async def test_session_factory_connects_to_tmp_sqlite(tmp_path) -> None:
    db_path = tmp_path / "session.db"
    settings = Settings(DATABASE_URL=f"sqlite+aiosqlite:///{db_path}")
    sessionmaker = get_sessionmaker(settings)

    async with sessionmaker() as session:
        result = await session.execute(text("select 1"))

    assert result.scalar_one() == 1
    assert db_path.exists()
